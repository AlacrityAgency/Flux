"""Fresh paired Senior/GOAT ablation with actual Flux adapters and local Laya."""
import hashlib, importlib.util, json, random, statistics, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent/'router_policy_20261006'
sys.path.insert(0,str(BASE))
spec = importlib.util.spec_from_file_location('original_benchmark',BASE/'benchmark.py')
B = importlib.util.module_from_spec(spec);spec.loader.exec_module(B)
sys.path.insert(0,str(HERE))
from provider import invoke
from adapter import FluxAdapter, PROGRAM_FAMILIES, execute, V61, tokens
from decision import Decisions, answers, final_action

ARMS = ['senior_base','goat_base','senior_flux_laya','goat_flux_laya']
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
def sources():
    files=[HERE/x for x in ['benchmark.py','adapter.py','decision.py','program_worker.py','provider.py']]
    files += [BASE/x for x in ['benchmark.py','worker.py','tasks.json']]
    files += [HERE.parent/'request_memory_v5_20261002'/x for x in ['contracts.py','memory_v5.py','engine_v5.py']]
    files += [HERE.parent/'request_reasoning_v6_1_20261002'/x for x in ['engine.py','worker.py']]
    files += [HERE.parent/'request_memory_v6_20261002/reasoning_v6.py',HERE/'checkpoint-provenance.json']
    files += [HERE.parents[1]/'src/flux/core/context.py',HERE.parents[1]/'src/flux/knowledge/retrieval.py']
    files += list((HERE/'checkpoint/multilingual').rglob('*.json'))
    files += list((HERE/'checkpoint/multilingual').rglob('*.safetensors'))
    return {str(p.relative_to(HERE.parents[1])):sha(p) for p in files}

def selfcheck():
    assert final_action('accept',False,0)=='escalate'
    assert final_action('accept',False,2)=='stop'
    assert final_action('escalate',True,0)=='escalate'
    assert final_action('stop',True,2)=='accept'
    assert not V61.checker_audit('def solve(): return 1\ndef check(a): return True')
    assert not V61.checker_audit('def solve(): return 1\ndef check(a): return a==solve()')
    assert execute('def solve(): return {"count":2}\ndef check(a): return sum([1,1])==a["count"]')['answer']=={'count':2}
    assert not execute('import os\ndef solve(): return {}\ndef check(a): return len(a)==0')['pass']
    assert not execute('def solve(): return {"count":2}\ndef check(a): return a["count"]==3')['pass']
    a=FluxAdapter();tasks=B.build_tasks()
    for t in tasks:
        _,p=a.prepare(t,'program' if t['family'] in PROGRAM_FAMILIES else 'direct')
        assert p['memory_route']=='self_contained' and p['selected_units']==0
    assert not B.check(tasks[1],{'completed':True,'tool_events':0,'text':'{"subtotal_cents":0,"tax_cents":0,"total_cents":0}'})['pass']
    print('10+ local safety, encoding, retrieval, checker and wrong-answer assertions passed')

def freeze():
    if (HERE/'plan.json').exists():raise ValueError('Already frozen')
    assert (HERE/'checkpoint/multilingual/model.safetensors').exists()
    # Loading can atomically repair tokenizer metadata; run smoke BEFORE freezing.
    write(HERE/'tasks.json',json.loads((BASE/'tasks.json').read_text(encoding='utf-8')))
    write(HERE/'plan.json',{'date':'2026-10-06','arms':ARMS,'tasks':6,'samples_per_arm_task':1,
      'seed':61106,'concurrency':2,'max_calls':84,'timeout_s':240,'models':B.MODELS,
      'rates':B.RATES,'pricing_source':'https://developers.openai.com/api/docs/pricing',
      'source_hashes':sources(),'task_hash':sha(HERE/'tasks.json'),
      'laya_revision':'7b928d828b7b0e022f929d9bd2e44165aa270148','laya_checkpoint':'multilingual',
      'laya_packages':{'laya':'0.3.28','transformers':'4.57.6','torch':'2.6.0+cu124'},
      'baseline':'Fresh independent executions of previous Senior and GOAT, same prompt and risk floors, up to 2 escalations. No answer replay.',
      'enhanced':'Front Laya: GOAT model/effort/verification; Senior retains Luna low and Laya chooses verification depth with floors. Actual v5 retrieval skips archive for self-contained tasks; production context admission. v6.1 adapted graph+solve+check for arithmetic/count/scheduling, JSON worker. Code/extraction direct. Last Laya chooses accept/escalate/stop after local checks. Failed checks never accepted; max 3 solver calls.',
      'method_selection':'Arithmetic/count/scheduling use program on every enhanced attempt; other families direct. Method determined before outputs; no benchmark gold in front decisions.',
      'risk_floor':'Low light; medium medium; high full. All final answers independent full audit. Senior base full.',
      'end_gate':'Accept iff local verifier passed and Laya did not request an available escalation. Wrong Laya accept forced to escalate/stop. Stop cannot discard a verified result.',
      'feedback':'Base includes prior output as original. Enhanced only bounded public error, no original program or graph; no gold.',
      'limitations':'Six synthetic tasks, one run each; no agent tools. Whole-stack ablation, no isolated causality per component. Empty project snapshot gives zero RAG savings; no production hookup. Account quota usage valued at API rates, actual dollars unknown; cache and network uncontrolled. Laya probabilities uncalibrated for routing; model identities requested not attested.',
      'criterion':'Compare all six tasks with same full-audit success and false-accept rate. Savings exact only when all call usage known.'})
    print('Frozen paired experiment')

def verify():
    p=json.loads((HERE/'plan.json').read_text(encoding='utf-8'))
    assert p['task_hash']==sha(HERE/'tasks.json')
    assert p['source_hashes']==sources(),'Source/checkpoint changed after freeze'

def routed_level(route,task):
    ranks={'light':0,'medium':1,'full':2}
    floor={'low':'light','medium':'medium','high':'full'}[task['risk_floor']]
    return route['verify'] if ranks[route['verify']]>=ranks[floor] else floor

def call(model,effort,prompt,label):
    if len(list((HERE/'receipts').glob('*.json')))>=84 and not (HERE/'receipts'/(label+'.json')).exists():raise ValueError('Budget reached')
    return invoke(model,effort,prompt,label,timeout=240)

def run_task(task,decisions,flux):
    order=ARMS[:];random.Random(61106+int(task['id'][1:])).shuffle(order)
    for arm in order:
        path=HERE/'trials'/(task['id']+'__'+arm+'.json')
        if path.exists():continue
        start=time.perf_counter();labels=[];local_labels=[];checks=[];preparations=[];programs=[];route=None;actions=[]
        enhanced=arm.endswith('flux_laya');goat=arm.startswith('goat')
        if enhanced:
            label=task['id']+'__'+arm+'_front'
            front=decisions.front(task,label);local_labels.append(label);d=answers(front)
            route={'model':B.MODELS[['luna','sol','astra'].index(d['model']['choice'])],
                'effort':d['effort']['choice'],'verify':d['verify']['choice']}
            model=route['model'] if goat else B.MODELS[0]
            effort=route['effort'] if goat else 'low'
            level=routed_level(route,task)
        elif goat:
            # Exact previous GOAT router wording for a fresh baseline.
            prompt='You are a cost-aware task router. Do not solve the task and do not use tools. Pick the least expensive model and effort likely to solve it correctly. Models in ascending cost: gpt-6-luna, gpt-6.1-sol, gpt-6-astra. Allowed effort low, medium, high, max. Pick verify light for low-impact simple data tasks, medium for moderate risk, full for high risk or hard reasoning. Return ONLY JSON {"model":"...","effort":"...","verify":"light|medium|full","reason":"brief"}. Task metadata: '+json.dumps({k:task[k] for k in ['family','risk_floor']})+'\nTask:\n'+task['prompt']
            label=task['id']+'__'+arm+'_router';r=call(B.MODELS[0],'low',prompt,label);labels.append(label)
            try:
                route=B.parse(r['text']);assert r['completed'] and not r['tool_events']
                assert route['model'] in B.MODELS and route['effort'] in ['low','medium','high','max'] and route['verify'] in ['light','medium','full']
            except Exception:route={'model':B.MODELS[1],'effort':'high','verify':'full'}
            model,effort,level=route['model'],route['effort'],routed_level(route,task)
        else:model,effort,level=B.MODELS[0],'low','full'
        method='program' if enhanced and task['family'] in PROGRAM_FAMILIES else 'direct'
        prompt=B.PREFIX+task['prompt'];error=None;accepted=False
        for attempt in range(3):
            if enhanced:
                prompt,prep=flux.prepare(task,method,error);preparations.append(prep)
            label=task['id']+'__'+arm+'_solve'+str(attempt)
            r=call(model,effort,prompt,label);labels.append(label)
            effective,program=flux.interpret(task,r,method) if enhanced else (r,{'method':'direct','pass':True})
            programs.append(program)
            c=B.check(task,effective,level)
            if enhanced and not program['pass']:c['reason']='Program validation: '+program.get('reason','failed')
            checks.append(c)
            if enhanced:
                label=task['id']+'__'+arm+'_end'+str(attempt)
                end=decisions.end(task,effective,c,attempt,label);local_labels.append(label)
                choice=answers(end)['action']['choice'];action=final_action(choice,c['pass'],attempt)
                actions.append({'proposed':choice,'applied':action,'guard_override':choice!=action})
                accepted=action=='accept'
            else:accepted=c['pass'];action='accept' if accepted else 'escalate' if attempt<2 else 'stop'
            if action in ['accept','stop'] or attempt==2:break
            model=B.MODELS[min(2,B.MODELS.index(model)+1)];effort='high';level='full';error=c['reason'] or 'Laya requested stronger verification despite passing checks'
            if not enhanced:prompt=B.PREFIX+task['prompt']+'\nPrevious output:\n'+r['text']+'\nLocal verifier failure: '+c['reason']+'\nReturn a corrected JSON answer.'
        audit=B.check(task,effective,'full')
        trial={'task':task['id'],'family':task['family'],'arm':arm,'order':order,'route':route,
            'labels':labels,'local_labels':local_labels,'checks':checks,'preparations':preparations,
            'programs':programs,'actions':actions,'policy_accepted':accepted,'audit':audit,
            'false_acceptance':accepted and not audit['pass'],'retries':len(checks)-1,
            'latency_s':time.perf_counter()-start,'final_model':model,'final_effort':effort}
        write(path,trial)
        print(json.dumps({'trial':path.stem,'correct':audit['pass'],'retries':trial['retries'],'route':route}),flush=True)

def live():
    verify();decisions=Decisions();flux=FluxAdapter()
    write(HERE/'runtime.json',{'laya_load_s':decisions.load_s,'index_s':flux.index_seconds})
    tasks=json.loads((HERE/'tasks.json').read_text(encoding='utf-8'))
    with ThreadPoolExecutor(max_workers=2) as pool:
        for future in as_completed([pool.submit(run_task,t,decisions,flux) for t in tasks]):future.result()
    analyze()

def analyze():
    verify();summary={};receipt_hashes={}
    for arm in ARMS:
        trials=[json.loads(p.read_text(encoding='utf-8')) for p in sorted((HERE/'trials').glob('*__'+arm+'.json'))]
        rs=[json.loads((HERE/'receipts'/(label+'.json')).read_text(encoding='utf-8')) for t in trials for label in t['labels']]
        ls=[json.loads((HERE/'laya_receipts'/(label+'.json')).read_text(encoding='utf-8')) for t in trials for label in t['local_labels']]
        known=all(B.cost(r) is not None for r in rs)
        total={k:sum(r['usage'].get(k,0) for r in rs) for k in ['input_tokens','cached_input_tokens','output_tokens','reasoning_output_tokens']}
        summary[arm]={'tasks':len(trials),'correct':sum(t['audit']['pass'] for t in trials),
            'false_accepts':sum(t['false_acceptance'] for t in trials),'calls':len(rs),
            'retries':sum(t['retries'] for t in trials),'provider_failures':sum(not r['completed'] for r in rs),
            'unknown_usage_calls':sum(B.cost(r) is None for r in rs),'usage_complete':known,
            'usage_known_sum':total,'provider_total_tokens_known':total['input_tokens']+total['output_tokens'],
            'api_equivalent_usd_exact':sum(B.cost(r) for r in rs) if known else None,
            'api_equivalent_usd_known_lower_bound':sum(B.cost(r) or 0 for r in rs),
            'actual_billing_usd':None,'provider_p50_s':statistics.median([r['latency_s'] for r in rs]) if rs else None,
            'trial_p50_s':statistics.median([t['latency_s'] for t in trials]) if trials else None,
            'visible_prompt_tokens':sum(tokens(r['prompt']) for r in rs),
            'laya_calls':len(ls),'laya_seconds':sum(x['latency_s'] for x in ls),
            'laya_p50_s':statistics.median([x['latency_s'] for x in ls]) if ls else None,
            'laya_local_state_tokens':sum(x['local_state_tokens'] for x in ls),
            'laya_encoder_input_tokens':sum(x['output'].get('usage',{}).get('input_tokens',0) for x in ls),
            'laya_truncated_calls':sum(bool(x['output'].get('usage',{}).get('truncated')) for x in ls),
            'laya_peak_gpu_bytes':max([x['peak_allocated_bytes'] for x in ls],default=0),
            'laya_guard_overrides':sum(a['guard_override'] for t in trials for a in t['actions']),
            'program_attempts':sum(x['method']=='program' for t in trials for x in t['programs']),
            'program_passes':sum(x['method']=='program' and x['pass'] for t in trials for x in t['programs']),
            'selected_memory_units':sum(x['selected_units'] for t in trials for x in t['preparations'])}
    comparisons={}
    for name in ['senior','goat']:
        a,b=summary[name+'_base'],summary[name+'_flux_laya']
        valid=a['tasks']==b['tasks']==6 and a['correct']==b['correct']==6 and a['false_accepts']==b['false_accepts']==0
        complete=a['usage_complete'] and b['usage_complete']
        comparisons[name]={'quality_equal_all_six':valid,'usage_complete':complete,
            'token_reduction_percent':100*(1-b['provider_total_tokens_known']/a['provider_total_tokens_known']) if valid and complete else None,
            'api_equivalent_cost_reduction_percent':100*(1-b['api_equivalent_usd_exact']/a['api_equivalent_usd_exact']) if valid and complete else None,
            'speedup_p50':a['trial_p50_s']/b['trial_p50_s'] if valid else None}
    for folder in ['receipts','laya_receipts','trials']:
        for p in (HERE/folder).glob('*.json'):receipt_hashes[str(p.relative_to(HERE))]=sha(p)
    result={'summary':summary,'comparisons':comparisons,'receipt_hashes':receipt_hashes,
        'plan_hash':sha(HERE/'plan.json'),'status':'complete' if all(x['tasks']==6 for x in summary.values()) else 'partial'}
    write(HERE/'results.json',result)
    print(json.dumps({'summary':summary,'comparisons':comparisons},ensure_ascii=False,indent=2))
    report=['# آزمون Flux + Laya روی Senior و GOAT','',
      'مقایسهٔ تازه و مستقل روی همان شش تسک ثابت؛ هر مسیر یک نمونه. مصرف از رویداد واقعی `turn.completed` در Codex گرفته شده است. هزینهٔ دلاری معادل تعرفهٔ API است؛ صورتحساب واقعی حساب ChatGPT مشخص نیست. خروجی شامل توکن استدلال است و دوباره جمع نمی‌شود.','',
      '|مسیر|درست|فراخوانی مدل|تکرار|ورودی|کش ورودی|خروجی شامل استدلال|مجموع توکن معلوم|فراخوانی با مصرف نامعلوم|دلار معلوم|',
      '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for arm,s in summary.items():
        u=s['usage_known_sum'];report.append(f"|{arm}|{s['correct']}/{s['tasks']}|{s['calls']}|{s['retries']}|{u['input_tokens']}|{u['cached_input_tokens']}|{u['output_tokens']}|{s['provider_total_tokens_known']}|{s['unknown_usage_calls']}|{s['api_equivalent_usd_known_lower_bound']:.6f}|")
    report += ['', 'اگر مصرف نامعلوم وجود داشته باشد، جمع توکن و دلار فقط حد پایین است و درصد کاهش قابل ادعا نیست.','']
    for name,c in comparisons.items():report.append(f"- {name}: کاهش توکن = {c['token_reduction_percent']}٪؛ کاهش هزینه = {c['api_equivalent_cost_reduction_percent']}٪؛ نسبت سرعت میانه = {c['speedup_p50']}.")
    report += ['', 'Laya چندزبانه با وزن واقعی روی CUDA اجرا شد. احتمالات برای این دامنه کالیبره نشده‌اند. مسیریاب GOAT مدل، تلاش و بررسی را انتخاب می‌کند؛ Senior ابتدا Luna low می‌ماند. تصمیم پایان Laya با شواهد محلی محدود می‌شود؛ پاسخ ردشده قابل قبول نیست. گراف و checker تولیدی مدل، تضمین معنایی نیستند؛ همهٔ پاسخ‌های نهایی ارزیابی مستقل کامل دارند.','',
      '|مسیر افزوده|فراخوانی Laya|مجموع ثانیهٔ Laya|میانهٔ ثانیه|بیشترین حافظه GPU گیگابایت|برنامهٔ موفق/تلاش|Override گیت|','|---|---:|---:|---:|---:|---:|---:|']
    for arm in ['senior_flux_laya','goat_flux_laya']:
        s=summary[arm];report.append(f"|{arm}|{s['laya_calls']}|{s['laya_seconds']:.3f}|{s['laya_p50_s']}|{s['laya_peak_gpu_bytes']/1024**3:.3f}|{s['program_passes']}/{s['program_attempts']}|{s['laya_guard_overrides']}|")
    report += ['', 'حافظه v5 واقعاً اجرا شده اما snapshot خالی است: تسک‌ها مستقل هستند، بنابراین واحد حافظهٔ انتخابی صفر و صرفه‌جویی RAG در این آزمایش صفر است. مسئله‌های محاسباتی از گراف محدودیت + solve/check نسخهٔ v6.1 با خروجی JSON استفاده می‌کنند؛ استخراج و تولید تابع مسیر مستقیم دارند. پذیرش بودجهٔ کانتکست از کد واقعی Flux اجرا می‌شود. بازخورد افزوده کوتاه است و کد قبلی را تکرار نمی‌کند.','',
      'این آزمون کل ترکیب را مقایسه می‌کند؛ اثر مستقل Laya، گراف و کوتاه‌کردن بازخورد تفکیک نشده است. شش مسئله و یک تکرار برای نتیجهٔ عمومی یا ادعای 15x کافی نیست. کش، شبکه و کانتکست پنهان CLI کنترل نشده‌اند. کد در experiments است و به سرویس اصلی Flux وصل نشده.','',
      'دستور بازتولید: `.venv/Scripts/python.exe -X utf8 benchmark.py selfcheck|live|analyze`. `live` رسید همان درخواست را برای ادامهٔ اجرای قطع‌شده نگه می‌دارد؛ برای نمونهٔ جدید باید پوشهٔ experiment جدید ساخت. `plan.json` هش کد و checkpoint و تسک‌ها را قفل می‌کند؛ `results.json` هش تمام رسیدها را نگه می‌دارد.']
    (HERE/'REPORT.fa.md').write_text('\n'.join(report)+'\n',encoding='utf-8')

if __name__=='__main__':
    if sys.argv[1]=='selfcheck':selfcheck()
    elif sys.argv[1]=='smoke':
        d=Decisions();print('load_s',d.load_s);print(d.front(B.build_tasks()[0],'smoke'))
    elif sys.argv[1]=='freeze':freeze()
    elif sys.argv[1]=='live':live()
    elif sys.argv[1]=='analyze':analyze()
    else:raise SystemExit('selfcheck | smoke | freeze | live | analyze')
