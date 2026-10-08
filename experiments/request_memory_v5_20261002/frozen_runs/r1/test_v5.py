from dataclasses import replace, asdict
import json
from pathlib import Path
import sys
import threading
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parent))
from contracts import Source, Need, Request, Policy, dumps, tokens
from memory_v5 import Snapshot
from engine_v5 import retrieve, route, normalize_request, prompt_for
from verifier_v5 import verify, calculate
from controller_v5 import Controller, Ledger, ScriptedProvider

def fixture_snapshot(extra=()):
    return Snapshot([Source('a', 'alpha owner: "team3"\nalpha limit: 250\nalpha link: "beta"', role='canonical',
                            schema={'owner':'string','limit':'integer','link':'entity_ref'}),
                     Source('b', 'beta owner: "team9"', role='canonical', schema={'owner':'string'}), *extra],
                    aliases={'human owner':'owner','مالک انسانی':'owner','concurrency limit':'limit'})

def request(field='owner', **kwargs):
    return Request('r', 'alpha '+field, needs=(Need('n', 'alpha', field),), task_kind='factual', **kwargs)

def answer(pack, value='team3', **overrides):
    b = pack.payload['bindings']['n']
    claim = {'need_id':'n','entity_ref':b['entity'],'field_ref':b['field'],'namespace':b['namespace'],
             'value':value,'value_type':b['value_type'],'proof_kind':b['proof_kind'],'evidence_refs':b['evidence_refs']}
    claim.update(overrides)
    return {'claims':[claim]}

def test_correct_fact():
    s=fixture_snapshot();r=request();p=retrieve(s,r)
    assert verify(s,r,p,answer(p)).status=='verified'

@pytest.mark.parametrize('field,value,patch', [
    ('owner','team9',{'entity_ref':'beta'}), ('owner','team3',{'field_ref':'limit'}),
    ('limit',25,{}), ('limit',True,{}), ('limit',250,{'evidence_refs':[]}),
    ('owner','team3',{'evidence_refs':['b:1']}), ('owner','team3',{'namespace':'other'})])
def test_wrong_bound_claim(field,value,patch):
    s=fixture_snapshot();r=request(field);p=retrieve(s,r)
    assert verify(s,r,p,answer(p,value,**patch)).status in ('invalid','contradicted')

@pytest.mark.parametrize('output,state', [({},'invalid'),({'claims':[]},'partial'),({'claims':[{'need_id':'n','value':None}]},'abstained')])
def test_empty_missing_abstain(output,state):
    s=fixture_snapshot();r=request();p=retrieve(s,r)
    assert verify(s,r,p,output).status==state

@pytest.mark.parametrize('question', ['What is the default concurrency limit in this project?',
    'Who is the human owner of this project?', 'مالک انسانی پروژه چه کسی است؟', 'How does this project manage memory?',
    'Fix this repository code'])
def test_ordinary_project_routing(question):
    assert route(Request('r',question))=='project_grounded'

def test_router_closed_and_uncertain():
    assert route(Request('r','Compute 2+2',task_kind='math',expression='2+2'))=='self_contained'
    assert route(Request('r','Write solve',task_kind='code',public_tests=({'input':1,'expected':2},)))=='self_contained'
    assert route(Request('r','Who owns it?'))=='uncertain'

def test_bilingual_public_alias():
    s=Snapshot([Source('p','workspace owner: "human"',role='canonical',schema={'owner':'string'})],
               aliases={'مالک انسانی':'owner'})
    r=normalize_request(Request('r','مالک انسانی پروژه چه کسی است؟'),s)
    assert len(r.needs)==1 and retrieve(s,r).payload['bindings']['n0']['entity']=='workspace'

def test_empty_snapshot():
    s=Snapshot([])
    p=retrieve(s,Request('r','Compute',task_kind='math',expression='2+2'))
    assert p.status=='ready' and p.payload['units']==[]
    assert verify(s,Request('r','Compute',task_kind='math',expression='2+2'),p,{'answer':4}).status=='verified'

@pytest.mark.parametrize('budget',[0,1,30])
def test_budget_fails_closed(budget):
    s=fixture_snapshot();p=retrieve(s,request(),Policy(evidence_budget=budget))
    assert p.status=='budget_infeasible' and p.count_passes==2
    assert set(p.required_ids)<={u['unit_id'] for u in p.payload['units']}

def test_trim_preserves_bundle_graph():
    s=fixture_snapshot();r=replace(request(),needs=(Need('n','alpha','owner',via_field='link'),))
    original=retrieve(s,r,Policy(optional_units=2))
    minimal=retrieve(s,r,Policy(optional_units=0))
    p=retrieve(s,r,Policy(evidence_budget=minimal.token_count,optional_units=2))
    assert p.status=='ready' and p.token_count<=minimal.token_count
    ids={u['unit_id'] for u in p.payload['units']}
    assert set(p.required_ids)<=ids and all(e['left'] in ids and e['right'] in ids for e in p.payload['relations'])
    assert verify(s,r,p,answer(p,'team9')).status=='verified'

def test_missing_relation_no_model():
    s=fixture_snapshot();r=replace(request(),needs=(Need('n','alpha','owner',via_field='absent'),))
    provider=ScriptedProvider([]);result=Controller(s,provider).run(r)
    assert result['status']=='missing' and not provider.calls

def test_cross_project_epoch_and_tombstone():
    rows=[Source('a','alpha owner: "old"',role='canonical',schema={'owner':'string'}),
          Source('a','',revision=2,status='deleted'),
          Source('b','alpha owner: "foreign"',project='other',role='canonical',schema={'owner':'string'}),
          Source('c','alpha owner: "proposal"',status='proposed',role='canonical',schema={'owner':'string'}),
          Source('d','alpha owner: "wrong epoch"',epoch='2',role='canonical',schema={'owner':'string'})]
    assert Snapshot(rows).units==()
    assert retrieve(fixture_snapshot(),request(epoch='2')).status=='scope_mismatch'

def test_conflicting_revision():
    with pytest.raises(ValueError): Snapshot([Source('a','x'),Source('a','y')])

def test_ambiguous_namespaces():
    s=Snapshot([Source('a','alpha owner: "A"',role='canonical',schema={'owner':'string'},namespace='left'),
                Source('b','alpha owner: "B"',role='canonical',schema={'owner':'string'},namespace='right')])
    assert retrieve(s,request()).status=='ambiguous'
    r=replace(request(),needs=(Need('n','alpha','owner',namespace='right'),))
    assert retrieve(s,r).status=='ready'

def test_literal_contract_not_fixture():
    s=Snapshot([Source('c.py',"from typing import Literal\nclass Contract:\n    owner: Literal['local-user']\n",format='python',role='contract'),
                Source('fixture','Contract owner: "Danial"',role='fixture',schema={'owner':'string'})])
    r=replace(request(),needs=(Need('n','Contract','owner',proof_kind='contract_literal',value_type='literal_set'),))
    p=retrieve(s,r)
    assert verify(s,r,p,answer(p,['local-user'])).status=='verified'
    assert verify(s,r,p,answer(p,['Danial'])).status=='contradicted'

def test_literal_set_exact_or_explicit_membership():
    s=Snapshot([Source('s','alpha owner: ["a","b"]',role='contract',schema={'owner':'literal_set'})])
    r=request();p=retrieve(s,r)
    assert verify(s,r,p,answer(p,['a'])).status=='contradicted'
    assert verify(s,r,p,answer(p,['b','a'])).status=='verified'
    r=replace(r,needs=(replace(r.needs[0],membership=True),))
    assert verify(s,r,retrieve(s,r),answer(p,'a')).status=='verified'

def test_quantity_units():
    s=Snapshot([Source('s','alpha delay: {"amount":250,"unit":"ms"}',role='config',schema={'delay':'quantity'})])
    r=request('delay');p=retrieve(s,r)
    assert verify(s,r,p,answer(p,{'amount':250,'unit':'ms'})).status=='verified'
    assert verify(s,r,p,answer(p,{'amount':250,'unit':'s'})).status=='contradicted'

def test_stale_and_tampered_pack():
    s=fixture_snapshot();r=request();p=retrieve(s,r)
    p.payload['units'][0]['text']='changed'
    assert verify(s,r,p,answer(p)).status=='invalid'
    p=retrieve(s,r);s2=fixture_snapshot([Source('extra','epoch change')])
    assert verify(s2,r,p,answer(p)).status=='invalid'

def test_pack_binding_cannot_authorize_wrong_entity():
    s=fixture_snapshot();r=request();p=retrieve(s,r,Policy(optional_units=3))
    p.payload['bindings']['n'].update(entity='beta',evidence_refs=['b:1'])
    assert verify(s,r,p,answer(p,'team9')).status=='contradicted'

def test_python_ast_preserves_decorator_signature_and_guard():
    src='@decorate\ndef choose(\n    x: int,\n):\n    if x < 0:\n        return -1\n    return x\n'
    s=Snapshot([Source('m.py',src,format='python',namespace='m')])
    assert any('@decorate' in u.text and 'x: int' in u.text for u in s.units)
    assert any('if x < 0' in u.text and 'return -1' in u.text for u in s.units)
    assert all(u.text=='\n'.join(src.splitlines()[u.line_start-1:u.line_end]) for u in s.units)

def test_prompt_budget_checked_before_call():
    provider=ScriptedProvider([]);r=Controller(fixture_snapshot(),provider).run(request(),Policy(prompt_budget=1))
    assert r['status']=='prompt_too_large' and not provider.calls

def test_repair_cap_and_idempotency(tmp_path):
    s=fixture_snapshot();r=request();p=retrieve(s,r)
    provider=ScriptedProvider([{},answer(p,'wrong'),answer(p)])
    ledger=Ledger(str(tmp_path/'ledger.sqlite'));controller=Controller(s,provider,ledger)
    result=controller.run(r)
    assert result['status']=='contradicted' and len(provider.calls)==2 and result['ledger']['repair_used']==1
    assert controller.run(r)==result and len(provider.calls)==2
    assert provider.calls[0]['prompt']!=provider.calls[1]['prompt']
    ledger.close();again=Ledger(str(tmp_path/'ledger.sqlite'))
    assert Controller(s,provider,again).run(r)==result
    again.close()

def test_provider_unknown_effect_no_retry():
    provider=ScriptedProvider([TimeoutError('unknown effect'),{}])
    result=Controller(fixture_snapshot(),provider).run(request())
    assert result['status']=='provider_incomplete' and len(provider.calls)==1

def test_no_third_call_policy():
    with pytest.raises(ValueError): Policy(max_calls=3)
    provider=ScriptedProvider([{},{}]);result=Controller(fixture_snapshot(),provider).run(request(),Policy(max_calls=1))
    assert result['ledger']['physical_attempts']==1 and len(provider.calls)==1

def test_concurrent_atomic_reservation(tmp_path):
    path=str(tmp_path/'ledger.sqlite');ledger=Ledger(path);ledger.begin('r','hash',100)
    outcomes=[]
    def reserve():
        db=Ledger(path)
        try: db.reserve('r',2);outcomes.append(True)
        except RuntimeError: outcomes.append(False)
        finally: db.close()
    threads=[threading.Thread(target=reserve) for _ in range(8)]
    for t in threads:t.start()
    for t in threads:t.join()
    assert sum(outcomes)==2 and ledger.stats('r')['physical_attempts']==2
    ledger.close()

def test_closed_math_escalation_and_truth():
    r=Request('m','2+2',task_kind='math',expression='2+2')
    provider=ScriptedProvider([{'answer':3},{'answer':4}])
    result=Controller(Snapshot([]),provider).run(r,Policy(allow_escalation=True))
    assert result['status']=='verified' and [c['model'] for c in provider.calls]==['gpt-6-luna','gpt-6.1-sol']
    assert result['memory_proposal']['auto_promoted'] is False and result['human_accepted'] is False

def test_no_checker_preserves_unverified():
    r=Request('m','Explain a proof',task_kind='math',memory_need='self_contained')
    result=Controller(Snapshot([]),ScriptedProvider([{'text':'a proof'}])).run(r)
    assert result['status']=='unverified' and result['ledger']['physical_attempts']==1

def test_real_public_code_execution():
    r=Request('c','Return twice arg',task_kind='code',public_tests=({'input':2,'expected':4},{'input':-3,'expected':-6}))
    s=Snapshot([]);p=retrieve(s,r)
    receipt=verify(s,r,p,{'code':'def solve(arg):\n    return arg*2'})
    assert receipt.status=='verified' and receipt.details['code']['passed']==[True,True]
    assert verify(s,r,p,{'code':'import os\ndef solve(arg): return 4'}).status=='contradicted'

def test_unknown_free_prose_not_verified():
    s=fixture_snapshot();r=Request('r','Describe the project')
    assert verify(s,r,retrieve(s,r),{'text':'confidence: 100%'}).status=='unverified'

def test_alias_boundary_and_consumed_words():
    s=Snapshot([Source('s','workspace owner_setting: "A"\nworkspace another: "B"\nalpha owner: "C"',
               role='canonical',schema={'owner_setting':'string','another':'string','owner':'string'})],
               aliases={'human owner for region 1':'another','human owner for region 10':'owner_setting'})
    r=normalize_request(Request('r','What is the human owner for region 10 in this project?'),s)
    assert len(r.needs)==1 and r.needs[0].field=='owner_setting'

@pytest.mark.parametrize('bad', [float('nan'),{'claims':[{'need_id':[]}]},{'claims':[{'need_id':'n','value':'A','evidence_refs':[{}]}]}])
def test_bad_schema_no_crash(bad):
    s=fixture_snapshot();r=request();p=retrieve(s,r)
    assert verify(s,r,p,bad).status in ('invalid','contradicted')

def test_named_code_bundle_and_defaults():
    s=Snapshot([Source('s.py','class Limits:\n    max_concurrency: int = Field(default=2)\n\ndef compute(arg):\n    if arg < 0:\n        return 0\n    return arg*2\n',format='python',role='code')])
    r=Request('r','Adapt compute in this repository',task_kind='code',public_tests=({'input':2,'expected':4},))
    r=normalize_request(r,s);p=retrieve(s,r)
    assert any('if arg < 0' in u['text'] for u in p.payload['units'])
    assert len(p.required_ids)==3
    assert any(u.field=='max_concurrency' and u.value==2 for u in s.units)

def test_code_bool_does_not_equal_integer():
    r=Request('c','Return one',task_kind='code',public_tests=({'input':0,'expected':1},))
    s=Snapshot([])
    assert verify(s,r,retrieve(s,r),{'code':'def solve(arg): return True'}).status=='contradicted'

def test_nonfinite_provider_output_is_schema_failure():
    r=Request('m','Compute',task_kind='math',expression='2+2')
    p=ScriptedProvider(['{"answer":NaN}',{'answer':4}])
    assert Controller(Snapshot([]),p).run(r)['status']=='verified'
