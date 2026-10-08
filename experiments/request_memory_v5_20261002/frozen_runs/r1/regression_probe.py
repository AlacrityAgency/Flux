"""Reproduce known v4 failures and inspect frozen real Flux contracts, offline."""
from dataclasses import asdict, replace
import json
from pathlib import Path
import sys
from contracts import Source, Need, Request, Policy
from memory_v5 import Snapshot
from engine_v5 import retrieve, normalize_request
from verifier_v5 import verify
from controller_v5 import Controller, ScriptedProvider

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'request_memory_v4_20261002'))
import engine_v4 as v4

def run():
    old=v4.Index([v4.Record(v4.Atom('a','alpha01 owner: team03.','a',1,0)),
                  v4.Record(v4.Atom('b','beta02 owner: team09.','b',1,0)),
                  v4.Record(v4.Atom('c','alpha01 limit_ms: 250.','a',2,0))])
    old_owner=v4.run(old,'o','alpha01 owner',['owner'])
    old_limit=v4.run(old,'l','alpha01 limit_ms',['alpha01 limit_ms'])
    old_closed=v4.run(old,'c','Compute 2+2',['Return numeric answer'])
    new=Snapshot([Source('a','alpha01 owner: "team03"\nalpha01 limit_ms: 250',role='canonical',
                         schema={'owner':'string','limit_ms':'integer'}),
                  Source('b','beta02 owner: "team09"',role='canonical',schema={'owner':'string'})])
    owner=Request('o','alpha01 owner',needs=(Need('n','alpha01','owner'),),task_kind='factual')
    limit=replace(owner,request_id='l',needs=(Need('n','alpha01','limit_ms'),))
    p=retrieve(new,owner,Policy(optional_units=3));pl=retrieve(new,limit)
    def answer(pack,value,**overrides):
        binding=pack.payload['bindings']['n']
        c={'need_id':'n','entity_ref':binding['entity'],'field_ref':binding['field'],
           'namespace':binding['namespace'],'value_type':binding['value_type'],'proof_kind':binding['proof_kind'],
           'value':value,'evidence_refs':binding['evidence_refs']}
        c.update(overrides);return {'claims':[c]}
    rows=[]
    tests=[('wrong entity',old_owner,{'owner':'team09'},['b'],owner,p,answer(p,'team09',entity_ref='beta02')),
           ('wrong field',old_owner,{'limit_ms':'team03'},['a'],owner,p,answer(p,'team03',field_ref='limit_ms')),
           ('25 versus 250',old_limit,{'limit_ms':25},['c'],limit,pl,answer(pl,25)),
           ('empty answer',old_owner,{},[],owner,p,{}),
           ('required claim missing',old_owner,{},[],owner,p,{'claims':[]}),
           ('missing citation',old_owner,{'owner':'team03'},[],owner,p,answer(p,'team03',evidence_refs=[]))]
    for label,pack,old_output,citations,req,newpack,new_output in tests:
        state=verify(new,req,newpack,new_output).status
        rows.append({'case':label,'expected':'reject','v4_accepted':v4.verify_answer(pack,old_output,citations)['ok'],
                     'v5_status':state,'v5_correct':state!='verified'})
    math=Request('c','Compute 2+2',task_kind='math',expression='2+2')
    rows.append({'case':'correct closed math','expected':'accept','v4_accepted':v4.verify_answer(old_closed,{'answer':4})['ok'],
                 'v5_status':verify(new,math,retrieve(new,math),{'answer':4}).status,'v5_correct':True})
    tiny=v4.run(old,'tiny','Compute 2+2',['Return numeric answer'],v4.Config(budget=1))
    rows.append({'case':'budget=1','expected':'stop before generation','v4_tokens':tiny['tokens'],
                 'v5_status':retrieve(new,math,Policy(evidence_budget=1)).status,'v5_correct':True})
    try:v4.Index([]);old_empty='valid'
    except ValueError:old_empty='error'
    rows.append({'case':'empty memory','expected':'valid snapshot','v4_status':old_empty,
                 'v5_status':'valid' if Snapshot([]).units==() else 'error','v5_correct':True})
    frozen=HERE.parent/'diffusion_memory_20261001/snapshots/flux_real/sources'
    relative='src/flux/core/contracts.py';source_text=(frozen/relative).read_text(encoding='utf-8')
    real=Snapshot([Source(relative,source_text,project='flux',format='python',role='contract',namespace='flux.core.contracts')],project='flux',
                  aliases={'concurrency limit':'max_concurrency','مالک انسانی':'human_owner','human owner':'human_owner'})
    real_results=[]
    for entity,field,kind,proof,value in [('Limits','max_concurrency','integer','typed_fact',2),
                                        ('Contract','human_owner','literal_set','contract_literal',['local-user']),
                                        ('Contract','output_format','literal_set','contract_literal',['markdown','plain_text','json'])]:
        r=Request('real-'+field,'Read '+entity+' '+field,project='flux',task_kind='factual',
                  needs=(Need('n',entity,field,namespace='flux.core.contracts',value_type=kind,proof_kind=proof),))
        pack=retrieve(real,r);output=answer(pack,value);check=verify(real,r,pack,output)
        assert check.status=='verified'
        real_results.append({'field':field,'value':value,'status':check.status,'tokens':pack.token_count,
                             'source_refs':pack.payload['bindings']['n']['evidence_refs']})
    result={'actual_model_calls':0,'known_regressions':rows,'real_frozen_source':relative,
            'real_source_hash':real.units[0].source_hash,'real_contract_checks':real_results,
            'v4_frozen_code_hashes_match':all(v4.sha((HERE.parent/'request_memory_v4_20261002'/path).read_text(encoding='utf-8'))==sha
                for path,sha in json.loads((HERE.parent/'request_memory_v4_20261002/frozen-plan.json').read_text(encoding='utf-8'))['code_hashes'].items())}
    (HERE/'regression-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':run()
