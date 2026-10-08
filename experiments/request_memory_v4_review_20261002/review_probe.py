"""Independent review diagnostics. Does not edit v4/v3 or invoke providers."""
from pathlib import Path
import json
import sys
from time import perf_counter

HERE=Path(__file__).resolve().parent
V4=HERE.parent/'request_memory_v4_20261002'
V3=HERE.parent/'request_memory_v3_20261002'
sys.path.insert(0,str(V4))
import engine_v4 as e


def main():
    plan=json.loads((V4/'frozen-plan.json').read_text(encoding='utf-8'))
    hashes={n:e.sha((V4/n).read_text(encoding='utf-8')) for n in plan['code_hashes']}
    assert hashes==plan['code_hashes']
    cfg=e.Config(**plan['config'])
    ix=e.Index([e.Record(e.Atom('a','alpha01 owner: team03.','a',1,0)),
                e.Record(e.Atom('b','beta02 owner: team09.','b',1,0)),
                e.Record(e.Atom('c','alpha01 limit_ms: 250.','a',2,0))])
    pack=e.run(ix,'r','alpha01 owner',['owner'],cfg)
    specific=e.run(ix,'s','alpha01 limit_ms',['alpha01 limit_ms'],cfg)
    closed=e.run(ix,'closed','Compute 2+2',['Return numeric answer'],cfg)
    tiny=e.run(ix,'tiny','Compute 2+2',['Return numeric answer'],e.Config(budget=1))
    diagnostics={
        'wrong_entity_accepted':e.verify_answer(pack,{'owner':'team09'},['b']),
        'wrong_field_accepted':e.verify_answer(pack,{'limit_ms':'team03'},['a']),
        'numeric_substring_accepted':e.verify_answer(specific,{'limit_ms':25},['c']),
        'missing_fields_accepted':e.verify_answer(pack,{}),
        'correct_closed_answer_rejected':e.verify_answer(closed,{'answer':4}),
        'empty_pack_over_budget':{'tokens':tiny['tokens'],'budget':tiny['budget']},
    }
    try:e.Index([]);empty={'raises':False}
    except Exception as ex:empty={'raises':True,'type':type(ex).__name__,'message':str(ex)}
    diagnostics['empty_eligible_memory']=empty
    old=HERE.parent/'diffusion_memory_20261001/snapshots/flux_real'
    atoms=[e.Atom(**a) for a in json.loads((old/'atoms.json').read_text(encoding='utf-8'))]
    real=e.Index([e.Record(a) for a in atoms])
    questions=[('What is the default concurrency limit in this project?',['concurrency limit']),
               ('Who is the human owner of this project?',['human owner']),
               ('مالک انسانی پروژه چه کسی است؟',['مالک انسانی']),
               ('How does this project manage memory?',['project memory'])]
    diagnostics['project_queries_skipped']=[{'query':q,'criteria':c,'retrieve':(s:=e.make_spec('r',q,c,real)).retrieve,'reason':s.reason}
                                          for q,c in questions]
    data=json.loads((V4/'holdout-results.json').read_text(encoding='utf-8'))
    aggregated={}
    for arm in ('v3_fixed','v3_adaptive','v4'):
        rows=[r for sub in data['rows'].values() for r in sub[arm]]
        aggregated[arm]={'tasks':len(rows),'complete':sum(r['complete'] for r in rows),
                         'mean_tokens':sum(r['tokens'] for r in rows)/len(rows),
                         'mean_noise':sum(r['noise_tokens'] for r in rows)/len(rows)}
        assert len(rows)==data['pooled'][arm]['tasks']
        assert aggregated[arm]['complete']/len(rows)==data['pooled'][arm]['complete_rate']
        assert abs(aggregated[arm]['mean_tokens']-data['pooled'][arm]['mean_pack_tokens'])<1e-9
    same8=[r for k in ('v3_frozen_synthetic','v3_frozen_real') for r in data['rows'][k]['v4']]
    original=json.loads((V3/'results.json').read_text(encoding='utf-8'))
    before=[r for r in original['rows'] if r['arm']=='luna_v3_fixed' and r['family'] in ('private_knowledge','project_knowledge')]
    same8_comparison={'v3_actual_postcritic_mean_tokens':sum(r['pack_tokens'] for r in before)/8,
                      'v4_mean_tokens':sum(r['tokens'] for r in same8)/8,
                      'scope':'Same 8 queries; saved v4 rows versus actual v3 final packs; not a new output-quality benchmark'}
    same8_comparison['reduction']=1-same8_comparison['v4_mean_tokens']/same8_comparison['v3_actual_postcritic_mean_tokens']
    assert hashes=={n:e.sha((V4/n).read_text(encoding='utf-8')) for n in hashes}
    result={'model_calls':0,'v4_frozen_hashes_match':True,'v4_files_unchanged':True,
            'diagnostics':diagnostics,'saved_holdout_recomputed':aggregated,'original_v3_same8_comparison':same8_comparison,
            'existing_unit_tests':'7 passed in 1.82s; separate pytest invocation',
            'baseline_note':'benchmark_v4 uses the v3 pipeline without planner/critic, and encoder_v4 replaces v3 windowed embeddings with truncation at 512 tokens'}
    (HERE/'review-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
