"""Opt-in website transport using an explicitly supplied, encrypted session export.

No default-profile inspection, undocumented service API, guest fallback or resend.
Only browser UI replies are returned. Website token counts and prices are unknown.
"""
import asyncio
import base64
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import threading
import time
from urllib.parse import urlparse
import uuid

from flux.local_agents.gemini_api import protect

SITES = {
    'gemini-web': {'url': 'https://gemini.google.com/app', 'host': 'gemini.google.com',
                   'domains': {'google.com', 'gemini.google.com', 'accounts.google.com'}},
    'deepseek-web': {'url': 'https://chat.deepseek.com/', 'host': 'chat.deepseek.com',
                     'domains': {'deepseek.com', 'chat.deepseek.com'}},
}
LIMIT = 1_000_000
STORE_LOCK = threading.RLock()


class SessionError(RuntimeError):
    pass


def site_for(provider):
    if provider not in SITES:
        raise ValueError('Unsupported website provider.')
    return SITES[provider]


def state_path(provider):
    site_for(provider)
    directory = Path(os.environ.get('FLUX_WEB_SESSION_DIR', str(Path.home()/'.flux/web-sessions')))
    return directory/(provider+'.json')


def normalize_state(provider, raw):
    """Keep only the chosen site's cookies/localStorage; never infer auth tokens."""
    site = site_for(provider)
    rows = raw if isinstance(raw, list) else raw.get('cookies', []) if isinstance(raw, dict) else None
    if not isinstance(rows, list) or len(rows) > 1000:
        raise ValueError('فایل باید فهرست کوکی یا خروجی storage_state باشد.')
    cookies = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('ساختار کوکی معتبر نیست.')
        domain = row.get('domain', '')
        if not isinstance(domain, str) or domain.lstrip('.').lower() not in site['domains']:
            continue
        name, value = row.get('name'), row.get('value')
        if not isinstance(name, str) or not name or not isinstance(value, str) or len(name)>256 or len(value)>64000:
            raise ValueError('نام و مقدار کوکی معتبر نیست.')
        path = row.get('path', '/')
        if not isinstance(path, str) or not path.startswith('/') or len(path)>2000:
            raise ValueError('مسیر کوکی معتبر نیست.')
        expires = row.get('expires', row.get('expirationDate', -1))
        if isinstance(expires, bool) or not isinstance(expires, (int, float)) or not math.isfinite(expires):
            raise ValueError('زمان انقضای کوکی معتبر نیست.')
        if expires > 0 and expires <= time.time():
            continue
        item = {'name': name, 'value': value, 'domain': domain, 'path': path,
                'expires': expires if expires > 0 else -1,
                'httpOnly': bool(row.get('httpOnly', False)), 'secure': bool(row.get('secure', True))}
        same = row.get('sameSite', 'Lax')
        item['sameSite'] = {'strict':'Strict','lax':'Lax','none':'None','no_restriction':'None'}.get(str(same).lower(),'Lax')
        cookies.append(item)
    origins = []
    origin_rows = raw.get('origins', []) if isinstance(raw, dict) else []
    if not isinstance(origin_rows, list) or len(origin_rows)>100:
        raise ValueError('ساختار نشست معتبر نیست.')
    for origin in origin_rows:
        if not isinstance(origin, dict) or origin.get('origin') != 'https://'+site['host']:
            continue
        storage = origin.get('localStorage', [])
        if not isinstance(storage, list) or len(storage)>1000:
            raise ValueError('ساختار ذخیرهٔ محلی معتبر نیست.')
        kept = []
        for entry in storage:
            if not isinstance(entry, dict) or not isinstance(entry.get('name'), str) or not isinstance(entry.get('value'), str):
                raise ValueError('ساختار ذخیرهٔ محلی معتبر نیست.')
            kept.append({'name':entry['name'],'value':entry['value']})
        origins.append({'origin':origin['origin'],'localStorage':kept})
    if not cookies and not any(o['localStorage'] for o in origins):
        raise ValueError('نشست غیرمنقضی مربوط به سایت انتخاب‌شده در فایل پیدا نشد.')
    state = {'cookies': cookies, 'origins': origins}
    if len(json.dumps(state).encode())>LIMIT:
        raise ValueError('فایل نشست بزرگ‌تر از حد مجاز است.')
    return state


def save_state(provider, state, *, verified=False):
    state = normalize_state(provider, state)
    payload = {'state':state,'verified':verified,'updated_at':time.time()}
    encrypted = base64.b64encode(protect(json.dumps(payload).encode())).decode('ascii')
    path = state_path(provider)
    with STORE_LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
        try:
            temp.write_text(json.dumps({'encrypted':encrypted}), encoding='utf-8')
            temp.replace(path)
        finally:
            temp.unlink(missing_ok=True)


def load_state(provider):
    path = state_path(provider)
    if not path.is_file():
        return None
    try:
        encrypted = json.loads(path.read_text(encoding='utf-8'))['encrypted']
        payload = json.loads(protect(base64.b64decode(encrypted), True))
        payload['state'] = normalize_state(provider, payload['state'])
        return payload
    except Exception:
        raise SessionError('نشست ذخیره‌شده قابل استفاده نیست؛ فایل نشست تازه را وارد کنید.') from None


def import_session(provider, filename):
    path = Path(filename).expanduser()
    if not path.is_absolute() or str(path).startswith('\\\\') or not path.is_file():
        raise ValueError('مسیر کامل یک فایل محلی JSON را وارد کنید.')
    try:
        with path.open('rb') as stream:
            content = stream.read(LIMIT+1)
        if len(content)>LIMIT:
            raise ValueError('فایل نشست باید کوچک‌تر از یک مگابایت باشد.')
        raw = json.loads(content.decode('utf-8-sig'))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise ValueError('فایل نشست JSON معتبر و قابل خواندن نیست.') from None
    state = normalize_state(provider, raw)
    save_state(provider, state)
    return {'saved': True, 'cookie_count':len(state['cookies']), 'origin_count':len(state['origins']),
            'credential_validated':False, 'transport_verified':False}


def inspect(provider):
    installed = importlib.util.find_spec('playwright') is not None
    try:
        payload = load_state(provider)
        verified = bool(payload and payload.get('verified'))
        configured = bool(payload)
        detail = ('آخرین آزمون دریافت پاسخ موفق بود؛ انقضای نشست با درخواست بعدی مشخص می‌شود.' if verified else
                  'فایل نشست وارد شده است؛ آزمون اتصال را اجرا کنید.' if configured else
                  'مسیر فایل محلی JSON نشست یا کوکی این سایت را وارد کنید.')
    except SessionError as exc:
        configured = verified = False
        detail = str(exc)
    if not installed:
        detail = 'موتور مرورگر نصب نیست؛ Playwright لازم است.'
    return {'id':provider,'installed':installed,'authenticated':verified and installed,
            'configured':configured,'credential_validated':verified,'transport_verified':verified,
            'version':'Website / Edge','billing':'website-account','detail':detail,
            'integration':'browser-ui','usage_available':False}


def valid_session_url(provider, url):
    site = site_for(provider)
    parsed = urlparse(url)
    pattern = r'/app/[A-Za-z0-9_-]+' if provider=='gemini-web' else r'/a/chat/s/[A-Za-z0-9_-]+'
    return parsed.scheme=='https' and parsed.netloc==site['host'] and bool(re.fullmatch(pattern,parsed.path)) and not parsed.query and not parsed.fragment


async def require_login(provider, page):
    site = site_for(provider)
    parsed = urlparse(page.url)
    if parsed.hostname!=site['host'] or '/sign_in' in parsed.path:
        raise SessionError('ورود حساب کامل نیست یا نشست منقضی شده است؛ خروجی نشست تازه لازم است.')
    composer = page.get_by_role('textbox',name='Enter a prompt for Gemini') if provider=='gemini-web' else page.locator('textarea')
    await composer.wait_for(state='visible',timeout=25000)
    if provider=='gemini-web':
        # The guest composer is usable too: require the visible Google account menu.
        if await page.get_by_role('link',name=re.compile('Google Account')).count()==0:
            raise SessionError('نشست Gemini وارد حساب نیست؛ حالت مهمان اتصال حساب محسوب نمی‌شود.')
    return composer


async def drive_page(provider, page, prompt):
    """Send once. Require a rendered response AND the site's post-generation controls."""
    composer = await require_login(provider, page)
    responses = page.locator('message-content') if provider=='gemini-web' else page.locator('.ds-assistant-message-main-content')
    before = await responses.count()
    terminal = page.get_by_role('button',name='Good response',exact=True) if provider=='gemini-web' else page.get_by_role('button',name='Read aloud',exact=True)
    terminal_before = await terminal.count()
    await composer.fill(prompt)
    await composer.press('Enter')
    last_complete_text = None
    while True:
        if await responses.count()>before:
            answer = responses.last
            text = (await answer.inner_text()).strip()
            # Existing replies' controls cannot finish the new response.
            done = await terminal.count()>terminal_before and await terminal.last.is_visible()
            if done and text:
                if last_complete_text==text:
                    return text
                last_complete_text = text
            else:
                last_complete_text = None
        await asyncio.sleep(.5)


async def generate(provider, prompt, session_id=None, *, verification=False):
    """Fresh isolated Edge context, with explicitly imported credentials only."""
    site = site_for(provider)
    payload = load_state(provider)
    if not payload:
        raise SessionError('ابتدا فایل محلی نشست را وارد کنید.')
    if session_id and not valid_session_url(provider, session_id):
        raise SessionError('شناسهٔ گفتگوی وب معتبر نیست؛ گفتگوی تازه بسازید.')
    sent = False
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as engine:
            browser = await engine.chromium.launch(channel='msedge',headless=False)
            try:
                context = await browser.new_context(storage_state=payload['state'],locale='en-GB')
                page = await context.new_page()
                await page.goto(session_id or site['url'],wait_until='domcontentloaded',timeout=45000)
                await require_login(provider,page)
                sent = True
                async with asyncio.timeout(180):
                    text = await drive_page(provider,page,prompt)
                if verification and text.strip()!=prompt.split('exactly ',1)[-1]:
                    raise SessionError('پاسخ آزمون اتصال مطابق انتظار نبود.')
                parsed = urlparse(page.url)
                url = parsed._replace(query='',fragment='').geturl()
                if not valid_session_url(provider,url):
                    raise SessionError('پاسخ دریافت شد اما شناسهٔ گفتگوی وب ثبت نشد؛ ارسال دوباره خودکار انجام نمی‌شود.')
                refreshed = await context.storage_state()
                save_state(provider,refreshed,verified=True)
                return text, {'billing':'website-account','physical_requests':1,'input_tokens':None,
                              'output_tokens':None,'actual_cost_usd':None,'usage_available':False}, url
            finally:
                await browser.close()
    except asyncio.CancelledError:
        save_state(provider,payload['state'],verified=False)
        raise
    except Exception:
        # No browser exception (which can contain state, page text or prompts) enters logs.
        save_state(provider,payload['state'],verified=False)
        message = ('پاسخ کامل وب تأیید نشد؛ درخواست ممکن است ارسال شده باشد. ارسال دوباره خودکار انجام نشد.' if sent else
                   'مرورگر یا ورود حساب آماده نیست؛ نشست تازه یا دسترسی به Edge را بررسی کنید.')
        raise SessionError(message) from None
