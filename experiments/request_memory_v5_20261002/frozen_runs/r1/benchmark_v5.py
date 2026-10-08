"""Offline paired retrieval/checker experiment, freeze-before-holdout, no LLM calls.

Usage: python benchmark_v5.py dev | freeze | holdout
Old v4 holdout is regression evidence, not this experiment's new holdout.
"""
from dataclasses import asdict
import hashlib
import importlib.metadata
import json
from pathlib import Path
import random
import sys
from time import perf_counter
import numpy as np
from contracts import Source, Need, Request, Policy, ENC, dumps, digest
from memory_v5 import Snapshot
from engine_v5 import normalize_request, retrieve, route
from verifier_v5 import verify

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
BASELINE = EXP / 'request_memory_v4_20261002'
sys.path.insert(0, str(BASELINE))
import engine_v4 as v4

POLICY = Policy(optional_units=1)
BASE_CONFIG = v4.Config(**json.loads((BASELINE/'frozen-plan.json').read_text(encoding='utf-8'))['config'])

def dataset(seed, prefix, background=11000):
    rng = random.Random(seed)
    sources, cases, aliases = [], [], {}
    def source(name, text, schema=None, **kwargs):
        sources.append(Source(prefix + '/' + name, text, role='canonical', schema=schema or {}, **kwargs))
    def case(family, i, request, expected, output=None, evidence=()):
        cases.append({'family':family,'request':asdict(request),'expected_status':expected,
                      'gold_output':output,'gold_evidence_texts':list(evidence)})
    for i in range(40):
        entity = prefix + '_asset_' + str(rng.randrange(100000,999999))
        field = ('owner_tag','limit','modes','delay')[i%4]
        values = ('group_' + str(rng.randrange(100,999)), 250+i*100,
                  ['enabled_'+str(i),'disabled_'+str(i)], {'amount':250+i,'unit':'ms'})
        kinds = ('string','integer','literal_set','quantity')
        value,kind=values[i%4],kinds[i%4]
        text=entity+' '+field+': '+dumps(value)
        source('fact'+str(i),text,{field:kind})
        r=Request(prefix+'-f'+str(i),'Return '+entity+' '+field,needs=(Need('n',entity,field,value_type=kind),),task_kind='factual')
        case('exact_fact',i,r,'verified',{'value':value},[text])
    for i in range(40):
        field=prefix+'_setting_'+str(i)
        phrases=['human owner','concurrency limit','retention period','retry threshold','memory mode']
        phrase=phrases[i%5]+' for region '+str(i)
        aliases[phrase]=field
        value='setting_value_'+str(rng.randrange(100000,999999))
        text='workspace '+field+': '+dumps(value)
        source('natural'+str(i),text,{field:'string'})
        query=('در پروژه '+phrase+' چیست؟') if i%2 else ('What is the '+phrase+' in this project?')
        r=Request(prefix+'-q'+str(i),query,task_kind='factual')
        case('natural_alias',i,r,'verified',{'value':value},[text])
    for i in range(40):
        entity=prefix+'_node_'+str(i)
        if i<20:
            target=prefix+'_target_'+str(i);value='team_'+str(i)
            a=entity+' upstream: '+dumps(target);b=target+' owner: '+dumps(value)
            source('relation'+str(i),a+'\n'+b,{'upstream':'entity_ref','owner':'string'})
            r=Request(prefix+'-h'+str(i),'Who owns the upstream of '+entity+'?',needs=(Need('n',entity,'owner',via_field='upstream'),),task_kind='factual')
            case('relation_identity',i,r,'verified',{'value':value},[a,b])
        else:
            for namespace in ('east','west'):
                source('amb'+str(i)+namespace,entity+' owner: '+dumps(namespace),{'owner':'string'},namespace=namespace)
            r=Request(prefix+'-h'+str(i),'Who owns '+entity+'?',needs=(Need('n',entity,'owner'),),task_kind='factual')
            case('relation_identity',i,r,'ambiguous')
    for i in range(40):
        entity=prefix+'_service_'+str(i);text=entity+' threshold: '+str(900+i)
        if i<10:
            source('revision'+str(i),entity+' threshold: 25',{'threshold':'integer'})
            source('revision'+str(i),text,{'threshold':'integer'},revision=2)
        elif i<20:
            source('revision'+str(i),text,{'threshold':'integer'})
            source('revision'+str(i),'',revision=2,status='deleted')
        elif i<30:
            source('revision'+str(i),text,{'threshold':'integer'})
            sources.append(Source(prefix+'/fixture'+str(i),entity+' threshold: 25',role='fixture',schema={'threshold':'integer'}))
        else:
            source('revision'+str(i),text,{'threshold':'integer'})
            sources.append(Source(prefix+'/foreign'+str(i),entity+' threshold: 25',project='foreign',role='canonical',schema={'threshold':'integer'}))
        r=Request(prefix+'-s'+str(i),'What is '+entity+' threshold?',needs=(Need('n',entity,'threshold',value_type='integer'),),task_kind='factual')
        case('freshness_scope',i,r,'missing' if 10<=i<20 else 'verified',{'value':900+i},[] if 10<=i<20 else [text])
    for i in range(40):
        a,b,c=rng.randrange(2,40),rng.randrange(2,15),rng.randrange(1,20)
        expr=f'({a}+{b})*{c}-{b}'
        r=Request(prefix+'-m'+str(i),'Compute '+expr,task_kind='math',expression=expr)
        case('closed_math',i,r,'verified',{'answer':(a+b)*c-b})
    for i in range(40):
        a,b=rng.randrange(2,30),rng.randrange(1,20)
        code=f'def solve(arg):\n    return arg*{a}+{b}'
        tests=({'input':2,'expected':2*a+b},{'input':-3,'expected':-3*a+b})
        if i<20:
            r=Request(prefix+'-c'+str(i),f'Implement a pure solve(arg) returning arg*{a}+{b}.',task_kind='code',public_tests=tests)
            evidence=[]
        else:
            name=prefix+'_compute_'+str(i)
            body=f'def {name}(arg):\n    if arg is None:\n        return 0\n    return arg*{a}+{b}\n'
            source('code'+str(i)+'.py',body,format='python',namespace='code')
            r=Request(prefix+'-c'+str(i),'Adapt '+name+' in this repository to pure solve(arg).',
                      needs=(Need('n',name,namespace='code',proof_kind='definition',value_type='string'),),
                      task_kind='code',public_tests=tests)
            evidence=[f'def {name}(arg):']
        case('code_public',i,r,'verified',{'code':code},evidence)
    # One archive source; full index is built once, not serialized per request.
    source('background','\n'.join(f'{prefix}_archive_{i} note: "unrelated memo {rng.randrange(1000000)}"' for i in range(background)),{'note':'string'})
    return {'seed':seed,'prefix':prefix,'sources':[asdict(s) for s in sources],
            'aliases':aliases,'cases':cases,'policy':asdict(POLICY),'baseline_config':asdict(BASE_CONFIG)}

def decode(raw):
    raw=dict(raw);raw['needs']=tuple(Need(**n) for n in raw['needs']);raw['public_tests']=tuple(raw['public_tests'])
    return Request(**raw)

def supplied_correct_output(request, pack, gold):
    # This is an evaluator-supplied fixture, NOT model generation, NOT passed to retrieval.
    output={key:value for key,value in (gold or {}).items() if key!='value'}
    claims=[]
    for need in request.needs:
        binding=pack.payload['bindings'].get(need.need_id)
        if not binding: continue
        value=(gold or {}).get('value')
        if need.proof_kind=='definition':
            unit=next(u for u in pack.payload['units'] if u['unit_id']==binding['evidence_refs'][0]);value=unit['text']
        claims.append({'need_id':need.need_id,'entity_ref':binding['entity'],'field_ref':binding['field'],
                       'namespace':binding['namespace'],'value_type':binding['value_type'],'proof_kind':binding['proof_kind'],
                       'value':value,'evidence_refs':binding['evidence_refs']})
    if request.needs: output['claims']=claims
    return output

def execute(data):
    start=perf_counter();snapshot=Snapshot([Source(**s) for s in data['sources']],aliases=data['aliases'])
    build_v5=(perf_counter()-start)*1000
    # Identical canonical evidence units provided to both retrieval engines. This grants
    # v4 v5's source gating/parser; canonicalization quality is tested separately.
    records=[v4.Record(v4.Atom(u.unit_id,u.text,u.source_id,u.line_start,0)) for u in snapshot.units]
    start=perf_counter();old=v4.Index(records);build_v4=(perf_counter()-start)*1000
    rows=[];rng=random.Random(77213)
    for item in data['cases']:
        request=normalize_request(decode(item['request']),snapshot)
        criteria=[n.entity+' '+n.field for n in request.needs] or [request.query]
        for _ in range(2):
            retrieve(snapshot,request,POLICY);v4.run(old,request.request_id,request.query,criteria,BASE_CONFIG)
        times={'v4':[],'v5':[]};packages={}
        for repeat in range(5):
            order=['v4','v5'];rng.shuffle(order)
            for arm in order:
                start=perf_counter()
                packages[arm]=v4.run(old,request.request_id,request.query,criteria,BASE_CONFIG) if arm=='v4' else retrieve(snapshot,request,POLICY)
                times[arm].append((perf_counter()-start)*1000)
        new,prev=packages['v5'],packages['v4']
        output=supplied_correct_output(request,new,item['gold_output'])
        receipt=verify(snapshot,request,new,output) if new.status=='ready' else None
        actual=receipt.status if receipt else new.status
        refs=item['gold_evidence_texts'];new_texts={u['text'] for u in new.payload.get('units',[])};old_texts={u['text'] for u in prev['items']}
        should_retrieve=bool(refs) or item['expected_status'] in ('ambiguous','missing')
        rows.append({'id':request.request_id,'family':item['family'],'expected_status':item['expected_status'],
                     'v5_status':actual,'checker_fixture_passed':actual==item['expected_status'],
                     'v4_evidence_complete':all(s in old_texts for s in refs) if refs else None,
                     'v5_evidence_complete':all(s in new_texts for s in refs) if refs else None,
                     'v4_route_correct':prev['spec'].retrieve==should_retrieve,
                     'v5_route_correct':(new.route!='self_contained')==should_retrieve,
                     'v4_tokens':prev['tokens'],'v5_tokens':new.token_count,
                     'v4_ms':float(np.median(times['v4'])),'v5_ms':float(np.median(times['v5'])),
                     'v5_count_passes':new.count_passes,'public_code_cases_run':len(request.public_tests) if receipt and request.public_tests else 0})
    def summary(subset):
        evidence=[r for r in subset if r['v5_evidence_complete'] is not None]
        return {'tasks':len(subset),'fixture_status_correct':sum(r['checker_fixture_passed'] for r in subset),
                'evidence_tasks':len(evidence),
                **{arm:{'evidence_complete':sum(r[arm+'_evidence_complete'] for r in evidence),
                        'route_correct':sum(r[arm+'_route_correct'] for r in subset),
                        'mean_tokens':float(np.mean([r[arm+'_tokens'] for r in subset])),
                        'median_ms':float(np.median([r[arm+'_ms'] for r in subset])),
                        'p95_ms':float(np.percentile([r[arm+'_ms'] for r in subset],95))} for arm in ('v4','v5')}}
    return {'actual_model_calls':0,'quality_measured':False,'index_units':len(snapshot.units),
            'build_ms':{'v4_on_v5_units':build_v4,'v5_full_snapshot':build_v5},
            'protocol':'paired lexical, canonical units shared, 2 warmups, 5 repeats random arm order; no embeddings',
            'checker_outputs':'correct evaluator fixtures, not LLM answers',
            'summary':summary(rows),'families':{f:summary([r for r in rows if r['family']==f]) for f in sorted({r['family'] for r in rows})},
            'public_code_cases_run':sum(r['public_code_cases_run'] for r in rows),'rows':rows}

def sha_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def protected_files():
    paths=[p for folder in ('request_memory_v3_20261002','request_memory_v4_20261002')
           for p in (EXP/folder).glob('*.py')]
    paths += [EXP/'diffusion_memory_20261001/memory.py',EXP/'diffusion_memory_v2_20261001/graph_memory.py',
              BASELINE/'frozen-plan.json']
    return sorted(paths)

def frozen_paths():
    return sorted(list(HERE.glob('*.py'))+[HERE/'holdout-data.json',HERE/'dev-data.json']+protected_files())

def main():
    command=sys.argv[1]
    if command=='dev':
        if (HERE/'frozen-manifest.json').exists(): raise RuntimeError('Already frozen: dev refuses mutation')
        data=dataset(602115,'dev',1000)
        (HERE/'dev-data.json').write_text(dumps(data),encoding='utf-8')
        result=execute(data);(HERE/'dev-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    elif command=='freeze':
        if (HERE/'frozen-manifest.json').exists(): raise RuntimeError('Freeze already exists')
        if not (HERE/'dev-results.json').exists(): raise RuntimeError('Run dev first')
        dev=json.loads((HERE/'dev-results.json').read_text(encoding='utf-8'))
        if dev['summary']['fixture_status_correct']!=240: raise RuntimeError('Dev fixture failures unresolved')
        (HERE/'holdout-data.json').write_text(dumps(dataset(981314,'hold')),encoding='utf-8')
        manifest={'sha256':{str(p.relative_to(EXP)):sha_file(p) for p in frozen_paths()},
                  'dependencies':{p:importlib.metadata.version(p) for p in ('numpy','scipy','scikit-learn','tiktoken','pytest')},
                  'tokenizer':'o200k_base','tokenizer_ranks_sha256':digest([(k.hex(),v) for k,v in sorted(ENC._mergeable_ranks.items())]),
                  'holdout_access':'dataset generated after implementation/dev; synthetic same generator families, NOT externally authored',
                  'policy':asdict(POLICY),'baseline_config':asdict(BASE_CONFIG),'actual_model_calls':0}
        with (HERE/'frozen-manifest.json').open('x',encoding='utf-8') as stream:stream.write(json.dumps(manifest,indent=2))
        result={'frozen':True,'files':len(manifest['sha256'])}
    elif command=='holdout':
        manifest=json.loads((HERE/'frozen-manifest.json').read_text(encoding='utf-8'))
        if any(sha_file(EXP/path)!=value for path,value in manifest['sha256'].items()): raise RuntimeError('Frozen hash mismatch')
        if any(importlib.metadata.version(p)!=v for p,v in manifest['dependencies'].items()): raise RuntimeError('Dependency drift')
        if digest([(k.hex(),v) for k,v in sorted(ENC._mergeable_ranks.items())])!=manifest['tokenizer_ranks_sha256']: raise RuntimeError('Tokenizer drift')
        with (HERE/'holdout-run.lock').open('x',encoding='utf-8') as stream: stream.write('one-shot holdout; no overwrite\n')
        result=execute(json.loads((HERE/'holdout-data.json').read_text(encoding='utf-8')))
        result['frozen_hashes_match']=all(sha_file(EXP/path)==value for path,value in manifest['sha256'].items())
        with (HERE/'holdout-results.json').open('x',encoding='utf-8') as stream:stream.write(json.dumps(result,ensure_ascii=False,indent=2))
    else: raise ValueError('dev | freeze | holdout')
    print(json.dumps({k:v for k,v in result.items() if k not in ('rows','families')},ensure_ascii=False,indent=2))

if __name__=='__main__': main()
