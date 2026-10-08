"""Post-run raw-usage/hash audit and independent final-program re-execution."""
import hashlib,json
from pathlib import Path
import benchmark_v2 as E
HERE=Path(__file__).resolve().parent
E.verify();r=json.loads((HERE/'results.json').read_text(encoding='utf-8'))
assert r['status']=='complete','Incomplete trial set'
assert E.sha(HERE/'plan.json')==r['plan_hash']
for path,h in r['receipt_hashes'].items():assert E.sha(HERE/path)==h,path
tasks={t['id']:t for t in json.loads((HERE/'tasks.json').read_text(encoding='utf-8'))}
old,new=E.FluxAdapter(),E.Optimizer();rechecks=[];failures=[];cost_overrides=[]
for file in sorted((HERE/'trials').glob('*.json')):
    t=json.loads(file.read_text(encoding='utf-8'));task=tasks[t['task']]
    expected_minimal=t['arm'].endswith('v2')
    for label in t['labels']:
        receipt=json.loads((HERE/'receipts'/(label+'.json')).read_text(encoding='utf-8'))
        assert receipt['minimal']==expected_minimal
        done=[x for x in receipt['raw_events'] if x.get('type')=='turn.completed']
        assert receipt['usage']==(done[-1].get('usage',{}) if done else {})
        assert receipt['completed']==(bool(done) and receipt['exit_code']==0)
        assert receipt['tool_events']==0
        if receipt['usage']:
            assert receipt['usage']['input_tokens']>=receipt['usage']['cached_input_tokens']+receipt['usage'].get('cache_write_input_tokens',0)
            assert receipt['usage']['output_tokens']>=receipt['usage'].get('reasoning_output_tokens',0)
    final=json.loads((HERE/'receipts'/(t['labels'][-1]+'.json')).read_text(encoding='utf-8'))
    method=t['programs'][-1]['method'];adapter=new if method=='compact' else old
    effective,program=adapter.interpret(task,final,method);verdict=E.check(task,effective,'full')
    assert verdict['pass']==t['audit']['pass'],file
    assert t['false_acceptance']==(t['policy_accepted'] and not verdict['pass'])
    rechecks.append({'trial':file.stem,'correct':verdict['pass'],'method':method})
    for n,c in enumerate(t['checks']):
        if not c['pass']:failures.append({'trial':file.stem,'attempt':n,'reason':c['reason']})
    if t['route'].get('raw_model_overridden'):cost_overrides.append({'trial':file.stem,'raw':t['route']['raw_laya_model'],'chosen':t['route']['model']})
    for label in t['local_labels']:
        local=json.loads((HERE/'laya_receipts'/(label+'.json')).read_text(encoding='utf-8'));u=local['output']['usage']
        assert local['checkpoint_revision']=='7b928d828b7b0e022f929d9bd2e44165aa270148'
        assert u['output_tokens']==0 and not u.get('truncated') and not u.get('truncated_questions') and u.get('state_tokens_dropped',0)==0

probes=[json.loads(p.read_text(encoding='utf-8')) for p in (HERE/'receipts').glob('dev_*.json')]
assert len(probes)==6 and all(p['completed'] and not p['tool_events'] for p in probes)
probe_cost=sum(E.B.cost(p) for p in probes)
facts={'passed':True,'trials_reaudited':len(rechecks),'hashes_verified':len(r['receipt_hashes']),
    'rechecks':rechecks,'failures':failures,'cost_router_overrides':cost_overrides,
    'development_probe_calls':6,'development_probe_api_equivalent_usd':probe_cost,
    'total_experiment_api_equivalent_known_lower_bound':probe_cost+sum(s['cost_known_lower_bound'] for s in r['summary'].values()),
    'actual_billing_usd':None}
E.write(HERE/'audit-results.json',facts)
print(json.dumps({k:v for k,v in facts.items() if k not in ['rechecks']},ensure_ascii=False,indent=2))
