"""Explicit live calls to a separately launched packaged Flux QA server."""
import argparse
import json
from pathlib import Path
import time
import uuid
from datetime import datetime, timezone

import httpx

parser=argparse.ArgumentParser()
parser.add_argument('--live', action='store_true', required=True)
parser.add_argument('--notebook', required=True, help='Dedicated synthetic notebook ID')
parser.add_argument('--url', default='http://127.0.0.1:8058')
args=parser.parse_args()
report={'timestamp':datetime.now(timezone.utc).isoformat(),'packaged':True,'synthetic_sources_only':True,'turns':[]}
with httpx.Client(base_url=args.url, timeout=90) as client:
    status=client.get('/api/local/status').raise_for_status().json()
    report['connections']=[{k:p.get(k) for k in ('id','version','authenticated','integration','error_code')} for p in status['providers']]
    chat=client.post('/api/local/chats',json={'provider':'notebooklm','cwd':status['default_cwd'],'notebook_id':args.notebook}).raise_for_status().json()
    for index,prompt in enumerate(['نشانگر آزمایش و سه مرحلهٔ سند Flux integration sample را بگو.', 'نام انگلیسی مرحلهٔ دوم همان سه مرحله چیست؟']):
        turn=client.post('/api/local/chats/'+chat['id']+'/turns',json={'prompt':prompt,'request_key':'packaged-google-'+str(uuid.uuid4()),'use_memory':False}).raise_for_status().json()
        deadline=time.monotonic()+180
        while time.monotonic()<deadline:
            turn=client.get('/api/local/turns/'+turn['id']).raise_for_status().json()
            if turn['state'] not in ('queued','running'):
                break
            time.sleep(.5)
        current=client.get('/api/local/chats/'+chat['id']).raise_for_status().json()
        report['turns'].append({'state':turn['state'],'text':turn['text'],'error':turn['error'],'references':turn['usage'].get('references',[]),'session_id':current['session_id']})
        print(json.dumps({'turn':index+1,'state':turn['state'],'reference_count':len(turn['usage'].get('references',[]))}),flush=True)
        if turn['state']!='completed':
            break
turns=report['turns']
report['passed']=(len(turns)==2 and all(t['state']=='completed' and t['references'] for t in turns)
                  and bool(turns[0]['session_id']) and turns[0]['session_id']==turns[1]['session_id']
                  and 'FLUX_GOOGLE_BRIDGE_20261001' in turns[0]['text'] and 'Verify' in turns[1]['text'])
Path('docs/google-integrations-packaged-check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
if not report['passed']:
    raise SystemExit(1)
