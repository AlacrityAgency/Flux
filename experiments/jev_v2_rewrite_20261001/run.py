"""Standalone context builder for a project. No model calls and no Flux database writes."""
import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
import corpus as C
import optimized_v2 as O

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root",type=Path,required=True)
    parser.add_argument("--project-id",required=True)
    parser.add_argument("--task",type=Path,required=True)
    parser.add_argument("--memory",type=Path)
    parser.add_argument("--budget",type=int,default=3000)
    parser.add_argument("--output",type=Path,required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    if not root.is_dir() or not args.project_id.strip():
        parser.error("An existing project directory and non-empty project ID are required")
    payload = json.loads(args.task.read_text(encoding="utf-8-sig"))
    if payload.get("project_id",args.project_id) != args.project_id:
        parser.error("Task project_id does not match --project-id")
    raw = payload.get("criteria",payload.get("acceptance_criteria",[]))
    criteria = [{"text":c if isinstance(c,str) else c["text"]} for c in raw]
    task = {"objective":payload["objective"],"project_id":args.project_id,"criteria":criteria}
    chunks, memories = [], []
    for c in C.load_code_corpus(root,include_docs=True):
        c.project_id = args.project_id
        if c.kind == "doc":
            title = c.id.split("#",1)[-1]
            memories.append(C.Memory(c.id,args.project_id,title,c.text,source=c.path))
        else:
            chunks.append(c)
    if args.memory:
        records=json.loads(args.memory.read_text(encoding="utf-8-sig"))
        for record in records:
            memories.append(C.Memory(**record))
    cfg = O.Config(budget=args.budget)
    pack = O.Index(chunks,memories,cfg).select(task)
    result = {"project_id":args.project_id,"root":str(root),"tokenizer":"o200k_base",
              "config":asdict(cfg),"context_tokens":pack.tokens,
              "worker_context":O.worker_context(pack),"head_context":O.head_context(pack),
              "assessments":pack.assessments,"trace":pack.trace,
              "algorithm_sha256":hashlib.sha256(Path(O.__file__).read_bytes()).hexdigest(),
              "model_calls":0}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"context_tokens":pack.tokens,"selected_units":len(pack.order),
                      "model_calls":0,"output":str(args.output)},ensure_ascii=True))

if __name__ == "__main__":
    main()
