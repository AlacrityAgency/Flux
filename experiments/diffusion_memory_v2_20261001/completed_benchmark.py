"""Repair diagnostic plus fresh-seed confirmation. No post-result weight tuning."""
import json
from pathlib import Path
from time import perf_counter
from completed_graph import CompletedMemoryGraph, CompletedRetriever
from graph_memory import Record, dumps, sha
from benchmark import HERE, read_frozen, run, NEW_REAL
from build_data import synthetic, save_corpus
from evaluate import grade,summarize,flat_retrieve,expand_hop
from memory import Lexical,GraphRetriever,compact


def evaluate(corpus):
    m=CompletedMemoryGraph([Record(a) for a in corpus['atoms']]); levels={}; retrievers={}
    d=HERE/'completed_snapshots'/corpus['name']; d.mkdir(parents=True,exist_ok=True)
    for cap in [100000,30000,10000]:
        g=m.compress(cap); (d/f'graph_{cap}.json').write_text(g['rendered'],encoding='utf-8')
        levels[str(cap)]={'graph_tokens':g['tokens'],'retained_atoms':len(g['atoms']),
                         'mini_blocks':len(g['payload']['mini_blocks']),'hash':g['hash']}
        retrievers[cap]=CompletedRetriever(m,g)
    r=retrievers[100000]; idx=Lexical([a.text for a in m.atoms])
    old=GraphRetriever(compact(m.atoms,corpus['blocks'],100000),m.atoms)
    arms={
      'flat_v1_full':lambda q,b,c:expand_hop(lambda q,b,c:flat_retrieve(m.atoms,idx,q,b,c),q,b,c),
      'graph_v1_full':lambda q,b,c:expand_hop(lambda q,b,c:old.retrieve(q,b,c,archive=True,adaptive=False),q,b,c),
      'flat_completed_values':lambda q,b,c:r.retrieve(q,b,c,mode='flat'),
      'graph_completed_values':lambda q,b,c:r.retrieve(q,b,c),
      'graph_completed_uniform':lambda q,b,c:r.retrieve(q,b,c,values=False),
      'graph_completed_no_shared':lambda q,b,c:r.retrieve(q,b,c,shared=False),
      'graph_completed_no_fallback':lambda q,b,c:r.retrieve(q,b,c,archive_fallback=False),
    }
    for cap in [30000,10000]:
        x=retrievers[cap];arms[f'graph_completed_{cap}']=lambda q,b,c,x=x:x.retrieve(q,b,c)
    rows={a:[] for a in arms}; diagnostics={a:[] for a in arms}
    for i,t in enumerate(corpus['tasks']):
        q=t['query']+' '+' '.join(t['criteria'])
        for a in (list(arms) if i%2 else list(reversed(arms))):
            p=arms[a](q,3000,t['criteria']);row=grade(p,t);row['used_fallback']=p.get('archive_relation_fallback',False)
            rows[a].append(row)
        if i%32==0:print(dumps({'phase':'completed_eval','corpus':corpus['name'],'task':i}),flush=True)
    (HERE/'evaluation_only'/f'{corpus["name"]}_completed_details.json').write_text(dumps(rows),encoding='utf-8')
    (HERE/'evaluation_only'/f'{corpus["name"]}_completed_tasks.json').write_text(dumps(corpus['tasks']),encoding='utf-8')
    return {'corpus':corpus['name'],'tasks':len(corpus['tasks']),'raw_tokens':corpus['raw_tokens'],
            'raw_hash':corpus['raw_hash'],'levels':levels,'summary':{a:summarize(v) for a,v in rows.items()},
            'fallback_tasks':{a:sum(x['used_fallback'] for x in v) for a,v in rows.items()}}


def main():
    start=perf_counter()
    plan={'phase':'invariant_repair_after_primary','fresh_confirmatory_seed':483917,'budget':3000,
          'repair':'Query-local source-backed mini-block fallback, revision hash, and counted relationship metadata.',
          'old_tasks_are_diagnostic':True,'independent_real_holdout':False,'weights_unchanged':True,
          'production_integration':False,'model_calls':0,
          'code_hashes':{p.name:sha(p.read_text(encoding='utf-8')) for p in HERE.glob('*.py')}}
    (HERE/'completed-plan.json').write_text(dumps(plan),encoding='utf-8')
    real=read_frozen('flux_real')
    real['tasks'] += [{'id':i,'query':q,'criteria':c,'needles':n,'kind':'new_source_anchor'} for i,q,c,n in NEW_REAL]
    fresh=synthetic(seed=483917);fresh['name']='synthetic_confirm_1m';fresh['raw_hash']=sha(fresh['raw'])
    save_corpus(fresh,HERE/'completed_snapshots'/fresh['name'])
    corpora=[read_frozen('synthetic_1m'),real,fresh]
    output={'results':[evaluate(c) for c in corpora],'model_calls':0,'production_integration':False,
            'retrieval_executions':sum(len(c['tasks'])*9 for c in corpora),'elapsed_seconds':perf_counter()-start}
    (HERE/'completed-results.json').write_text(dumps(output),encoding='utf-8')
    print(dumps({'phase':'completed_finished','runs':output['retrieval_executions'],'seconds':output['elapsed_seconds']}),flush=True)


if __name__=='__main__':main()
