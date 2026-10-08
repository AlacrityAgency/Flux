"""Dev-only configuration grid for JEVS v1 (never touches the holdout tasks)."""
import sys, itertools
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parents[1] / "src"))
sys.stdout.reconfigure(encoding="utf-8")
import corpus as C, jevs as J, run_experiment as R
from tasks import TASKS
code, files = R.load_all()
envs = [R.build_env(C.build_memory_store(3, 60, s), code, files, key=("main", s)) for s in (0, 1, 2)]
rows = []
for stem, prf, sub, theta, budget in itertools.product((False, True), (False, True), (False, True), (0.25, 0.35, 0.5), (4000, 6000)):
    flags = J.Flags(stemming=stem, subchunk=sub, selector="per_criterion", prf=prf, theta=theta)
    res = []
    for env in envs:
        res.append(R.summarize(R.run_strategy("g", R.make_jevs(flags, budget), env, workflows=("low",), tasks=TASKS)["low"]))
    m = lambda k: sum(r[k] for r in res) / len(res)
    rows.append((m("recall"), m("complete"), m("tokens"), stem, prf, sub, theta, budget))
rows.sort(key=lambda r: (-r[0], r[2]))
print("recall complete tokens | stem prf subchunk theta budget")
for r in rows[:14]:
    print(f"{r[0]:.3f} {r[1]:.2f} {r[2]:7.0f} | {r[3]!s:5} {r[4]!s:5} {r[5]!s:5} {r[6]} {r[7]}")
print("...")
for r in rows[-4:]:
    print(f"{r[0]:.3f} {r[1]:.2f} {r[2]:7.0f} | {r[3]!s:5} {r[4]!s:5} {r[5]!s:5} {r[6]} {r[7]}")
