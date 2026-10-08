"""Fresh held-out inputs; independent local task audit, never sent to solvers."""
import importlib.util, json, random, subprocess, sys, time
from pathlib import Path
HERE=Path(__file__).resolve().parent
BASE=HERE.parent/'router_policy_20261006'
sys.path.insert(0,str(BASE))
spec=importlib.util.spec_from_file_location('task_oracles',BASE/'benchmark.py')
B=importlib.util.module_from_spec(spec);spec.loader.exec_module(B)

def build_tasks():
    rng=random.Random(611262026);tasks=[]
    for sample in range(2):
        records=[{'id':f'Z{i}','category':rng.choice(['alpha','beta','gamma']), 'active':rng.choice([True,False])} for i in range(1,17)]
        rng.shuffle(records)
        lines=[{'qty':rng.randint(1,8),'unit_cents':rng.randint(101,3900),'discount_percent':rng.choice([0,5,13,17,25,50])} for _ in range(4)]
        invoice={'lines':lines,'shipping':rng.randint(50,750),'tax_percent':rng.choice([6.5,7.25,8.75,9.5])}
        cardinality=3 if sample==0 else 5
        witness=[i<cardinality for i in range(8)];rng.shuffle(witness);clauses=[]
        while len(clauses)<20+sample*2:
            c=[(i+1)*rng.choice([-1,1]) for i in rng.sample(range(8),3)]
            if any(witness[abs(x)-1]==(x>0) for x in c):clauses.append(c)
        sat={'clauses':clauses,'true_count':cardinality,'var_count':8}
        jobs=[{'id':f'J{i}','duration':rng.randint(1,7),'due':rng.randint(3,28),'weight':rng.randint(1,9)} for i in range(8)]
        entries=[
            ('extraction','low',records,'Select records with category alpha and active true. Return their IDs in lexicographic order and their count as {"ids":[...],"count":integer}. Records: ',None),
            ('arithmetic','high',invoice,
             f'Calculate an invoice in integer cents. Round EACH qty*unit_cents*(1-discount_percent/100) HALF UP before summing subtotal. Tax is {invoice["tax_percent"]}% of subtotal rounded HALF UP. Shipping is {invoice["shipping"]} cents, untaxed. Total=subtotal+tax+shipping. Return {{"subtotal_cents":integer,"tax_cents":integer,"total_cents":integer}}. Invoice data: ',
             'Calculate invoice in integer cents using facts.lines, facts.tax_percent and facts.shipping. Round EACH discounted line HALF UP before summing. Round tax on subtotal HALF UP. Shipping is untaxed. Return {"subtotal_cents":integer,"tax_cents":integer,"total_cents":integer}.'),
            ('code_intervals','medium',None,
             'Write Python solve(intervals), returning sorted merged [start,end] lists. Half-open integer intervals can be negative, unsorted, duplicated or nested. Ignore start>=end. Merge only strict overlaps; touching intervals stay separate. Preserve the input. Handle empty input. No imports. Return {"code":"Python source defining solve"}.' if sample==0 else
             'Implement solve(intervals) in Python, without imports. Each [a,b] represents [a,b); discard a>=b. Coalesce intervals only when their intersection has positive length. Output sorted [a,b] lists, retaining merely adjacent components. Input must not change. Include duplicate, nested, negative and empty cases. Return only {"code":"source"}.',None),
            ('code_ledger','high',None,
             'Write Python solve(events) with no imports. Events contain id, account and integer delta. An id is processed only on its FIRST occurrence across ALL accounts. Ignore later duplicates entirely, including changed account or delta. Return account balances, keeping zero balances. Do not change events. Return {"code":"source defining solve"}.' if sample==0 else
             'Implement solve(events). Each event has string id/account and integer delta. Deduplicate by id globally, retaining earliest input occurrence, then sum per account. Return a balance dict and retain accounts whose balance ends at zero. Later copies may disagree with the first. Do not mutate input; no imports. Return {"code":"Python source"}.',None),
            ('logic_count','high',sat,
             f'Eight Boolean variables x1..x8. Exactly {cardinality} must be true. A positive integer i denotes xi; negative -i denotes NOT xi. Each clause is OR; all clauses are AND. Return the number of satisfying assignments as {{"count":integer}}. Logic data: ',
             'Count assignments for facts.var_count Boolean variables. Exactly facts.true_count are true. Literal i means xi, -i means NOT xi. Each facts.clauses item is OR; all clauses are AND. Return {"count":integer}.'),
            ('scheduling','high',jobs,
             'Find a globally optimal order of eight nonpreemptive jobs on one machine. Start at zero, allow no idle time. Objective is sum(weight*max(0,completion_time-due)). Any optimal order is valid. Return {"order":[job IDs],"weighted_tardiness":integer}. Jobs: ',
             'Use facts.jobs to find a globally optimal order of nonpreemptive jobs on ONE machine from time zero with no idle time. Minimize sum(weight*max(0,completion_time-due)). Any optimal order is accepted. Return {"order":[job IDs],"weighted_tardiness":integer}.')]
        for family,risk,data,instruction,compact in entries:
            ident='H'+str(len(tasks)+1).zfill(2)
            tasks.append({'id':ident,'family':family,'risk_floor':risk,'data':data,
                'prompt':instruction+(json.dumps(data) if data is not None else ''),
                'compact_instruction':compact,'eval_seed':rng.randint(1,10**8)})
    return tasks

def check(task,receipt,level='full'):
    if not task['family'].startswith('code_'):return B.check(task,receipt,level)
    start=time.perf_counter();out={'pass':False,'level':level,'reason':'','seconds':0}
    try:
        if not receipt['completed'] or receipt['tool_events']:raise ValueError('Provider incomplete or tools used')
        d=B.parse(receipt['text']);cases,ref=B.code_cases(task,False)
        rng=random.Random(task['eval_seed'])
        if level=='full':
            for _ in range(70):
                if task['family']=='code_intervals':cases.append([[rng.randint(-30,30),rng.randint(-30,30)] for _ in range(rng.randint(0,22))])
                else:cases.append([{'id':'e'+str(rng.randrange(9)),'account':'a'+str(rng.randrange(6)),'delta':rng.randint(-11,11)} for _ in range(rng.randint(0,32))])
        p=subprocess.run([sys.executable,'-I','-S',str(BASE/'worker.py')],input=json.dumps({'code':d['code'],'cases':cases}),capture_output=True,text=True,encoding='utf-8',timeout=4)
        if p.returncode:raise ValueError(p.stderr[-180:])
        values=json.loads(p.stdout)
        assert len(values)==len(cases)
        assert all(not x['mutated'] and x['value']==ref(case) for x,case in zip(values,cases))
        out['pass']=True
    except Exception as e:out['reason']=type(e).__name__+': '+str(e)[:220]
    out['seconds']=time.perf_counter()-start
    return out
