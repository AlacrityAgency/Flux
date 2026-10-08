"""Browser checks against a separate local Flux test database, without model calls."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

out = Path("docs/screenshots/local-agents")
out.mkdir(parents=True, exist_ok=True)
with sync_playwright() as playwright:
    browser = playwright.chromium.launch(executable_path=r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", headless=True)
    page = browser.new_page(viewport={"width":1440,"height":960})
    page.add_init_script("localStorage.setItem('flux-provider-choice','codex')")
    page.set_default_timeout(45000)
    page.emulate_media(reduced_motion="reduce")
    page.route("**/api/local/notebooks", lambda route: route.fulfill(json={"notebooks":[{"id":"flux-ui-book","title":"دفتر آزمایشی Flux"}]}))
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    base_url = os.environ.get("FLUX_UI_BASE_URL", "http://127.0.0.1:8056")
    page.goto(base_url)
    expect(page.locator("#side-resize")).to_be_visible()
    assert page.locator('#side').bounding_box()['width'] == 280
    grip = page.locator('#side-resize').bounding_box()
    start_x, y = grip['x'] + grip['width'] / 2, grip['y'] + 90
    page.mouse.move(start_x, y)
    page.mouse.down()
    page.mouse.move(start_x - 48, y, steps=6)
    page.mouse.up()
    expect(page.locator('#side')).to_have_css('width', '328px')
    assert page.evaluate("localStorage.getItem('flux-design-v2-sidebar-width')") == '328'
    page.locator('#collapse').click()
    assert 'collapsed' in page.locator('#app').get_attribute('class')
    page.locator('#collapse').click()
    expect(page.locator('#side')).to_have_css('width', '328px')
    if not any(p['path'].casefold()==r'D:\project\Alacrity\Flux'.casefold() for p in page.request.get(base_url + '/projects').json()):
        project = page.request.post(base_url + '/projects', data={
            'name': 'HEAD browser fixture', 'path': r'D:\project\Alacrity\Flux',
        })
        assert project.status == 201, project.text()
    mock_status = lambda route: route.fulfill(json={'providers': [{'id': 'codex', 'authenticated': True}]})
    page.route('**/api/local/status', mock_status)
    page.locator('[data-focus-composer]').first.click()
    expect(page.locator('#head-project option')).to_have_count(1)
    page.locator('#head-objective').fill('یک گزارش کوتاه از پروژه تهیه کن')
    page.locator('#wizard-next').click()
    page.locator('#head-scope').fill('بررسی ساختار پروژه')
    page.locator('#wizard-next').click()
    expect(page.locator('#head-request-provider')).to_be_visible()
    assert page.locator('#head-budget').count() == 0
    assert page.locator('#head-reserve').count() == 0
    page.unroute('**/api/local/status', mock_status)
    page.goto(base_url + '/chat')
    expect(page.locator("#folder-label")).not_to_have_text("پوشهٔ کاری", timeout=45000)
    expect(page.locator("#welcome")).to_be_visible()
    assert page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--bg').trim()") == '#0a0a0a'
    assert page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--accent').trim()") == '#f2f2ee'
    assert page.locator('#sidebar').bounding_box()['x'] == 1440-252
    assert page.locator('.brand img').get_attribute('src') == '/static/flux-mark.png'
    page.screenshot(path=str(out / "desktop.png"), full_page=True)
    page.locator('#model-settings').click()
    expect(page.locator('#workspace-settings')).to_be_visible()
    page.locator('#model').fill('gpt-6.1-sol')
    page.locator('#access').select_option('read')
    page.locator('#save-settings').click()
    expect(page.locator('#model-label')).to_have_text('gpt-6.1-sol')
    expect(page.locator('#access-label')).to_have_text('فقط خواندن')
    page.locator('#provider-toggle').click()
    expect(page.locator('#provider-menu')).to_be_visible()
    expect(page.locator('#provider-menu [role=option]')).to_have_count(10)
    page.screenshot(path=str(out / 'provider-menu.png'), full_page=True)
    page.locator('[data-provider="claude"]').click()
    expect(page.locator('#provider-label')).to_have_text('Claude')
    expect(page.locator('#model-label')).to_have_text('پیش‌فرض')
    assert 'opus' in page.locator('#model-list option').evaluate_all('(items)=>items.map(item=>item.value)')
    page.locator('#provider-toggle').focus()
    page.keyboard.press('ArrowDown')
    page.keyboard.press('Home')
    page.keyboard.press('ArrowDown')
    page.keyboard.press('Enter')
    expect(page.locator('#provider-label')).to_have_text('Codex')
    page.locator('#model-settings').click()
    page.locator('#model').fill('gpt-6.1-sol')
    page.locator('#save-settings').click()
    page.locator('#provider-toggle').click()
    page.locator('[data-provider="codex"]').click()
    expect(page.locator('#model-label')).to_have_text('gpt-6.1-sol')
    page.locator('#collapse-sidebar').click()
    assert page.locator('#sidebar').bounding_box()['width'] == 74
    page.locator('#collapse-sidebar').click()
    assert page.locator('#sidebar').bounding_box()['width'] == 252
    grip = page.locator('#sidebar-resize').bounding_box()
    start_x, y = grip['x'] + grip['width'] / 2, grip['y'] + 100
    page.mouse.move(start_x, y)
    page.mouse.down()
    page.mouse.move(start_x - 40, y, steps=5)
    page.mouse.up()
    rendered_width = int(float(page.locator('#sidebar').evaluate("el=>getComputedStyle(el).width")[:-2]))
    resized_width = int(page.evaluate("localStorage.getItem('flux-sidebar-width')"))
    assert 289 <= resized_width <= 293 and abs(rendered_width-resized_width) <= 2, (rendered_width,resized_width)
    page.locator("#connections-button").click()
    current_status = page.request.get(base_url + '/api/local/status').json()
    expect(page.locator("#provider-cards .provider-card")).to_have_count(len(current_status['providers']))
    assert page.locator("#provider-cards .ready").count() == sum(bool(p['authenticated']) for p in current_status['providers'])
    quota_data = page.request.get(base_url + '/api/local/usage').json()['providers']
    for provider_id in ('codex','claude','notebooklm'):
        quota = next(item for item in quota_data if item['id']==provider_id)
        if quota['windows']:
            expect(page.locator(f'#quota-{provider_id} .quota-track')).not_to_have_count(0)
        elif quota['detail']:
            expect(page.locator(f'#quota-{provider_id}')).to_contain_text(quota['detail'])
    expect(page.locator('#quota-antigravity .quota-track')).to_have_count(0)
    page.screenshot(path=str(out / "connections.png"), full_page=True)
    page.locator('[data-close="connections"]').click()
    page.locator("#folder-button").click()
    expect(page.locator("#folder-dialog")).to_be_visible()
    page.locator("#cwd").fill(r"D:\project\Alacrity\Flux")
    page.locator("#folder-form button[type=submit]").click()
    page.locator("[data-prompt]").first.click()
    expect(page.locator("#prompt")).not_to_be_empty()

    # Test rendering, model locking, and safe display of untrusted model output.
    fake_chat = {"id":"ui-check", "title":"بررسی رابط", "cwd":r"D:\project\Alacrity\Flux", "provider":"codex",
                 "model":"", "access":"work", "turns":[{"id":"ui-turn","prompt":"یک نمونه کد بنویس",
                 "text":"پاسخ نمونه\n```html\n<img src=x onerror=alert(1)>\n```", "state":"completed", "error":"", "usage":{"references":[{"source_id":"sample","cited_text":"<img src=x onerror=alert(1)>"}]}}]}
    page.route("**/api/local/chats/ui-check", lambda route: route.fulfill(json=fake_chat))
    page.route("**/api/local/chats", lambda route: route.fulfill(json=[fake_chat]))
    page.route("**/api/local/turns/ui-turn/events?*", lambda route: route.fulfill(json=[{"sequence":1,"kind":"tool","payload":{"name":"command_execution","status":"completed","output":"passed"}}]))
    page.reload()
    expect(page.locator('#sidebar')).to_have_css('width', f'{rendered_width}px')
    expect(page.locator("#history .history-item")).to_have_count(1)
    page.locator("#history .history-item").click()
    expect(page.locator(".message-content pre")).to_contain_text("onerror")
    assert page.locator(".message-content img").count() == 0
    expect(page.locator('.source-references')).to_have_count(1)
    assert page.locator('.source-references img').count() == 0
    expect(page.locator("#provider")).to_be_enabled()
    expect(page.locator("#provider-toggle")).to_be_enabled()
    page.locator('#model-settings').click()
    expect(page.locator('#model')).to_be_disabled()
    expect(page.locator('#access')).to_be_disabled()
    page.locator('#save-settings').click()
    page.locator('#prompt').fill('متن پیش‌نویس حفظ شود')
    page.locator('#provider-toggle').click()
    page.locator('[data-provider="notebooklm"]').click()
    expect(page.locator('#welcome')).to_be_visible()
    expect(page.locator('#prompt')).to_have_value('متن پیش‌نویس حفظ شود')
    expect(page.locator('#history .history-item')).to_have_count(1)
    expect(page.locator('#notebook-control')).to_be_visible()
    expect(page.locator('#model-settings')).to_be_hidden()
    expect(page.locator('#folder-button')).to_be_hidden()
    expect(page.locator('#composer-settings')).to_be_hidden()
    expect(page.locator('[data-prompt]').first).to_have_text('خلاصهٔ منابع')
    page.locator('#notebook-select').select_option('flux-ui-book')
    expect(page.locator('#open-notebook')).to_have_attribute('href','https://notebooklm.google.com/notebook/flux-ui-book')
    page.screenshot(path=str(out / 'notebook-selector.png'), full_page=True)
    page.set_viewport_size({'width':375,'height':900})
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
    page.screenshot(path=str(out / 'notebook-mobile.png'), full_page=True)
    page.set_viewport_size({'width':1440,'height':960})
    page.locator('#provider-toggle').click()
    page.locator('[data-provider="antigravity"]').click()
    expect(page.locator('#provider-hint')).not_to_be_empty()
    antigravity = next(p for p in page.request.get(base_url + '/api/local/status').json()['providers'] if p['id']=='antigravity')
    if antigravity['authenticated']:
        assert len(page.locator('#model-list option').evaluate_all('(items)=>items.map(item=>item.value)')) > 0
    page.locator('#history .history-item').click()
    expect(page.locator('#provider-label')).to_have_text('Codex')
    expect(page.locator('#notebook-control')).to_be_hidden()
    page.locator('#search-button').click()
    page.locator('#chat-search').fill('missing-chat')
    expect(page.locator('#search-results')).to_have_text('گفتگویی پیدا نشد.')
    page.locator('#chat-search').fill('بررسی')
    page.locator('#search-results button').click()
    expect(page.locator('#search-dialog')).not_to_be_visible()
    page.get_by_role("button",name="فعالیت اجرا", exact=True).click()
    expect(page.locator(".activity-event")).to_have_count(1)
    page.screenshot(path=str(out / "conversation.png"), full_page=True)
    page.locator("#close-activity").click()
    def mock_submit(route):
        fake_chat['turns'].append({'id':'running-turn','prompt':'بررسی آزمایشی رابط','text':'','state':'running','error':'','usage':{}})
        route.fulfill(json=fake_chat['turns'][-1], status=202)
    def mock_cancel(route):
        fake_chat['turns'][-1]['state']='cancelled'
        route.fulfill(json=fake_chat['turns'][-1])
    page.route('**/api/local/chats/ui-check/turns', mock_submit)
    page.route('**/api/local/turns/running-turn/events?*', lambda route: route.fulfill(json=[]))
    page.route('**/api/local/turns/running-turn/cancel', mock_cancel)
    page.locator('#prompt').fill('بررسی آزمایشی رابط')
    page.locator('#send').click()
    expect(page.locator('#send')).to_have_attribute('aria-label','توقف اجرا')
    expect(page.locator('#provider-toggle')).to_be_disabled()
    page.locator('#send').click()
    expect(page.locator('#send')).to_have_attribute('aria-label','ارسال پیام')
    expect(page.locator('#provider-toggle')).to_be_enabled()
    for width in (375,768,1024):
        page.set_viewport_size({"width":width,"height":900})
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"), width
        if width==375:
            page.locator('#provider-toggle').click()
            box = page.locator('#provider-menu').bounding_box()
            assert box['x'] >= 0 and box['x'] + box['width'] <= width
            page.keyboard.press('Escape')
            expect(page.locator('#provider-menu')).to_be_hidden()
            page.screenshot(path=str(out / "mobile.png"), full_page=True)
            page.locator("#menu-button").click()
            expect(page.locator("#sidebar")).to_have_class("sidebar open")
            assert page.locator('#sidebar').bounding_box()['x'] == width-260
    assert not errors, errors
    browser.close()
print(json.dumps({"page_errors":errors,"responsive_widths":[375,768,1024,1440],"screenshots":str(out)},ensure_ascii=False))
