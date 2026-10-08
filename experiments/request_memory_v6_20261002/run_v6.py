"""v6 live reasoning test.

  python run_v6.py freeze    write frozen plan + evaluation-only gold, no model calls
  python run_v6.py live      refuse if frozen hashes changed; call models (cached by label + prompt hash)
  python run_v6.py analyze   recompute every metric from saved receipts
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from fractions import Fraction
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import numpy as np
import reasoning_v6 as R
import tasks_v6 as T

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
PLAN = HERE/'frozen-plan.json'
RUNS = HERE/'model_runs'
SAMPLES = 2
WORKERS = 6
HEDGE_AFTER = 10.0      # seconds; fixed before any call
ARMS = {'luna_direct': ('gpt-6-luna', None), 'luna_pot_A': ('gpt-6-luna', 'A'),
        'luna_pot_B': ('gpt-6-luna', 'B'), 'sol_direct': ('gpt-6.1-sol', None)}
CODEX = (os.environ.get('CODEX_BIN') or shutil.which('codex')
         or max(map(str, (Path.home()/'AppData/Local/OpenAI/Codex/bin').glob('*/codex.exe')), key=os.path.getmtime))
CODE_FILES = ['reasoning_v6.py', 'tasks_v6.py', 'worker_v6.py', 'run_v6.py']


def sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def tasks():
    return T.fresh_tasks()+T.regression_tasks()


def prompt(task, arm):
    method = ARMS[arm][1]
    return R.program_prompt(task['query'], method) if method else R.direct_prompt(task['query'])


def jobs():
    out = []
    for t in tasks():
        for arm, (model, _) in ARMS.items():
            for s in range(SAMPLES):
                p = prompt(t, arm)
                out.append({'task': t['id'], 'arm': arm, 'model': model, 'sample': s,
                            'label': f"{t['id']}__{arm}__s{s}", 'prompt': p, 'prompt_sha256': sha(p)})
    return out


def code_hashes():
    return {f: sha((HERE/f).read_text(encoding='utf-8')) for f in CODE_FILES}


def freeze():
    ts = tasks()
    (HERE/'evaluation_only').mkdir(exist_ok=True)
    (HERE/'evaluation_only/gold.json').write_text(json.dumps({t['id']: t['gold'] for t in ts}), encoding='utf-8')
    plan = {'date': '2026-10-02', 'arms': {k: v[0] for k, v in ARMS.items()}, 'samples': SAMPLES,
            'hedge_after_seconds': HEDGE_AFTER, 'reasoning_effort': 'low', 'workers': WORKERS,
            'tasks': [{k: t[k] for k in ('id', 'family', 'set', 'lang', 'query')} | {'spec': R.classify(t['query']).spec.__dict__,
                       'route': R.classify(t['query']).kind} for t in ts],
            'calls': len(jobs()), 'prompt_hashes': {j['label']: j['prompt_sha256'] for j in jobs()},
            'code_hashes': code_hashes(),
            'primary': ['error reduction of v6 cascade vs luna_direct', 'accuracy gap v6 vs sol_direct',
                        'false agreement rate', 'sol share', 'latency p50/p95'],
            'grading': 'same grade() for every arm; rounded answers within half a unit of the last requested place'}
    PLAN.write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps({'tasks': len(ts), 'calls': plan['calls']}))


def invoke(model, text, label, timeout=240):
    RUNS.mkdir(exist_ok=True)
    work = HERE/'model_sandbox'
    work.mkdir(exist_ok=True)
    env = dict(os.environ)
    for name in ['OPENAI_API_KEY', 'CODEX_API_KEY', 'OPENAI_BASE_URL', 'CODEX_ACCESS_TOKEN']:
        env.pop(name, None)
    env.update(PYTHONUTF8='1', NO_COLOR='1')
    cmd = [CODEX, 'exec', '--ignore-user-config', '--ephemeral', '--json', '--skip-git-repo-check', '--sandbox', 'read-only',
           '-C', str(work), '-c', 'approval_policy="never"', '-c', 'model_reasoning_effort="low"', '-m', model, '-']
    start = time.perf_counter()
    try:
        p = subprocess.run(cmd, input=text, text=True, encoding='utf-8', capture_output=True, env=env, timeout=timeout)
        raw, err, code, timed = p.stdout, p.stderr[-3000:], p.returncode, False
    except subprocess.TimeoutExpired as e:
        raw, err, code, timed = e.stdout or '', e.stderr or '', None, True
        raw = raw.decode('utf-8', 'replace') if isinstance(raw, bytes) else raw
        err = err.decode('utf-8', 'replace') if isinstance(err, bytes) else err
    events = []
    for line in raw.splitlines():
        try:
            events.append(json.loads(line))
        except ValueError:
            pass
    texts = [e.get('item', {}).get('text', '') for e in events
             if e.get('type') == 'item.completed' and e.get('item', {}).get('type') == 'agent_message']
    done = [e for e in events if e.get('type') == 'turn.completed']
    tools = [e for e in events if e.get('item', {}).get('type') in ['command_execution', 'mcp_tool_call', 'web_search']]
    r = {'model_requested': model, 'label': label, 'exit_code': code, 'timed_out': timed, 'prompt_sha256': sha(text),
         'provider_completed': bool(done) and code == 0, 'text': '\n'.join(texts),
         'usage': done[-1].get('usage', {}) if done else {}, 'tool_events': len(tools),
         'latency_seconds': time.perf_counter()-start, 'stderr': err, 'billing_usd': None}
    (RUNS/f'{label}.json').write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding='utf-8')
    return r


def live():
    plan = json.loads(PLAN.read_text(encoding='utf-8'))
    if plan['code_hashes'] != code_hashes():
        raise SystemExit('Code changed after freezing; live run refused.')
    js = jobs()
    if any(plan['prompt_hashes'][j['label']] != j['prompt_sha256'] for j in js):
        raise SystemExit('Prompt changed after freezing; live run refused.')

    def call(j):
        saved = RUNS/f"{j['label']}.json"
        if saved.exists():
            r = json.loads(saved.read_text(encoding='utf-8'))
            if r['prompt_sha256'] == j['prompt_sha256'] and r['provider_completed']:
                return j['label'], 'cached'
        r = invoke(j['model'], j['prompt'], j['label'])
        return j['label'], 'ok' if r['provider_completed'] else 'incomplete'

    start = time.perf_counter()
    status = {}
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        futures = [pool.submit(call, j) for j in js]
        for i, f in enumerate(as_completed(futures), 1):
            label, st = f.result()
            status[st] = status.get(st, 0)+1
            if i % 20 == 0 or i == len(js):
                print(json.dumps({'done': i, 'total': len(js), 'elapsed_s': round(time.perf_counter()-start), **status}), flush=True)


def outcome(j, spec):
    """Turn one saved receipt into a value + latency. PoT programs are executed here."""
    r = json.loads((RUNS/f"{j['label']}.json").read_text(encoding='utf-8'))
    out = {'latency': r['latency_seconds'], 'completed': r['provider_completed'] and not r['tool_events'],
           'usage': r['usage'], 'value': None, 'exec': None, 'exec_ms': 0}
    if not out['completed']:
        out['exec'] = 'incomplete'
        return out
    try:
        data = R.parse_json(r['text'])
    except ValueError:
        out['exec'] = 'format'
        return out
    if ARMS[j['arm']][1]:
        code = data.get('code') if isinstance(data, dict) else None
        if not isinstance(code, str):
            out['exec'] = 'format'
            return out
        receipt = R.run_program(code)
        out.update(exec=receipt['status'], exec_ms=receipt['exec_ms'], error=receipt.get('error'))
        out['value'] = R.to_fraction(receipt.get('result')) if receipt['status'] == 'ok' else None
    else:
        out['value'] = R.to_fraction(data.get('answer') if isinstance(data, dict) else None)
        out['exec'] = 'ok' if out['value'] is not None else 'format'
    return out


def pct(xs, q):
    return float(np.percentile(xs, q)) if xs else None


def boot_diff(a, b, seed=6):
    a, b = np.array(a, float), np.array(b, float)
    idx = np.random.default_rng(seed).integers(0, len(a), size=(5000, len(a)))
    d = (a[idx]-b[idx]).mean(1)
    return [float(np.quantile(d, .025)), float(np.quantile(d, .975))]


def analyze():
    gold = json.loads((HERE/'evaluation_only/gold.json').read_text(encoding='utf-8'))
    ts = {t['id']: t for t in tasks()}
    js = jobs()
    res = {}
    for j in js:
        spec = R.classify(ts[j['task']]['query']).spec
        o = outcome(j, spec)
        o['correct'] = R.grade(o['value'], gold[j['task']], spec)
        res[(j['task'], j['arm'], j['sample'])] = o
    trials = []
    for tid, t in ts.items():
        spec = R.classify(t['query']).spec
        for s in range(SAMPLES):
            a, b, sol, d = (res[(tid, arm, s)] for arm in ('luna_pot_A', 'luna_pot_B', 'sol_direct', 'luna_direct'))
            tr = R.Trial(a, b, sol, spec)
            econ, hedged = R.cascade(tr, hedge_after=HEDGE_AFTER)
            # Variant without Sol: when the pair disagrees fall back to program A, then to Luna direct.
            luna_only_value = a['value'] if econ['status'] == 'agreed' or a['exec'] == 'ok' else d['value']
            trials.append({'task': tid, 'family': t['family'], 'set': t['set'], 'lang': t['lang'], 'sample': s,
                           'luna_direct': d['correct'], 'pot_A': a['correct'], 'pot_B': b['correct'], 'sol_direct': sol['correct'],
                           'agreed': econ['status'] == 'agreed',
                           'v6': R.grade(econ['value'], gold[tid], spec), 'v6_luna_only': R.grade(luna_only_value, gold[tid], spec),
                           'v6_status': econ['status'], 'v6_calls': econ['calls'], 'v6_sol': econ['sol'],
                           'v6_hedged_sol': hedged['sol'],
                           'lat': {'luna_direct': d['latency'], 'sol_direct': sol['latency'], 'pot_A': a['latency'],
                                   'pot_B': b['latency'], 'v6': econ['latency'], 'v6_hedged': hedged['latency']},
                           'exec': {'A': a['exec'], 'B': b['exec']}, 'exec_ms': [a['exec_ms'], b['exec_ms']],
                           'values': {k: (str(v['value']) if v['value'] is not None else None)
                                      for k, v in (('A', a), ('B', b), ('sol', sol), ('direct', d))},
                           'gold': gold[tid], 'tokens': {arm: res[(tid, arm, s)]['usage'] for arm in ARMS}})
    acc = lambda key, rows: float(np.mean([r[key] for r in rows])) if rows else None
    arms = ['luna_direct', 'pot_A', 'pot_B', 'v6_luna_only', 'v6', 'sol_direct']
    summary = {k: acc(k, trials) for k in arms}
    agreed = [r for r in trials if r['agreed']]
    lat = {k: [r['lat'][k] for r in trials] for k in ('luna_direct', 'sol_direct', 'pot_A', 'v6', 'v6_hedged')}
    latency = {k: {'p50': pct(v, 50), 'p95': pct(v, 95), 'mean': float(np.mean(v))} for k, v in lat.items()}
    groups = {}
    for key in ('family', 'set', 'lang'):
        for g in sorted({r[key] for r in trials}):
            rows = [r for r in trials if r[key] == g]
            groups[f'{key}:{g}'] = {k: acc(k, rows) for k in arms} | {'n': len(rows),
                                     'agree_rate': acc('agreed', rows), 'sol_share': float(np.mean([r['v6_sol'] for r in rows]))}
    per_task = {}
    for r in trials:
        per_task.setdefault(r['task'], []).append(r)
    by_task = lambda k: [float(np.mean([r[k] for r in rs])) for rs in per_task.values()]
    tok = {}
    for arm in ARMS:
        us = [r['tokens'][arm] for r in trials]
        tok[arm] = {'input': sum(u.get('input_tokens', 0) for u in us), 'cached': sum(u.get('cached_input_tokens', 0) for u in us),
                    'output': sum(u.get('output_tokens', 0) for u in us), 'reasoning': sum(u.get('reasoning_output_tokens', 0) for u in us)}
    execs = [ms for r in trials for ms in r['exec_ms'] if ms]
    err = lambda k: 1-summary[k]
    out = {'n_trials': len(trials), 'n_tasks': len(per_task), 'accuracy': summary,
           'error_reduction_vs_luna_direct': {k: (1-err(k)/err('luna_direct')) if err('luna_direct') else None for k in arms},
           'v6_vs_luna_direct_ci95': boot_diff(by_task('v6'), by_task('luna_direct')),
           'v6_vs_sol_direct_ci95': boot_diff(by_task('v6'), by_task('sol_direct')),
           'agreement': {'rate': len(agreed)/len(trials), 'accuracy_when_agreed': acc('v6', agreed),
                         'false_agreements': sum(1 for r in agreed if not r['v6']),
                         'false_agreement_rate': (sum(1 for r in agreed if not r['v6'])/len(agreed)) if agreed else None},
           'sol_share': {'economy': float(np.mean([r['v6_sol'] for r in trials])), 'hedged': float(np.mean([r['v6_hedged_sol'] for r in trials]))},
           'calls_per_request': {'v6': float(np.mean([r['v6_calls'] for r in trials])), 'luna_direct': 1, 'sol_direct': 1},
           'latency': latency, 'exec_ms': {'p50': pct(execs, 50), 'p95': pct(execs, 95)},
           'exec_status': {s: sum(1 for r in trials for v in r['exec'].values() if v == s) for s in ('ok', 'error', 'timeout', 'format', 'incomplete')},
           'tokens': tok, 'groups': groups, 'trials': trials}
    (HERE/'results.json').write_text(json.dumps(out, ensure_ascii=False, default=str), encoding='utf-8')
    print(json.dumps({k: out[k] for k in ('n_trials', 'accuracy', 'error_reduction_vs_luna_direct', 'v6_vs_luna_direct_ci95',
                                          'v6_vs_sol_direct_ci95', 'agreement', 'sol_share', 'calls_per_request', 'latency',
                                          'exec_ms', 'exec_status')}, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    {'freeze': freeze, 'live': live, 'analyze': analyze}[sys.argv[1]]()
