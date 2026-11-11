"""Proactive conflict prevention between agents working in parallel worktrees.

Signals, from strongest to weakest:

* ``conflict`` – ``git merge-tree`` on snapshots of both working trees reports a textual conflict;
* ``symbol``   – both agents touched the same function/class (or overlapping line ranges);
* ``file``     – both agents changed the same file in different places;
* ``scope``    – an agent's declared/implied scope covers files another agent is changing.

The coordinator runs this before a turn starts (and can defer it) and periodically while
agents are running, raising items in the attention inbox.
"""
from __future__ import annotations

import ast
import fnmatch
import re
import threading
from pathlib import Path

from flux.parallel import config as project_config
from flux.parallel.gitops import GitError, changed_ranges, git, merge_conflicts, snapshot_commit

LEVELS = {"scope": 1, "file": 2, "symbol": 3, "conflict": 4}
SYMBOL_RE = re.compile(
    r"^(?P<indent>\s*)(?:export\s+)?(?:default\s+)?(?:async\s+)?(?:"
    r"(?:def|class|function|func|fn|interface|struct|enum|trait|impl|module)\s+(?P<a>[A-Za-z_$][\w$]*)"
    r"|(?:const|let|var)\s+(?P<b>[A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>"
    r"|(?:public|private|protected|static|\s)*(?P<c>[A-Za-z_$][\w$]*)\s*\([^)]*\)\s*\{\s*$)")
PATH_HINT = re.compile(r"(?<![\w/.-])((?:[\w.-]+/)*[\w.-]+\.[A-Za-z0-9]{1,8})(?![\w/])")


def python_symbols(source: str):
    tree = ast.parse(source)
    spans = []

    def walk(node, prefix):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                name = prefix + child.name
                start = min([child.lineno] + [d.lineno for d in child.decorator_list])
                spans.append((name, start, child.end_lineno or child.lineno))
                walk(child, name + ".")
            else:
                walk(child, prefix)

    walk(tree, "")
    return spans


def generic_symbols(source: str):
    lines = source.splitlines()
    starts = []
    for number, line in enumerate(lines, 1):
        match = SYMBOL_RE.match(line)
        if match:
            name = match.group("a") or match.group("b") or match.group("c")
            if name and name not in {"if", "for", "while", "switch", "catch", "return", "else"}:
                starts.append((name, number, len(match.group("indent").expandtabs(4))))
    spans = []
    for index, (name, start, indent) in enumerate(starts):
        end = len(lines)
        for other_name, other_start, other_indent in starts[index + 1:]:
            if other_indent <= indent:
                end = other_start - 1
                break
        spans.append((name, start, end))
    return spans


def symbols_for(path: str, source: str):
    if path.endswith(".py"):
        try:
            return python_symbols(source)
        except (SyntaxError, ValueError):
            pass
    return generic_symbols(source)


def touched_symbols(spans, ranges):
    names = set()
    for start, end in ranges:
        hits = [(name, s, e) for name, s, e in spans if s <= end and start <= e]
        if hits:  # innermost only: the narrowest enclosing span per range
            names.add(min(hits, key=lambda h: h[2] - h[1])[0])
    return names


def scope_matches(pattern: str, path: str) -> bool:
    pattern = pattern.strip().replace("\\", "/").lstrip("./")
    if not pattern:
        return False
    if pattern.endswith("/"):
        return path.startswith(pattern)
    return fnmatch.fnmatch(path, pattern) or path == pattern or path.startswith(pattern.rstrip("/") + "/")


class ChangeSet:
    def __init__(self, worktree: dict, files: dict, symbols: dict, claims: list, snapshot: str | None):
        self.worktree, self.files, self.symbols, self.claims, self.snapshot = worktree, files, symbols, claims, snapshot

    @property
    def id(self):
        return self.worktree["id"]


def compute_changes(worktree: dict, extra_claims=()) -> ChangeSet:
    path, base = worktree["path"], worktree["base_commit"]
    files = changed_ranges(path, base)
    files = {f: r for f, r in files.items() if not f.startswith(".flux/runtime/")}
    symbols = {}
    for name, ranges in files.items():
        if not ranges:
            continue
        try:
            source = git(path, "show", f"{base}:{name}", check=True)
        except GitError:
            continue  # new file in base terms
        symbols[name] = touched_symbols(symbols_for(name, source), ranges)
    snapshot = None
    if files:
        try:
            snapshot = snapshot_commit(path, git(path, "rev-parse", "HEAD").strip())
        except GitError:
            snapshot = None
    return ChangeSet(worktree, files, symbols, list(worktree.get("scope") or []) + list(extra_claims), snapshot)


def implied_claims(prompt: str, root) -> list[str]:
    """File paths mentioned in a prompt that exist in the repository."""
    found = []
    for match in PATH_HINT.findall(prompt or ""):
        candidate = match.replace("\\", "/").lstrip("./")
        if candidate and (Path(root) / candidate).exists() and candidate not in found:
            found.append(candidate)
    return found[:50]


def compare(a: ChangeSet, b: ChangeSet, repo_path=None) -> list[dict]:
    findings: dict[str, dict] = {}

    def add(path, level, detail=None):
        current = findings.get(path)
        if not current or LEVELS[level] > LEVELS[current["level"]]:
            findings[path] = {"path": path, "level": level, **(detail or {})}

    same_base = a.worktree["base_commit"] == b.worktree["base_commit"]
    for path in sorted(set(a.files) & set(b.files)):
        ra, rb = a.files[path], b.files[path]
        shared_symbols = sorted(a.symbols.get(path, set()) & b.symbols.get(path, set()))
        if same_base and shared_symbols:
            add(path, "symbol", {"symbols": shared_symbols})
        elif same_base and ra and rb and any(s1 <= e2 and s2 <= e1 for s1, e1 in ra for s2, e2 in rb):
            add(path, "symbol", {"symbols": [], "lines": True})
        else:
            add(path, "file")
    for left, right in ((a, b), (b, a)):
        for pattern in left.claims:
            for path in right.files:
                if scope_matches(pattern, path):
                    add(path, "scope", {"claimed_by": left.id, "pattern": pattern})
            for other in right.claims:
                if pattern.strip("/") == other.strip("/") or scope_matches(pattern, other) or scope_matches(other, pattern):
                    add(other, "scope", {"claimed_by": left.id, "pattern": pattern})
    if a.snapshot and b.snapshot and repo_path:
        try:
            for path in merge_conflicts(repo_path, a.snapshot, b.snapshot) or []:
                add(path, "conflict")
        except GitError:
            pass
    return sorted(findings.values(), key=lambda f: (-LEVELS[f["level"]], f["path"]))


class Coordinator:
    def __init__(self, manager, runtime, attention=None, events=None):
        self.manager, self.runtime, self.attention, self.events = manager, runtime, attention, events
        self._lock = threading.Lock()

    def active_worktree_ids(self) -> set[str]:
        rows = self.runtime.conn.execute(
            "SELECT DISTINCT c.worktree_id FROM local_turns t JOIN local_chats c ON c.id=t.chat_id "
            "WHERE t.state IN ('queued','running') AND c.worktree_id<>''").fetchall()
        return {r[0] for r in rows}

    def check(self, worktree_id: str, prompt: str = "", against_active_only=True) -> list[dict]:
        me = self.manager.get(worktree_id)
        mine = compute_changes(me, implied_claims(prompt, me["path"]))
        active = self.active_worktree_ids()
        results = []
        for other in self.manager.list(me["project_id"]):
            if other["id"] == worktree_id or (against_active_only and other["id"] not in active):
                continue
            theirs = compute_changes(other)
            for finding in compare(mine, theirs, me["main_path"]):
                results.append({**finding, "worktree": worktree_id, "other": other["id"], "other_name": other["name"],
                                "other_running": other["id"] in active})
        return sorted(results, key=lambda f: (-LEVELS[f["level"]], f["path"]))

    def gate(self, chat: dict, prompt: str):
        """Called by the runtime before a worktree turn starts. Returns a hold reason or None."""
        worktree_id = chat.get("worktree_id")
        if not worktree_id:
            return None
        me = self.manager.get(worktree_id)
        policy = project_config.load(me["main_path"])["coordination"]
        if policy["policy"] == "off":
            return None
        findings = self.check(worktree_id, prompt)
        if not findings:
            return None
        blocking = [f for f in findings if f["level"] in policy["defer_on"] and f["other_running"]]
        if policy["policy"] == "defer" and blocking:
            top = blocking[0]
            return {"action": "defer", "level": top["level"], "path": top["path"], "other": top["other"],
                    "reason": f"همپوشانی «{top['level']}» با worktree «{top['other_name']}» روی {top['path']}",
                    "findings": findings[:20]}
        self._report(worktree_id, findings)
        return None

    def _report(self, worktree_id, findings):
        if not self.attention:
            return
        for finding in findings:
            level = finding["level"]
            pair = "|".join(sorted([finding["worktree"], finding["other"]]))
            self.attention.raise_item(
                kind="overlap", priority=1 if LEVELS[level] >= 3 else 2,
                key=f"overlap:{pair}:{finding['path']}:{level}",
                title=f"همپوشانی {level}: {finding['path']}",
                detail=finding, worktree_id=worktree_id)

    def scan(self) -> list[dict]:
        """Pairwise scan of all active worktrees per project (used periodically and on demand)."""
        if not self._lock.acquire(blocking=False):
            return []
        try:
            report = []
            by_project: dict[str, list] = {}
            for item in self.manager.list():
                by_project.setdefault(item["project_id"], []).append(item)
            active = self.active_worktree_ids()
            for project_id, items in by_project.items():
                changes = {}
                for item in items:
                    try:
                        changes[item["id"]] = compute_changes(item)
                    except GitError:
                        continue
                    for stale in self.manager.link_health(item["id"]):
                        if self.attention:
                            self.attention.raise_item(kind="dependencies", priority=2,
                                key=f"deps:{item['id']}:{stale['name']}", worktree_id=item["id"],
                                title=f"وابستگی‌های {stale['name']} در «{item['name']}» با شاخهٔ اصلی فرق کرده است",
                                detail={**stale, "hint": "unshare and install locally"})
                ids = sorted(changes)
                for i, left in enumerate(ids):
                    for right in ids[i + 1:]:
                        if left not in active and right not in active:
                            continue
                        for finding in compare(changes[left], changes[right], items[0]["main_path"]):
                            entry = {**finding, "worktree": left, "other": right,
                                     "other_name": self.manager.get(right)["name"], "project_id": project_id}
                            report.append(entry)
                            self._report(left, [entry])
            if self.events:
                self.events.publish("overlap.scan", {"findings": len(report)})
            return report
        finally:
            self._lock.release()

