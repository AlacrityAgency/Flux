"""Parallel agent work: isolated worktrees, overlap prevention, shared memory, attention inbox
and DAG pipelines. ``ParallelHub`` wires all parts into a ``LocalRuntime``."""
from __future__ import annotations

import asyncio
from functools import lru_cache

from flux.parallel import config as project_config
from flux.parallel.attention import AttentionInbox
from flux.parallel.events import EventBus
from flux.parallel.gitops import GitError, repo_root
from flux.parallel.overlap import Coordinator
from flux.parallel.pipelines import PipelineRunner
from flux.parallel.wiki import ProjectWiki
from flux.parallel.worktrees import WorktreeManager


class ParallelHub:
    def __init__(self, repo, workspace, runtime, worktree_root=None, docker=None, notify_url=None):
        self.repo, self.workspace, self.runtime = repo, workspace, runtime
        self.events = EventBus()
        self.attention = AttentionInbox(repo, self.events, notify_url)
        self.worktrees = WorktreeManager(repo, workspace, self.events, worktree_root, docker)
        self.wiki = ProjectWiki(self.events, self.attention)
        self.coordinator = Coordinator(self.worktrees, runtime, self.attention, self.events)
        self.pipelines = PipelineRunner(repo, workspace, self.worktrees, runtime, self.attention, self.events)
        runtime.worktree_lookup = self._lookup
        runtime.worktree_env = self.worktrees.env
        runtime.gate = self._gate
        runtime.listeners.extend([self._publish_turn, self.attention.on_turn, self._capture_memory, self.pipelines.on_turn])
        runtime.preface_hooks.append(self._preface)
        self._scanner = None

    # ---------- runtime hooks ----------
    def _lookup(self, ident):
        try:
            return self.worktrees.get(ident)
        except KeyError:
            return None

    def _gate(self, chat, prompt):
        try:
            hold = self.coordinator.gate(chat, prompt)
        except (GitError, OSError, ValueError, KeyError):
            return None  # never block work because the analysis itself failed
        if hold and self.events:
            self.events.publish("turn.deferred", {"chat_id": chat["id"], "hold": {k: v for k, v in hold.items() if k != "findings"}})
        return hold

    def _publish_turn(self, turn, chat):
        self.events.publish("turn.state", {"turn_id": turn["id"], "chat_id": chat["id"], "state": turn["state"],
                                           "worktree_id": chat.get("worktree_id") or "", "title": chat.get("title")})

    @staticmethod
    @lru_cache(maxsize=256)
    def _repo_for_path(path):
        try:
            return str(repo_root(path))
        except (GitError, OSError):
            return None

    def repo_for_chat(self, chat):
        if chat.get("worktree_id"):
            worktree = self._lookup(chat["worktree_id"])
            return worktree["main_path"] if worktree else None
        return self._repo_for_path(chat["cwd"]) if chat.get("cwd") else None

    def repo_for_project(self, project_id):
        project = self.workspace.get_project(project_id)
        if not project:
            raise KeyError(project_id)
        path = self._repo_for_path(project["path"])
        if not path:
            raise ValueError("پوشهٔ پروژه مخزن git نیست.")
        return path

    def _capture_memory(self, turn, chat):
        if turn["state"] != "completed" or "<flux-memory" not in (turn.get("text") or ""):
            return
        path = self.repo_for_chat(chat)
        if not path:
            return
        auto = project_config.load(path)["memory"]["auto_verify"]
        self.wiki.capture(path, turn["text"], {"chat_id": chat["id"], "turn_id": turn["id"],
                                               "worktree_id": chat.get("worktree_id") or "", "provider": chat["provider"]}, auto)

    def _preface(self, chat, prompt):
        parts = []
        if chat.get("worktree_id"):
            worktree = self._lookup(chat["worktree_id"])
            if worktree:
                env = worktree["env"]
                ports = ", ".join(f"{k}={v}" for k, v in worktree["ports"].items())
                linked = [l["name"] for l in worktree["links"] if l.get("status") == "linked"]
                parts.append(
                    f"You are in an isolated git worktree '{worktree['name']}' (branch {worktree['branch']}). Other agents work "
                    f"in parallel in other worktrees. Never use default ports: use these reserved ports from the environment: {ports}. "
                    f"Use DATABASE_URL={env.get('DATABASE_URL', '(none)')} and FLUX_DATA_DIR for any data; COMPOSE_PROJECT_NAME is unique.\n")
                if linked:
                    parts.append("These dependency directories are shared links to the main checkout and must stay read-only: "
                                 + ", ".join(linked) + ". If you must change dependencies, stop and say so instead of reinstalling.\n")
        path = self.repo_for_chat(chat)
        if path:
            cfg = project_config.load(path)
            share = bool(self.workspace.preferences().get("wiki_share_proposed", False))
            parts.append(self.wiki.context(path, prompt, cfg["memory"]["pinned_budget_chars"], share))
            if chat.get("access") == "work":
                parts.append(self.wiki.CAPTURE_INSTRUCTION)
        return "".join(parts)

    # ---------- lifecycle ----------
    def recover(self):
        self.pipelines.recover()

    async def scan_loop(self, interval=20):
        while True:
            await asyncio.sleep(interval)
            if self.coordinator.active_worktree_ids():
                try:
                    await asyncio.to_thread(self.coordinator.scan)
                except Exception:
                    pass

    def start(self):
        if self._scanner is None:
            self._scanner = asyncio.get_running_loop().create_task(self.scan_loop())

    async def stop(self):
        if self._scanner:
            self._scanner.cancel()
            await asyncio.gather(self._scanner, return_exceptions=True)
            self._scanner = None
        for task in list(self.pipelines.tasks):
            task.cancel()
        await asyncio.gather(*self.pipelines.tasks, return_exceptions=True)

