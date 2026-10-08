"""Adversarial scenario: sibling projects hold perturbed copies of Flux's own notes. JEVS code is frozen."""
import json, sys, statistics
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parents[1] / "src"))
sys.stdout.reconfigure(encoding="utf-8")
import corpus as C, run_experiment as R
from tasks import TASKS
from tasks_holdout import HOLDOUT
from tasks_holdout2 import HOLDOUT2

code, files = R.load_all()
tasks = TASKS + HOLDOUT + HOLDOUT2
names = ["A1 الگوریتم فعلی Flux", "JEVS v1", "JEVS v2", "JEVS v2 دقیق", "v2 − فیلتر پروژه", "v2 − فیلتر منسوخ"]
allstrat = {**R.STRATEGIES, **R.ABLATIONS}
out = []
for n_other, per in ((1, 10), (3, 60), (10, 300)):
    for name in names:
        rows = []
        for seed in (0, 1, 2):
            store = C.build_memory_store(n_other, per, seed, siblings=True)
            env = R.build_env(store, code, files)
            rows += R.run_strategy(name, allstrat[name], env, workflows=("low",), tasks=tasks)["low"]
        s = R.summarize(rows)
        s.update(strategy=name, n_other=n_other, per=per, store=len(store), n_runs=len(rows),
                 foreign_runs=sum(r["foreign"] > 0 for r in rows) / len(rows),
                 foreign_notes=statistics.mean(r["foreign"] for r in rows))
        out.append(s)
        print(f"{n_other:2d}x{per:<4d} store={len(store):5d} {name:30s} tok={s['tokens']:7.0f} recall={s['recall']:.2f} "
              f"foreign_runs={s['foreign_runs']:.2f} (avg {s['foreign_notes']:.2f}) stale_runs={s['stale_tasks']:.2f} safe={s['safe']:.2f}", flush=True)
(HERE / "results_adversarial.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
