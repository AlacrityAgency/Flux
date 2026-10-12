"""Local reference search: SQLite FTS5 + BM25 over every Markdown file in core/ and modules/.

- Each section is indexed with its module ("core", "ui-ux", "testing", ...), so searches can be filtered.
- Persian queries are normalised and expanded through core/rag/glossary.json before matching
  English documents.
- The index is rebuilt automatically when any indexed file is added, removed or modified.
"""

import hashlib
import json
import re
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


SKILL_DIR = Path(__file__).resolve().parents[2]
GLOSSARY_PATH = SKILL_DIR / "core" / "rag" / "glossary.json"
SOURCE_DIRS = ("core", "modules")
HEADING = re.compile(r"^(#{1,4})\s+(.+)$")
PERSIAN_FIXES = str.maketrans({"ي": "ی", "ك": "ک", "ة": "ه", "‌": " ", "‏": "", "‎": ""})
DIACRITICS = re.compile("[ً-ٰٟ]")


def default_db_path() -> Path:
    """Index next to the skill when writable, otherwise in the user's temp directory."""
    candidate = SKILL_DIR / "core" / "rag" / "index.db"
    try:
        candidate.parent.mkdir(parents=True, exist_ok=True)
        probe = candidate.parent / ".write-probe"
        probe.write_text("ok")
        probe.unlink()
        return candidate
    except OSError:
        return Path(tempfile.gettempdir()) / "superagent-skill-index.db"


def normalize(text: str) -> str:
    return DIACRITICS.sub("", text.translate(PERSIAN_FIXES)).lower()


def load_glossary(path: Path = GLOSSARY_PATH) -> List[Tuple[str, List[str]]]:
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = [(normalize(term), keywords) for term, keywords in data.get("terms", {}).items()]
    return sorted(entries, key=lambda e: -len(e[0]))  # longest phrases first


def source_files(root: Path = SKILL_DIR) -> List[Path]:
    files: List[Path] = []
    for name in SOURCE_DIRS:
        base = root / name
        if base.is_dir():
            files.extend(p for p in base.rglob("*.md") if "node_modules" not in p.parts)
    return sorted(files)


def module_of(path: Path, root: Path) -> str:
    parts = path.relative_to(root).parts
    if parts[0] == "modules" and len(parts) > 1:
        return parts[1]
    return parts[0]


def parse_sections(path: Path) -> List[Tuple[str, str]]:
    sections: List[Tuple[str, str]] = []
    heading, lines = "Overview", []
    in_code = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("```"):
            in_code = not in_code
        match = None if in_code else HEADING.match(line.strip())
        if match:
            body = "\n".join(lines).strip()
            if body:
                sections.append((heading, body))
            heading, lines = match.group(2).strip(), []
        else:
            lines.append(line)
    body = "\n".join(lines).strip()
    if body or not sections:
        sections.append((heading, body))
    return sections


def manifest(files: List[Path]) -> str:
    digest = hashlib.sha256()
    for path in files:
        digest.update(str(path).encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def build_index(db_path: Path, root: Path = SKILL_DIR, files: Optional[List[Path]] = None) -> int:
    files = files if files is not None else source_files(root)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.cursor()
        cur.execute("DROP TABLE IF EXISTS docs_fts")
        cur.execute("DROP TABLE IF EXISTS meta")
        cur.execute("CREATE VIRTUAL TABLE docs_fts USING fts5(module, path, section, content, tokenize = 'porter unicode61')")
        cur.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
        count = 0
        for path in files:
            rel = str(path.relative_to(root))
            for section, content in parse_sections(path):
                cur.execute("INSERT INTO docs_fts VALUES (?, ?, ?, ?)", (module_of(path, root), rel, section, content))
                count += 1
        cur.execute("INSERT INTO meta VALUES ('manifest', ?)", (manifest(files),))
        conn.commit()
        return count
    finally:
        conn.close()


def ensure_index(db_path: Path, root: Path = SKILL_DIR) -> None:
    files = source_files(root)
    wanted = manifest(files)
    if db_path.is_file():
        try:
            conn = sqlite3.connect(str(db_path))
            row = conn.execute("SELECT value FROM meta WHERE key = 'manifest'").fetchone()
            conn.close()
            if row and row[0] == wanted:
                return
        except sqlite3.Error:
            pass
    build_index(db_path, root, files)


def expand_query(raw: str, glossary: Optional[List[Tuple[str, List[str]]]] = None) -> List[str]:
    """Return search terms: English words from the query plus glossary expansions of Persian phrases."""
    glossary = load_glossary() if glossary is None else glossary
    text = normalize(raw)
    terms: List[str] = []
    for phrase, keywords in glossary:
        # Whole-word match so short terms (e.g. «تب») do not fire inside longer words.
        pattern = re.compile(rf"(?<!\w){re.escape(phrase)}(?!\w)")
        if phrase and pattern.search(text):
            terms.extend(keywords)
            text = pattern.sub(" ", text)
    for token in re.findall(r"[a-z0-9]+", text):
        if token not in {"or", "and", "not", "near"} and len(token) > 1:
            terms.append(token)
    seen, unique = set(), []
    for term in terms:
        for word in re.findall(r"[a-z0-9]+", term.lower()):
            if word not in seen and len(word) > 1:
                seen.add(word)
                unique.append(word)
    return unique


def search(query: str, module: Optional[str] = None, limit: int = 5, db_path: Optional[Path] = None,
           root: Path = SKILL_DIR, glossary: Optional[List[Tuple[str, List[str]]]] = None) -> List[Dict[str, Any]]:
    db_path = db_path or default_db_path()
    ensure_index(db_path, root)
    terms = expand_query(query, glossary)
    if not terms:
        return []
    match = " OR ".join(f'"{t}"' for t in terms)
    sql = (
        "SELECT module, path, section, snippet(docs_fts, 3, '>>> ', ' <<<', '...', 24), bm25(docs_fts, 0.0, 0.0, 5.0, 1.0) AS rank "
        "FROM docs_fts WHERE docs_fts MATCH ?"
    )
    params: List[Any] = [match]
    if module:
        sql += " AND module IN (?, 'core')"
        params.append(module)
    sql += " ORDER BY rank LIMIT ?"
    params.append(limit)
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute(sql, params).fetchall()
    except sqlite3.Error as exc:
        print(f"search error: {exc}", file=sys.stderr)
        return []
    finally:
        conn.close()
    return [
        {"module": m, "path": p, "section": s, "snippet": snip, "score": round(r, 4), "terms": terms}
        for m, p, s, snip, r in rows
    ]
