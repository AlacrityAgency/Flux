"""Inspect an explicitly supplied cookie export through the real website UI.

No private API emulation, raw-cookie logging, default-browser cookie extraction,
or login challenge bypass. Input is a local JSON cookie export, never a URL.
"""
import argparse
import json
from pathlib import Path
import time
from playwright.sync_api import sync_playwright

parser=argparse.ArgumentParser()
parser.add_argument('--site',choices=['gemini','deepseek'],required=True)
parser.add_argument('--cookie-file',type=Path)
args=parser.parse_args()
url='https://gemini.google.com/' if args.site=='gemini' else 'https://chat.deepseek.com/'
domains={'google.com','gemini.google.com','accounts.google.com'} if args.site=='gemini' else {'deepseek.com','chat.deepseek.com'}
cookies=[]
if args.cookie_file:
    path=args.cookie_file.expanduser().resolve()
    if not path.is_file() or path.stat().st_size>256000:raise SystemExit('Choose an explicit JSON export below 256 KB.')
    raw=json.loads(path.read_text(encoding='utf-8-sig'))
    raw=raw.get('cookies',[]) if isinstance(raw,dict) else raw
    if not isinstance(raw,list):raise SystemExit('Expected a JSON list of browser cookies.')
    for row in raw:
        if str(row.get('domain','')).lstrip('.').lower() not in domains:continue
        if not isinstance(row.get('value'),str) or not row.get('name'):continue
        item={k:row[k] for k in ('name','value','domain','path','secure','httpOnly') if k in row}
        item.setdefault('path','/')
        if row.get('sameSite') in {'Strict','Lax','None'}:item['sameSite']=row['sameSite']
        if isinstance(row.get('expires'),(int,float)) and row['expires']>0:item['expires']=row['expires']
        cookies.append(item)
    if not cookies:raise SystemExit('No cookies with values for the selected site were supplied.')
profile=Path.home()/('.flux/integrations/'+args.site+'-browser')
with sync_playwright() as p:
    context=p.chromium.launch_persistent_context(str(profile),executable_path=r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',headless=False)
    try:
        if cookies:context.add_cookies(cookies)
        page=context.pages[0];page.goto(url,wait_until='domcontentloaded',timeout=45000)
        try:page.locator('textarea,[contenteditable="true"][role="textbox"]').first.wait_for(state='visible',timeout=30000)
        except Exception:pass
        report={'site':args.site,'cookie_count_imported':len(cookies),'composer_observed':page.locator('textarea,[contenteditable="true"][role="textbox"]').count()>0,
            'login_page':any(s in page.url for s in ['/sign_in','accounts.google.com']), 'messages_sent':0,'transport_verified':False,'checked_at':time.time()}
        dest=Path(__file__).resolve().parents[1]/'docs/knowledge'/('web-'+args.site+'-session-check.json')
        dest.write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
    finally:context.close()
