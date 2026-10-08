"""Actual Flux v5 retrieval/admission and adapted v6.1 program/check pipeline."""
import importlib.util, json, subprocess, sys, time
from dataclasses import asdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT/'src'))
sys.path.insert(0, str(ROOT/'experiments/request_memory_v5_20261002'))
from contracts import Request, Policy, tokens
from memory_v5 import Snapshot
from engine_v5 import retrieve
from flux.core.context import admit_context
spec = importlib.util.spec_from_file_location('flux_reasoning_v61', ROOT/'experiments/request_reasoning_v6_1_20261002/engine.py')
V61 = importlib.util.module_from_spec(spec); spec.loader.exec_module(V61)

PROGRAM = V61.CONTRACT.replace('Define solve() returning an int, Fraction or float.',
    'Define solve() returning the JSON OBJECT requested by the TASK, with integer values and lists as needed.')
PROGRAM = PROGRAM.replace('Whole program must finish within 2 seconds.',
    'Whole program including check must finish within 4 seconds. Builtin type is FORBIDDEN; use isinstance. Decimal is allowed. Return no direct answer alongside the code.')
PROGRAM_FAMILIES = {'arithmetic', 'logic_count', 'scheduling'}

def decode(item):
    t, v = item['type'], item['value']
    if t == 'mapping': return {k:decode(x) for k,x in v.items()}
    if t == 'sequence': return [decode(x) for x in v]
    if t in {'bool','string'}: return v
    if t in {'fraction','decimal'}:
        if v[1] != 1: raise ValueError('Task requires integer results')
        return v[0]
    raise ValueError('Unsupported encoding')

def execute(code):
    start = time.perf_counter()
    try:
        p = subprocess.run([sys.executable,'-I','-S',str(HERE/'program_worker.py')],
            input=json.dumps({'code':code,'checked':True}),capture_output=True,text=True,encoding='utf-8',timeout=5)
        r = json.loads(p.stdout)
        if r.get('status') != 'ok' or r.get('verified') is not True: raise ValueError(str(r))
        result = decode(r['result'])
        if not isinstance(result,dict): raise ValueError('JSON object required')
        return {'pass':True,'answer':result,'seconds':time.perf_counter()-start}
    except Exception as e:
        return {'pass':False,'reason':type(e).__name__+': '+str(e)[:180],'seconds':time.perf_counter()-start}

class FluxAdapter:
    def __init__(self):
        start = time.perf_counter()
        self.snapshot = Snapshot([],project='laya-pilot',epoch='1')
        self.index_seconds = time.perf_counter()-start

    def prepare(self, task, method, error=None):
        kind = 'code' if task['family'].startswith('code_') else 'math' if task['family'] in PROGRAM_FAMILIES else 'factual'
        request = Request(task['id'],task['prompt'],project='laya-pilot',memory_need='self_contained',task_kind=kind)
        pack = retrieve(self.snapshot,request,Policy())
        if pack.status != 'ready': raise ValueError('Pack failed: '+pack.status)
        prefix = PROGRAM if method == 'program' else 'Use only the TASK. No tools, files or browsing. Return ONLY the JSON object requested by TASK.\nTASK:\n'
        prompt = prefix+task['prompt']
        # Self-contained tasks have no evidence units. Do not pad them with metadata or archive.
        if pack.payload['units']: prompt += '\nEvidence: '+pack.rendered
        if error: prompt += '\nPrevious attempt failed local checks: '+error[:300]+'\nRepair all constraints. No previous solution is supplied.'
        admission = admit_context(prompt,input_budget=8000,output_reserve=4000,window=24000)
        return prompt, {'memory_route':pack.route,'pack_tokens':pack.token_count,
            'selected_units':len(pack.payload['units']),'prepare_ms':pack.prepare_ms,
            'admission':admission,'method':method}

    def interpret(self, task, receipt, method):
        if method != 'program': return receipt, {'method':'direct','pass':True}
        diagnostic = {'method':'program','pass':False}
        try:
            if not receipt['completed'] or receipt['tool_events']: raise ValueError('Provider incomplete or tools used')
            d = json.loads(receipt['text'].strip())
            ok,reason = V61.graph_audit(d,task['prompt'])
            diagnostic['graph'] = {'pass':ok,'reason':reason}
            if not ok: raise ValueError(reason)
            if not V61.checker_audit(d['code']): raise ValueError('Invalid independent checker')
            diagnostic.update(execute(d['code']))
            if not diagnostic['pass']: raise ValueError(diagnostic['reason'])
            effective = dict(receipt,text=json.dumps(diagnostic['answer']),tool_events=0)
            return effective,diagnostic
        except Exception as e:
            diagnostic.update(pass_=False,reason=str(e)[:250])
            diagnostic['pass'] = False
            return dict(receipt,completed=False),diagnostic
