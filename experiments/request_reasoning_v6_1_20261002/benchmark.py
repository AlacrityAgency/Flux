"""Frozen, actual conditional pipelines; receipts include raw provider events.

Commands: freeze, live, analyze. No gold loaded during live. Resume reuses receipts
without changing their content. Maximum 144 calls, four concurrent provider calls.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from fractions import Fraction
import hashlib
import json
import os
import random
import shutil
import subprocess
import sys
import threading
import time
import numpy as np
import tiktoken
import engine as E

HERE=Path(__file__).resolve().parent
RUNS=HERE/'model_runs'
FILES=['engine.py','worker.py','make_tasks.py','benchmark.py','test_engine.py','tasks.json','evaluation_only/gold.json','ALGORITHM.fa.md']
SEM=threading.Semaphore(4)
ENC=tiktoken.get_encoding('o200k_base')
MAX_CALLS=144
CALL_LOCK=threading.Lock()
CALL_COUNT=0
CODEX=shutil.which('codex')


def sha(s):
    return hashlib.sha256(s.encode('utf-8')).hexdigest()


def hashes():
    out={f:sha((HERE/f).read_text(encoding='utf-8')) for f in FILES}
    out.update({'v6/'+f:sha((E.BASE/f).read_text(encoding='utf-8')) for f in ['reasoning_v6.py','worker_v6.py','tasks_v6.py']})
    return out


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2),encoding='utf-8')


def freeze():
    if (HERE/'frozen-plan.json').exists():
        raise SystemExit('Already frozen; do not overwrite.')
    ts=load(HERE/'tasks.json')
    write(HERE/'frozen-plan.json', {'hashes':hashes(),'tasks':len(ts),'samples':1,'effort':'low',
          'max_calls':MAX_CALLS,'provider_concurrency':4,'arms':['v6','v6.1','sol_direct','luna_B_shared'],
          'seeds':{'tasks':610120261002,'arm_order':6101},
          'primary':['answer_accuracy','reported_input_tokens_per_task','reported_output_tokens_per_task'],
          'secondary':['visible_prompt_tokens','latency_p50_p95','sol_share','false_acceptance'],
          'timing':'actual conditional pipelines; initial A/B concurrent; no replay timing',
          'inference_gold_access':False,'limits':'144 model calls, timeout180s/call, code timeout2.5s, no retries',
          'notes':'Luna B is a shared ablation, not an additional physical call; no claim of equivalence.'})
    print(json.dumps({'frozen_tasks':len(ts),'max_calls':MAX_CALLS}))


def verify():
    if load(HERE/'frozen-plan.json')['hashes']!=hashes():
        raise SystemExit('Frozen content changed. Refusing execution or analysis.')


def call(model, prompt, label):
    global CALL_COUNT
    file=RUNS/(label+'.json')
    if file.exists():
        r=load(file)
        assert r['prompt_sha256']==sha(prompt) and r['model_requested']==model
        return r
    with SEM:
        with CALL_LOCK:
            if CALL_COUNT>=MAX_CALLS:
                raise RuntimeError('Call budget exhausted')
            CALL_COUNT+=1
        env=dict(os.environ)
        for n in ['OPENAI_API_KEY','CODEX_API_KEY','OPENAI_BASE_URL','CODEX_ACCESS_TOKEN']:
            env.pop(n,None)
        env.update(PYTHONUTF8='1',NO_COLOR='1')
        command=[CODEX,'exec','--ignore-user-config','--ephemeral','--json','--skip-git-repo-check','--sandbox','read-only',
                 '-C',str(HERE/'model_sandbox'),'-c','approval_policy="never"','-c','model_reasoning_effort="low"','-m',model,'-']
        start=time.perf_counter()
        try:
            proc=subprocess.run(command,input=prompt,text=True,encoding='utf-8',capture_output=True,env=env,timeout=180)
            raw,err,exit_code,timed=proc.stdout,proc.stderr[-3000:],proc.returncode,False
        except subprocess.TimeoutExpired as ex:
            raw,err,exit_code,timed=ex.stdout or '',ex.stderr or '',None,True
            raw=raw.decode('utf-8','replace') if isinstance(raw,bytes) else raw
            err=err.decode('utf-8','replace') if isinstance(err,bytes) else err
        elapsed=time.perf_counter()-start
        events=[]
        for line in raw.splitlines():
            try: events.append(json.loads(line))
            except ValueError: pass
        done=[e for e in events if e.get('type')=='turn.completed']
        texts=[e.get('item',{}).get('text','') for e in events if e.get('type')=='item.completed' and e.get('item',{}).get('type')=='agent_message']
        tools=[e for e in events if e.get('item',{}).get('type') in ['command_execution','mcp_tool_call','web_search']]
        r={'label':label,'model_requested':model,'prompt':prompt,'prompt_sha256':sha(prompt),
           'provider_completed':bool(done) and exit_code==0 and not timed,'exit_code':exit_code,'timed_out':timed,
           'usage':done[-1].get('usage',{}) if done else {},'latency_seconds':elapsed,
           'visible_prompt_tokens':len(ENC.encode(prompt)),'text':'\n'.join(texts),
           'visible_output_tokens':len(ENC.encode('\n'.join(texts))),'tool_events':len(tools),
           'raw_events':events,'stderr':err,'billing_usd':None}
        with file.open('x',encoding='utf-8') as f: json.dump(r,f,ensure_ascii=False,indent=2)
        return r


def plain(out):
    return {k:(str(v) if isinstance(v,Fraction) else v) for k,v in out.items()}


def legacy_program(receipt,query):
    out={'accepted':False,'value':None,'status':'provider','exec_ms':0}
    if not receipt.get('provider_completed') or receipt.get('tool_events'): return out
    try:
        d=E.V6.parse_json(receipt['text'])
        r=E.V6.run_program(d['code'])
        value=E.V6.to_fraction(r.get('result')) if r['status']=='ok' else None
        return out | {'accepted':E.V6.sanity(value,E.V6.answer_spec(query)),'value':value,'status':r['status'],
                      'exec_ms':r['exec_ms'],'error':r.get('error')}
    except (ValueError,KeyError,TypeError): return out | {'status':'format'}


def task_live(task):
    q=task['query'];tid=task['id']
    results={}
    arms=['v6','v6.1','sol_direct']
    random.Random(6101+int(sha(tid)[:8],16)).shuffle(arms)
    for arm in arms:
        started=time.perf_counter();labels=[]
        if arm=='v6':
            def program(method):
                label=tid+'__v6_'+method
                receipt=call('gpt-6-luna',E.V6.program_prompt(q,method),label)
                return label,legacy_program(receipt,q)
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures=[pool.submit(program,m) for m in ['A','B']]
                a,b=[f.result() for f in futures]
            labels=[a[0],b[0]];oa,ob=a[1],b[1]
            accepted=oa['accepted'] and ob['accepted'] and E.V6.close(oa['value'],ob['value'],E.V6.answer_spec(q))
            initial=oa if accepted else ob
            results['luna_B_shared']={'value':str(ob['value']) if ob['value'] is not None else None,
                    'initial':plain(ob),'labels':[b[0]],'sol':False,
                    'latency_seconds':load(RUNS/(b[0]+'.json'))['latency_seconds']+ob['exec_ms']/1000}
            diagnostics={'A':plain(oa),'B':plain(ob),'agreement':accepted}
        elif arm=='v6.1':
            label=tid+'__v61_graph'
            receipt=call('gpt-6-luna',E.prompt(q),label);labels=[label]
            initial=E.interpret(receipt,q,'graph');accepted=initial['accepted']
            diagnostics={'graph':plain(initial)}
        else:
            label=tid+'__sol_direct'
            receipt=call('gpt-6.1-sol',E.V6.direct_prompt(q),label);labels=[label]
            initial=E.interpret(receipt,q,'direct');accepted=initial['accepted']
            diagnostics={}
        final=initial
        escalated=arm!='sol_direct' and not accepted
        if escalated:
            label=tid+'__'+arm.replace('.','')+'_fallback'
            receipt=call('gpt-6.1-sol',E.V6.direct_prompt(q),label);labels.append(label)
            final=E.interpret(receipt,q,'direct')
        results[arm]={'value':str(final['value']) if final['value'] is not None else None,
                     'initial':plain(initial),'accepted_initial':accepted,'sol':escalated,'labels':labels,
                     'latency_seconds':time.perf_counter()-started,'diagnostics':diagnostics}
    write(HERE/'trials'/f'{tid}.json', {'task':tid,'family':task['family'],'lang':task['lang'],'arm_order':arms,'results':results})
    return tid


def live():
    global CALL_COUNT
    verify()
    RUNS.mkdir(exist_ok=True);(HERE/'trials').mkdir(exist_ok=True);(HERE/'model_sandbox').mkdir(exist_ok=True)
    CALL_COUNT=len(list(RUNS.glob('*.json')))
    tasks=load(HERE/'tasks.json')
    pending=[t for t in tasks if not (HERE/'trials'/f'{t["id"]}.json').exists()]
    started=time.perf_counter()
    with ThreadPoolExecutor(max_workers=2) as pool:
        fs=[pool.submit(task_live,t) for t in pending]
        for i,f in enumerate(as_completed(fs),1):
            print(json.dumps({'done':i,'pending':len(pending),'task':f.result(),'physical_calls':CALL_COUNT,'elapsed_s':round(time.perf_counter()-started)}),flush=True)


def analyze():
    verify()
    gold=load(HERE/'evaluation_only/gold.json');tasks=load(HERE/'tasks.json')
    rows=[]
    for task in tasks:
        trial=load(HERE/'trials'/f'{task["id"]}.json')
        for arm,r in trial['results'].items():
            receipts=[load(RUNS/(label+'.json')) for label in r['labels']]
            value=E.V6.to_fraction(r['value'])
            correct=E.V6.grade(value,gold[task['id']],E.V6.answer_spec(task['query']))
            row={'task':task['id'],'family':task['family'],'lang':task['lang'],'arm':arm,'correct':correct,
                 'value':r['value'],'gold':gold[task['id']],'calls':len(receipts),'sol':r['sol'],
                 'latency_seconds':r['latency_seconds'],'initial_accepted':r.get('accepted_initial',False),
                 'input_tokens':sum(x['usage'].get('input_tokens',0) for x in receipts),
                 'cached_input_tokens':sum(x['usage'].get('cached_input_tokens',0) for x in receipts),
                 'output_tokens':sum(x['usage'].get('output_tokens',0) for x in receipts),
                 'visible_prompt_tokens':sum(x['visible_prompt_tokens'] for x in receipts),
                 'visible_output_tokens':sum(x['visible_output_tokens'] for x in receipts),
                 'all_completed':all(x['provider_completed'] and not x['tool_events'] for x in receipts)}
            rows.append(row)
    def summary(rs):
        return {'n':len(rs),'correct':sum(r['correct'] for r in rs),'accuracy':np.mean([r['correct'] for r in rs]),
                'false_accepts':sum(r['initial_accepted'] and not r['correct'] for r in rs),
                'sol_share':np.mean([r['sol'] for r in rs]),
                'latency_p50':float(np.median([r['latency_seconds'] for r in rs])),
                'latency_p95':float(np.percentile([r['latency_seconds'] for r in rs],95)),
                'means':{key:float(np.mean([r[key] for r in rs])) for key in ['calls','input_tokens','cached_input_tokens','output_tokens','visible_prompt_tokens','visible_output_tokens']}}
    arms=['v6','v6.1','sol_direct','luna_B_shared']
    metrics={a:summary([r for r in rows if r['arm']==a]) for a in arms}
    by_set={s:{a:summary([r for r in rows if r['arm']==a and r['family'].startswith('logic_')==flag]) for a in arms}
            for s,flag in [('logic',True),('math',False)]}
    rng=np.random.default_rng(6101)
    diffs={}
    for other in ['v6','sol_direct','luna_B_shared']:
        aa={r['task']:r['correct'] for r in rows if r['arm']=='v6.1'}
        bb={r['task']:r['correct'] for r in rows if r['arm']==other}
        d=np.array([int(aa[t['id']])-int(bb[t['id']]) for t in tasks])
        boots=np.mean(d[rng.integers(0,len(d),(10000,len(d)))],axis=1)
        diffs[other]={'difference':float(np.mean(d)),'paired_bootstrap_95':list(np.percentile(boots,[2.5,97.5])),
                      'v61_wins':int(sum(d==1)),'v61_losses':int(sum(d==-1))}
    physical=[load(f) for f in RUNS.glob('*.json')]
    result={'metrics':metrics,'by_set':by_set,'paired_differences':diffs,'rows':rows,
            'physical_calls':len(physical),'physical_completed':sum(r['provider_completed'] for r in physical),
            'tool_events':sum(r['tool_events'] for r in physical),
            'total_reported_input_tokens':sum(r['usage'].get('input_tokens',0) for r in physical),
            'frozen_hashes_verified':True,'timing':'actual; semaphore queue time included in controller latency',
            'limitations':['24 synthetic finite-domain tasks, one sample each','model-written check can share solver errors',
                          'CLI scaffolding dominates provider input; billing unavailable','no weight learning or general noninferiority claim']}
    write(HERE/'results.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ['rows']},ensure_ascii=False,indent=2))


if __name__=='__main__':
    {'freeze':freeze,'live':live,'analyze':analyze}[sys.argv[1]]()
