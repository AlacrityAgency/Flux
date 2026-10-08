"""Where does each missed evidence unit get lost?  retrieval | packing | windowing"""
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parents[1] / "src"))
sys.stdout.reconfigure(encoding="utf-8")
import corpus as C, jevs as J
from tasks import TASKS
import run_experiment as R
from collections import Counter

def analyse(flags=None, budget=6000, tasks=TASKS, verbose=True):
    flags = flags or J.v1_flags()
    norm = R.norm
    code = C.load_code_corpus()
    store = C.build_memory_store(3, 60, 0)
    idx = J.Index(code, store, subchunk=flags.subchunk, stemming=flags.stemming)
    stages = Counter(); rows = []
    for t in tasks:
        pack = idx.select(t, budget, flags)
        chosen = {d.meta.get("parent", d.id): part for d, txt, part in pack.items}
        text = R.ctx_text(J.worker_context(pack))
        obj = idx.query(t["objective"], flags.glossary); union = dict(obj)
        for c in t["criteria"]:
            for k, w in idx.query(c["text"], flags.glossary).items(): union[k] = max(union.get(k, 0), w)
        elig = [d for d in idx.docs if d.project_id in (t["project_id"], "global") and d.status == "active"]
        rank = {}
        for i, (s, d) in enumerate(sorted(((idx.bm25(union, d), d) for d in elig), key=lambda x: -x[0])):
            if s > 0: rank.setdefault(d.meta.get("parent", d.id), i + 1)
        for c in t["criteria"]:
            for kind, val in c["needs"]:
                if kind == "mem":
                    owners = [val]
                else:
                    owners = [d.id for d in idx.docs if d.kind == "code" and any(norm(a) in norm(d.text) for a in val)]
                ok = R.present((kind, val), text)
                best = min((rank.get(o, 10**9) for o in owners), default=10**9)
                inpack = [o for o in owners if o in chosen]
                if ok: st = "hit"
                elif not owners: st = "not_in_corpus"
                elif best > J.CANDIDATES_K: st = "not_retrieved(rank>80)"
                elif not inpack: st = "retrieved_not_packed"
                else: st = "packed_but_anchor_windowed_out"
                stages[st] += 1
                rows.append((t["id"], kind, (val if kind == "mem" else val[0])[:55], st, best if best < 10**9 else None))
    if verbose:
        print(dict(stages))
        for r in rows:
            if r[3] != "hit": print(r)
    return stages, rows

if __name__ == "__main__":
    analyse()
