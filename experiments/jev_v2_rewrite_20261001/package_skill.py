"""Package the tested selector without benchmark corpora, gold tasks or synthetic decisions."""
import ast, hashlib, json
from pathlib import Path
HERE=Path(__file__).resolve().parent
DEST=Path("C:/Users/xio/.codex/skills/project-evidence-rag-v2")

def extract(path,names,header):
    raw=path.read_text(encoding="utf-8")
    lines=raw.splitlines()
    found={}
    for node in ast.parse(raw).body:
        if isinstance(node,(ast.FunctionDef,ast.ClassDef)):
            keys={node.name}
        elif isinstance(node,ast.Assign):
            keys={t.id for t in node.targets if isinstance(t,ast.Name)}
        else:
            continue
        for key in keys & names:
            first=min([node.lineno]+[d.lineno for d in getattr(node,"decorator_list",[])])
            found[key]=(first,"\n".join(lines[first-1:node.end_lineno]))
    assert set(found)==names,names-set(found)
    return header+"\n\n"+"\n\n".join(text for _,text in sorted(found.values()))+"\n"

def main():
    assert not DEST.exists(),"Existing skill must be reviewed before replacement"
    scripts=DEST/"scripts"
    scripts.mkdir(parents=True)
    (scripts/"optimized_v2.py").write_bytes((HERE/"optimized_v2.py").read_bytes())
    (scripts/"run.py").write_bytes((HERE/"run.py").read_bytes())
    legacy=extract(HERE/"jevs.py",{"STOP","GLOSSARY","_ID_SPLIT","_WORD","normalize","stem","tokenize"},
                   '"""Shared normalization vocabulary; no benchmark tasks or selector baseline."""\nimport re')
    (scripts/"jevs.py").write_text(legacy,encoding="utf-8")
    corpus=extract(HERE/"corpus.py",{"IGNORED_DIRS","TEXT_EXT","SENSITIVE","SPLIT_FN_LINES","WINDOW_LINES", "Chunk","Memory",
                  "project_files","_py_chunks","_window_chunks","_md_sections","load_code_corpus"},
                 '"""Source-only corpus loader; no generated decisions or test gold."""\nfrom __future__ import annotations\n'
                 'import ast, re\nfrom dataclasses import dataclass, field\nfrom pathlib import Path\nFLUX_ROOT=Path.cwd()')
    (scripts/"corpus.py").write_text(corpus,encoding="utf-8")
    (DEST/"SKILL.md").write_text('''---
name: project-evidence-rag-v2
description: Build a project-scoped RAG evidence pack under an exact token budget for source-code investigation or project-memory retrieval.
---

Prepare compact source evidence with the bundled local selector. Requires Python and `tiktoken`.
This is a local retrieval algorithm; it does not call TypeSafe Jev or a generative model.

1. Use the selected project's root and a stable project ID. Keep the user's objective and acceptance criteria unchanged.
2. Save a temporary task JSON with `objective`, `project_id`, and `criteria` (strings or objects containing `text`).
3. Run `scripts/run.py` relative to this skill directory:

```text
python scripts/run.py --root PROJECT_ROOT --project-id PROJECT_ID --task TASK_JSON --budget 3000 --output PACK_JSON
```

Optionally pass `--memory MEMORY_JSON`: an array of records with `id`, `project_id`, `title`, `content`, and optional `status`, `revision`, `superseded_by`, `source`. Active records of the selected project and explicit `global` records are eligible. The latest revision of a stable ID wins within a project.

Use `head_context` to route work and `worker_context` as selected evidence. Source excerpts include owner signatures, bounded enclosing expressions and omitted-line markers. Chunk-line positions are relative to the original indexed chunk, not absolute file line numbers.

The 3000-token limit covers the rendered worker evidence including the verification warning. Task instructions, message framing and model output require separate budgets. `o200k_base` counts are local, not provider billing.

Inspect `assessments`: `missing` means no typed criterion candidate was selected; `candidate` does not establish semantic sufficiency. `semantic_sufficiency` remains `unverified`. Check each criterion against the cited source; when evidence is incomplete, retrieve the missing source or report the limitation. An indexed test function does not mean a test was executed.

The helper reads project files and writes only the requested pack. It does not mutate project memory, execute project code or integrate with Flux. Do not feed evaluation gold anchors into a task used to measure retrieval quality.
''',encoding="utf-8")
    manifest={str(p.relative_to(DEST)).replace("\\","/"):hashlib.sha256(p.read_bytes()).hexdigest() for p in DEST.rglob("*") if p.is_file()}
    (HERE/"skill_manifest.json").write_text(json.dumps({"directory":str(DEST),"files":manifest},indent=2),encoding="utf-8")
    print("Created",DEST,"with",len(manifest),"files; no benchmark inputs included")

if __name__=="__main__":
    main()
