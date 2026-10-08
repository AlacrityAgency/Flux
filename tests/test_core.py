"""Behavioral checks for frozen contracts, gates, limits, recovery and ledger races."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import pytest
from httpx import ASGITransport, AsyncClient
from flux.api.app import create_app
from flux.core.service import CoreService
from flux.core.contracts import Contract, Evidence
from flux.knowledge.retrieval import build_pack, token_count
from flux.knowledge.sources import SourceIndex
from flux.storage.database import init_db
from flux.storage.repository import Repository
from flux.storage.workspace import Workspace
from flux.local_agents.runtime import ChatSpec, TurnSpec


@pytest.fixture
def core(repo,tmp_path):
    workspace=Workspace(repo)
    project=workspace.create_project('Fixture project',str(tmp_path))
    return CoreService(repo,workspace),project


def contract(project,key='fixture',**extra):
    return {'project_id':project['id'],'request_key':key,'objective':'Write the required technical explanation',
            'acceptance_criteria':[{'criterion_id':'C1','text':'Explain the architecture','evidence_type':'source_document'}],**extra}


def generated(service,project,**extra):
    task=service.register(contract(project,**extra))
    service.claim(task['id'],'gen:'+task['id'])
    with service.atomic():service.conn.execute("UPDATE core_operations SET state='completed' WHERE task_id=?",(task['id'],))
    return service.artifact(task['id'],'Fixture architecture deliverable','fixture-worker')


def review_payload(task,status='PASS',refs=None,**extra):
    return {'artifact_hash':task['artifact_hash'],'contract_hash':task['contract_hash'],'policy_revision':1,
            'criterion_results':[{'criterion_id':'C1','status':status,'evidence_refs':refs if refs is not None else [task['evidence'][0]['id']],
                                  'reason_code':'VERIFIED' if status=='PASS' else 'DEFECT','explanation':'Observed fixture evidence'}],**extra}


def test_contract_idempotency_and_unknown_project(core):
    s,p=core;t=s.register(contract(p));assert s.register(contract(p))['id']==t['id']
    with pytest.raises(ValueError,match='conflict'):s.register(contract(p,objective='Changed objective here'))
    with pytest.raises(ValueError,match='project'):s.register(contract({'id':'missing'},key='missing'))
    with pytest.raises(ValueError):Contract.model_validate(contract(p,acceptance_criteria=[{'criterion_id':'C1','text':'one'},{'criterion_id':'C1','text':'two'}]))
    with pytest.raises(ValueError):Contract.model_validate(contract(p,tenant_id='other'))


def test_execution_provider_is_frozen_with_contract_and_inherited_by_children(core):
    s,p=core
    root=s.register(contract(p,key='provider-root',execution_provider='claude'))
    with pytest.raises(ValueError,match='frozen contract account'):
        s.claim(root['id'],'wrong-account',provider='codex')
    with pytest.raises(ValueError,match='billing/provider/budget'):
        s.register(contract(p,key='provider-child',parent_task_id=root['id'],execution_provider='codex'))
    operation=s.claim(root['id'],'right-account',provider='claude')
    assert operation['provider']=='claude'


def test_api_receipt_crash_rolls_back_effect_then_applies_once(core,monkeypatch):
    s,p=core;t=s.register(contract(p,billing='api'))
    s.claim(t['id'],'crash-receipt',provider='gapgpt',amount_micros=1000)
    original=s.event
    def crash(task_id,kind,payload):
        original(task_id,kind,payload)
        if kind=='artifact':raise RuntimeError('simulated crash after artifact effect')
    monkeypatch.setattr(s,'event',crash)
    with pytest.raises(RuntimeError,match='simulated crash'):
        s.finish_api('crash-receipt',json.dumps({'content':'real persisted worker receipt'}),{'billing':'api'},10)
    t=s.task(t['id']);assert t['state']=='RUNNING' and t['artifact'] is None and not t['evidence']
    assert t['operations'][0]['state']=='received'
    monkeypatch.setattr(s,'event',original)
    t=s.apply_api_receipt('crash-receipt')
    assert t['state']=='REVIEWING' and len(t['evidence'])==1
    again=s.apply_api_receipt('crash-receipt')
    assert again['artifact_hash']==t['artifact_hash'] and len(again['evidence'])==1


def test_exact_acceptance_and_proposed_memory(core):
    s,p=core;t=generated(s,p);t=s.review(t['id'],review_payload(t))
    assert t['state']=='ACCEPT_CANDIDATE' and not t['acceptance']
    with pytest.raises(ValueError):s.accept(t['id'],'a'*64,t['review_revision'])
    with pytest.raises(ValueError):s.accept(t['id'],t['artifact_hash'],t['review_revision']+1)
    t=s.accept(t['id'],t['artifact_hash'],t['review_revision'])
    assert t['state']=='ACCEPTED' and t['acceptance']['actor']=='local-user'
    assert s.workspace.memories(project_id=p['id'])[0]['status']=='proposed'
    assert s.workspace.retrieve('architecture',project_id=p['id'])==[]
    assert s.accept(t['id'],t['artifact_hash'],t['review_revision'])['state']=='ACCEPTED'
    assert len(s.workspace.memories(project_id=p['id']))==1


@pytest.mark.parametrize('bad',['missing','wrong_type','failed','not_run','different_hash'])
def test_false_pass_is_unknown(core,bad):
    s,p=core;t=generated(s,p,acceptance_criteria=[{'criterion_id':'C1','text':'Tests pass','evidence_type':'test_execution'}])
    refs=[]
    if bad!='missing':
        kind='test_definition' if bad=='wrong_type' else 'test_execution'
        outcome=bad if bad in {'failed','not_run'} else 'passed'
        eid=s.add_evidence(t['id'],Evidence(artifact_hash=t['artifact_hash'],evidence_type=kind,content='fixture',outcome=outcome,source_ref='test receipt'))
        if bad=='different_hash':
            with s.atomic():s.conn.execute('UPDATE core_evidence SET artifact_hash=? WHERE id=?',('a'*64,eid))
        refs=[eid]
    t=s.review(t['id'],review_payload(t,refs=refs))
    assert t['state']=='ESCALATED' and t['review']['criterion_results'][0]['status']=='UNKNOWN'


def test_review_conflict_preserved_and_criterion_identity(core):
    s,p=core;t=generated(s,p)
    wrong=review_payload(t);wrong['criterion_results'][0]['criterion_id']='unknown'
    with pytest.raises(ValueError,match='criterion ID'):s.review(t['id'],wrong)
    t=s.review(t['id'],review_payload(t,blocking_issues=['Actual blocking defect']))
    assert t['state']=='ESCALATED' and 'Actual blocking defect' in t['review']['blocking_issues']


def test_source_change_invalidates_review_and_accept(core,tmp_path):
    s,p=core;(tmp_path/'code.py').write_text('version=1')
    t=generated(s,p,allowed_paths=['code.py']);t=s.review(t['id'],review_payload(t))
    (tmp_path/'code.py').write_text('version=2')
    with pytest.raises(ValueError,match='revision changed'):s.accept(t['id'],t['artifact_hash'],t['review_revision'])


def test_repair_requires_new_method_preserves_root_limit(core):
    s,p=core;t=generated(s,p,limits={'max_calls':2})
    t=s.review(t['id'],review_payload(t,'FAIL',repair_method='inspect dependency'))
    t=s.retry(t['id'],'inspect dependency');assert t['root_counters']['calls']==1
    s.claim(t['id'],'second')
    with s.atomic():s.conn.execute("UPDATE core_operations SET state='completed' WHERE id='second'")
    t=s.artifact(t['id'],'Repaired fixture artifact');t=s.review(t['id'],review_payload(t,'FAIL',repair_method='inspect dependency'))
    with pytest.raises(ValueError,match='Same repair'):s.retry(t['id'],'inspect dependency')
    s.retry(t['id'],'different method')
    assert s.decision(t['id'])['action']=='ESCALATE'
    with pytest.raises(ValueError,match='limit'):s.claim(t['id'],'third')


def test_recovery_does_not_replay_unknown_dispatch(core):
    s,p=core;t=s.register(contract(p));op=s.claim(t['id'],'unknown')
    s.recover();assert s.task(t['id'])['state']=='RECOVERING'
    assert s.claim(t['id'],'unknown')['state']=='unknown'
    with pytest.raises(ValueError):s.claim(t['id'],'another')
    t=s.reconcile(t['id'],'unknown','no_effect')
    assert t['state']=='READY' and t['root_counters']['calls']==1


def test_children_share_counters_dependencies_and_no_cross_scope(core):
    s,p=core;root=s.register(contract(p,limits={'max_children':2}))
    child=s.register(contract(p,key='child',parent_task_id=root['id'],limits={'max_children':2}))
    other=s.workspace.create_project('Other',p['path'])
    with pytest.raises(ValueError,match='Cross-project'):s.register(contract(other,key='cross',parent_task_id=root['id']))
    dep=s.register(contract(p,key='dependency',parent_task_id=root['id'],dependencies=[child['id']],limits={'max_children':2}))
    assert s.decision(root['id'])['action']=='WAIT'
    assert s.decision(dep['id'])['action']=='WAIT'
    with pytest.raises(ValueError,match='Child count'):s.register(contract(p,key='extra',parent_task_id=root['id']))
    s.claim(child['id'],'child-gen')
    with s.atomic():s.conn.execute("UPDATE core_operations SET state='completed' WHERE id='child-gen'")
    child=s.artifact(child['id'],'Child evidence');s.review(child['id'],review_payload(child))
    assert s.decision(dep['id'])['action']=='GENERATE'
    assert s.task(root['id'])['root_counters']['calls']==1


def test_budget_ancestors_review_floor_unknown_and_conflict(core):
    s,p=core;t=s.register(contract(p,billing='api',budget_cap_micros=100,review_reserve_micros=20));account='task:'+t['id']
    with s.atomic():
        assert s.budget.reserve('a',account,81,'a')=='BLOCKED_BUDGET'
        assert s.budget.reserve('a',account,80,'a')=='active'
        assert s.budget.reserve('a',account,80,'a')=='active'
        assert s.budget.reserve('b',account,20,'b',review=True)=='active'
        assert s.budget.settle('a')=='held_unknown'
        assert s.budget.settle('a')=='held_unknown'
        assert s.budget.settle('a',50)=='settled'
        assert s.budget.settle('a',50)=='settled'
        assert s.budget.settle('a',51)=='BLOCKED_RECONCILIATION'
        assert s.budget.reserve('c',account,1,'c')=='BLOCKED_RECONCILIATION'
    for ancestor in s.budget.ancestors(account):
        assert ancestor['spent']==50 and ancestor['reserved']==20 and ancestor['unknown']==0 and ancestor['blocked']==1


def test_budget_shared_company_cap(core):
    s,p=core;a=s.register(contract(p,key='a',billing='api'));b=s.register(contract(p,key='b',billing='api'))
    with s.atomic():
        s.budget.revise('company:local',100)
        assert s.budget.reserve('a','task:'+a['id'],70,'physical-a')=='active'
        assert s.budget.reserve('b','task:'+b['id'],31,'physical-b')=='BLOCKED_BUDGET'


def test_two_db_connections_cannot_double_admit(tmp_path):
    path=str(tmp_path/'race.db');conn=init_db(path);repo=Repository(conn);ws=Workspace(repo);p=ws.create_project('Race',str(tmp_path));s=CoreService(repo,ws)
    t=s.register(contract(p,budget_cap_micros=100));conn.close()
    def reserve(i):
        conn=init_db(path);service=CoreService(Repository(conn),Workspace(Repository(conn)))
        with service.atomic():result=service.budget.reserve(str(i),'task:'+t['id'],60,'physical:'+str(i))
        conn.close();return result
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(reserve,[1,2]))
    assert sorted(results)==['BLOCKED_BUDGET','active']


def test_memory_scope_proposals_revision_deletion(core):
    s,p=core;ws=s.workspace;p2=ws.create_project('Other',p['path'])
    old=ws.save_memory('architecture','old architecture',project_id=p['id'])
    ws.save_memory('architecture','other secret architecture',project_id=p2['id'])
    ws.save_memory('architecture','unassigned architecture')
    ws.save_memory('architecture','global architecture',project_id='*')
    ws.save_memory('architecture','proposed architecture',project_id=p['id'],status='proposed')
    contents=[r['content'] for r in ws.retrieve('architecture',project_id=p['id'])]
    assert set(contents)=={'old architecture','global architecture'}
    with pytest.raises(ValueError,match='revision'):ws.save_memory('architecture','changed',ident=old['id'],expected_revision=0)
    ws.save_memory('architecture','stale architecture',ident=old['id'],status='stale')
    assert 'old architecture' not in str(ws.retrieve('architecture',project_id=p['id']))
    ws.delete_memory(old['id']);assert not any(m['id']==old['id'] for m in ws.memories())
    assert all(r[0]=='' for r in s.conn.execute('SELECT content FROM memory_revisions WHERE id=?',(old['id'],)))


def test_canonical_tombstone_prevents_old_revision_resurrection():
    records=[{'ref':'note','title':'architecture','content':'old architecture','revision':1,'status':'verified'},
             {'ref':'note','title':'architecture','content':'','revision':2,'status':'deleted'}]
    assert build_pack('architecture',[],records)['evidence']==[]
    records[-1].update(status='proposed',content='proposed architecture')
    assert build_pack('architecture',[],records)['evidence'][0]['revision']==1


def test_pack_exact_tokens_and_no_cut_evidence():
    records=[{'ref':str(i),'title':'architecture','content':'architecture '*200,'revision':1,'status':'verified'} for i in range(10)]
    pack=build_pack('architecture',[{'criterion_id':'C1','text':'architecture'}],records,700)
    assert pack['tokens']==token_count(pack['rendered'])<=700
    assert pack['evidence'] and all(r['content']==records[0]['content'] for r in pack['evidence'])
    assert pack['semantic_sufficiency']=='unverified'


def test_context_admission_preserves_mandatory_artifact():
    from flux.core.context import admit_context
    assert admit_context('Short mandatory contract')['provider_hidden_context']=='unknown'
    with pytest.raises(ValueError,match='silently truncated'):admit_context('architecture '*10000,input_budget=100)


@pytest.mark.asyncio
async def test_offline_cli_worker_and_independent_reviewer_through_api(engine,tmp_path,monkeypatch):
    import sys
    from flux.local_agents import runtime as module
    import flux.core.api as core_api
    app=create_app(engine=engine);runtime=app.state.local_runtime
    async def status(refresh=False):return {'providers':[{'id':'codex','authenticated':True}]}
    monkeypatch.setattr(runtime,'status',status)
    monkeypatch.setattr(module,'find_cli',lambda p:sys.executable)
    monkeypatch.setattr(core_api,'find_cli',lambda p:sys.executable)
    script=tmp_path/'fixture_cli.py'
    script.write_text('''import sys,json
prompt=sys.stdin.buffer.read().decode('utf-8')
if 'independent Flux reviewer' in prompt:
    bindings=json.loads(prompt.split('Review bindings:\\n')[1].split('\\nArtifact:')[0])
    evidence=json.loads(prompt.split('Available evidence:\\n')[1])
    output=json.dumps(dict(**bindings,criterion_results=[dict(criterion_id='C1',status='PASS',evidence_refs=[evidence[0]['id']],reason_code='VERIFIED',explanation='Fixture source evidence inspected')],blocking_issues=[]))
else:output='Actual fixture process generated this architecture artifact.'
print(json.dumps({'type':'thread.started','thread_id':'fixture-session'}),flush=True)
print(json.dumps({'type':'item.completed','item':{'type':'agent_message','text':output}}),flush=True)
print(json.dumps({'type':'turn.completed','usage':{'input_tokens':20,'output_tokens':10}}),flush=True)
''',encoding='utf-8')
    monkeypatch.setattr(module,'command_for',lambda c,e:[sys.executable,'-u',str(script)])
    project=app.state.workspace.create_project('CLI fixture',str(tmp_path))
    async with AsyncClient(transport=ASGITransport(app),base_url='http://test') as client:
        task=(await client.post('/api/core/tasks',json=contract(project))).json();base='/api/core/tasks/'+task['id']
        generation={'operation_key':'worker','phase':'generation'}
        dispatched=await client.post(base+'/execute',json=generation)
        assert dispatched.status_code==202
        assert (await client.post(base+'/execute',json=generation)).status_code==202
        await asyncio.wait_for(asyncio.gather(*runtime.jobs.values()),10)
        task=(await client.get(base)).json();assert task['state']=='REVIEWING'
        assert task['root_counters']['calls']==1 and not task['acceptance']
        review=(await client.post(base+'/execute',json={'operation_key':'reviewer','phase':'review'})).json()
        assert review['operations'][0]['chat_id']!=review['operations'][1]['chat_id']
        await asyncio.wait_for(asyncio.gather(*runtime.jobs.values()),10)
        task=(await client.get(base)).json();assert task['state']=='ACCEPT_CANDIDATE'
        task=(await client.post(base+'/accept',json={'artifact_hash':task['artifact_hash'],'review_revision':task['review_revision']})).json()
        assert task['state']=='ACCEPTED' and task['root_counters']['calls']==2
        assert all(json.loads(op['usage'])['actual_cost_usd'] is None for op in task['operations'])


def test_legacy_unknown_reconciliation_conflict_and_shared_root(repo,sample_task_data):
    for ident in ['one','two']:
        repo.create_run(ident,ident,'shared-root','project','owner',sample_task_data,.1)
    assert repo.reserve_budget('r','one','call','model',.07,1,1)
    assert not repo.reserve_budget('r2','two','call2','model',.04,1,1)
    assert repo.settle_reservation('r',None)=='held_unknown'
    assert repo.settle_reservation('r',.03)=='settled'
    assert repo.settle_reservation('r',.03)=='settled'
    assert repo.get_run('one')['unknown_cost_usd']==0
    assert repo.get_run('one')['spent_cost_usd']==.03
    assert repo.settle_reservation('r',.04)=='BLOCKED_RECONCILIATION'
    assert not repo.reserve_budget('r3','two','call3','model',.01,1,1)


@pytest.mark.asyncio
async def test_api_execution_reserves_and_settles_all_ancestors(engine,tmp_path,fake_provider):
    app=create_app(engine=engine);s=app.state.core;p=app.state.workspace.create_project('API fixture',str(tmp_path))
    fake_provider.custom_responses['gpt-5.6-luna']=json.dumps({'content':'Architecture fixture artifact'})
    async with AsyncClient(transport=ASGITransport(app),base_url='http://test') as client:
        task=(await client.post('/api/core/tasks',json=contract(p,billing='api'))).json();base='/api/core/tasks/'+task['id']
        dispatched=await client.post(base+'/execute-api',json={'operation_key':'api-worker','max_output_tokens':1000})
        assert dispatched.status_code==200 and dispatched.json()['state']=='REVIEWING'
        task=dispatched.json();calls=fake_provider.call_count
        assert (await client.post(base+'/execute-api',json={'operation_key':'api-worker','max_output_tokens':1000})).status_code==200
        assert fake_provider.call_count==calls
        assert (await client.post(base+'/execute-api',json={'operation_key':'api-worker','max_output_tokens':2000})).status_code==409
        fake_provider.custom_responses['gapgpt-qwen-3.6-thinking']=json.dumps(review_payload(task))
        reviewed=await client.post(base+'/execute-api',json={'operation_key':'api-review','phase':'review','max_output_tokens':1000})
        assert reviewed.status_code==200 and reviewed.json()['state']=='ACCEPT_CANDIDATE'
        for account in reviewed.json()['budget']:assert account['spent']>0 and account['reserved']==0 and account['unknown']==0


@pytest.mark.asyncio
async def test_api_failure_holds_unknown_blocks_replay(engine,tmp_path,fake_provider):
    from flux.providers.base import ProviderError
    app=create_app(engine=engine);s=app.state.core;p=app.state.workspace.create_project('API failure',str(tmp_path))
    async def unavailable(*args,**kwargs):raise ProviderError('Unknown request outcome',is_transient=True)
    fake_provider.generate=unavailable
    async with AsyncClient(transport=ASGITransport(app),base_url='http://test') as client:
        task=(await client.post('/api/core/tasks',json=contract(p,billing='api'))).json();base='/api/core/tasks/'+task['id']
        failed=(await client.post(base+'/execute-api',json={'operation_key':'unknown-api','max_output_tokens':1000})).json()
        assert failed['state']=='RECOVERING'
        assert all(a['unknown']>0 for a in failed['budget'])
        assert (await client.post(base+'/execute-api',json={'operation_key':'unknown-api','max_output_tokens':1000})).json()['root_counters']['calls']==1
        assert (await client.post(base+'/execute-api',json={'operation_key':'different-api','max_output_tokens':1000})).status_code==422


def test_source_index_live_hash_and_exclusions(core,tmp_path):
    s,p=core;index=SourceIndex(s.repo,s.workspace)
    (tmp_path/'main.py').write_text('architecture = 1',encoding='utf-8')
    index.index(p['id'],['main.py']);assert s.workspace.retrieve('architecture',project_id=p['id'])
    (tmp_path/'main.py').write_text('architecture = 2',encoding='utf-8')
    assert s.workspace.retrieve('architecture',project_id=p['id'])==[]
    assert index.sources(p['id'])[0]['status']=='stale'
    index.index(p['id'],['main.py']);assert index.sources(p['id'])[0]['revision']==2
    (tmp_path/'.env').write_text('secret');(tmp_path/'auth.json').write_text('{}')
    for name in ['.env','auth.json','../outside.py']:
        with pytest.raises(ValueError):index.index(p['id'],[name])


@pytest.mark.asyncio
async def test_memory_switch_rebuilds_native_session_and_blocks_active_edit(core,monkeypatch,tmp_path):
    s,p=core
    from flux.local_agents.runtime import LocalRuntime
    runtime=LocalRuntime(s.repo,s.workspace)
    import flux.local_agents.runtime as module
    monkeypatch.setattr(module,'find_cli',lambda provider:'fixture.exe')
    async def noop(*args):pass
    monkeypatch.setattr(runtime,'execute',noop)
    chat=runtime.create_chat(ChatSpec(cwd=str(tmp_path),project_id=p['id']))
    s.workspace.save_memory('architecture','project architecture',project_id=p['id'])
    turn=runtime.submit(chat['id'],TurnSpec(prompt='architecture',request_key='one'));await asyncio.gather(*runtime.jobs.values());runtime.jobs.clear()
    with pytest.raises(ValueError,match='اجرای'):s.workspace.save_memory('architecture','changed architecture',project_id=p['id'])
    runtime.update(turn['id'],state='completed')
    with s.conn:s.conn.execute("UPDATE local_chats SET session_id='old-native' WHERE id=?",(chat['id'],))
    runtime.submit(chat['id'],TurnSpec(prompt='architecture',request_key='two',use_memory=False))
    assert runtime.chat(chat['id'])['session_id'] is None
    await asyncio.gather(*runtime.jobs.values());runtime.jobs.clear()
    with pytest.raises(ValueError):runtime.submit(chat['id'],TurnSpec(prompt='architecture',request_key='two',use_memory=True))


@pytest.mark.asyncio
async def test_real_pytest_receipt_and_versioned_acceptance_api(engine,tmp_path):
    # Real pytest child process, temporary project and DB; no models or user files.
    app=create_app(engine=engine);s=app.state.core
    (tmp_path/'test_fixture.py').write_text('def test_real_evidence():\n    assert 2+2 == 4\n',encoding='utf-8')
    project=app.state.workspace.create_project('Pilot',str(tmp_path))
    task=generated(s,project,allowed_tools=['read_workspace','pytest'],allowed_paths=['test_fixture.py'],acceptance_criteria=[{'criterion_id':'C1','text':'Fixture tests pass','evidence_type':'test_execution'}])
    async with AsyncClient(transport=ASGITransport(app),base_url='http://test') as client:
        result=await client.post('/api/core/tasks/'+task['id']+'/checks/pytest',json={'paths':['test_fixture.py']})
        assert result.status_code==200 and result.json()['passed']
        task=s.task(task['id']);eid=result.json()['evidence_id']
        reviewed=await client.post('/api/core/tasks/'+task['id']+'/review',json=review_payload(task,refs=[eid]))
        assert reviewed.status_code==200 and reviewed.json()['state']=='ACCEPT_CANDIDATE'
        payload={'artifact_hash':task['artifact_hash'],'review_revision':reviewed.json()['review_revision']}
        accepted=await client.post('/api/core/tasks/'+task['id']+'/accept',json=payload)
        assert accepted.status_code==200 and accepted.json()['state']=='ACCEPTED'
        assert (await client.get('/head')).status_code==200
        assert (await client.get('/api/core/tasks/missing')).status_code==404
        forbidden=await client.post('/api/core/tasks/'+task['id']+'/checks/pytest',json={'paths':['../test_fixture.py']})
        assert forbidden.status_code==409
