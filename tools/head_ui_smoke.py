"""Offline browser acceptance flow and responsive HEAD page verification."""
import json
import mimetypes
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from threading import Thread
from playwright.sync_api import sync_playwright,expect

ROOT=Path(__file__).resolve().parents[1];STATIC=ROOT/'src/flux/static'
task={'id':'fixture-head','contract':{'objective':'هدف تستی HEAD','execution_provider':'codex','acceptance_criteria':[{'criterion_id':'C1','text':'متن معیار دقیق','evidence_type':'source_document'}],'allowed_tools':['read_workspace'],'allowed_paths':[],'policy_revision':1},
      'state':'READY','root_counters':{'calls':0},'generations':0,'artifact':None,'artifact_hash':None,'contract_hash':'b'*64,'review_revision':0,'review':None,'evidence':[],'operations':[]}
class Server(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def send(self,data,kind='application/json'):
        content=json.dumps(data,ensure_ascii=False).encode() if kind=='application/json' else data
        self.send_response(200);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(content)));self.end_headers();self.wfile.write(content)
    def do_GET(self):
        if self.path=='/head':return self.send((STATIC/'head.html').read_bytes(),'text/html; charset=utf-8')
        if self.path.startswith('/static/'):
            path=(STATIC/self.path.removeprefix('/static/')).resolve()
            if path.is_relative_to(STATIC) and path.is_file():return self.send(path.read_bytes(),mimetypes.guess_type(path)[0] or 'application/octet-stream')
        if self.path=='/projects':return self.send([{'id':'project','name':'پروژهٔ آزمایشی'}])
        if self.path=='/api/local/status':return self.send({'providers':[{'id':'codex','authenticated':True},{'id':'claude','authenticated':False}]})
        if self.path.endswith('/events'):return self.send([{'kind':'state','payload':{'state':task['state']}}])
        if self.path=='/api/core/tasks':return self.send([task])
        return self.send(task)
    def do_POST(self):
        data=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        if self.path=='/api/core/tasks':
            assert data['scope']==['تحلیل مستندات'] and data['execution_provider']=='codex'
            assert 'budget_cap_micros' not in data and 'review_reserve_micros' not in data
            assert data['limits']['max_generation_attempts']==2 and data['output_format']=='json'
            task['contract']=data
        if self.path.endswith('/execute'):
            assert data['provider']==task['contract']['execution_provider']
            task.update(state='REVIEWING',artifact='<img src=x onerror=alert(1)> خروجی دقیق تست',artifact_hash='a'*64,generations=1)
            task['root_counters']['calls']=1
            task['evidence']=[{'id':'evidence','artifact_hash':'a'*64,'evidence_type':'source_document','outcome':'observed','source_ref':'fixture artifact','content':task['artifact']}]
        if self.path.endswith('/review'):
            assert data['criterion_results'][0]['criterion_id']=='C1' and data['criterion_results'][0]['evidence_refs']==['evidence']
            task.update(state='ACCEPT_CANDIDATE',review_revision=1,review=data)
        if self.path.endswith('/accept'):
            assert data=={'artifact_hash':'a'*64,'review_revision':1};task['state']='ACCEPTED'
        return self.send(task)

server=ThreadingHTTPServer(('127.0.0.1',0),Server);Thread(target=server.serve_forever,daemon=True).start();errors=[]
try:
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path=r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',headless=True)
        page=browser.new_page(viewport={'width':1440,'height':960});page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(f'http://127.0.0.1:{server.server_port}/head')
        page.locator('#head-objective').fill('هدف تستی HEAD')
        page.locator('#wizard-next').click()
        page.locator('#head-scope').fill('تحلیل مستندات')
        page.locator('#wizard-next').click()
        expect(page.locator('#head-request-provider')).to_have_value('codex')
        page.locator('#wizard-next').click()
        page.locator('#head-attempts').fill('2')
        page.locator('#wizard-next').click()
        page.locator('#head-criteria').fill('متن معیار دقیق')
        page.locator('#wizard-next').click()
        page.locator('#head-output-format').select_option('json')
        page.locator('#head-ambiguity').fill('زبان خروجی مشخص نیست')
        page.locator('#wizard-next').click()
        expect(page.locator('#contract-question')).to_be_visible()
        expect(page.locator('#contract-sheet')).to_be_hidden()
        page.locator('#head-output-notes').fill('خروجی فارسی')
        page.locator('#head-ambiguity').fill('')
        page.locator('#wizard-next').click()
        expect(page.locator('#contract-summary')).to_contain_text('خروجی فارسی')
        page.locator('#contract-submit').click()
        expect(page.locator('#contract-question')).to_be_visible()
        page.locator('#contract-approved').check()
        page.locator('#contract-submit').click()
        expect(page.locator('#head-detail')).to_be_visible()
        expect(page.locator('#head-generate')).to_be_enabled();expect(page.locator('#head-accept')).to_be_disabled()
        page.locator('#head-generate').click();expect(page.locator('#head-state')).to_contain_text('بازبینی')
        assert page.locator('#head-artifact img').count()==0
        page.locator('[data-field=status]').select_option('PASS');page.locator('[data-field=evidence]').select_option('evidence')
        page.locator('[data-field=explanation]').fill('شاهد مشاهده و تطبیق داده شد');page.locator('#head-submit-review').click()
        expect(page.locator('#head-accept')).to_be_enabled();page.locator('#head-accept').click()
        expect(page.locator('#head-state')).to_contain_text('پذیرفته‌شده');expect(page.locator('#head-accept')).to_be_disabled()
        screenshots=ROOT/'docs/screenshots/head';screenshots.mkdir(parents=True,exist_ok=True)
        for width in [375,768,1024,1440]:
            page.set_viewport_size({'width':width,'height':960})
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),width
            if width in [375,1440]:page.screenshot(path=str(screenshots/f'head-{width}.png'),full_page=True)
        assert not errors,errors;browser.close()
finally:server.shutdown();server.server_close()
report={'passed':True,'responsive_widths':[375,768,1024,1440],'page_errors':errors,'model_calls':0,'data':'isolated fixture','acceptance_bound_to_artifact_and_review':True}
(ROOT/'docs/knowledge/head-ui-check.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report))
