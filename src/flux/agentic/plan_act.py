"""Plan vs. Act Two-Phase Architecture (Cline-style Read-Only Planning + Verified Execution).

In ``plan`` mode:
- Forces read-only execution (zero file mutation; any stray edit is rolled back).
- Prompts the model to analyze requirements, edge cases, affected modules/symbols,
  and output a structured step-by-step architectural plan stored in ``agentic_plans``.

In ``act`` mode:
- Injects the latest approved plan for the chat/project as the execution blueprint
  so multi-step tasks execute deterministically without mid-flight architectural drift.
"""
from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

from flux.storage.workspace import now

PLAN_TAG_RE = re.compile(r"<flux-plan>\s*(.*?)\s*</flux-plan>", re.DOTALL)
STEP_LINE_RE = re.compile(r"^\s*(?:[-*]|\d+[.)])\s+(.+)$")
FILE_HINT_RE = re.compile(r"(?:`|\b)([A-Za-z0-9_./-]+?\.(?:py|js|ts|tsx|jsx|go|rs|java|sql|html|css|json|md))(?:`|\b)")

PLAN_MODE_INSTRUCTIONS = (
    "=== ARCHITECTURE PHASE: PLAN MODE (STRICTLY READ-ONLY) ===\n"
    "DO NOT edit, create, or delete any files in this turn. Do NOT emit <flux-edit> or <flux-create> blocks.\n"
    "Instead, carefully inspect the Repository Structural Map and Project Standards above and produce a rigorous architectural plan wrapped in <flux-plan>...</flux-plan> containing:\n"
    "1. هدف و نیازمندی‌ها (Requirements & Constraints)\n"
    "2. فایل‌ها و توابع هدف (Exact Target Files & Signatures)\n"
    "3. سناریوهای مرزی و ریسک‌ها (Edge Cases & Failure Modes)\n"
    "4. گام‌های اجرایی دقیق به ترتیب (Step-by-Step Numbered Execution Plan)\n"
)


def parse_plan_output(text: str) -> dict:
    raw = (text or "").strip()
    m = PLAN_TAG_RE.search(raw)
    body = m.group(1).strip() if m else raw
    steps = []
    risks = []
    in_risks = False
    for line in body.splitlines():
        s = line.strip()
        if not s:
            continue
        low = s.lower()
        if s.startswith("#") or s.endswith(":"):
            in_risks = any(k in low for k in ("risk", "edge", "مرزی", "ریسک", "خطر"))
            continue
        sm = STEP_LINE_RE.match(s)
        if sm:
            item = sm.group(1).strip()
            if in_risks:
                risks.append(item[:240])
            else:
                steps.append(item[:280])
    files = sorted(dict.fromkeys(FILE_HINT_RE.findall(body)))[:25]
    return {
        "body": body[:16000],
        "steps": steps[:30],
        "risks": risks[:15],
        "target_files": files,
    }


class PlanActManager:
    def __init__(self, repo):
        self.repo, self.conn = repo, repo.conn
        with self.repo._lock, self.conn:
            self.conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS agentic_plans (
                    id TEXT PRIMARY KEY,
                    chat_id TEXT NOT NULL DEFAULT '',
                    turn_id TEXT NOT NULL DEFAULT '',
                    cwd TEXT NOT NULL,
                    objective TEXT NOT NULL,
                    body TEXT NOT NULL,
                    steps TEXT NOT NULL DEFAULT '[]',
                    risks TEXT NOT NULL DEFAULT '[]',
                    target_files TEXT NOT NULL DEFAULT '[]',
                    status TEXT NOT NULL DEFAULT 'draft',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_agentic_plans_chat ON agentic_plans(chat_id, created_at DESC);
                """
            )

    def record_plan(self, cwd: str | Path, objective: str, model_text: str, chat_id: str = "", turn_id: str = "", auto_approve: bool = False) -> dict:
        parsed = parse_plan_output(model_text)
        ident = "plan_" + uuid.uuid4().hex[:12]
        ts = now()
        status = "approved" if auto_approve else "draft"
        with self.repo._lock, self.conn:
            self.conn.execute(
                "INSERT INTO agentic_plans VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    ident,
                    chat_id,
                    turn_id,
                    str(Path(cwd).resolve()),
                    objective[:4000],
                    parsed["body"],
                    json.dumps(parsed["steps"], ensure_ascii=False),
                    json.dumps(parsed["risks"], ensure_ascii=False),
                    json.dumps(parsed["target_files"], ensure_ascii=False),
                    status,
                    ts,
                    ts,
                ),
            )
        return self.get(ident)

    def get(self, ident: str) -> dict:
        row = self.conn.execute("SELECT * FROM agentic_plans WHERE id=?", (ident,)).fetchone()
        if not row:
            raise KeyError(ident)
        d = dict(row)
        d["steps"] = json.loads(d["steps"] or "[]")
        d["risks"] = json.loads(d["risks"] or "[]")
        d["target_files"] = json.loads(d["target_files"] or "[]")
        return d

    def list(self, chat_id: str | None = None, cwd: str | None = None, limit: int = 30) -> list[dict]:
        clauses, params = [], []
        if chat_id:
            clauses.append("chat_id=?")
            params.append(chat_id)
        if cwd:
            clauses.append("cwd=?")
            params.append(str(Path(cwd).resolve()))
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        rows = self.conn.execute(
            f"SELECT id FROM agentic_plans {where} ORDER BY created_at DESC LIMIT ?",
            (*params, limit),
        ).fetchall()
        return [self.get(r[0]) for r in rows]

    def approve(self, ident: str) -> dict:
        self.get(ident)
        with self.repo._lock, self.conn:
            self.conn.execute("UPDATE agentic_plans SET status='approved', updated_at=? WHERE id=?", (now(), ident))
        return self.get(ident)

    def mark_executed(self, ident: str) -> dict:
        self.get(ident)
        with self.repo._lock, self.conn:
            self.conn.execute("UPDATE agentic_plans SET status='executed', updated_at=? WHERE id=?", (now(), ident))
        return self.get(ident)

    def active_approved_plan(self, chat_id: str) -> dict | None:
        if not chat_id:
            return None
        row = self.conn.execute(
            "SELECT id FROM agentic_plans WHERE chat_id=? AND status='approved' ORDER BY updated_at DESC LIMIT 1",
            (chat_id,),
        ).fetchone()
        return self.get(row[0]) if row else None

    @staticmethod
    def render_act_blueprint(plan: dict) -> str:
        steps = "\n".join(f"  {i}. {s}" for i, s in enumerate(plan.get("steps") or [], 1))
        files = ", ".join(plan.get("target_files") or [])
        body = plan.get("body") or ""
        return (
            f"=== EXECUTION PHASE: ACT MODE (Approved Plan {plan['id']}) ===\n"
            f"Execute the approved architectural plan step-by-step using minimal surgical edits:\n"
            + (f"Target files: {files}\n" if files else "")
            + (f"Approved steps:\n{steps}\n" if steps else f"{body[:2500]}\n")
        )

