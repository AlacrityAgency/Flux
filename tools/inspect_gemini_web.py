"""Inspect the dedicated Gemini browser page; no credential extraction."""
import json
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright
parser=argparse.ArgumentParser();parser.add_argument('--send-test',action='store_true');args=parser.parse_args()
with sync_playwright() as p:
    c=p.chromium.launch_persistent_context(str(Path.home()/'.flux/integrations/gemini-browser'),executable_path=r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',headless=False)
    try:
        page=c.pages[0];page.goto('https://gemini.google.com/',wait_until='domcontentloaded',timeout=45000)
        page.locator('[contenteditable=true]').first.wait_for(timeout=15000)
        controls=page.locator('button,[role=button],textarea,[role=textbox],a').evaluate_all('''(els)=>els.map(e=>({tag:e.tagName,role:e.getAttribute("role"),label:e.getAttribute("aria-label"),text:(e.innerText||"").slice(0,80)})).filter(e=>e.label||e.text)''')
        if args.send_test:
            reject=page.get_by_role('button',name='Reject all',exact=True)
            if reject.count() and reject.is_visible():reject.click()
            page.get_by_role('textbox',name='Enter a prompt for Gemini').fill('Reply exactly FLUX_WEB_CONNECTION_OK. No tools.')
            page.get_by_role('textbox',name='Enter a prompt for Gemini').press('Enter')
            received=False
            try:
                page.get_by_text('FLUX_WEB_CONNECTION_OK',exact=True).first.wait_for(state='visible',timeout=45000)
                received=True
            except Exception:pass
            text=page.locator('body').inner_text()
            report={'site':'gemini','session':'dedicated-browser','cookies_imported':0,'guest_mode':page.get_by_role('link',name='Sign in',exact=True).count()>0,
                'send_attempts':1,'messages_sent':1 if received else None,'expected_reply_received':received,'transport_verified':received,'response_excerpt':text[-800:]}
            (Path(__file__).resolve().parents[1]/'docs/knowledge/web-gemini-message-check.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
            print(json.dumps(report,ensure_ascii=False))
        else:print(json.dumps({'url':page.url,'controls':controls,'text':page.locator('body').inner_text()[:700]},ensure_ascii=False))
        page.screenshot(path=str(Path(__file__).resolve().parents[1]/'docs/screenshots/gemini-web.png'))
    finally:c.close()
