"""Offline v3 vs v4 benchmark. No model calls; gold is read only inside grade().

  python benchmark_v4.py tune     dev sets only: v3 reference + v4 grid, then freeze the config
  python benchmark_v4.py holdout  refuses to run unless code hashes match frozen-plan.json
"""
from pathlib import Path
import itertools
import json
import sys
from time import perf_counter
import numpy as np

HERE = Path(__file__).resolve().parent
V3 = HERE.parent/'request_memory_v3_20261002'
OLD = HERE.parent/'diffusion_memory_20261001'
sys.path.insert(0, str(HERE))
import engine_v4 as v4
from engine_v4 import Atom, Config, Index, Record, dumps, sha, tokens
from encoder_v4 import Encoder
sys.path.insert(1, str(V3))
import engine as v3
from build_data import REAL_TASKS, synthetic
from holdout_tasks import real_holdout_tasks

DEV_SEED = 6417
HOLDOUT_SEED = 20261002
V3_SEED = 771239
FROZEN = HERE/'frozen-plan.json'
CODE = ['engine_v4.py', 'benchmark_v4.py', 'encoder_v4.py', 'holdout_tasks.py']
GRID = {'per_criterion': [1, 2, 3], 'neighbors': [0, 1], 'scope_k': [0, 2, 4], 'fill_tokens': [0, 300, 600, 1200],
        'embedding': [False, True], 'beta': [.25, .5]}


def code_hashes():
    return {p: sha((HERE/p).read_text(encoding='utf-8')) for p in CODE}


def real_corpus():
    d = OLD/'snapshots/flux_real'
    atoms = [Atom(**a) for a in json.loads((d/'atoms.json').read_text(encoding='utf-8'))]
    chunks = [Atom(**a) for a in json.loads((d/'chunks.json').read_text(encoding='utf-8'))]
    return atoms, chunks


def dev_real_tasks():
    raw = (OLD/'snapshots/flux_real/raw.txt').read_text(encoding='utf-8')
    out = []
    for ident, query, criteria, needles in REAL_TASKS:
        assert all(n in raw for n in needles), ident
        out.append({'id': ident, 'kind': 'source_evidence', 'query': query, 'criteria': criteria, 'needles': needles})
    return out


def v3_frozen_tasks():
    tasks = json.loads((V3/'evaluation_only/tasks.json').read_text(encoding='utf-8'))
    return [t for t in tasks if t['external_evidence']], tasks


class Corpus:
    def __init__(self, name, atoms, chunks, encoder, with_v3=True):
        self.name = name
        records = [Record(a) for a in atoms]
        t = perf_counter()
        self.v4 = Index(records, encoder=encoder)
        self.v4_build_ms = (perf_counter()-t)*1000
        self.v3 = self.builder = None
        if with_v3:
            t = perf_counter()
            self.v3 = v3.Memory(records, encoder)
            self.builder = v3.ArchiveBuilder(chunks)
            self.v3_build_ms = (perf_counter()-t)*1000


def grade(pack, task):
    items = pack.get('items', [])
    joined = '\n'.join(x['text'] for x in items)
    hits = [n in joined for n in task['needles']]
    signal = noise = 0
    for x in items:
        cost = tokens(dumps(x))
        if any(n in x['text'] for n in task['needles']):
            signal += cost
        else:
            noise += cost
    return {'task': task['id'], 'kind': task['kind'], 'hits': sum(hits), 'needs': len(hits), 'complete': all(hits),
            'tokens': pack.get('tokens', 0), 'signal_tokens': signal, 'noise_tokens': noise,
            'latency_ms': pack.get('latency_ms', 0.), 'budget_violation': pack.get('tokens', 0) > pack.get('budget', 3000),
            'error': pack.get('error')}


def run_v3(c, task, adaptive):
    req = v3.Request(task['id'], task['query'], tuple(task['criteria']))
    t = perf_counter()
    try:
        r = v3.pipeline(req, c.v3, c.builder, adaptive=adaptive)
    except ValueError as e:
        return {'items': [], 'tokens': 0, 'budget': 3000, 'latency_ms': (perf_counter()-t)*1000, 'error': str(e)}
    r['latency_ms'] = (perf_counter()-t)*1000
    return r


def run_v4(c, task, cfg):
    try:
        return v4.run(c.v4, task['id'], task['query'], task['criteria'], cfg)
    except ValueError as e:
        return {'items': [], 'tokens': 0, 'budget': cfg.budget, 'latency_ms': 0., 'error': str(e)}


def summarize(rows):
    if not rows:
        return {}
    lat = [r['latency_ms'] for r in rows]
    return {'tasks': len(rows), 'complete_rate': float(np.mean([r['complete'] for r in rows])),
            'evidence_recall': sum(r['hits'] for r in rows)/max(1, sum(r['needs'] for r in rows)),
            'incomplete_tasks': [r['task'] for r in rows if not r['complete']],
            'mean_pack_tokens': float(np.mean([r['tokens'] for r in rows])),
            'mean_signal_tokens': float(np.mean([r['signal_tokens'] for r in rows])),
            'mean_noise_tokens': float(np.mean([r['noise_tokens'] for r in rows])),
            'median_ms': float(np.median(lat)), 'p95_ms': float(np.percentile(lat, 95)), 'mean_ms': float(np.mean(lat)),
            'budget_violations': sum(r['budget_violation'] for r in rows), 'errors': sum(bool(r['error']) for r in rows)}


def paired(a_rows, b_rows, key='complete', seed=4501):
    a = np.array([r[key] for r in a_rows], dtype=float)
    b = np.array([r[key] for r in b_rows], dtype=float)
    idx = np.random.default_rng(seed).integers(0, len(a), size=(4000, len(a)))
    d = (a[idx]-b[idx]).mean(axis=1)
    return {'delta': float((a-b).mean()), 'ci95': np.quantile(d, [.025, .975]).tolist()}


def evaluate(sets, cfg, arms=('v3_fixed', 'v3_adaptive', 'v4')):
    out = {}
    for name, (c, tasks) in sets.items():
        rows = {a: [] for a in arms}
        # Warm-up so the first timed request is not a cold-cache artifact for any arm.
        warm = tasks[0]
        for a in arms:
            _arm(a, c, warm, cfg)
        for no, t in enumerate(tasks):
            order = arms if no % 2 == 0 else tuple(reversed(arms))
            for a in order:
                rows[a].append(grade(_arm(a, c, t, cfg), t))
        out[name] = {'rows': rows, 'summary': {a: summarize(rows[a]) for a in arms}}
    return out


def _arm(a, c, t, cfg):
    if a == 'v3_fixed':
        return run_v3(c, t, False)
    if a == 'v3_adaptive':
        return run_v3(c, t, True)
    return run_v4(c, t, cfg)


def router_check(c_syn, c_real, all_v3_tasks):
    rows = []
    for t in all_v3_tasks:
        c = c_syn if t['corpus'] == 'synthetic' else c_real
        spec = v4.make_spec(t['id'], t['query'], t['criteria'], c.v4)
        rows.append({'task': t['id'], 'expected': t['external_evidence'], 'retrieve': spec.retrieve, 'reason': spec.reason})
    return {'accuracy': float(np.mean([r['expected'] == r['retrieve'] for r in rows])), 'rows': rows}


def choose(grid_rows):
    # Pre-declared rule: best macro complete rate; within 0.01 of it, fewest macro tokens;
    # then no embedding; then fewer units per criterion.
    best = max(r['macro_complete'] for r in grid_rows)
    near = [r for r in grid_rows if r['macro_complete'] >= best-.01]
    return min(near, key=lambda r: (round(r['macro_tokens'], 1), r['cfg']['embedding'], r['cfg']['per_criterion']))


def tune():
    enc = Encoder()
    syn = synthetic(seed=DEV_SEED)
    atoms, chunks = real_corpus()
    c_syn = Corpus('dev_synthetic', syn['atoms'], syn['chunks'], enc)
    c_real = Corpus('dev_real', atoms, chunks, enc)
    sets = {'dev_synthetic': (c_syn, syn['tasks']), 'dev_real': (c_real, dev_real_tasks())}
    grid_rows = []
    for values in itertools.product(*GRID.values()):
        cfg = Config(**dict(zip(GRID, values)))
        res = evaluate(sets, cfg, arms=('v4',))
        s = {k: v['summary']['v4'] for k, v in res.items()}
        grid_rows.append({'cfg': cfg.__dict__, 'per_set': s,
                          'macro_complete': float(np.mean([x['complete_rate'] for x in s.values()])),
                          'macro_tokens': float(np.mean([x['mean_pack_tokens'] for x in s.values()]))})
        print(dumps({'phase': 'grid', 'cfg': cfg.__dict__, 'macro_complete': grid_rows[-1]['macro_complete'],
                     'macro_tokens': round(grid_rows[-1]['macro_tokens'], 1)}), flush=True)
    pick = choose(grid_rows)
    cfg = Config(**pick['cfg'])
    reference = evaluate(sets, cfg)
    plan = {'date': '2026-10-02', 'config': pick['cfg'], 'selection_rule': choose.__doc__ or 'see choose()',
            'dev_seed': DEV_SEED, 'holdout_seed': HOLDOUT_SEED, 'v3_seed': V3_SEED, 'code_hashes': code_hashes(),
            'holdout_sets': ['holdout_synthetic (fresh seed, 136 tasks)', 'v3_frozen (K00-K05, F00-F01)', 'holdout_real (HR01-HR12)'],
            'targets': {'speed': 'median hot-path latency at least 95% below v3_fixed',
                        'output': 'complete-evidence rate not below v3_fixed; incomplete rate and noise tokens reduced'},
            'model_calls': 0, 'answer_quality_measured': False}
    FROZEN.write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding='utf-8')
    (HERE/'dev-results.json').write_text(dumps({'grid': grid_rows, 'chosen': pick, 'reference': {
        k: v['summary'] for k, v in reference.items()}, 'build_ms': {
        'dev_synthetic': {'v4': c_syn.v4_build_ms, 'v3': c_syn.v3_build_ms},
        'dev_real': {'v4': c_real.v4_build_ms, 'v3': c_real.v3_build_ms}}}), encoding='utf-8')
    print(dumps({'phase': 'frozen', 'config': pick['cfg'], 'reference': {k: v['summary'] for k, v in reference.items()}}))


def holdout():
    plan = json.loads(FROZEN.read_text(encoding='utf-8'))
    if plan['code_hashes'] != code_hashes():
        raise SystemExit('Code changed after freezing; holdout refused.')
    cfg = Config(**plan['config'])
    enc = Encoder()
    syn = synthetic(seed=HOLDOUT_SEED)
    v3syn = synthetic(seed=V3_SEED)
    atoms, chunks = real_corpus()
    c_syn = Corpus('holdout_synthetic', syn['atoms'], syn['chunks'], enc)
    c_v3 = Corpus('v3_synthetic', v3syn['atoms'], v3syn['chunks'], enc)
    c_real = Corpus('real', atoms, chunks, enc)
    v3_ext, v3_all = v3_frozen_tasks()
    sets = {'holdout_synthetic': (c_syn, syn['tasks']),
            'v3_frozen_synthetic': (c_v3, [t for t in v3_ext if t['corpus'] == 'synthetic']),
            'v3_frozen_real': (c_real, [t for t in v3_ext if t['corpus'] == 'real']),
            'holdout_real': (c_real, real_holdout_tasks())}
    res = evaluate(sets, cfg)
    allrows = {a: [r for v in res.values() for r in v['rows'][a]] for a in ('v3_fixed', 'v3_adaptive', 'v4')}
    pooled = {a: summarize(rows) for a, rows in allrows.items()}
    comparisons = {b: {'complete': paired(allrows['v4'], allrows[b]),
                       'latency_reduction_median': 1-pooled['v4']['median_ms']/pooled[b]['median_ms'],
                       'noise_reduction': 1-pooled['v4']['mean_noise_tokens']/max(1e-9, pooled[b]['mean_noise_tokens']),
                       'pack_token_reduction': 1-pooled['v4']['mean_pack_tokens']/pooled[b]['mean_pack_tokens'],
                       'incomplete_reduction': (None if pooled[b]['complete_rate'] == 1 else
                                                1-(1-pooled['v4']['complete_rate'])/(1-pooled[b]['complete_rate']))}
                   for b in ('v3_fixed', 'v3_adaptive')}
    router = router_check(c_v3, c_real, v3_all)
    t = perf_counter()
    for _ in range(50):
        enc.encode(['warm query'], 'query')
    query_embed_ms = (perf_counter()-t)*1000/50
    out = {'config': plan['config'], 'sets': {k: v['summary'] for k, v in res.items()}, 'pooled': pooled,
           'comparisons': comparisons, 'router': router, 'query_embedding_ms': query_embed_ms,
           'device': enc.device, 'build_ms': {c.name: {'v4': c.v4_build_ms, 'v3': c.v3_build_ms} for c in (c_syn, c_v3, c_real)},
           'rows': {k: v['rows'] for k, v in res.items()}, 'model_calls': 0}
    (HERE/'holdout-results.json').write_text(dumps(out), encoding='utf-8')
    print(dumps({k: out[k] for k in ('sets', 'pooled', 'comparisons', 'query_embedding_ms', 'device', 'build_ms')}))
    print(dumps({'router_accuracy': router['accuracy'], 'router_errors': [r for r in router['rows'] if r['expected'] != r['retrieve']]}))


if __name__ == '__main__':
    {'tune': tune, 'holdout': holdout}[sys.argv[1]]()
