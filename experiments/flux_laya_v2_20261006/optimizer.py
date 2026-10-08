"""Compact parameterized programs; field references replace repeated model graph."""
import ast, json, subprocess, sys, time
from pathlib import Path
HERE=Path(__file__).resolve().parent
V1=HERE.parent/'flux_laya_policy_20261006'
sys.path.insert(0,str(V1))
from adapter import FluxAdapter, PROGRAM_FAMILIES, decode, tokens, admit_context

COMPACT='''Use only TASK and FACTS. No tools, files, commands or browsing. Return ONLY JSON {"refs":[all required FACTS keys],"code":"Python source"}.
Define solve(facts) returning the JSON answer requested by TASK. Read input from facts; do not copy the dataset into code. Define check(answer,facts) returning bool using an independent derivation or enumeration; it must use answer and facts, must not call solve or return True unconditionally. For an optimum check feasibility AND global optimality; counts must be rechecked.
Prefer concise exact arithmetic. Allowed imports math, fractions, itertools, functools, collections, heapq, bisect, decimal. Builtin type is forbidden; use isinstance. No classes, randomness, IO, dynamic evaluation or introspection. Finish solve AND check within 4 seconds. No explanatory graph or essay.
'''
CONSTRAINTS={
 'arithmetic':['line_half_up','subtotal_sum','tax_half_up','shipping_untaxed','total_sum'],
 'logic_count':['literal_polarity','clause_or','clauses_and','exact_cardinality','count_all'],
 'scheduling':['every_job_once','one_machine','no_idle','weighted_tardiness','global_minimum']}

def facts_for(task):return {'jobs':task['data']} if task['family']=='scheduling' else task['data']
def compact_audit(data,facts):
    refs=data.get('refs')
    if not isinstance(refs,list) or not all(isinstance(x,str) for x in refs):raise ValueError('Invalid refs')
    if len(set(refs))!=len(refs) or set(refs)!=set(facts):raise ValueError('Mandatory facts reference mismatch')
    code=data.get('code');tree=ast.parse(code)
    funcs={n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
    if 'solve' not in funcs or [x.arg for x in funcs['solve'].args.args]!=['facts']:raise ValueError('solve(facts) contract')
    checker=funcs.get('check')
    if checker is None or [x.arg for x in checker.args.args]!=['answer','facts']:raise ValueError('check(answer,facts) contract')
    for name,needed in [('solve',{'facts'}),('check',{'answer','facts'})]:
        used={n.id for n in ast.walk(funcs[name]) if isinstance(n,ast.Name) and isinstance(n.ctx,ast.Load)}
        if not needed<=used:raise ValueError('Arguments unused: '+name)
    body=[n for n in checker.body if not(isinstance(n,ast.Expr) and isinstance(n.value,ast.Constant))]
    if len(body)==1 and isinstance(body[0],ast.Return) and isinstance(body[0].value,ast.Constant):raise ValueError('Constant checker')
    if any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='solve' for n in ast.walk(checker)):raise ValueError('Checker calls solver')
    return True

def execute_compact(code,facts):
    start=time.perf_counter()
    try:
        p=subprocess.run([sys.executable,'-I','-S',str(HERE/'compact_worker.py')],
            input=json.dumps({'code':code,'facts':facts,'checked':True}),capture_output=True,text=True,encoding='utf-8',timeout=5)
        r=json.loads(p.stdout)
        if r.get('status')!='ok' or r.get('verified') is not True:raise ValueError(str(r))
        value=decode(r['result'])
        if not isinstance(value,dict):raise ValueError('JSON object required')
        return {'pass':True,'answer':value,'seconds':time.perf_counter()-start}
    except Exception as e:return {'pass':False,'reason':type(e).__name__+': '+str(e)[:220],'seconds':time.perf_counter()-start}

class Optimizer(FluxAdapter):
    def prepare(self,task,method,error=None):
        prompt,prep=super().prepare(task,'direct',error=None)
        if method=='compact':
            facts=facts_for(task)
            prompt=COMPACT+'TASK:\n'+task['compact_instruction']+'\nFACTS:\n'+json.dumps(facts,separators=(',',':'))
            prep['local_graph']={'input_refs':sorted(facts),'constraints':CONSTRAINTS[task['family']],
                'objective':'task_json_answer','check':'independent_model_checker_plus_task_verifier'}
            prep['facts_hash']=__import__('hashlib').sha256(json.dumps(facts,sort_keys=True).encode()).hexdigest()
        if error:prompt+='\nRepair after local failure: '+error[:240]
        prep['admission']=admit_context(prompt,input_budget=8000,output_reserve=4000,window=24000)
        prep['method']=method
        return prompt,prep

    def interpret(self,task,receipt,method):
        if method!='compact':return super().interpret(task,receipt,method)
        result={'method':'compact','pass':False}
        try:
            if not receipt['completed'] or receipt['tool_events']:raise ValueError('Provider incomplete or tools used')
            data=json.loads(receipt['text'].strip());facts=facts_for(task)
            compact_audit(data,facts)
            result.update(execute_compact(data['code'],facts))
            if not result['pass']:raise ValueError(result['reason'])
            return dict(receipt,text=json.dumps(result['answer'])),result
        except Exception as e:
            result['pass']=False;result['reason']=str(e)[:250]
            return dict(receipt,completed=False),result
