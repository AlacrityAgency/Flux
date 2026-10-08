"""Read-only provenance audit, separate from inference and answer grading."""
import json
from pathlib import Path
import benchmark as B


def main():
    B.verify()
    tasks={t['id']:t for t in B.load(B.HERE/'tasks.json')}
    oldqueries={t['query'] for t in B.load(B.E.BASE/'frozen-plan.json')['tasks']}
    assert not oldqueries.intersection(t['query'] for t in tasks.values()), 'Repeated old prompt'
    receipts={f.stem:B.load(f) for f in B.RUNS.glob('*.json')}
    assert len(receipts)<=B.MAX_CALLS
    for label,r in receipts.items():
        tid=label.split('__')[0];task=tasks[tid]
        if label.endswith('_graph'):
            expected=B.E.prompt(task['query']);model='gpt-6-luna'
        elif label.endswith('_A') or label.endswith('_B'):
            expected=B.E.V6.program_prompt(task['query'],label[-1]);model='gpt-6-luna'
        else:
            expected=B.E.V6.direct_prompt(task['query']);model='gpt-6.1-sol'
        assert r['prompt']==expected and r['prompt_sha256']==B.sha(expected)
        assert r['model_requested']==model
        done=[e for e in r['raw_events'] if e.get('type')=='turn.completed']
        if r['provider_completed']:
            assert done and r['exit_code']==0 and not r['timed_out']
            assert done[-1].get('usage',{})==r['usage']
        tools=[e for e in r['raw_events'] if e.get('item',{}).get('type') in ['command_execution','mcp_tool_call','web_search']]
        assert len(tools)==r['tool_events']==0
        for key in ['input_tokens','cached_input_tokens','output_tokens']:
            assert r['usage'].get(key,0)>=0
        assert r['visible_prompt_tokens']==len(B.ENC.encode(expected))
    used=set()
    for tid in tasks:
        t=B.load(B.HERE/'trials'/f'{tid}.json')
        for arm,r in t['results'].items():
            assert all(x in receipts and x.startswith(tid+'__') for x in r['labels'])
            assert len(r['labels'])==({'v6':3 if r['sol'] else 2,'v6.1':2 if r['sol'] else 1,'sol_direct':1,'luna_B_shared':1}[arm])
            used.update(r['labels'])
    assert used==set(receipts),'Unused physical receipt'
    print(json.dumps({'audit':'PASS','fresh_tasks':len(tasks),'receipt_count':len(receipts),
                      'verified_raw_usage':True,'verified_prompt_hashes':True,'unreferenced_receipts':0,
                      'frozen_integrity':True,'provider_completed':sum(r['provider_completed'] for r in receipts.values())}))


if __name__=='__main__': main()
