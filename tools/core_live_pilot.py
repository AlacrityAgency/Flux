"""Explicit two-call read-only HEAD pilot, with real pytest evidence; no human acceptance."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
import tempfile
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from httpx import AsyncClient,ASGITransport
from flux.api.app import create_app
from flux.engine.orchestrator import FluxEngine
from flux.providers.fake import FakeProvider
from flux.storage.database import init_db
from flux.storage.repository import Repository


async def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live',action='store_true',required=True)
    parser.add_argument('--provider',choices=['codex','claude'],default='codex')
    args=parser.parse_args()
    os.environ['PYTHONPATH']=str(ROOT/'src')+os.pathsep+os.environ.get('PYTHONPATH','')
    folder=Path(tempfile.mkdtemp(prefix='flux-head-live-pilot-'))
    (folder/'architecture.md').write_text('Flux local HEAD freezes a contract, generates a read-only artifact, checks exact criterion IDs with version-bound evidence, then waits for human acceptance. Memory proposals are excluded until human verification. API money and subscription quotas are separate.\n',encoding='utf-8')
    (folder/'test_retrieval.py').write_text('''from flux.knowledge.retrieval import build_pack
def test_tombstone_does_not_resurrect_old_memory():
    records=[dict(ref='m',revision=1,status='verified',title='architecture',content='old architecture'),dict(ref='m',revision=2,status='deleted',title='architecture',content='')]
    assert build_pack('architecture',[],records)['evidence']==[]
''',encoding='utf-8')
    repo=Repository(init_db(str(folder/'pilot.db')))
    app=create_app(engine=FluxEngine(repo,FakeProvider()))
    runtime=app.state.local_runtime;runtime.timeout=180
    project=app.state.workspace.create_project('HEAD live pilot',str(folder))
    report={'timestamp':datetime.now(timezone.utc).isoformat(),'provider':args.provider,'project_folder':str(folder),
            'database':str(folder/'pilot.db'),'human_acceptance_recorded':False,'calls':[],'source_project_modified_by_cli':False}
    async with AsyncClient(transport=ASGITransport(app),base_url='http://test') as client:
        response=await client.post('/api/core/tasks',json={'project_id':project['id'],'request_key':'live-pilot',
            'objective':'Write a concise Persian technical note accurately describing the sequence in architecture.md and explaining the deletion regression in test_retrieval.py. Do not modify files or run commands. Flux itself will run the authorized test after generation.',
            'acceptance_criteria':[{'criterion_id':'C1','text':'The note accurately describes frozen contracts, exact criterion evidence and final human acceptance.','evidence_type':'source_document'},
                                   {'criterion_id':'C2','text':'The authorized deletion regression test actually passes.','evidence_type':'test_execution'}],
            'allowed_tools':['read_workspace','pytest'],'allowed_paths':['architecture.md','test_retrieval.py'],
            'limits':{'max_calls':2,'max_active_seconds':360}})
        response.raise_for_status();task=response.json();base='/api/core/tasks/'+task['id']
        for phase in ['generation','review']:
            if phase=='review':
                checks=await client.post(base+'/checks/pytest',json={'paths':['test_retrieval.py']})
                checks.raise_for_status();report['pytest']=checks.json()
                if not report['pytest']['passed']:break
            dispatched=await client.post(base+'/execute',json={'operation_key':'live-'+phase,'phase':phase,'provider':args.provider})
            dispatched.raise_for_status()
            await asyncio.gather(*runtime.jobs.values())
            task=(await client.get(base)).json()
            operation=task['operations'][-1]
            turn=runtime.turn(operation['turn_id'])
            report['calls'].append({'phase':phase,'state':turn['state'],'usage':turn['usage'],'error':turn['error'],'text':turn['text']})
            print(json.dumps({'phase':phase,'task_state':task['state'],'turn_state':turn['state']},ensure_ascii=False),flush=True)
            if turn['state']!='completed':break
        report['task']=task
    await runtime.close();repo.conn.close()
    output=ROOT/'docs/knowledge/core-live-pilot.json'
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'report':str(output),'state':task['state'],'real_cli_calls':len(report['calls']),'human_acceptance_recorded':False},ensure_ascii=False))
    if task['state']!='ACCEPT_CANDIDATE':raise SystemExit(1)


if __name__=='__main__':asyncio.run(main())
