"""Attention inbox: one prioritized queue of everything that is waiting for a human.

Priority 0 is the most urgent (an agent is blocked on a permission/question); larger numbers
are less urgent. Items are deduplicated by ``key`` while open, so repeated scans never spam.
"""
from __future__ import annotations

import json
import os
import threading
import uuid
import urllib.request

from flux.storage.workspace import now

PRIORITY_LABELS = {0: "blocked", 1: "action", 2: "warning", 3: "review", 4: "info"}


class AttentionInbox:
    def __init__(self, repo, events=None, notify_url: str | None = None):
        self.repo, self.conn, self.events = repo, repo.conn, events
        self.notify_url = notify_url if notify_url is not None else os.environ.get("FLUX_NOTIFY_URL", "")
        with self.repo._lock, self.conn:
            self.conn.executescript('''
                CREATE TABLE IF NOT EXISTS attention_items (
                    id TEXT PRIMARY KEY, key TEXT NOT NULL, kind TEXT NOT NULL, priority INTEGER NOT NULL,
                    title TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '{}', chat_id TEXT NOT NULL DEFAULT '',
                    turn_id TEXT NOT NULL DEFAULT '', worktree_id TEXT NOT NULL DEFAULT '',
                    pipeline_id TEXT NOT NULL DEFAULT '', state TEXT NOT NULL DEFAULT 'open',
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL, resolved_at TEXT NOT NULL DEFAULT '');
                CREATE INDEX IF NOT EXISTS attention_open ON attention_items(state, priority, created_at);
            ''')

    def _row(self, row):
        item = dict(row)
        item["detail"] = json.loads(item["detail"])
        item["label"] = PRIORITY_LABELS.get(item["priority"], "info")
        return item

    def raise_item(self, kind, title, priority=2, key=None, detail=None, chat_id="", turn_id="",
                   worktree_id="", pipeline_id=""):
        key = key or f"{kind}:{uuid.uuid4().hex}"
        with self.repo._lock, self.conn:
            existing = self.conn.execute("SELECT * FROM attention_items WHERE key=? AND state='open'", (key,)).fetchone()
            if existing:
                self.conn.execute("UPDATE attention_items SET priority=MIN(priority,?),detail=?,title=?,updated_at=? WHERE id=?",
                                  (priority, json.dumps(detail or {}, ensure_ascii=False), title[:300], now(), existing["id"]))
                return self.get(existing["id"])
            ident = "att_" + uuid.uuid4().hex[:12]
            self.conn.execute("INSERT INTO attention_items (id,key,kind,priority,title,detail,chat_id,turn_id,worktree_id,"
                              "pipeline_id,state,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,'open',?,?)",
                              (ident, key, kind, int(priority), title[:300], json.dumps(detail or {}, ensure_ascii=False),
                               chat_id, turn_id, worktree_id, pipeline_id, now(), now()))
        item = self.get(ident)
        if self.events:
            self.events.publish("attention.raised", item)
        if priority <= 1:
            self._notify(item)
        return item

    def get(self, ident):
        row = self.conn.execute("SELECT * FROM attention_items WHERE id=?", (ident,)).fetchone()
        if not row:
            raise KeyError(ident)
        return self._row(row)

    def items(self, state="open", limit=200):
        sql = "SELECT * FROM attention_items" + (" WHERE state=?" if state != "all" else "")
        args = (state,) if state != "all" else ()
        return [self._row(r) for r in self.conn.execute(sql + " ORDER BY priority ASC, created_at ASC LIMIT ?", (*args, limit))]

    def counts(self):
        rows = self.conn.execute("SELECT priority, COUNT(*) FROM attention_items WHERE state='open' GROUP BY priority")
        return {PRIORITY_LABELS.get(p, str(p)): c for p, c in rows}

    def resolve(self, ident, state="resolved"):
        with self.repo._lock, self.conn:
            self.conn.execute("UPDATE attention_items SET state=?,resolved_at=?,updated_at=? WHERE id=?",
                              (state, now(), now(), ident))
        item = self.get(ident)
        if self.events:
            self.events.publish("attention.resolved", {"id": ident})
        return item

    def resolve_where(self, **match):
        clauses = " AND ".join(f"{k}=?" for k in match)
        with self.repo._lock, self.conn:
            ids = [r[0] for r in self.conn.execute(f"SELECT id FROM attention_items WHERE state='open' AND {clauses}",
                                                   tuple(match.values()))]
        for ident in ids:
            self.resolve(ident)
        return len(ids)

    # ---------- runtime integration ----------
    def on_turn(self, turn: dict, chat: dict):
        state = turn["state"]
        base = {"chat_id": chat["id"], "turn_id": turn["id"], "worktree_id": chat.get("worktree_id") or ""}
        # A new outcome for this chat supersedes earlier open turn notices.
        self.resolve_where(chat_id=chat["id"], kind="turn")
        title = chat.get("title") or "گفتگو"
        if state == "needs_input":
            self.raise_item("turn", f"منتظر تأیید/پاسخ شما: {title}", 0, key=f"turn:{turn['id']}",
                            detail={"state": state, "error": turn.get("error", "")}, **base)
        elif state in {"failed", "interrupted"}:
            self.raise_item("turn", f"اجرا ناموفق: {title}", 1, key=f"turn:{turn['id']}",
                            detail={"state": state, "error": (turn.get("error") or "")[-1200:]}, **base)
        elif state == "deferred":
            self.raise_item("turn", f"به تعویق افتاد: {title}", 2, key=f"turn:{turn['id']}",
                            detail={"state": state, "hold": turn.get("hold") or {}}, **base)
        elif state == "completed" and chat.get("worktree_id"):
            self.raise_item("turn", f"آمادهٔ بازبینی: {title}", 3, key=f"turn:{turn['id']}",
                            detail={"state": state, "summary": (turn.get("text") or "")[:600]}, **base)

    def _notify(self, item):
        """Optional push to phones/desktops through an ntfy-compatible webhook (FLUX_NOTIFY_URL)."""
        if not self.notify_url:
            return

        def send():
            try:
                request = urllib.request.Request(self.notify_url, data=item["title"].encode("utf-8"), method="POST",
                                                 headers={"Title": "Flux", "Priority": "high" if item["priority"] == 0 else "default",
                                                          "Tags": item["kind"]})
                urllib.request.urlopen(request, timeout=8).close()
            except Exception:
                pass

        threading.Thread(target=send, daemon=True).start()

