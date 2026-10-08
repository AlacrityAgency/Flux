"""Check bundled UI and shared APIs on an isolated temporary packaged server."""
import argparse
import hashlib
import json
import os
import socket
import subprocess
import tempfile
import time
from pathlib import Path

import httpx
import psutil
from PyInstaller.archive.readers import CArchiveReader

parser = argparse.ArgumentParser()
parser.add_argument('--exe', type=Path, default=Path('dist/local-agents/Flux.exe'))
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
exe = args.exe.resolve()
report = {'exe': str(exe), 'sha256': hashlib.sha256(exe.read_bytes()).hexdigest(),
          'model_calls': 0, 'user_database_access': False, 'checks': []}
archive = CArchiveReader(str(exe))
for filename in ['local.html', 'local.css', 'local.js', 'project-memory.js','head.html','head.js','head.css']:
    key = next(k for k in archive.toc if k.replace('\\', '/') == 'flux/static/' + filename)
    assert archive.extract(key) == (root / 'src/flux/static' / filename).read_bytes(), filename
    report['checks'].append('bundled source equals ' + filename)
with socket.socket() as listener:
    listener.bind(('127.0.0.1', 0))
    port = listener.getsockname()[1]
qa_dir = Path(tempfile.mkdtemp(prefix='flux-packaged-project-memory-'))
env = dict(os.environ, FLUX_DB_PATH=str(qa_dir / 'flux.db'))
log = (qa_dir / 'server.log').open('wb')
proc = subprocess.Popen([str(exe), 'serve', '--host', '127.0.0.1', '--port', str(port), '--no-browser'],
                        cwd=root, env=env, stdout=log, stderr=log,
                        creationflags=subprocess.CREATE_NO_WINDOW)
try:
    with httpx.Client(base_url=f'http://127.0.0.1:{port}', timeout=10) as client:
        deadline = time.monotonic() + 90
        while True:
            try:
                page = client.get('/').raise_for_status()
                break
            except (httpx.HTTPError, ConnectionError):
                if proc.poll() is not None or time.monotonic() >= deadline:
                    raise RuntimeError('Packaged QA server did not start; see ' + str(qa_dir / 'server.log'))
                time.sleep(.25)
        assert 'id="project-memory-button"' in page.text
        assert '/static/project-memory.js' in page.text
        assert client.get('/static/project-memory.js').raise_for_status().content == (root / 'src/flux/static/project-memory.js').read_bytes()
        assert '/static/app.js' in client.get('/legacy').raise_for_status().text
        report['checks'].append('packaged current page and explicit legacy route')
        project = client.post('/projects', json={'name': 'Packaged QA', 'path': str(qa_dir)}).raise_for_status().json()
        assert client.get('/head').raise_for_status().text == (root/'src/flux/static/head.html').read_text(encoding='utf-8')
        capabilities=client.get('/api/core/capabilities').raise_for_status().json()
        assert capabilities['deployment']=='local-single-owner' and 'gapcode-read-only' in capabilities['execution']
        task=client.post('/api/core/tasks',json={'project_id':project['id'],'request_key':'packaged-contract',
            'objective':'Explain this isolated packaged check','acceptance_criteria':[{'criterion_id':'C1','text':'An actual artifact must be reviewed'}]}).raise_for_status().json()
        assert task['state']=='READY' and client.get('/api/core/tasks/'+task['id']+'/decision').json()['action']=='GENERATE'
        assert client.post('/api/core/tasks/'+task['id']+'/accept',json={'artifact_hash':'a'*64,'review_revision':1}).status_code==422
        scoped=client.post('/memories',json={'title':'Scoped proof','content':'Project-specific current evidence','project_id':project['id']}).raise_for_status().json()
        pack=client.post('/api/core/projects/'+project['id']+'/retrieve',json={'objective':'Project-specific current evidence','budget':500}).raise_for_status().json()
        assert pack['tokens']<=500 and any(e['ref']==scoped['id'] for e in pack['evidence'])
        client.delete('/memories/'+scoped['id']).raise_for_status()
        report['checks'].append('HEAD contract/gate and project-scoped bounded retrieval in packaged runtime')
        edited = client.patch('/projects/' + project['id'], json={'name': 'Packaged QA edited'}).raise_for_status().json()
        assert edited['name'] == 'Packaged QA edited'
        memory = client.post('/memories', json={'title': 'Packaged QA', 'content': 'isolated temporary note'}).raise_for_status().json()
        assert any(n['id'] == memory['id'] for n in client.get('/memories').raise_for_status().json())
        client.delete('/memories/' + memory['id']).raise_for_status()
        assert client.get('/memories').raise_for_status().json() == []
        report['checks'].append('project create/edit and memory create/read/delete on isolated DB')
    report['passed'] = True
finally:
    try:
        descendants = psutil.Process(proc.pid).children(recursive=True)
        for child in reversed(descendants):
            try:
                child.terminate()
            except psutil.NoSuchProcess:
                pass
    except psutil.NoSuchProcess:
        descendants = []
    if proc.poll() is None:
        proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=10)
    for child in descendants:
        try:
            child.wait(timeout=3)
        except psutil.TimeoutExpired:
            child.kill()
        except psutil.NoSuchProcess:
            pass
    log.close()
(root / 'docs/knowledge/project-memory-packaged-check.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report, indent=2))
