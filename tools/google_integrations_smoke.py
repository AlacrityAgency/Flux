"""Explicit live NotebookLM check using a dedicated synthetic notebook only."""
import argparse
import asyncio
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from flux.local_agents.runtime import ChatSpec, LocalRuntime, TurnSpec
from flux.storage.database import init_db
from flux.storage.repository import Repository
from flux.storage.workspace import Workspace, now


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--live', action='store_true', required=True)
    parser.add_argument('--notebook', required=True, help='Dedicated synthetic test notebook ID')
    args = parser.parse_args()
    report = {'timestamp': now(), 'notebook_id': args.notebook, 'synthetic_sources_only': True, 'turns': []}
    with tempfile.TemporaryDirectory(prefix='flux-google-check-') as folder:
        repo = Repository(init_db(str(Path(folder) / 'test.db')))
        runtime = LocalRuntime(repo, Workspace(repo), timeout=180)
        try:
            status = await runtime.status(refresh=True)
            report['connections'] = [{k:p.get(k) for k in ('id','version','authenticated','integration','error_code','detail')}
                                     for p in status['providers']]
            chat = runtime.create_chat(ChatSpec(provider='notebooklm', notebook_id=args.notebook, cwd=folder))
            prompts = [
                'از سند Flux integration sample، نشانگر آزمایش و نام سه مرحله را به ترتیب بگو.',
                'در پاسخ قبلی سه مرحله گفتی. نام انگلیسی مرحلهٔ دوم چه بود؟ به منبع ارجاع بده.',
            ]
            for index, prompt in enumerate(prompts):
                turn = runtime.submit(chat['id'], TurnSpec(prompt=prompt, request_key=f'google-check-{index}', use_memory=False))
                await runtime.jobs[turn['id']]
                result = runtime.turn(turn['id'])
                session = runtime.chat(chat['id'])['session_id']
                report['turns'].append({'state':result['state'], 'text':result['text'], 'error':result['error'],
                                       'references':result['usage'].get('references',[]), 'session_id':session})
                print(json.dumps({'turn':index+1,'state':result['state'],'reference_count':len(result['usage'].get('references',[])),
                                  'session_saved':bool(session)}, ensure_ascii=False), flush=True)
                if result['state'] != 'completed':
                    break
            turns = report['turns']
            report['passed'] = (len(turns)==2 and all(t['state']=='completed' and t['references'] for t in turns)
                                and bool(turns[0]['session_id']) and turns[0]['session_id']==turns[1]['session_id']
                                and 'FLUX_GOOGLE_BRIDGE_20261001' in turns[0]['text'] and 'Verify' in turns[1]['text'])
        finally:
            await runtime.close()
            repo.conn.close()
    output = Path(__file__).resolve().parents[1] / 'docs/google-integrations-live-check.json'
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    if not report['passed']:
        raise SystemExit(1)


if __name__=='__main__':
    asyncio.run(main())
