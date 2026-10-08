"""Dev-only grid for v2 options."""
import sys
import time
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import dev_v2 as D, jevs2 as J2, run_experiment as R

BASE = dict(graph=True, fa_stop=True, fa_translated=0.5, path_prior=True, dedup_lines=True)


def run(label, **kw):
    t = time.time()
    m = D.evaluate(R.make_jevs2(J2.Cfg(**{**BASE, **kw})))
    D.line(label + f" ({time.time() - t:.0f}s)", m)
    return m


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "vocab"
    if which == "vocab":
        for b in (3000, 4000):
            run(f"base b={b}", budget=b)
            run(f"morph.7 b={b}", budget=b, morph=0.7)
            for lam in (0.2, 0.35, 0.5):
                run(f"lsa{lam} b={b}", budget=b, lsa=lam)
            run(f"morph.7+lsa.35 b={b}", budget=b, morph=0.7, lsa=0.35)
    if which == "budget":
        for b in (1500, 2000, 2500, 3000, 4000, 5000, 6000):
            run(f"fixed b={b}", budget=b)
        for pc in (400, 500, 600, 700, 800, 1000):
            run(f"per_crit={pc}", budget=99999, per_crit=pc)
    if which == "dims":
        for d in (64, 128, 256):
            run(f"lsa.35 dims={d} b=3000", budget=3000, morph=0.7, lsa=0.35, lsa_dims=d)
