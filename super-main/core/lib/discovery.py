"""Bounded project map and incremental source retrieval, independent of skill references."""

import ast
import hashlib
import json
import re
import sqlite3
from collections import Counter
from pathlib import Path

from gatekit import iter_project_files, is_within
from project import load_config
from rag import expand_query, normalize

TEXT_EXT = {".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".html", ".css", ".scss",
            ".md", ".json", ".toml", ".yaml", ".yml", ".sql", ".go", ".vue", ".svelte"}
def role_of(rel, sources):
    path = Path(rel)
    for role in ("generated", "reference", "active"):
        for prefix in sources.get(role, []):
            if path == Path(prefix) or Path(prefix) in path.parents:
                return role, "declared:" + prefix
    if re.search(r"(^|/)(tests?|__tests__|e2e)(/|$)|(^|/)test_|\.(test|spec)\.", rel):
        return "test", "test path convention"
    if any(p in {"graphify-out", "generated"} for p in path.parts):
        return "unknown", "possible generated output; inspect and declare the root"
    if path.parts[0] in {"docs", "design", "mockups"} or path.parts[0].startswith("stitch_"):
        return "unknown", "possible reference/mockup; inspect and declare the root"
    if rel in sources.get("entrypoints", []):
        return "active", "declared entrypoint"
    return "unknown", "activation not established"


def files(project):
    for path in iter_project_files(project, TEXT_EXT):
        if path.is_symlink() or not is_within(path, project):
            continue
        if re.search(r"secret|credential|private.key", path.name, re.I):
            continue
        if path.stat().st_size <= 512_000:
            yield path


def build_map(project):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "modules/testing/gates"))
    import testlib
    config = load_config(project)
    sources = config.get("sources", {})
    records = []
    for path in files(project):
        rel = str(path.relative_to(project))
        role, reason = role_of(rel, sources)
        records.append({"path": rel, "role": role, "reason": reason,
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    return {"version": 1, "project": str(project), "files": records,
            "roles": dict(Counter(row["role"] for row in records)),
            "entrypoints": sources.get("entrypoints", []), "suites": testlib.detect_suites(project),
            "pages": [row["path"] for row in records if Path(row["path"]).suffix == ".html" and row["role"] in {"active", "unknown"}],
            "contracts": [row["path"] for row in records if re.search(r"openapi|swagger|schema|migration", row["path"], re.I)],
            "acceptance": config.get("acceptance", []), "product_areas": config.get("product", {}).get("areas", {}),
            "limits": {"max_file_bytes": 512_000, "max_files": 20000},
            "notes": ["Unknown files are not assumed inactive. Declared roots require agent inspection of entrypoints/imports/build configuration."]}


def chunks(path, text):
    lines = text.splitlines()
    if path.suffix == ".py":
        try:
            tree = ast.parse(text)
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    end = node.end_lineno or node.lineno
                    for start in range(node.lineno, end + 1, 100):
                        yield node.name, start, min(start + 99, end), "\n".join(lines[start - 1:min(start + 99, end)])
        except SyntaxError:
            pass
    # Module-level imports, constants and surrounding text remain searchable.
    for start in range(0, len(lines), 100):
        yield "context", start + 1, min(start + 100, len(lines)), "\n".join(lines[start:start + 100])


def search_project(project, query, limit=5, roles=None):
    manifest = build_map(project)
    out = project / ".superagent" / "retrieval"
    out.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(out / "project.db"))
    try:
        db.execute("CREATE TABLE IF NOT EXISTS files(path TEXT PRIMARY KEY, hash TEXT, role TEXT)")
        db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS chunks USING fts5(path, role UNINDEXED, symbol, start UNINDEXED, end UNINDEXED, content, tokenize='unicode61')")
        existing = {p: (h, r) for p, h, r in db.execute("SELECT path, hash, role FROM files")}
        changed = 0
        current = {row["path"] for row in manifest["files"]}
        for stale in existing.keys() - current:
            db.execute("DELETE FROM files WHERE path=?", (stale,))
            db.execute("DELETE FROM chunks WHERE path=?", (stale,))
        for row in manifest["files"]:
            rel, role, sha = row["path"], row["role"], row["sha256"]
            if existing.get(rel) == (sha, role):
                continue
            changed += 1
            db.execute("DELETE FROM chunks WHERE path=?", (rel,))
            text = (project / rel).read_text(encoding="utf-8", errors="replace")
            for symbol, start, end, content in chunks(Path(rel), text):
                db.execute("INSERT INTO chunks VALUES(?,?,?,?,?,?)", (rel, role, symbol, start, end, content))
            db.execute("INSERT OR REPLACE INTO files VALUES(?,?,?)", (rel, sha, role))
        db.commit()
        terms = list(dict.fromkeys(re.findall(r"\w+", normalize(query)) + expand_query(query)))
        if not terms:
            return {"results": [], "updated_files": changed, "notes": ["No searchable terms."]}
        match = " OR ".join('"' + term.replace('"', '""') + '"' for term in terms)
        sql = "SELECT path, role, symbol, start, end, snippet(chunks,5,'','', '...',48), bm25(chunks,8,0,6,0,0,1) FROM chunks WHERE chunks MATCH ?"
        params = [match]
        if roles:
            sql += " AND role IN (" + ",".join("?" for _ in roles) + ")"
            params.extend(roles)
        sql += " ORDER BY bm25(chunks,8,0,6,0,0,1) LIMIT ?"
        params.append(limit)
        hashes = {row["path"]: row["sha256"] for row in manifest["files"]}
        results = [{"path": p, "role": r, "symbol": s, "start": int(a), "end": int(b),
                    "snippet": content, "rank": rank, "sha256": hashes[p]}
                   for p, r, s, a, b, content, rank in db.execute(sql, params)]
        return {"results": results, "updated_files": changed,
                "notes": ["Rank measures lexical relevance, not confidence. Read callers/producers/consumers before concluding; no call graph or embeddings are inferred."]}
    finally:
        db.close()
