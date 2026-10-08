"""User-controlled sign-in; session cookies stay inside a dedicated Edge profile."""
import json
from pathlib import Path
import time
from playwright.sync_api import sync_playwright

root=Path.home()/'.flux/integrations/deepseek-browser';root.mkdir(parents=True,exist_ok=True)
state=root/'flux-status.json'
def record(ready,detail):
    state.write_text(json.dumps({'browser_login_observed':ready,'checked_at':time.time(),'detail':detail,'message_transport_verified':False}),encoding='utf-8')
with sync_playwright() as p:
    context=p.chromium.launch_persistent_context(str(root),executable_path=r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',headless=False)
    try:
        page=context.pages[0];page.goto('https://chat.deepseek.com/',wait_until='domcontentloaded',timeout=45000)
        record(False,'Login pending in the browser.')
        print('Sign in to DeepSeek in the opened Edge window. Cookies stay in this browser profile.',flush=True)
        deadline=time.monotonic()+600
        while time.monotonic()<deadline:
            if page.is_closed():break
            if page.url.startswith('https://chat.deepseek.com/') and '/sign_' not in page.url and page.locator('textarea').count():
                record(True,'Chat composer observed after user login. Sending still requires verification.')
                print('Browser login observed; message transport not yet tested.',flush=True)
                # Read only the input controls, never cookies or previous chats.
                controls=page.locator('textarea').evaluate_all('(items)=>items.map(e=>({tag:e.tagName,placeholder:e.getAttribute("placeholder"),ariaLabel:e.getAttribute("aria-label")}))')
                (root/'flux-composer.json').write_text(json.dumps(controls,ensure_ascii=False),encoding='utf-8')
                break
            page.wait_for_timeout(1000)
    finally:context.close()
