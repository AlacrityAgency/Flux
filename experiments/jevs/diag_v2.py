"""Dev-only: where does v2 lose each needed anchor?"""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_experiment as R, corpus as C, jevs2 as J2
from tasks import TASKS
from collections import Counter

def diag(cfg, show=True):
    code = C.load_code_corpus(); store = C.build_memory_store(3, 60, 0)
    idx = J2.Index2(code, store, cfg)
    st = Counter()
    for t in TASKS:
        pack = J2.select(idx, t, cfg)
        text = R.ctx_text(J2.worker_context(pack))
        ok = lambda u: u.project_id == "flux" and u.status == "active"
        for ci, c in enumerate(t["criteria"]):
            q = {k: w * .5 for k, w in idx.query(t["objective"]).items()}
            for k, w in idx.query(c["text"]).items(): q[k] = max(q.get(k, 0), w)
            ranked = idx.score(q, ok)
            for kind, val in c["needs"]:
                if R.present((kind, val), text):
                    st["hit"] += 1; continue
                if kind == "mem":
                    pos = next((i for i, (s, p) in enumerate(ranked) if p.unit.id == val), None)
                else:
                    a = R.norm(val[0])
                    pos = next((i for i, (s, p) in enumerate(ranked) if a in R.norm("\n".join(p.unit.lines[p.a:p.b]))), None)
                top = ranked[0][0] if ranked else 0
                sc = ranked[pos][0] / top if pos is not None else 0
                why = "no_lexical_match" if pos is None else ("below_theta" if sc < cfg.theta else ("beyond_k" if pos >= cfg.k_per_crit else "budget/order"))
                st[why] += 1
                if show:
                    print(f"{t['id']} c{ci} {kind:4s} rank={pos} rel={sc:.2f} {why:16s} {(val if kind=='mem' else val[0])[:60]}")
    print(dict(st))

if __name__ == "__main__":
    diag(J2.Cfg(budget=3000))
