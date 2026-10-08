"""Audit saved evidence and generate delivery metrics; never calls a model."""
import csv
import json
import math
from pathlib import Path
from collections import Counter
from engine import HERE, OLD, dumps, sha, tokens


def main():
    result=json.loads((HERE/'results.json').read_text(encoding='utf-8'))
    offline=json.loads((HERE/'offline-results.json').read_text(encoding='utf-8'))
    plan=json.loads((HERE/'frozen-plan.json').read_text(encoding='utf-8'))
    checks={}
    checks['frozen_candidate_hashes_match']=all(sha((HERE/n).read_text(encoding='utf-8'))==h for n,h in plan['code_hashes'].items())
    rows=result['rows']; runs={p.stem:json.loads(p.read_text(encoding='utf-8')) for p in (HERE/'model_runs').glob('*.json')}
    checks['140_unique_answer_calls']=len(rows)==140 and len({(r['task'],r['arm']) for r in rows})==140
    checks['all_answer_calls_completed']=all(r['provider_completed'] for r in rows)
    checks['no_answer_tool_events']=all(r['grade']['tool_events']==0 for r in rows)
    checks['all_144_calls_completed_without_tools']=len(runs)==144 and all(r['provider_completed'] and r['tool_events']==0 for r in runs.values())
    checks['prompt_output_model_provenance']=all(
        (run:=runs[r['task']+'_'+r['arm']])['prompt_sha256']==r['prompt_hash']==sha((HERE/'artifacts'/f"{r['task']}_{r['arm']}_prompt.txt").read_text(encoding='utf-8'))
        and run['model_requested']==r['model'] and sha(run['text'])==r['output_hash'] for r in rows)
    checks['reasoning_effort_low']=all(r['reasoning_effort']=='low' for r in runs.values())
    checks['visible_prompt_tokens_recount']=all(tokens((HERE/'artifacts'/f"{r['task']}_{r['arm']}_prompt.txt").read_text(encoding='utf-8'))==r['visible_prompt_tokens'] for r in rows)
    checks['evidence_and_visible_prompt_caps']=max(r['pack_tokens'] for r in rows)<=3000 and max(r['visible_prompt_tokens'] for r in rows)<=16000
    checks['all_84_code_cases_passed']=sum(len(r['grade']['test_details']['passed']) for r in rows if r['family']=='executable_code')==84 and all(all(r['grade']['test_details']['passed']) for r in rows if r['family']=='executable_code')
    checks['synthetic_raw_exact_1m']=tokens((HERE/'snapshots/synthetic_fresh_1m/raw.txt').read_text(encoding='utf-8'))==1000000
    archive_sizes={};pack_sizes={};post_critic_sizes={}; archive_sources_intact=True; final_packs_intact=True
    for t in plan['tasks']:
        if not t['external_evidence']:continue
        ident=t['id'];archive=HERE/'artifacts'/f'{ident}_fixed_archive.json'
        raw=archive.read_text(encoding='utf-8'); archive_sizes[ident]=tokens(raw)
        trace=json.loads((HERE/'artifacts'/f'{ident}_fixed_trace.json').read_text(encoding='utf-8'))
        archive_sources_intact &= sha(raw)==trace['archive_hash'] and tokens(raw)==trace['archive_tokens']
        folder=HERE/'snapshots/synthetic_fresh_1m' if t['corpus']=='synthetic' else OLD/'snapshots/flux_real'
        chunks=json.loads((folder/'chunks.json').read_text(encoding='utf-8'))
        source_text={c['source']:c['text'] for c in chunks}
        # Real chunks share a source; concatenate in line order for whole excerpt checks.
        source_text={s:'\n'.join(c['text'] for c in sorted(chunks,key=lambda c:c['line']) if c['source']==s) for s in source_text}
        archive_sources_intact &= all(record['text'] in source_text[record['source']] for record in json.loads(raw)['records'])
        packraw=(HERE/'artifacts'/f'{ident}_fixed_pack.json').read_text(encoding='utf-8')
        patch=json.loads((HERE/'artifacts'/f'{ident}_critic_patch.json').read_text(encoding='utf-8'))
        pack_sizes[ident]=tokens(packraw)
        final_packs_intact &= sha(packraw)==patch['pack_hash'] and tokens(packraw)<=3000
        final_packs_intact &= all(x['text'] in source_text[x['source']] for x in json.loads(packraw)['evidence'])
        final_packs_intact &= all(r['pack_tokens']==tokens(packraw) for r in rows if r['task']==ident and r['arm'] in ('luna_v3_fixed','sol_v3_fixed'))
        accepted=[x for x in patch['trace'] if x['accepted']]
        post_critic_sizes[ident]=accepted[-1]['after_tokens'] if accepted else patch['trace'][0]['before_tokens']
    checks['archive_hashes_counts_source_text_intact']=bool(archive_sources_intact)
    checks['actual_postcritic_pack_hashes_counts_sources_intact']=bool(final_packs_intact)
    checks['external_synthetic_archives_exact_1m']=all(archive_sizes[t['id']]==1000000 for t in plan['tasks'] if t['family']=='private_knowledge')
    checks['real_archives_honestly_underfilled']=archive_sizes['F00']==archive_sizes['F01']==281610
    checks['graph_caps']=all(t['initial_graph_tokens']<=100000 and t['graph_tokens']<=100000 for t in result['traces']) and all(x<=100000 for x in post_critic_sizes.values())
    usage={k:sum(r['usage'].get(k,0) for r in runs.values()) for k in ['input_tokens','cached_input_tokens','output_tokens','reasoning_output_tokens']}
    metrics=[]
    for arm,s in result['summary'].items():
        closed=[r for r in rows if r['arm']==arm and r['family'] in ('closed_reasoning','executable_code')]
        ext=[r for r in rows if r['arm']==arm and r['family'] in ('private_knowledge','project_knowledge')]
        metrics.append({'arm':arm,'passed':s['passed'],'tasks':20,'closed_passed':sum(r['grade']['passed'] for r in closed),'closed_tasks':12,
                        'knowledge_passed':sum(r['grade']['passed'] for r in ext),'knowledge_tasks':8,
                        'mean_generation_seconds':s['mean_seconds'],'input_tokens':s['input_tokens'],
                        'mean_external_pack_tokens':sum(r['pack_tokens'] for r in ext)/8})
    saving=1-offline['summary']['full']['mean_pack_tokens']/offline['summary']['no_pruning']['mean_pack_tokens']
    audit={'checks':checks,'all_checks_passed':all(checks.values()),'calls':len(runs),'model_counts':dict(Counter(r['model_requested'] for r in runs.values())),
           'all_calls_usage':usage,'max_pack_tokens':max(r['pack_tokens'] for r in rows),'max_visible_prompt_tokens':max(r['visible_prompt_tokens'] for r in rows),
           'fixed_external_archive_tokens':archive_sizes,'actual_fixed_external_pack_tokens':pack_sizes,'postcritic_graph_tokens':post_critic_sizes,
           'offline_pruning_pack_reduction':saving,'metrics':metrics,'billing_usd':None,
           'limitations':['one completion per arm per task','provider scaffolding outside local evidence cap','source probes do not prove semantic sufficiency','critic graph snapshots are precritic; patch is authoritative']}
    (HERE/'verification.json').write_text(dumps(audit),encoding='utf-8')
    with (HERE/'metrics.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(metrics[0]));w.writeheader();w.writerows(metrics)
    print(json.dumps(audit,ensure_ascii=False,indent=2))
    assert audit['all_checks_passed'],checks


if __name__=='__main__':main()
