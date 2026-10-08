"""Frozen offline evaluation. Gold is consumed ONLY by the evaluator, never graphs."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import platform
import shutil
import sys
from time import perf_counter
import numpy as np
from build_data import HERE, ROOT, real_sources, save_corpus, synthetic
from memory import Atom, GraphRetriever, Lexical, compact, dumps, envelope, pack, sha, tokens

CAPS=[100000,30000,10000,3000]
BUDGETS=[1500,3000]


def flat_retrieve(atoms,index,query,budget,criteria,adaptive=False):
    start=perf_counter();result=pack(atoms,index.score(query),budget,adaptive,criteria)
    result.update(latency_ms=(perf_counter()-start)*1000,external_atom_tokens_scanned=0,model_calls=0)
    return result


def expand_hop(fetch,query,budget,criteria):
    """Shared rule for BOTH flat and graph, based only on retrieved evidence."""
    result=fetch(query,budget,criteria)
    if 'dependency' not in query.lower():return result
    import re
    matches=[]
    for item in result['items']:
        matches.extend(re.findall(r'(svc\d{5}) depends_on: (svc\d{5})',item['text']))
    if not matches:return result
    starting=re.search(r'svc\d{5}',query)
    exact=[m for m in matches if starting and m[0]==starting.group()]
    if not exact:return result
    source,target=exact[0]
    second=fetch(f'{target} owner',budget,[f'{target} owner'])
    items=[];seen=set()
    # Pin the explicit relationship and fetched target-owner only; no gold/oracle.
    for p in [result,second]:
        for item in p['items']:
            if item['id'] in seen:continue
            text=item['text']
            if f'{source} depends_on:' in text or f'{target} owner:' in text:
                if tokens(envelope(items+[item]))<=budget:items.append(item);seen.add(item['id'])
    rendered=envelope(items)
    return {'items':items,'ids':[x['id'] for x in items],'rendered':rendered,'tokens':tokens(rendered),
            'budget':budget,'pack_hash':sha(rendered),'latency_ms':result['latency_ms']+second['latency_ms'],
            'external_atom_tokens_scanned':result.get('external_atom_tokens_scanned',0)+second.get('external_atom_tokens_scanned',0),
            'model_calls':0,'semantic_sufficiency':'unverified'}


def grade(result,task):
    # Exact known facts/anchors, never LLM answer scores or task acceptance.
    text='\n'.join(x['text'] for x in result['items'])
    hits=[n in text for n in task['needles']]
    return {'hits':sum(hits),'needs':len(hits),'complete':all(hits),
            'tokens':result['tokens'],'latency_ms':result['latency_ms'],
            'external_atom_tokens_scanned':result.get('external_atom_tokens_scanned',0),
            'pack_hash':result['pack_hash'],'budget_violation':result['tokens']>result['budget'],
            'task_id':task['id'],'kind':task['kind'],'matched_needles':hits}


def summarize(rows):
    hits=sum(x['hits'] for x in rows);needs=sum(x['needs'] for x in rows)
    complete=sum(x['complete'] for x in rows)
    return {'tasks':len(rows),'hits':hits,'needs':needs,'evidence_recall':hits/needs,
            'complete_tasks':complete,'complete_rate':complete/len(rows),
            'mean_pack_tokens':float(np.mean([x['tokens'] for x in rows])),
            'median_ms':float(np.median([x['latency_ms'] for x in rows])),
            'p95_ms':float(np.percentile([x['latency_ms'] for x in rows],95)),
            'mean_external_atom_tokens_scanned':float(np.mean([x['external_atom_tokens_scanned'] for x in rows])),
            'budget_violations':sum(x['budget_violation'] for x in rows)}


def bootstrap_pair(rows_a,rows_b,seed=4501):
    # Paired task bootstrap, stratified task families are additionally reported.
    rng=np.random.default_rng(seed);a=np.array([x['complete'] for x in rows_a],dtype=float)
    b=np.array([x['complete'] for x in rows_b],dtype=float)
    ids=rng.integers(0,len(a),size=(3000,len(a)))
    vals=(a[ids]-b[ids]).mean(axis=1)
    return {'complete_rate_delta':float((a-b).mean()),'ci95':np.quantile(vals,[.025,.975]).tolist(),
            'limits':'Task bootstrap for deterministic, controlled corpus; not general answer quality.'}


def current_flux(corpus,budget):
    # Freeze and import ONLY the pure selector. Never initialize Workspace/API/DB.
    baseline=HERE/'frozen_flux_retrieval.py'
    if not baseline.exists():shutil.copyfile(ROOT/'src/flux/knowledge/retrieval.py',baseline)
    spec=importlib.util.spec_from_file_location('frozen_flux_selector',baseline)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    records=[]
    # Mirror SourceIndex 4000-character, complete-line chunking from frozen files.
    for f in corpus['files']:
        content=(HERE/'snapshots/flux_real/sources'/f['path']).read_text(encoding='utf-8')
        current=[];start=1
        for no,line in enumerate(content.splitlines(keepends=True),1):
            if current and sum(map(len,current))+len(line)>4000:
                txt=''.join(current);ref=f'{f["path"]}:{start}'
                records.append({'ref':ref,'title':ref,'revision':1,'content':txt,
                                'content_hash':sha(txt),'source_ref':f['path'],'evidence_type':'code','status':'verified'})
                current=[];start=no
            current.append(line)
        if current:
            txt=''.join(current);ref=f'{f["path"]}:{start}'
            records.append({'ref':ref,'title':ref,'revision':1,'content':txt,
                            'content_hash':sha(txt),'source_ref':f['path'],'evidence_type':'code','status':'verified'})
    rows=[]
    for task in corpus['tasks']:
        t=perf_counter();p=module.build_pack(task['query'],task['criteria'],records,budget)
        result={'items':[{'text':e['content']} for e in p['evidence']], 'tokens':p['tokens'],'budget':budget,
                'pack_hash':p['pack_hash'],'latency_ms':(perf_counter()-t)*1000}
        rows.append(grade(result,task))
    return rows


def run(corpus):
    directory=HERE/'snapshots'/corpus['name'];save_corpus(corpus,directory)
    if corpus['name']=='flux_real':
        for f in corpus['files']:
            p=directory/'sources'/f['path'];p.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(ROOT/f['path'],p)
            if sha(p.read_text(encoding='utf-8'))!=f['sha256']:raise RuntimeError('Source drift while freezing')
    gold_dir=HERE/'evaluation_only';gold_dir.mkdir(exist_ok=True)
    (gold_dir/f'{corpus["name"]}_tasks.json').write_text(dumps(corpus['tasks']),encoding='utf-8')
    levels={};graphs={};prior=None
    for cap in CAPS:
        level=compact(corpus['atoms'],corpus['blocks'],cap,prior)
        levels[cap]=level;graphs[cap]=GraphRetriever(level,corpus['atoms']);prior=level
        (directory/f'graph_{cap}.json').write_text(level['rendered'],encoding='utf-8')
        print(dumps({'phase':'compressed','corpus':corpus['name'],'cap':cap,'actual_graph_tokens':level['tokens'],
                     'retained_atoms':len(level['atoms']),'build_ms':round(level['build_ms'],2)}),flush=True)
    atom_index=Lexical([a.text for a in corpus['atoms']]);chunk_index=Lexical([a.text for a in corpus['chunks']])
    arms={
      'flat_chunks':lambda q,b,c:flat_retrieve(corpus['chunks'],chunk_index,q,b,c),
      'flat_atoms':lambda q,b,c:flat_retrieve(corpus['atoms'],atom_index,q,b,c),
      'flat_atoms_adaptive':lambda q,b,c:flat_retrieve(corpus['atoms'],atom_index,q,b,c,True),
      'flat_atoms_expand':lambda q,b,c:expand_hop(lambda q,b,c:flat_retrieve(corpus['atoms'],atom_index,q,b,c,True),q,b,c),
    }
    for cap in CAPS:
        g=graphs[cap]
        arms[f'graph_only_{cap}']=lambda q,b,c,g=g:g.retrieve(q,b,c)
        arms[f'graph_archive_{cap}']=lambda q,b,c,g=g:expand_hop(lambda q,b,c:g.retrieve(q,b,c,archive=True,adaptive=True),q,b,c)
    g=graphs[100000]
    arms['graph_archive_no_diffusion']=lambda q,b,c:expand_hop(lambda q,b,c:g.retrieve(q,b,c,archive=True,diffusion=False,adaptive=True),q,b,c)
    details={};summary={};comparisons={}
    # Reverse arm order on alternate queries to limit warm-order latency artifacts.
    for budget in BUDGETS:
        details[str(budget)]={name:[] for name in arms}
        for no,task in enumerate(corpus['tasks']):
            q=task['query']+' '+' '.join(task['criteria'])
            order=list(arms);order=order if no%2 else list(reversed(order))
            for name in order:
                result=arms[name](q,budget,task['criteria'])
                details[str(budget)][name].append(grade(result,task))
            if no%24==0:print(dumps({'phase':'eval','corpus':corpus['name'],'budget':budget,'task':no}),flush=True)
        # Restore task ordering for paired comparisons regardless arm execution order.
        for name in arms:details[str(budget)][name].sort(key=lambda r:r['task_id'])
        if corpus['name']=='flux_real':
            rows=current_flux(corpus,budget);rows.sort(key=lambda r:r['task_id'])
            details[str(budget)]['flux_current_selector']=rows
        summary[str(budget)]={name:summarize(rows) for name,rows in details[str(budget)].items()}
        comparisons[str(budget)]={name:bootstrap_pair(rows,details[str(budget)]['flat_atoms_expand'])
                                  for name,rows in details[str(budget)].items() if name!='flat_atoms_expand'}
    level_metrics={str(cap):{'cap':cap,'graph_tokens':x['tokens'],'retained_atoms':len(x['atoms']),
                     'raw_atoms':len(corpus['atoms']),'retention_fraction':len(x['atoms'])/len(corpus['atoms']),
                     'graph_hash':x['hash'],'build_ms':x['build_ms'],
                     'all_extracted_facts_retained':len(x['atoms'])==len(corpus['atoms'])} for cap,x in levels.items()}
    total_storage={'raw_tokens':corpus['raw_tokens'],
        'external_atoms_json_tokens':tokens(dumps([a.public() for a in corpus['atoms']])),
        'active_graph_100k_tokens':levels[100000]['tokens'],
        'graph_levels_sum_tokens':sum(x['tokens'] for x in levels.values()),
        'index_memory_bytes':int(atom_index.bm25.data.nbytes+atom_index.bm25.indices.nbytes+atom_index.bm25.indptr.nbytes+atom_index.tfidf.data.nbytes),
        'limits':'Illustrative components, not total process RSS; raw archive and extraction index are retained.'}
    result={'corpus':corpus['name'],'raw_tokens':corpus['raw_tokens'],'raw_sha256':sha(corpus['raw']),
            'levels':level_metrics,'summary':summary,'comparisons':comparisons,'storage':total_storage,
            'tasks':len(corpus['tasks']),'model_calls':0,'answer_quality_measured':False,
            'decision_action_accuracy_measured':False,'limits':corpus['limits']}
    (directory/'results.json').write_text(dumps(result),encoding='utf-8')
    (gold_dir/f'{corpus["name"]}_details.json').write_text(dumps(details),encoding='utf-8')
    return result


def main():
    plan={'caps':CAPS,'query_budgets':BUDGETS,'synthetic_seed':6417,'synthetic_tokens':1000000,
          'real_corpus':'allowlisted deduplicated src/tests/docs, no credentials, databases or knowledge snapshots',
          'mode':'extractive offline','no_model_calls':True,'metrics':['anchor_recall','complete_evidence','pack_tokens','query_ms'],
          'gold_is_external':True,'integration':False}
    (HERE/'frozen-plan.json').write_text(dumps(plan),encoding='utf-8')
    for name in ['memory.py','build_data.py','evaluate.py','test_memory.py']:
        plan.setdefault('candidate_hashes',{})[name]=sha((HERE/name).read_text(encoding='utf-8'))
    plan['baseline_selector_hash']=sha((ROOT/'src/flux/knowledge/retrieval.py').read_text(encoding='utf-8'))
    (HERE/'frozen-plan.json').write_text(dumps(plan),encoding='utf-8')
    results=[];start=perf_counter()
    for corpus in [synthetic(),real_sources()]:
        print(dumps({'phase':'start','corpus':corpus['name'],'tokens':corpus['raw_tokens'],'tasks':len(corpus['tasks'])}),flush=True)
        results.append(run(corpus))
    report={'results':results,'elapsed_seconds':perf_counter()-start,'python':sys.version,'platform':platform.platform(),
            'model_calls':0,'integration':False,'gold_scope':'Exact facts/anchors, not general semantic correctness'}
    (HERE/'results.json').write_text(dumps(report),encoding='utf-8')
    print(dumps({'phase':'finished','seconds':report['elapsed_seconds']}),flush=True)


if __name__=='__main__':main()
