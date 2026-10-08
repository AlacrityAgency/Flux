"""Isolated v6.1: public constraint graph + executable independent check.

No evaluator imports, gold answers, persistent learning, or production integration.
Graph coverage and a model-written checker are diagnostics, not formal proofs.
"""
import ast
import json
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / 'request_memory_v6_20261002'
sys.path.insert(0, str(BASE))
import reasoning_v6 as V6

CONTRACT = '''Use only the TASK; no tools, files, browsing or commands.
Return JSON {"nodes":[{"id":"n","kind":"input|constraint|objective|check","text":"..."}],"edges":[["id","id"]],"code":"Python source"}.
Build a compact dependency graph of ALL stated inputs and constraints, connected to the objective and check. Preserve every numeric literal in node texts; do not paraphrase away any denomination, edge weight, exception or boundary. Merge related facts into nodes. No explanatory essay.
Define solve() returning an int, Fraction or float. Prefer enumeration, DP, or exact state equations.
Define check(answer) returning exactly bool, independently verifying the objective and all constraints. Use a different derivation or exhaustive reference; do not call solve(), copy its result, or return True unconditionally. For minimum/maximum prove feasibility AND no better solution, for counts re-enumerate or use an independent identity, for probabilities use exact fractions before final rounding. For modular congruences verify every constraint AND minimality. For logical assignments enumerate the complete finite domain including negative and exactly-one constraints.
Exact arithmetic; float only for requested rounding. Allowed imports: math, fractions, itertools, functools, collections, heapq, bisect. No classes, randomness, simulation, IO, dynamic evaluation or introspection. Whole program must finish within 2 seconds. Keep code and graph concise.
TASK:
'''


def prompt(query):
    return CONTRACT + query


def literals(text):
    return set(re.findall(r'(?<![\w])\d+(?:\.\d+)?', text.translate(V6.FA_DIGITS)))


def graph_audit(data, query):
    nodes, edges = data.get('nodes'), data.get('edges')
    if not isinstance(nodes, list) or not 2 <= len(nodes) <= 64 or not isinstance(edges, list) or len(edges) > 256:
        return False, 'graph shape'
    try:
        ids = [n['id'] for n in nodes]
        if any(not isinstance(x, str) for x in ids) or len(set(ids)) != len(ids):
            return False, 'node identifiers'
        if any(n['kind'] not in {'input', 'constraint', 'objective', 'check'} or not isinstance(n['text'], str) for n in nodes):
            return False, 'node schema'
        if not {'input', 'objective', 'check'} <= {n['kind'] for n in nodes}:
            return False, 'missing roles'
        missing = literals(query) - literals(' '.join(n['text'] for n in nodes))
        if missing:
            return False, 'missing literals: ' + ','.join(sorted(missing))
        adj = {n: set() for n in ids}
        for edge in edges:
            if not isinstance(edge, list) or len(edge) != 2 or any(e not in adj for e in edge):
                return False, 'invalid edge'
            adj[edge[0]].add(edge[1])
        targets = {n['id'] for n in nodes if n['kind'] in {'objective', 'check'}}
        for node in nodes:
            if node['kind'] not in {'input', 'constraint', 'objective'}:
                continue
            seen, stack = set(), [node['id']]
            while stack:
                at = stack.pop()
                if at not in seen:
                    seen.add(at)
                    stack.extend(adj[at] - seen)
            required = targets - {node['id']}
            if not required <= seen:
                return False, 'disconnected constraint'
        return True, 'public graph coverage only'
    except (KeyError, TypeError):
        return False, 'invalid graph'


def checker_audit(code):
    tree = ast.parse(code)
    funcs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    checker = funcs.get('check')
    if checker is None or len(checker.args.args) != 1:
        return False
    body = [n for n in checker.body if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant))]
    if len(body) == 1 and isinstance(body[0], ast.Return) and isinstance(body[0].value, ast.Constant):
        return False
    if any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'solve' for n in ast.walk(checker)):
        return False
    return True  # Cannot establish semantic independence by AST alone.


def run(code, checked=False, timeout=2.5):
    start = time.perf_counter()
    try:
        p = subprocess.run([sys.executable, '-I', '-S', str(HERE / 'worker.py')],
                           input=json.dumps({'code': code, 'checked': checked}), text=True,
                           encoding='utf-8', capture_output=True, timeout=timeout)
        r = json.loads(p.stdout.strip().splitlines()[-1]) if p.stdout.strip() else {'status': 'error', 'error': 'no output'}
    except subprocess.TimeoutExpired:
        r = {'status': 'timeout'}
    except (ValueError, IndexError):
        r = {'status': 'error', 'error': 'invalid worker receipt'}
    r['exec_ms'] = (time.perf_counter() - start) * 1000
    return r


def interpret(receipt, query, mode):
    out = {'accepted': False, 'value': None, 'status': 'provider', 'exec_ms': 0}
    if not receipt.get('provider_completed') or receipt.get('tool_events'):
        return out
    try:
        data = V6.parse_json(receipt['text'])
        if not isinstance(data, dict):
            return out | {'status': 'format'}
        if mode == 'direct':
            value = V6.to_fraction(data.get('answer'))
            return out | {'value': value, 'accepted': V6.sanity(value, V6.answer_spec(query)), 'status': 'direct'}
        code = data.get('code')
        if not isinstance(code, str):
            return out | {'status': 'format'}
        if mode == 'graph':
            ok, detail = graph_audit(data, query)
            out['graph_detail'] = detail
            out['graph_nodes'] = len(data.get('nodes', []))
            if not ok or not checker_audit(code):
                return out | {'status': 'graph_or_checker_rejected'}
        r = run(code, checked=mode == 'graph')
        value = V6.to_fraction(r.get('result')) if r['status'] == 'ok' else None
        accepted = V6.sanity(value, V6.answer_spec(query)) and (mode != 'graph' or r.get('verified') is True)
        return out | {'status': r['status'], 'value': value, 'accepted': accepted, 'exec_ms': r['exec_ms'],
                      'verified': r.get('verified'), 'error': r.get('error')}
    except (ValueError, SyntaxError, TypeError):
        return out | {'status': 'format'}


def exact_agreement(a, b, spec):
    """Canonical requested rounding, instead of allowing adjacent rounded values."""
    if a is None or b is None:
        return False
    return round(a, spec.places) == round(b, spec.places) if spec.places is not None else a == b
