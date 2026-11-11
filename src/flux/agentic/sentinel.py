"""Context Sentinel: Coding Standards Re-Injection & Persistent Error Memory.

Prevents Context Drift in long chats by re-injecting compressed project standards
(``AGENTS.md``, ``CLAUDE.md``, ``.cursorrules``, ``.flux/rules.md``) on every turn,
and automatically records & recalls repository-specific compiler/test pitfalls so
the model never repeats past mistakes.
"""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from pathlib import Path

from flux.storage.workspace import now

RULE_FILES = [
    "AGENTS.md",
    "CLAUDE.md",
    ".cursorrules",
    ".flux/rules.md",
    ".github/copilot-instructions.md",
]

_WORD_RE = re.compile(r"[A-Za-z_\u0600-\u06FF][A-Za-z0-9_\u0600-\u06FF]{2,}")


def _compress_markdown_rules(text: str, budget: int) -> str:
    """Keep headings, bullet rules, and MUST/NEVER/IMPORTANT lines within budget."""
    lines = [ln.rstrip() for ln in text.splitlines()]
    cleaned = [ln for ln in lines if ln.strip() and not ln.strip().startswith("<!--")]
    joined = "\n".join(cleaned)
    if len(joined) <= budget:
        return joined
    priority, normal = [], []
    for ln in cleaned:
        s = ln.strip()
        if s.startswith(("#", "-", "*", "1.", "2.", "3.", ">")) or any(
            kw in s.lower() for kw in ("must", "never", "always", "important", "الزامی", "هرگز", "حتماً")
        ):
            priority.append(ln)
        else:
            normal.append(ln)
    out, used = [], 0
    for ln in (*priority, *normal):
        if used + len(ln) + 1 > budget:
            break
        out.append(ln)
        used += len(ln) + 1
    return "\n".join(out)


class ContextSentinel:
    def __init__(self, repo):
        self.repo, self.conn = repo, repo.conn
        with self.repo._lock, self.conn:
            self.conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS sentinel_lessons (
                    id TEXT PRIMARY KEY,
                    cwd TEXT NOT NULL,
                    fingerprint TEXT NOT NULL,
                    stage TEXT NOT NULL DEFAULT 'general',
                    files TEXT NOT NULL DEFAULT '[]',
                    symptom TEXT NOT NULL,
                    resolution TEXT NOT NULL DEFAULT '',
                    occurrences INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(cwd, fingerprint)
                );
                CREATE INDEX IF NOT EXISTS idx_sentinel_cwd ON sentinel_lessons(cwd, updated_at DESC);
                """
            )

    def discover_rules(self, cwd: str | Path, budget_chars: int = 3200) -> dict:
        root = Path(cwd).resolve()
        if not root.is_dir():
            return {"sources": [], "rendered": "", "chars": 0}
        found_sources = []
        chunks = []
        remaining = budget_chars
        for rel in RULE_FILES:
            candidate = root / rel
            if candidate.is_file() and remaining > 120:
                try:
                    raw = candidate.read_text(encoding="utf-8", errors="replace").strip()
                except OSError:
                    continue
                if not raw:
                    continue
                alloc = min(remaining, max(400, budget_chars // 2))
                snippet = _compress_markdown_rules(raw, alloc)
                found_sources.append(rel)
                chunks.append(f"[{rel}]\n{snippet}")
                remaining -= len(snippet) + len(rel) + 4
        rendered = "\n\n".join(chunks)
        return {"sources": found_sources, "rendered": rendered, "chars": len(rendered)}

    def record_lesson(
        self,
        cwd: str | Path,
        stage: str,
        symptom: str,
        files: list[str] | None = None,
        resolution: str = "",
    ) -> dict:
        root_str = str(Path(cwd).resolve())
        clean_symptom = re.sub(r"\s+", " ", symptom.strip())[:600]
        clean_res = re.sub(r"\s+", " ", (resolution or "").strip())[:600]
        fp_seed = f"{stage}:{sorted(files or [])}:{clean_symptom[:180]}"
        fp = hashlib.sha256(fp_seed.encode("utf-8")).hexdigest()[:20]
        ts = now()
        with self.repo._lock, self.conn:
            existing = self.conn.execute(
                "SELECT id, occurrences, resolution FROM sentinel_lessons WHERE cwd=? AND fingerprint=?",
                (root_str, fp),
            ).fetchone()
            if existing:
                ident = existing["id"]
                merged_res = clean_res or existing["resolution"]
                self.conn.execute(
                    "UPDATE sentinel_lessons SET occurrences=?, resolution=?, updated_at=? WHERE id=?",
                    (int(existing["occurrences"]) + 1, merged_res, ts, ident),
                )
            else:
                ident = "les_" + uuid.uuid4().hex[:12]
                self.conn.execute(
                    "INSERT INTO sentinel_lessons VALUES (?,?,?,?,?,?,?,1,?,?)",
                    (ident, root_str, fp, stage, json.dumps(sorted(set(files or [])), ensure_ascii=False), clean_symptom, clean_res, ts, ts),
                )
        return self.get_lesson(ident)

    def get_lesson(self, ident: str) -> dict:
        row = self.conn.execute("SELECT * FROM sentinel_lessons WHERE id=?", (ident,)).fetchone()
        if not row:
            raise KeyError(ident)
        data = dict(row)
        data["files"] = json.loads(data["files"] or "[]")
        return data

    def list_lessons(self, cwd: str | Path, limit: int = 30) -> list[dict]:
        root_str = str(Path(cwd).resolve())
        rows = self.conn.execute(
            "SELECT id FROM sentinel_lessons WHERE cwd=? ORDER BY occurrences DESC, updated_at DESC LIMIT ?",
            (root_str, limit),
        ).fetchall()
        return [self.get_lesson(r[0]) for r in rows]

    def build_context(self, cwd: str | Path, prompt: str = "", rules_budget: int = 3000, lessons_budget: int = 1500) -> dict:
        rules = self.discover_rules(cwd, rules_budget)
        lessons = self.list_lessons(cwd, limit=25)
        prompt_words = {w.lower() for w in _WORD_RE.findall(prompt or "")}

        ranked = []
        for les in lessons:
            hay = " ".join([les["stage"], *les["files"], les["symptom"], les["resolution"]]).lower()
            les_words = {w.lower() for w in _WORD_RE.findall(hay)}
            overlap = len(prompt_words & les_words) if prompt_words else 0
            score = overlap * 3 + min(5, les["occurrences"]) + (2 if les["resolution"] else 0)
            ranked.append((score, les))
        ranked.sort(key=lambda x: (-x[0], x[1]["updated_at"]))

        lesson_lines = []
        used = 0
        picked_ids = []
        for _, les in ranked[:8]:
            f_tag = f" ({', '.join(les['files'][:3])})" if les["files"] else ""
            fix_tag = f" -> Fix: {les['resolution']}" if les["resolution"] else ""
            line = f"- [{les['stage']}{f_tag}] Avoid: {les['symptom'][:220]}{fix_tag}"
            if used + len(line) + 1 > lessons_budget:
                break
            lesson_lines.append(line)
            used += len(line) + 1
            picked_ids.append(les["id"])

        blocks = []
        if rules["rendered"]:
            blocks.append(
                "### Context Sentinel — Active Project Coding Standards (Mandatory on every turn)\n"
                + rules["rendered"]
            )
        if lesson_lines:
            blocks.append(
                "### Context Sentinel — Past Repository Pitfalls & Verified Fixes\n"
                + "\n".join(lesson_lines)
            )
        rendered = ("\n\n".join(blocks) + "\n") if blocks else ""
        return {
            "rendered": rendered,
            "rule_sources": rules["sources"],
            "lessons_injected": picked_ids,
            "chars": len(rendered),
        }
