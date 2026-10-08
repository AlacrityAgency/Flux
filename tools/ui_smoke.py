"""Optional browser QA: .venv-ui/Scripts/python tools/ui_smoke.py."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

out = Path('docs/screenshots')
out.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe', headless=True)
    context = browser.new_context(viewport={"width":1440,"height":960}, device_scale_factor=1)
    page = context.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto('http://127.0.0.1:8040/legacy')
    page.locator('#mode-badge').get_by_text('حالت آزمایشی').wait_for()
    page.wait_for_load_state('networkidle')
    if page.locator('html').get_attribute('data-theme') != 'dark':
        page.locator('#theme-toggle').click()
    expect(page.locator('html')).to_have_attribute('data-theme', 'dark')
    page.screenshot(path=str(out/'flux-welcome-dark.png'),full_page=True)

    # 1. Memory Test
    page.locator('[data-view="memory"]').click()
    page.locator('#add-memory').click()
    page.locator('#memory-title').fill('معماری Flux')
    page.locator('#memory-content').fill('رابط Flux باید فارسی باشد. داده‌های شخصی روی همین سیستم ذخیره شوند.')
    page.locator('#memory-form .primary-button').click()
    page.locator('#memory-dialog').wait_for(state='hidden')
    page.locator('.memory-card').first.wait_for()
    page.screenshot(path=str(out/'flux-memory.png'),full_page=True)

    # 2. Projects and Folder Management QA
    page.locator('[data-view="projects"]').click()
    page.locator('#projects-overview').wait_for()
    page.locator('#overview-add-project').click()
    page.locator('#project-dialog').wait_for(state='visible')
    page.locator('#proj-name-input').fill('پروژه اتوماسیون Flux')
    page.locator('#proj-path-input').fill(r'D:\project\Alacrity\Flux')
    page.locator('.path-feedback.success').wait_for(timeout=8000)
    page.locator('#project-form .primary-button').click()
    page.locator('#project-dialog').wait_for(state='hidden')
    page.locator('#project-detail-view').wait_for(state='visible')
    assert 'Flux' in page.locator('#proj-detail-title').inner_text()
    page.screenshot(path=str(out/'flux-project-detail.png'), full_page=True)

    # Add task to project
    page.locator('#add-project-task-btn').click()
    page.locator('#project-task-dialog').wait_for(state='visible')
    page.locator('#ptask-title-input').fill('بررسی ساختار فایل‌های پروژه')
    page.locator('#ptask-objective-input').fill('بررسی مسیر پوشه و اطمینان از صحت فایل‌های پیکربندی')
    page.locator('#ptask-criteria-input').fill('فایل‌های اصلی بررسی شوند\nگزارش کوتاه ارائه شود')
    page.locator('#project-task-form .primary-button').click()
    page.locator('#project-task-dialog').wait_for(state='hidden')
    page.locator('.task-card').first.wait_for()
    assert page.locator('.task-card').count() >= 1

    # 3. Conversation & 5-Agent Pipeline
    page.locator('#new-chat').click()
    page.locator('[data-template="technical"]').click()
    page.locator('#send-button').click()
    page.locator('[data-accept]').wait_for(timeout=20000)
    assert page.locator('.step-pill.done').count() == 5
    page.locator('[data-accept]').click()
    page.locator('.accepted-label').wait_for()
    page.locator('#agents-toggle').click()
    page.screenshot(path=str(out/'flux-conversation.png'),full_page=True)
    page.locator('#close-agents').click()
    page.locator('#prompt').fill('همین پیشنهاد را کوتاه‌تر بنویس و محدودیت‌ها را نگه دار.')
    page.locator('#send-button').click()
    page.locator('.message-turn').nth(1).locator('[data-accept]').wait_for(timeout=20000)
    assert page.locator('.message-turn').count() == 2
    page.reload()
    page.locator('.message-turn').nth(1).wait_for()
    assert page.locator('.accepted-label').count() == 1

    # 4. Usage
    page.locator('[data-view="usage"]').first.click()
    page.locator('.usage-table').wait_for()
    page.screenshot(path=str(out/'flux-usage.png'),full_page=True)

    # 5. Theme & Mobile
    page.locator('#new-chat').click()
    page.locator('#theme-toggle').click()
    expect(page.locator('html')).to_have_attribute('data-theme', 'light')
    page.screenshot(path=str(out/'flux-welcome-light.png'),full_page=True)
    page.emulate_media(reduced_motion="reduce")
    page.set_viewport_size({"width":390,"height":844})
    page.screenshot(path=str(out/'flux-mobile.png'),full_page=True,animations='disabled')
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.locator('#open-sidebar').click()
    page.locator('#sidebar.mobile-open').wait_for()
    page.locator('#collapse-sidebar').click()
    assert errors == [], errors
    print(json.dumps({"browser_errors": errors,"checks":["welcome","memory CRUD create","projects & folder connection","project task creation","five agent run","human acceptance","followup","reload persistence","usage","light theme","mobile sidebar","no horizontal overflow"]}))
    browser.close()
