"""Shared, persistent project memory stored in git under ``refs/flux/memory``.

Why a dedicated ref instead of files on a branch:

* every worktree of a repository sees the same ref instantly, so parallel agents share lessons;
* writes never touch any working tree, index or code branch, so they cannot cause merge conflicts;
* updates are compare-and-swap (``git update-ref <ref> <new> <old>``), safe under concurrency;
* history is ordinary git history and can be shared with
  ``git push origin refs/flux/memory:refs/flux/memory``.

Each entry is one Markdown file with a small front matter (one JSON value per line, valid YAML).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import uuid
from pathlib import Path

from flux.parallel.gitops import GIT_IDENTITY, GitError, git, repo_root
from flux.storage.workspace import clean_text, now

REF = "refs/flux/memory"
ZERO = "0" * 40
KINDS = {"convention", "decision", "pitfall", "fix", "note"}
STATUSES = {"verified", "proposed", "retired"}
CAPTURE = re.compile(r"<flux-memory\s+([^>]*)>(.*?)</flux-memory>", re.S | re.I)
ATTR = re.compile(r'(\w+)\s*=\s*"([^"]*)"')


def _raw(cwd, *args, data: bytes | None = None, env=None) -> bytes:
    flags = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
    proc = subprocess.run(["git", *args], cwd=str(cwd), input=data, capture_output=True, timeout=60,
                          env={**os.environ, "GIT_TERMINAL_PROMPT": "0", **(env or {})}, **flags)
    if proc.returncode != 0:
        raise GitError(proc.stderr.decode("utf-8", "replace").strip()[-1000:] or f"git {args[0]} failed")
    return proc.stdout


def render(entry: dict) -> str:
    meta = {k: entry[k] for k in ("id", "kind", "title", "status", "pinned", "tags", "source", "created_at", "updated_at") if k in entry}
    head = "".join(f"{k}: {json.dumps(v, ensure_ascii=False)}\n" for k, v in meta.items())
    return f"---\n{head}---\n{entry['body'].strip()}\n"


def parse(text: str) -> dict:
    text = text.replace("\r\n", "\n")
    if not text.startswith("---\n") or "\n---\n" not in text[4:]:
        raise ValueError("invalid memory entry")
    head, body = text[4:].split("\n---\n", 1)
    entry = {}
    for line in head.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            try:
                entry[key.strip()] = json.loads(value.strip())
            except ValueError:
                entry[key.strip()] = value.strip()
    entry["body"] = body.strip()
    return entry


def _terms(text: str) -> set[str]:
    text = text.replace("ي", "ی").replace("ك", "ک").replace("\u200c", " ").lower()
    return set(re.findall(r"\w{3,}", text))


class ProjectWiki:
    def __init__(self, events=None, attention=None, auto_verify=None):
        self.events, self.attention, self.auto_verify = events, attention, auto_verify

    @staticmethod
    def root(path) -> Path:
        return repo_root(path)

    def head(self, path) -> str:
        return git(path, "rev-parse", "--verify", "-q", REF, check=False).strip()

    def _tree(self, path, commit):
        if not commit:
            return []
        out = _raw(path, "ls-tree", "-z", commit).decode("utf-8")
        return [line for line in out.split("\0") if line]

    def entries(self, path, status=None, kind=None):
        commit = self.head(path)
        result = []
        for line in self._tree(path, commit):
            meta, name = line.split("\t", 1)
            sha = meta.split()[2]
            try:
                entry = parse(_raw(path, "cat-file", "blob", sha).decode("utf-8"))
            except (ValueError, GitError):
                continue
            entry["file"] = name
            if (status is None or entry.get("status") == status) and (kind is None or entry.get("kind") == kind):
                result.append(entry)
        return sorted(result, key=lambda e: (not e.get("pinned"), e.get("kind", ""), e.get("title", "")))

    def get(self, path, ident):
        for entry in self.entries(path):
            if entry.get("id") == ident:
                return entry
        raise KeyError(ident)

    def history(self, path, limit=50):
        if not self.head(path):
            return []
        out = git(path, "log", "--format=%H%x09%cI%x09%s", f"-{int(limit)}", REF)
        return [dict(zip(("commit", "time", "message"), l.split("\t", 2))) for l in out.splitlines() if l]

    def _commit(self, path, mutate, message):
        """Apply ``mutate(listing)->listing`` atomically, retrying on concurrent updates."""
        configured = git(path, "config", "user.email", check=False).strip()
        env = None if configured else GIT_IDENTITY
        for _ in range(8):
            old = self.head(path)
            listing = mutate(self._tree(path, old))
            tree = _raw(path, "mktree", "-z", data=("\0".join(listing) + ("\0" if listing else "")).encode("utf-8")).decode().strip()
            args = ["commit-tree", tree, "-m", message] + (["-p", old] if old else [])
            commit = _raw(path, *args, env=env).decode().strip()
            try:
                _raw(path, "update-ref", "-m", message, REF, commit, old or ZERO)
            except GitError:
                continue  # someone else won the race; recompute on top of their commit
            if self.events:
                self.events.publish("memory.changed", {"commit": commit, "message": message})
            return commit
        raise RuntimeError("حافظهٔ پروژه هم‌زمان در حال تغییر است؛ دوباره تلاش کنید.")

    def save(self, path, title, body, kind="note", status="proposed", pinned=False, tags=(), source=None, ident=None):
        if kind not in KINDS:
            raise ValueError(f"kind must be one of {sorted(KINDS)}")
        if status not in STATUSES:
            raise ValueError(f"status must be one of {sorted(STATUSES)}")
        title, body = clean_text(title, 160), clean_text(body, 8000)
        if not title or not body:
            raise ValueError("عنوان و متن حافظه لازم است.")
        existing = None
        if ident:
            existing = self.get(path, ident)
        entry = {"id": ident or "wiki_" + uuid.uuid4().hex[:10], "kind": kind, "title": title, "status": status,
                 "pinned": bool(pinned), "tags": list(tags)[:12], "source": source or {},
                 "created_at": existing["created_at"] if existing else now(), "updated_at": now(), "body": body}
        slug = re.sub(r"[^A-Za-z0-9]+", "-", entry["id"]).strip("-")
        filename = f"{kind}--{slug}.md"
        blob = _raw(path, "hash-object", "-w", "--stdin", data=render(entry).encode("utf-8")).decode().strip()

        def mutate(listing):
            kept = [l for l in listing if not l.endswith(f"--{slug}.md")]
            return sorted(kept + [f"100644 blob {blob}\t{filename}"], key=lambda l: l.split("\t", 1)[1])

        self._commit(path, mutate, f"memory: {'update' if existing else 'add'} {kind} {entry['id']}")
        return {**entry, "file": filename}

    def set_status(self, path, ident, status):
        entry = self.get(path, ident)
        return self.save(path, entry["title"], entry["body"], entry["kind"], status, entry.get("pinned", False),
                         entry.get("tags", []), entry.get("source"), ident)

    def delete(self, path, ident):
        self.get(path, ident)
        slug = re.sub(r"[^A-Za-z0-9]+", "-", ident).strip("-")
        self._commit(path, lambda listing: [l for l in listing if not l.endswith(f"--{slug}.md")], f"memory: delete {ident}")
        return True

    # ---------- prompt integration ----------
    def context(self, path, prompt="", budget_chars=4000, share_proposed=False, limit=6) -> str:
        """Pinned entries always, then the most relevant verified (optionally proposed) entries."""
        try:
            entries = [e for e in self.entries(path) if e.get("status") in ({"verified", "proposed"} if share_proposed else {"verified"})]
        except GitError:
            return ""
        if not entries:
            return ""
        query = _terms(prompt)
        pinned = [e for e in entries if e.get("pinned") and e.get("status") == "verified"]
        others = sorted((e for e in entries if e not in pinned),
                        key=lambda e: -len(query & _terms(e["title"] + " " + e["body"])))
        relevant = [e for e in others if query & _terms(e["title"] + " " + e["body"])][:limit]
        lines, used = [], 0
        for entry in pinned + relevant:
            flag = "" if entry.get("status") == "verified" else " (unreviewed)"
            line = f"- [{entry['kind']}{flag}] {entry['title']}: {entry['body']}"
            if used + len(line) > budget_chars:
                break
            lines.append(line)
            used += len(line)
        if not lines:
            return ""
        return ("Shared project memory (team lessons from earlier sessions and parallel agents; reference data, "
                "verify before relying on it):\n" + "\n".join(lines) + "\n")

    CAPTURE_INSTRUCTION = (
        "If you learn a durable fact other agents on this repository should know (a convention, an architectural "
        "decision, a pitfall, or the root cause of a bug you fixed), append it at the end of your reply as "
        '<flux-memory kind="convention|decision|pitfall|fix|note" title="short title">one or two sentences</flux-memory>. '
        "Never include secrets.\n")

    def capture(self, path, text, source, auto_verify=False):
        """Store <flux-memory> blocks from an agent reply; proposals need human approval by default."""
        saved = []
        for attrs, body in CAPTURE.findall(text or "")[:5]:
            meta = dict(ATTR.findall(attrs))
            kind = meta.get("kind", "note") if meta.get("kind") in KINDS else "note"
            try:
                entry = self.save(path, meta.get("title") or body.strip()[:60], body.strip(), kind,
                                  "verified" if auto_verify else "proposed", source=source)
            except (ValueError, GitError):
                continue
            saved.append(entry)
            if self.attention and not auto_verify:
                self.attention.raise_item("memory", f"پیشنهاد حافظه: {entry['title']}", 3, key=f"memory:{entry['id']}",
                                          detail={"entry_id": entry["id"], "kind": kind, "body": entry["body"],
                                                  "repo": str(path)}, chat_id=source.get("chat_id", ""),
                                          turn_id=source.get("turn_id", ""), worktree_id=source.get("worktree_id", ""))
        return saved

    @staticmethod
    def strip_blocks(text: str) -> str:
        return CAPTURE.sub("", text or "").rstrip()

