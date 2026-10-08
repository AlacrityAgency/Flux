"""Installed-binary checks with synthetic cookies and a separate temporary database.

Does not launch a website, click Verify, or use real model credentials.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time

import httpx
import psutil
from PyInstaller.archive.readers import CArchiveReader

parser=argparse.ArgumentParser()
parser.add_argument('--exe',type=Path,default=Path.home()/'AppData/Local/Programs/Flux/Flux.exe')
args=parser.parse_args();root=Path(__file__).resolve().parents[1];exe=args.exe.resolve()
temporary=Path(tempfile.mkdtemp(prefix='flux-web-packaged-'))
report={'version':'0.5.1','exe':str(exe),'sha256':hashlib.sha256(exe.read_bytes()).hexdigest(),
        'model_calls':0,'real_session_imports':0,'user_database_access':False,'checks':[]}
archive=CArchiveReader(str(exe))
for filename in ['local.html','local.css','local.js','project-memory.js','head.html','head.js']:
    key=next(k for k in archive.toc if k.replace('\\','/')=='flux/static/'+filename)
    assert archive.extract(key)==(root/'src/flux/static'/filename).read_bytes()
report['checks'].append('bundled UI equals current source')
assert any(k.replace('\\','/').endswith('playwright/driver/node.exe') for k in archive.toc)
assert any('playwright/driver/package' in k.replace('\\','/') for k in archive.toc)
report['checks'].append('browser driver bundled')
with socket.socket() as listener:
    listener.bind(('127.0.0.1',0));port=listener.getsockname()[1]
env=dict(os.environ,FLUX_DB_PATH=str(temporary/'flux.db'),FLUX_WEB_SESSION_DIR=str(temporary/'sessions'),
         FLUX_KEYS_PATH=str(temporary/'keys.json'))
log=(temporary/'server.log').open('wb')
process=subprocess.Popen([str(exe),'serve','--host','127.0.0.1','--port',str(port),'--no-browser'],
    cwd=root,env=env,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
try:
    with httpx.Client(base_url=f'http://127.0.0.1:{port}',timeout=30) as client:
        deadline=time.monotonic()+60
        while True:
            try:
                client.get('/').raise_for_status();break
            except httpx.HTTPError:
                if process.poll() is not None or time.monotonic()>deadline:raise RuntimeError('Packaged server failed; see '+str(temporary/'server.log'))
                time.sleep(.25)
        assert client.get('/openapi.json').json()['info']['version']=='0.5.1'
        assert 'Gemini Web' in client.get('/').text and 'DeepSeek Web' in client.get('/').text
        assert client.get('/head').status_code==200 and client.get('/legacy').status_code==200
        report['checks'].append('installed version and UI routes')
        source=temporary/'synthetic-session.json'
        source.write_text(json.dumps([{'name':'synthetic_session','value':'NO_REAL_CREDENTIAL_FIXTURE','domain':'chat.deepseek.com','path':'/'}]),encoding='utf-8')
        before=source.read_bytes()
        response=client.put('/api/local/connections/web/deepseek-web',json={'path':str(source)}).raise_for_status().json()
        assert response['saved'] and not response['credential_validated'] and not response['transport_verified']
        assert source.read_bytes()==before
        encrypted=(temporary/'sessions/deepseek-web.json').read_text()
        assert 'NO_REAL_CREDENTIAL_FIXTURE' not in encrypted
        assert client.put('/api/local/connections/web/gemini-web',json={'path':str(source)}).status_code==400
        assert client.put('/api/local/connections/web/not-a-site',json={'path':str(source)}).status_code==404
        report['checks'].append('scoped encrypted import; no premature connected claim')
        chat=client.post('/api/local/chats',json={'provider':'deepseek-web','cwd':str(temporary),'access':'work'}).raise_for_status().json()
        assert chat['access']=='read'
        assert client.post('/api/local/chats',json={'provider':'gemini-web','cwd':str(temporary),'model':'fake-model'}).status_code==422
        report['checks'].append('website read-only boundary and model selection validation')
        project=client.post('/projects',json={'name':'Web packaged QA','path':str(temporary)}).raise_for_status().json()
        note=client.post('/memories',json={'title':'Scoped QA','content':'Packaged web release regression proof','project_id':project['id']}).raise_for_status().json()
        pack=client.post('/api/core/projects/'+project['id']+'/retrieve',json={'objective':'Packaged web release regression proof','budget':500}).raise_for_status().json()
        assert pack['tokens']<=500 and any(e['ref']==note['id'] for e in pack['evidence'])
        report['checks'].append('project memory retrieval still bounded and scoped')
finally:
    try:
        owned=psutil.Process(process.pid)
        for child in owned.children(recursive=True):
            try:child.kill()
            except psutil.Error:pass
        owned.kill();process.wait(timeout=10)
    except psutil.NoSuchProcess:pass
    log.close()
report['temporary_check_directory']=str(temporary)
(root/'docs/knowledge/web-session-packaged-check.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report,indent=2))
