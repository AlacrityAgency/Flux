"""Explicit tiny live Gemini test through the installed Flux API on a temporary DB."""
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
root=Path(__file__).resolve().parents[1]
exe=Path.home()/'AppData/Local/Programs/Flux/Flux.exe'
folder=Path(tempfile.mkdtemp(prefix='flux-packaged-gemini-'))
with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
env=dict(os.environ,FLUX_DB_PATH=str(folder/'probe.db'))
with (folder/'server.log').open('wb') as log:
    proc=subprocess.Popen([str(exe),'serve','--host','127.0.0.1','--port',str(port),'--no-browser'],cwd=folder,env=env,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        with httpx.Client(base_url=f'http://127.0.0.1:{port}',timeout=30) as client:
            until=time.monotonic()+90
            while True:
                try:client.get('/').raise_for_status();break
                except httpx.HTTPError:
                    if time.monotonic()>until:raise
                    time.sleep(.25)
            chat=client.post('/api/local/chats',json={'provider':'gemini-api','cwd':str(folder),'access':'read'}).raise_for_status().json()
            turn=client.post('/api/local/chats/'+chat['id']+'/turns',json={'prompt':'Reply exactly FLUX_PACKAGED_GEMINI_OK. No tools.','request_key':'packaged-gemini-one','use_memory':False}).raise_for_status().json()
            until=time.monotonic()+150
            while turn['state'] in {'queued','running'}:
                if time.monotonic()>until:raise RuntimeError('Live probe timeout.')
                time.sleep(.5);turn=client.get('/api/local/turns/'+turn['id']).raise_for_status().json()
            report={'exe_sha256':hashlib.sha256(exe.read_bytes()).hexdigest(),'provider':'gemini-api','user_database_access':False,
                'model_calls_requested':1,'state':turn['state'],'successful':turn['state']=='completed' and turn['text'].strip()=='FLUX_PACKAGED_GEMINI_OK',
                'response':turn['text'],'error':turn['error'],'usage':turn['usage'],'keys_returned':False}
            (root/'docs/knowledge/packaged-gemini-live-check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps(report,ensure_ascii=False))
    finally:
        try:
            parent=psutil.Process(proc.pid)
            for child in parent.children(recursive=True):child.kill()
            parent.kill()
        except psutil.Error:pass
        proc.wait(timeout=15)
