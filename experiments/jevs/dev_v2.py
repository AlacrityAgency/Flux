"""Dev-only harness for JEVS v2 tuning. Never imports a holdout file."""
import sys, time, itertools, json
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parents[1] / "src"))
sys.stdout.reconfigure(encoding="utf-8")
import corpus as C, jevs as J, jevs2 as J2, run_experiment as R
from tasks import TASKS
assert "tasks_holdout" not in sys.modules and "tasks_holdout2" not in sys.modules

code, files = R.load_all()
ENVS = [R.build_env(C.build_memory_store(3, 60, s), code, files, key=("main", s)) for s in (0, 1, 2)]

def evaluate(fn, workflows=("low",)):
    rows = []
    for env in ENVS:
        rows.append(R.summarize(R.run_strategy("x", fn, env, workflows=workflows, tasks=TASKS)[workflows[0]]))
    return {k: sum(r[k] for r in rows) / len(rows) for k in ("tokens", "recall", "recall_ctx", "complete", "complete_ctx", "foreign_tasks", "stale_tasks")}

def line(name, m):
    print(f"{name:40s} tok={m['tokens']:7.0f} recall={m['recall']:.3f} ctx={m['recall_ctx']:.3f} "
          f"complete={m['complete']:.2f}/{m['complete_ctx']:.2f}", flush=True)

if __name__ == "__main__":
    line("A1 Flux", evaluate(R.STRATEGIES["A1 الگوریتم فعلی Flux"]))
    line("JEVS v1", evaluate(R.STRATEGIES["JEVS v1"]))
    for b in (1500, 2000, 3000, 4000, 6000):
        t = time.time()
        line(f"v2 default budget={b}", evaluate(R.make_jevs2(J2.Cfg(budget=b))))
