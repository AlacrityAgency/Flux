"""Isolated rerun of the two EXISTING local selectors, not the TypeSafe Jev model.
No runtime integration, no gold evidence supplied to retrieval, no parameter tuning.
"""
from __future__ import annotations
import hashlib, json, re, statistics, sys, time
from pathlib import Path
from dataclasses import asdict
import tiktoken

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.stdout.reconfigure(encoding="utf-8")
import corpus as C
import jevs as J
import tasks
DEV = list(tasks.TASKS)
import tasks_holdout
EVAL = list(tasks_holdout.HOLDOUT)
ENC = tiktoken.get_encoding("o200k_base")
count = lambda s: len(ENC.encode(s, disallowed_special=()))
norm = lambda s: re.sub(r"\s+", " ", s)
BUDGETS = (1500, 3000, 6000)

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def save(name, data):
    (HERE / name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def materialize():
    dest = HERE / "corpus_snapshot.json"
    if dest.exists():
        snap = json.loads(dest.read_text(encoding="utf-8"))
        return [C.Chunk(**c) for c in snap["chunks"]], [C.Memory(**m) for m in snap["memories"]]
    chunks = C.load_code_corpus(ROOT)
    memories = C.load_flux_doc_memories(ROOT) + list(C.DECISIONS)
    memories += C.synth_memories("flux", 80, 42)
    for k in range(4):
        memories += C.synth_memories(f"other{k}", 80, 42)
    save("corpus_snapshot.json", {"chunks": [asdict(c) for c in chunks],
                                  "memories": [asdict(m) for m in memories]})
    return chunks, memories

def evidence(t, text):
    """Evaluator only. All literal anchors must appear; this is NOT answer grading."""
    ntext = norm(text)
    hit, total, details = 0, 0, []
    for criterion in t["criteria"]:
        outcomes = []
        for kind, needed in criterion["needs"]:
            found = needed in text if kind == "mem" else all(norm(a) in ntext for a in needed)
            hit += int(found)
            total += 1
            outcomes.append({"kind": kind, "required": needed, "found": found})
        details.append({"criterion": criterion["text"], "needs": outcomes,
                        "complete": all(x["found"] for x in outcomes)})
    return {"hits": hit, "total": total, "recall": hit / total,
            "complete": hit == total, "details": details}

def retrieve(index, task, budget, flags):
    # Gold anchors and forbid records deliberately stripped before retrieval.
    public = {"objective": task["objective"], "project_id": task["project_id"],
              "criteria": [{"text": c["text"]} for c in task["criteria"]]}
    start = time.perf_counter()
    pack = index.select(public, budget, flags)
    elapsed = (time.perf_counter() - start) * 1000
    text = "\n\n".join(body for _, body, _ in pack.items)
    actual = count(text)
    assert actual <= budget, (task["id"], actual, budget)
    assert all(d.project_id in (task["project_id"], "global") for d, _, _ in pack.items)
    assert all(d.status == "active" for d, _, _ in pack.items)
    return pack, text, actual, elapsed

def main():
    chunks, memories = materialize()
    # Exact local tokenizer replaces ONLY the selector's cost estimate. Selection logic/flags unchanged.
    J.est_tokens = count
    flags = {"v0": J.Flags(), "v1": J.v1_flags()}
    build_times, indices = {}, {}
    for label, f in flags.items():
        start = time.perf_counter()
        indices[label] = J.Index(chunks, memories, subchunk=f.subchunk, stemming=f.stemming)
        build_times[label] = time.perf_counter() - start
    all_raw = "\n\n".join([c.text for c in chunks] + [f"{m.id}\n{m.content}" for m in memories])
    scoped_raw = "\n\n".join([f"[{c.id}]\n{c.text}" for c in chunks if c.project_id == "flux"] +
                                [f"[mem:{m.id}]\n{m.title}\n{m.content}" for m in memories
                                 if m.project_id == "flux" and m.status == "active"])
    invalid = []
    for task in DEV + EVAL:
        sc = evidence(task, all_raw)
        if not sc["complete"]:
            invalid.append({"task": task["id"], "missing": [d for d in sc["details"] if not d["complete"]]})
    excluded = {x["task"] for x in invalid}
    save("protocol.json", {"budgets": BUDGETS, "tokenizer": "o200k_base", "count_override": True,
          "flags": {k: asdict(v) for k, v in flags.items()}, "chunk_count": len(chunks),
          "memory_count": len(memories), "invalid_ground_truth": invalid,
          "limits": ["Local lexical selectors, not TypeSafe Jev", "Evidence presence, not answer quality",
                     "Existing ten additional cases are reused; this is not a new blind holdout",
                     "Source-derived memories plus synthetic decisions/noise", "No end-to-end Flux execution"]})
    rows = []
    for split, taskset in (("development", DEV), ("additional", EVAL)):
        for task in taskset:
            if task["id"] in excluded:
                continue
            for budget in BUDGETS:
                for label, f in flags.items():
                    pack, text, actual, elapsed = retrieve(indices[label], task, budget, f)
                    sc = evidence(task, text)
                    row = {"task": task["id"], "lang": task["lang"], "split": split,
                           "algorithm": label, "budget": budget, "context_tokens": actual,
                           "selection_ms": elapsed, "selected_count": len(pack.items),
                           "foreign": sum(d.project_id not in (task["project_id"], "global") for d, _, _ in pack.items),
                           "obsolete": sum(d.status != "active" for d, _, _ in pack.items),
                           "selected_ids": [d.id for d, _, _ in pack.items], "gaps": pack.gaps, **sc}
                    rows.append(row)
                    if budget == 3000:
                        (HERE / f"context_{task['id']}_{label}.txt").write_text(text, encoding="utf-8")
        print(f"Completed {split}: {len(taskset)} scenarios", flush=True)
    summary = []
    for split in ("all", "development", "additional"):
        for budget in BUDGETS:
            for label in flags:
                selected = [r for r in rows if r["algorithm"] == label and r["budget"] == budget
                            and (split == "all" or r["split"] == split)]
                hit, total = sum(r["hits"] for r in selected), sum(r["total"] for r in selected)
                summary.append({"split": split, "algorithm": label, "budget": budget, "tasks": len(selected),
                                "hits": hit, "total": total, "evidence_recall": hit / total,
                                "complete_tasks": sum(r["complete"] for r in selected),
                                "mean_context_tokens": statistics.mean(r["context_tokens"] for r in selected),
                                "median_selection_ms": statistics.median(r["selection_ms"] for r in selected),
                                "foreign": sum(r["foreign"] for r in selected),
                                "obsolete": sum(r["obsolete"] for r in selected)})
    output = {"summary": summary, "rows": rows, "index_seconds": build_times,
              "dump_all_scoped_tokens": count(scoped_raw), "invalid_ground_truth": invalid}
    save("results.json", output)
    save("tasks_snapshot.json", DEV + EVAL)
    manifest = {p.name: digest(p) for p in sorted(HERE.glob("*.py"))}
    manifest["corpus_snapshot.json"] = digest(HERE / "corpus_snapshot.json")
    manifest["tasks_snapshot.json"] = digest(HERE / "tasks_snapshot.json")
    save("manifest.json", manifest)
    print(json.dumps({"all": [s for s in summary if s["split"] == "all"],
                      "invalid": invalid, "scoped_dump_tokens": output["dump_all_scoped_tokens"]},
                     ensure_ascii=False, indent=2), flush=True)

if __name__ == "__main__":
    main()
