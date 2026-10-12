"""Separately preregistered calculator-enabled normal solver; primary run unchanged."""
import concurrent.futures
import datetime
import json
import random
import time
from pathlib import Path
import benchmark as B
from transport import invoke

HERE=B.HERE/'calculator_ablation'
INSTRUCTIONS=B.COMMON+'\nSolve directly by writing a short Python program. No skills, references, generated checker, Laya, online verification or repair feedback. The caller executes your solve(facts) as a calculator. Return only {"code":"source"}.\n'

def prepare():
    HERE.mkdir(exist_ok=True)
    if (HERE/'plan.json').exists():raise FileExistsError('ablation frozen')
    ts=[t for t in B.read(B.HERE/'tasks.json') if t['track']=='reasoning']
    order=[t['id'] for t in ts];random.Random(B.SEED+1007).shuffle(order)
    (HERE/'instructions.txt').write_text(INSTRUCTIONS,encoding='utf-8')
    B.write(HERE/'plan.json',{'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
      'status':'secondary prospective extension; not primary','tasks':12,'repetitions':1,'order':order,
      'model':['codex','gpt-6.1-sol','medium'],'timeout_s':90,'concurrency':2,'max_calls':12,
      'primary_plan_sha256':B.sha(B.HERE/'plan.json'),'task_sha256':B.sha(B.HERE/'tasks.json'),
      'script_sha256':B.sha(Path(__file__)),'instructions_sha256':B.sha(HERE/'instructions.txt'),
      'reason':'Direct normal solver cannot execute calculations inside model sessions due tool-policy problem. Add a code-as-calculator normal arm with the same external restricted execution capability as FLux, without refs/checker/Laya/feedback. Extension declared after five primary trials, including C4 normal timeout, before any extension output. No primary task/arm/result changed; all 12 reasoning tasks included, no selection.',
      'limits':'Later time window, one repetition vs two in primary; compare task-mean primary receipts. No causal isolate of Laya/checker/retries; no claim of full desktop tool baseline. Raw code correctness independently audited, no online oracle feedback.'})
    print('Frozen secondary normal calculator ablation on all 12 reasoning tasks.')

def verify():
    B.verify();p=B.read(HERE/'plan.json')
    assert p['primary_plan_sha256']==B.sha(B.HERE/'plan.json') and p['task_sha256']==B.sha(B.HERE/'tasks.json')
    assert p['script_sha256']==B.sha(Path(__file__)) and p['instructions_sha256']==B.sha(HERE/'instructions.txt')

def trial(task):
    label=task['id']+'__normal_calculator';path=HERE/'trials'/(label+'.json')
    if path.exists():return B.read(path)
    prompt='Return only {"code":"Python source defining solve(facts)"}. Read all inputs from facts; no dataset literals. No generated check function is needed. The caller executes this program as a local calculator.\n'+B.public(task)
    receipt_path=HERE/'receipts'/(label+'.json');start=time.perf_counter()
    if receipt_path.exists():
        receipt=B.read(receipt_path);assert receipt['prompt']==prompt
    else:receipt=invoke('codex','gpt-6.1-sol','medium',prompt,receipt_path,HERE/'workspaces'/label,HERE/'instructions.txt',False,90)
    code=None;answer=None;accepted=False;failure=''
    if receipt['completed'] and not receipt['tool_events']:
        try:
            data=B.normalize(receipt['text']);code=data['code']
            # The common restricted worker supplies execution only, not a reference to the model.
            from subprocess import run
            import sys
            p=run([str(B.CLEAN_PYTHON),'-I','-S',str(B.SKILL/'scripts/compact_worker.py')],input=json.dumps({'code':code,'facts':task['facts']}),capture_output=True,text=True,encoding='utf-8',timeout=5)
            output=json.loads(p.stdout)
            if output.get('status')!='ok':raise ValueError('calculator worker failed')
            from validate_program import decode
            answer=decode(output['result']);accepted=True
        except Exception as exc:failure=type(exc).__name__+': '+str(exc)[:200]
    audit=B.full_audit(task,answer,code)
    result={'task_id':task['id'],'family':task['family'],'arm':'normal_calculator','label':label,
      'policy_accepted':accepted,'correct':accepted and audit['pass'],'false_accept':accepted and not audit['pass'],
      'answer':answer,'code':code,'audit':audit,'failure':failure,'latency_s':time.perf_counter()-start,
      'receipt':str(receipt_path.relative_to(B.HERE)),'usage':receipt['usage']}
    B.write(path,result);print(json.dumps({'ablation':label,'correct':result['correct'],'seconds':round(result['latency_s'],2)}),flush=True)
    return result

def live():
    verify();ts={t['id']:t for t in B.read(B.HERE/'tasks.json')};order=B.read(HERE/'plan.json')['order']
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        for x in pool.map(lambda tid:trial(ts[tid]),order):pass
    analyze()

def analyze():
    verify();trials=[B.read(p) for p in sorted((HERE/'trials').glob('*.json'))]
    usage_complete=all(t.get('usage') and all(k in t['usage'] for k in ['input_tokens','output_tokens']) for t in trials)
    total=sum((t.get('usage') or {}).get('input_tokens',0)+(t.get('usage') or {}).get('output_tokens',0) for t in trials)
    result={'complete':len(trials)==12,'trials':trials,'correct':sum(t['correct'] for t in trials),
      'false_accepts':sum(t['false_accept'] for t in trials),'usage_complete':usage_complete,'total_tokens_known':total,
      'plan_sha256':B.sha(HERE/'plan.json'),'receipt_hashes':{str(p.relative_to(B.HERE)):B.sha(p) for p in (HERE/'receipts').glob('*.json')}}
    B.write(HERE/'results.json',result);print(json.dumps({k:result[k] for k in ['complete','correct','false_accepts','usage_complete','total_tokens_known']},indent=2))

if __name__=='__main__':
    import sys
    {'prepare':prepare,'live':live,'analyze':analyze}[sys.argv[1]]()
