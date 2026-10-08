"""Dev-only: robustness of v2 to a large, noisy same-project memory store (no holdout task is imported)."""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import corpus as C, jevs2 as J2, run_experiment as R
from tasks import TASKS
assert "tasks_holdout" not in sys.modules and "tasks_holdout2" not in sys.modules

code, files = R.load_all()
STORES = {"main 280": [(3, 60, s) for s in (0, 1, 2)], "noisy 3340": [(10, 300, s) for s in (0, 1)],
          "noisy 21040": [(20, 1000, 0)]}
ENVS = {k: [R.build_env(C.build_memory_store(*a), code, files) for a in v] for k, v in STORES.items()}


def ev(cfg):
    out = []
    for k, envs in ENVS.items():
        rs = [R.summarize(R.run_strategy("x", R.make_jevs2(cfg), e, workflows=("low",), tasks=TASKS)["low"]) for e in envs]
        out.append((k, sum(r["tokens"] for r in rs) / len(rs), sum(r["recall"] for r in rs) / len(rs)))
    return out


for label, cfg in [("v2 economy", J2.v2_cfg()), ("v2 accurate", J2.v2_cfg("accurate")),
                   ("v2 note_every=2", J2.v2_cfg(note_every=2)), ("v2 note_every=3", J2.v2_cfg(note_every=3)),
                   ("v2 note_every=4", J2.v2_cfg(note_every=4))]:
    print(f"{label:18s} " + "  ".join(f"{k}: tok={t:6.0f} recall={r:.3f}" for k, t, r in ev(cfg)), flush=True)
