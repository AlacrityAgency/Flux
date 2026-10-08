"""Development-only by default; frozen additional cases require --evaluate.
Gold evidence never enters the retrieval interface. No model requests.
"""
import argparse, hashlib, importlib, json, re, statistics, sys, time
from dataclasses import asdict, replace
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.stdout.reconfigure(encoding="utf-8")
import corpus as C
import jevs as J
import prior_v2 as P
import optimized_v2 as O
import tasks
DEV = list(tasks.TASKS)
norm = lambda text: re.sub(r"\s+", " ", text)

def save(name, data):
    (HERE / name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def load():
    s = json.loads((HERE / "corpus_snapshot.json").read_text(encoding="utf-8"))
    return [C.Chunk(**c) for c in s["chunks"]], [C.Memory(**m) for m in s["memories"]]

class Evaluator:
    def __init__(self, chunks, memories):
        grouped = {}
        self.chunk_files = {c.id: c.path for c in chunks}
        for c in chunks:
            grouped.setdefault(c.path, []).append(c.text)
        self.chunks = {path: norm("\n".join(parts)) for path,parts in grouped.items()}
        self.memories = {m.id: norm(m.title + "\n" + m.content) for m in memories}
        self.sources = {}

    def score(self, task, blocks):
        hits, total, details = 0, 0, []
        grouped = {}
        for id,text in blocks:
            if id in self.chunk_files:
                grouped.setdefault(self.chunk_files[id], []).append(text)
        source_blocks = {path: norm("\n".join(parts)) for path,parts in grouped.items()}
        for ci, criterion in enumerate(task["criteria"]):
            needs = []
            for kind, evidence in criterion["needs"]:
                if kind == "code":
                    key = tuple(evidence)
                    if key not in self.sources:
                        self.sources[key] = {id for id, text in self.chunks.items() if all(norm(a) in text for a in evidence)}
                    allowed = self.sources[key]
                    assert allowed, (task["id"], evidence, "stale benchmark ground truth")
                    found = any(path in allowed and all(norm(a) in text for a in evidence) for path,text in source_blocks.items())
                else:
                    assert evidence in self.memories
                    found = any(id == evidence and self.memories[evidence] in norm(text) for id, text in blocks)
                needs.append({"kind": kind, "required": evidence, "found": found})
                hits += int(found)
                total += 1
            details.append({"criterion_index": ci, "criterion": criterion["text"], "needs": needs,
                            "complete": all(n["found"] for n in needs)})
        return {"hits": hits, "total": total, "recall": hits / total,
                "complete": hits == total, "details": details}

def public(task):
    return {"objective": task["objective"], "project_id": task["project_id"],
            "criteria": [{"text": c["text"]} for c in task["criteria"]]}

def summarize(rows):
    return {"tasks": len(rows), "hits": sum(r["hits"] for r in rows), "needs": sum(r["total"] for r in rows),
            "micro_recall": sum(r["hits"] for r in rows) / sum(r["total"] for r in rows),
            "macro_recall": statistics.mean(r["recall"] for r in rows),
            "complete_tasks": sum(r["complete"] for r in rows),
            "mean_context_tokens": statistics.mean(r["tokens"] for r in rows),
            "median_select_ms": statistics.median(r["select_ms"] for r in rows),
            "foreign": sum(r["foreign"] for r in rows), "obsolete": sum(r["obsolete"] for r in rows)}

def evaluate(label, config, taskset, chunks, memories, evaluator):
    start = time.perf_counter()
    if label == "v1":
        flags = J.v1_flags()
        index = J.Index(chunks, memories, subchunk=flags.subchunk, stemming=flags.stemming)
    elif label == "prior_v2":
        cfg = P.Cfg(budget=config.budget)
        index = P.Index2(chunks, memories, cfg)
    else:
        index = O.Index(chunks, memories, config)
        index.space("flux")
    build_ms = (time.perf_counter() - start) * 1000
    rows = []
    for task in taskset:
        start = time.perf_counter()
        if label == "v1":
            pack = index.select(public(task), config.budget, flags)
            blocks = [(d.meta.get("parent",d.id), text) for d,text,_ in pack.items]
            units = [d for d,_,_ in pack.items]
            assessments = [{"retrieval_status": "missing"} for _ in pack.gaps]
            text = "\n\n".join(t for _,t in blocks)
        elif label == "prior_v2":
            pack = P.select(index, public(task), cfg)
            blocks = [(u.id,P.render_unit(u,pack.keep[u])) for u in pack.order]
            units = pack.order
            assessments = [{"retrieval_status": "missing"} for _ in pack.gaps]
            text = "\n\n".join(t for _,t in blocks)
        else:
            pack = index.select(public(task), config)
            blocks = [(u.id,O.render(u,pack.keep[u])) for u in pack.order]
            units, assessments, text = pack.order, pack.assessments, pack.content
        elapsed = (time.perf_counter() - start)*1000
        tokens = O.token_count(text)
        assert tokens <= config.budget
        foreign = sum(u.project_id not in (task["project_id"],"global") for u in units)
        obsolete = sum(u.status != "active" for u in units)
        assert not foreign and not obsolete
        row = {"id": task["id"], "algorithm": label, "budget":config.budget, "tokens":tokens,
               "select_ms":elapsed, "foreign":foreign, "obsolete":obsolete,
               "assessments": assessments, "selected_ids":[u.id for u in units], **evaluator.score(task,blocks)}
        rows.append(row)
        folder = HERE / "contexts" / f"{label}_{config.budget}"
        folder.mkdir(parents=True,exist_ok=True)
        (folder / f"{task['id']}.txt").write_text(text,encoding="utf-8")
    return {"summary":summarize(rows),"rows":rows,"build_ms":build_ms,"config":asdict(config)}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--evaluate",action="store_true")
    parser.add_argument("--tune",action="store_true")
    args = parser.parse_args()
    chunks,memories=load()
    evaluator=Evaluator(chunks,memories)
    J.est_tokens=O.token_count
    base=O.Config()
    if args.tune:
        assert "tasks_holdout" not in sys.modules and "tasks_extra" not in sys.modules
        variants={"rewrite_default":base,
                  "rewrite_small":replace(base,window=4,stride=2,neighbours=2),
                  "rewrite_focus":replace(base,objective_weight=0.05,name_weight=1.5),
                  "rewrite_wide":replace(base,window=12,stride=6,neighbours=1),
                  "rewrite_no_graph":replace(base,graph=False),
                  "rewrite_no_prior":replace(base,source_prior=False)}
        out={}
        for label,cfg in {"v1":base,"prior_v2":base,**variants}.items():
            out[label]=evaluate(label,cfg,DEV,chunks,memories,evaluator)
            print(label,json.dumps(out[label]["summary"],ensure_ascii=False),flush=True)
        save("development.json",out)
        return
    config_file=HERE/"chosen_config.json"
    cfg=O.Config(**json.loads(config_file.read_text(encoding="utf-8"))) if config_file.exists() else base
    sets={"development":DEV}
    if args.evaluate:
        frozen=json.loads((HERE/"frozen_candidate.json").read_text(encoding="utf-8"))
        for name,expected in frozen.items():
            assert hashlib.sha256((HERE/name).read_bytes()).hexdigest()==expected,(name,"changed after freezing")
        module=importlib.import_module("tasks_holdout")
        sets["regression"]=list(module.HOLDOUT)
        # Imported only after candidate is frozen; the file was copied before development runs.
        extra=importlib.import_module("tasks_extra")
        lists=[v for k,v in vars(extra).items() if k.startswith("HOLDOUT") and isinstance(v,list)]
        if not lists:
            lists=[v for k,v in vars(extra).items() if k in ("H","H2","TASKS") and isinstance(v,list)]
        assert lists,"No additional scenarios exported"
        sets["additional"]=list(lists[0])
    output={}
    for split,taskset in sets.items():
        output[split]={}
        for budget in (1500,3000,6000):
            output[split][budget]={}
            for label in ("v1","prior_v2","rewrite"):
                result=evaluate(label,replace(cfg,budget=budget),taskset,chunks,memories,evaluator)
                output[split][budget][label]=result
                print(split,budget,label,json.dumps(result["summary"],ensure_ascii=False),flush=True)
    save("evaluation.json" if args.evaluate else "dev_final.json",output)
    save("evaluation_tasks.json",sets)

if __name__=="__main__":
    main()
