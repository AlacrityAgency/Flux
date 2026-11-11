"""DAG task pipelines: each step runs in its own worktree and only starts after its
dependencies have finished *and* passed their gates (build/test commands).

Dependent steps are branched from their dependency's gated commit, so step B literally
starts from the code that made step A's tests pass. Several dependencies are merged into
the new worktree first; a merge conflict stops that step and is sent to the inbox.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import time
import uuid
from collections import defaultdict, deque

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Literal

from flux.parallel.gitops import GIT_IDENTITY, GitError, git, git_ok
from flux.storage.workspace import now

TERMINAL = {"passed", "failed", "blocked", "cancelled"}


class GateSpec(BaseModel):
    run: str = Field(min_length=1, max_length=2000)
    name: str = Field(default="", max_length=120)
    timeout: int = Field(default=900, ge=5, le=7200)


class StepSpec(BaseModel):
    id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,40}$")
    title: str = Field(default="", max_length=160)
    prompt: str = Field(min_length=1, max_length=40000)
    provider: Literal["codex", "claude", "gemini", "gapcode", "antigravity"] = "codex"
    model: str = Field(default="", max_length=100)
    depends_on: list[str] = Field(default_factory=list)
    gates: list[GateSpec] = Field(default_factory=list)
    scope: list[str] = Field(default_factory=list)
    max_attempts: int = Field(default=2, ge=1, le=5)


class PipelineSpec(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    project_id: str = Field(min_length=1, max_length=100)
    base: str = Field(default="HEAD", max_length=200)
    steps: list[StepSpec] = Field(min_length=1, max_length=30)

    @field_validator("base")
    @classmethod
    def safe_ref(cls, value):
        if not re.fullmatch(r"[A-Za-z0-9_./~^@{}-]+", value) or value.startswith("-"):
            raise ValueError("invalid base ref")
        return value

    @model_validator(mode="after")
    def acyclic(self):
        topological_tiers(self.steps)
        return self


def topological_tiers(steps) -> list[list[str]]:
    ids = [s.id for s in steps]
    if len(ids) != len(set(ids)):
        raise ValueError("step ids must be unique")
    indegree, children = {i: 0 for i in ids}, defaultdict(list)
    for step in steps:
        for dep in step.depends_on:
            if dep == step.id:
                raise ValueError(f"step {step.id} depends on itself")
            if dep not in indegree:
                raise ValueError(f"step {step.id} depends on unknown step {dep}")
            children[dep].append(step.id)
            indegree[step.id] += 1
    queue, tiers, seen = deque(i for i in ids if indegree[i] == 0), [], 0
    while queue:
        tier = [queue.popleft() for _ in range(len(queue))]
        tiers.append(tier)
        seen += len(tier)
        for node in tier:
            for child in children[node]:
                indegree[child] -= 1
                if indegree[child] == 0:
                    queue.append(child)
    if seen != len(ids):
        raise ValueError("pipeline steps contain a dependency cycle")
    return tiers


def run_gate(path, env, gate: dict) -> dict:
    started = time.monotonic()
    flags = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
    try:
        proc = subprocess.run(gate["run"], shell=True, cwd=str(path), env={**os.environ, **env}, capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=gate.get("timeout", 900), **flags)
        code, output = proc.returncode, (proc.stdout + proc.stderr)
    except subprocess.TimeoutExpired as exc:
        code, output = -1, f"timeout after {gate.get('timeout')}s\n" + str(exc.stdout or "")
    return {"name": gate.get("name") or gate["run"][:60], "run": gate["run"], "code": code, "passed": code == 0,
            "seconds": round(time.monotonic() - started, 2), "output": output[-6000:]}


class PipelineRunner:
    def __init__(self, repo, workspace, manager, runtime, attention=None, events=None):
        self.repo, self.conn, self.workspace = repo, repo.conn, workspace
        self.manager, self.runtime, self.attention, self.events = manager, runtime, attention, events
        self._lock = asyncio.Lock()
        self.tasks: set = set()
        with self.repo._lock, self.conn:
            self.conn.executescript('''
                CREATE TABLE IF NOT EXISTS pipelines (
                    id TEXT PRIMARY KEY, project_id TEXT NOT NULL, name TEXT NOT NULL, state TEXT NOT NULL,
                    spec TEXT NOT NULL, error TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS pipeline_steps (
                    pipeline_id TEXT NOT NULL REFERENCES pipelines(id), step_id TEXT NOT NULL, state TEXT NOT NULL,
                    worktree_id TEXT NOT NULL DEFAULT '', chat_id TEXT NOT NULL DEFAULT '', turn_id TEXT NOT NULL DEFAULT '',
                    attempt INTEGER NOT NULL DEFAULT 0, gates TEXT NOT NULL DEFAULT '[]', commit_sha TEXT NOT NULL DEFAULT '',
                    error TEXT NOT NULL DEFAULT '', started_at TEXT NOT NULL DEFAULT '', finished_at TEXT NOT NULL DEFAULT '',
                    PRIMARY KEY (pipeline_id, step_id));
            ''')

    # ---------- storage ----------
    def get(self, ident):
        row = self.conn.execute("SELECT * FROM pipelines WHERE id=?", (ident,)).fetchone()
        if not row:
            raise KeyError(ident)
        item = dict(row)
        item["spec"] = json.loads(item["spec"])
        steps = {}
        for r in self.conn.execute("SELECT * FROM pipeline_steps WHERE pipeline_id=?", (ident,)):
            row = dict(r)
            row["gate_results"] = json.loads(row.pop("gates"))
            steps[r["step_id"]] = row
        item["tiers"] = topological_tiers([StepSpec(**s) for s in item["spec"]["steps"]])
        item["steps"] = [{**s, **steps.get(s["id"], {})} for s in item["spec"]["steps"]]
        return item

    def list(self, project_id=None):
        sql = "SELECT id FROM pipelines" + (" WHERE project_id=?" if project_id else "") + " ORDER BY created_at DESC LIMIT 100"
        return [self.get(r[0]) for r in self.conn.execute(sql, (project_id,) if project_id else ())]

    def _step(self, pipeline_id, step_id, **fields):
        with self.repo._lock, self.conn:
            self.conn.execute("UPDATE pipeline_steps SET " + ",".join(f"{k}=?" for k in fields) +
                              " WHERE pipeline_id=? AND step_id=?", (*fields.values(), pipeline_id, step_id))
        if self.events:
            self.events.publish("pipeline.step", {"pipeline_id": pipeline_id, "step_id": step_id, **{k: v for k, v in fields.items() if k != "gates"}})

    def _pipeline(self, ident, **fields):
        fields["updated_at"] = now()
        with self.repo._lock, self.conn:
            self.conn.execute("UPDATE pipelines SET " + ",".join(f"{k}=?" for k in fields) + " WHERE id=?", (*fields.values(), ident))
        if self.events:
            self.events.publish("pipeline.state", {"pipeline_id": ident, **fields})

    def create(self, spec: PipelineSpec):
        project = self.workspace.get_project(spec.project_id)
        if not project or project["archived"]:
            raise ValueError("پروژهٔ فعال پیدا نشد.")
        ident = "pipe_" + uuid.uuid4().hex[:12]
        with self.repo._lock, self.conn:
            self.conn.execute("INSERT INTO pipelines VALUES (?,?,?,'draft',?,'',?,?)",
                              (ident, spec.project_id, spec.name, spec.model_dump_json(), now(), now()))
            for step in spec.steps:
                self.conn.execute("INSERT INTO pipeline_steps (pipeline_id,step_id,state) VALUES (?,?,'pending')", (ident, step.id))
        return self.get(ident)

    # ---------- execution ----------
    def _spawn(self, coro):
        task = asyncio.create_task(coro)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return task

    async def start(self, ident):
        pipeline = self.get(ident)
        if pipeline["state"] not in {"draft", "paused"}:
            raise RuntimeError("این پایپلاین قبلاً شروع شده است.")
        self._pipeline(ident, state="running", error="")
        await self.advance(ident)
        return self.get(ident)

    async def advance(self, ident):
        async with self._lock:
            pipeline = self.get(ident)
            if pipeline["state"] != "running":
                return
            states = {s["id"]: s["state"] for s in pipeline["steps"]}
            for step in pipeline["steps"]:
                if step["state"] != "pending":
                    continue
                deps = [states[d] for d in step["depends_on"]]
                if any(d in {"failed", "blocked", "cancelled"} for d in deps):
                    self._step(ident, step["id"], state="blocked", error="یک وابستگی موفق نشد.", finished_at=now())
                    states[step["id"]] = "blocked"
                elif all(d == "passed" for d in deps):
                    try:
                        await self._launch(pipeline, step)
                        states[step["id"]] = "running"
                    except Exception as exc:
                        self._fail(ident, step, str(exc))
                        states[step["id"]] = "failed"
            if all(s in TERMINAL for s in states.values()):
                final = "completed" if all(s == "passed" for s in states.values()) else "failed"
                self._pipeline(ident, state=final)
                if self.attention:
                    self.attention.raise_item("pipeline", f"پایپلاین «{pipeline['name']}» {'کامل شد' if final == 'completed' else 'ناموفق ماند'}",
                                              3 if final == "completed" else 1, key=f"pipeline:{ident}:done",
                                              detail={"state": final}, pipeline_id=ident)
            elif any(s == "blocked" for s in states.values()) and not any(s in {"running", "gating", "waiting", "pending"} for s in states.values()):
                self._pipeline(ident, state="failed")

    def _fail(self, ident, step, error):
        self._step(ident, step["id"], state="failed", error=error[-4000:], finished_at=now())
        if self.attention:
            self.attention.raise_item("pipeline", f"گام «{step.get('title') or step['id']}» ناموفق شد", 1,
                                      key=f"pipeline:{ident}:{step['id']}", detail={"error": error[-1500:]},
                                      pipeline_id=ident, worktree_id=step.get("worktree_id") or "",
                                      chat_id=step.get("chat_id") or "")

    async def _launch(self, pipeline, step):
        from flux.local_agents.runtime import ChatSpec, TurnSpec
        ident = pipeline["id"]
        by_id = {s["id"]: s for s in pipeline["steps"]}
        deps = [by_id[d] for d in step["depends_on"]]
        base = deps[0]["commit_sha"] if deps else pipeline["spec"]["base"]
        worktree = await asyncio.to_thread(self.manager.create, pipeline["project_id"],
                                           f"{pipeline['name']}-{step['id']}", base, step.get("scope") or [])
        self._step(ident, step["id"], state="running", worktree_id=worktree["id"], started_at=now())
        configured = git(worktree["path"], "config", "user.email", check=False).strip()
        for extra in deps[1:]:
            code, out, err = await asyncio.to_thread(git_ok, worktree["path"], "merge", "--no-edit", "--no-ff",
                                                     extra["commit_sha"], env=None if configured else GIT_IDENTITY)
            if code != 0:
                await asyncio.to_thread(git_ok, worktree["path"], "merge", "--abort")
                raise RuntimeError(f"ادغام خروجی گام {extra['id']} تعارض داشت:\n{(out + err)[-2000:]}")
        summaries = "".join(f"- {d['id']}: {d.get('title') or ''} (commit {d['commit_sha'][:10]})\n" for d in deps)
        prompt = step["prompt"]
        if summaries:
            prompt += "\n\nThis step builds on these completed and verified steps (already in your working tree):\n" + summaries
        if step.get("gates"):
            prompt += "\nYour work will be accepted only if these commands pass in this directory:\n" + "".join(
                f"- {g['run']}\n" for g in step["gates"])
        chat = self.runtime.create_chat(ChatSpec(title=f"{pipeline['name']} · {step.get('title') or step['id']}"[:160],
                                                 provider=step["provider"], model=step.get("model") or "",
                                                 cwd=worktree["path"], access="work", project_id=pipeline["project_id"],
                                                 worktree_id=worktree["id"]))
        self._step(ident, step["id"], chat_id=chat["id"], attempt=1)
        turn = self.runtime.submit(chat["id"], TurnSpec(prompt=prompt, request_key=f"pipe:{ident}:{step['id']}:1"))
        self._step(ident, step["id"], turn_id=turn["id"])

    def on_turn(self, turn, chat):
        """Runtime listener (sync). Gating runs in a task so the runtime is never blocked."""
        row = self.conn.execute("SELECT pipeline_id,step_id FROM pipeline_steps WHERE chat_id=? AND state IN ('running','waiting')",
                                (chat["id"],)).fetchone()
        if row:
            try:
                self._spawn(self._after_turn(row[0], row[1], turn))
            except RuntimeError:
                pass  # no running loop (e.g. shutdown)

    async def _after_turn(self, ident, step_id, turn):
        live = self.runtime.turn(turn["id"])
        state = live["state"]
        if state in {"queued", "running"}:
            if turn["state"] == "queued":
                self._step(ident, step_id, state="running", turn_id=turn["id"])
            return
        pipeline = self.get(ident)
        step = next(s for s in pipeline["steps"] if s["id"] == step_id)
        if step["state"] in TERMINAL:
            return
        if state in {"needs_input", "deferred"}:
            self._step(ident, step_id, state="waiting", turn_id=turn["id"])
            return
        if state == "cancelled":
            self._step(ident, step_id, state="cancelled", finished_at=now())
            return await self.advance(ident)
        if state != "completed":
            self._fail(ident, step, live.get("error") or f"agent turn ended as {state}")
            return await self.advance(ident)
        self._step(ident, step_id, state="gating", turn_id=turn["id"])
        try:
            commit = await asyncio.to_thread(self.manager.commit_all, step["worktree_id"],
                                             f"flux pipeline {pipeline['name']}: {step.get('title') or step_id}")
            commit = commit or await asyncio.to_thread(lambda: git(self.manager.get(step["worktree_id"])["path"], "rev-parse", "HEAD").strip())
            env = self.manager.env(step["worktree_id"])
            path = self.manager.get(step["worktree_id"])["path"]
            results = []
            for gate in step.get("gates") or []:
                result = await asyncio.to_thread(run_gate, path, env, gate)
                results.append(result)
                if not result["passed"]:
                    break
        except (GitError, OSError, KeyError) as exc:
            self._fail(ident, step, str(exc))
            return await self.advance(ident)
        history = (step.get("gates_history") or []) + results
        if all(r["passed"] for r in results):
            self._step(ident, step_id, state="passed", commit_sha=commit, gates=json.dumps(results), finished_at=now(), error="")
            return await self.advance(ident)
        failed = next(r for r in results if not r["passed"])
        attempt = int(step.get("attempt") or 1)
        if attempt < step.get("max_attempts", 2):
            from flux.local_agents.runtime import TurnSpec
            self._step(ident, step_id, state="running", attempt=attempt + 1, gates=json.dumps(results))
            fix = (f"The gate `{failed['run']}` failed (exit code {failed['code']}). Fix the cause in this directory, "
                   f"do not weaken or skip the check.\nOriginal step objective:\n{step['prompt']}\n\n"
                   f"Output tail:\n{failed['output'][-3500:]}")
            try:
                turn = self.runtime.submit(step["chat_id"], TurnSpec(prompt=fix, request_key=f"pipe:{ident}:{step_id}:{attempt + 1}"))
                self._step(ident, step_id, turn_id=turn["id"])
            except (RuntimeError, ValueError) as exc:
                self._fail(ident, step, f"retry could not start: {exc}")
                await self.advance(ident)
            return
        self._step(ident, step_id, gates=json.dumps(results))
        self._fail(ident, {**step, "gates_history": history}, f"gate failed: {failed['run']} (exit {failed['code']})\n{failed['output'][-2000:]}")
        await self.advance(ident)

    async def cancel(self, ident):
        pipeline = self.get(ident)
        for step in pipeline["steps"]:
            if step["state"] in {"running", "waiting", "gating"} and step.get("turn_id"):
                try:
                    await self.runtime.cancel(step["turn_id"])
                except (RuntimeError, KeyError):
                    pass
            if step["state"] not in TERMINAL:
                self._step(ident, step["id"], state="cancelled", finished_at=now())
        self._pipeline(ident, state="cancelled")
        return self.get(ident)

    def recover(self):
        """After a restart nothing is replayed automatically; running pipelines become paused."""
        for row in self.conn.execute("SELECT id FROM pipelines WHERE state='running'").fetchall():
            for step in self.get(row[0])["steps"]:
                if step["state"] in {"running", "gating", "waiting"}:
                    self._step(row[0], step["id"], state="pending" if not step.get("worktree_id") else "interrupted")
            self._pipeline(row[0], state="paused", error="برنامه بسته شد؛ با «ادامه» گام‌های قطع‌شده دوباره اجرا می‌شوند.")

    async def resume(self, ident):
        """Re-run interrupted steps in their existing worktree and chat, then continue the DAG."""
        from flux.local_agents.runtime import TurnSpec
        pipeline = self.get(ident)
        if pipeline["state"] != "paused":
            raise RuntimeError("فقط پایپلاین متوقف‌شده ادامه پیدا می‌کند.")
        self._pipeline(ident, state="running", error="")
        for step in pipeline["steps"]:
            if step["state"] == "interrupted":
                attempt = int(step.get("attempt") or 0) + 1
                self._step(ident, step["id"], state="running", attempt=attempt)
                turn = self.runtime.submit(step["chat_id"], TurnSpec(
                    prompt="The previous run was interrupted. Continue the original task:\n" + step["prompt"],
                    request_key=f"pipe:{ident}:{step['id']}:resume{attempt}:{uuid.uuid4().hex[:6]}"))
                self._step(ident, step["id"], turn_id=turn["id"])
        await self.advance(ident)
        return self.get(ident)

    # ---------- orchestration ----------
    PLAN_PROMPT = (
        "You are the orchestrator. Break the objective below into a small dependency graph of steps that separate "
        "coding agents can execute, each in its own git worktree. A step must depend on another only when it needs that "
        "step's code. Give each step objective acceptance commands (build/test/lint) as gates when the repository has them. "
        "Do not modify any files. Reply with ONLY a JSON object of this shape:\n"
        '{"name": "short-name", "steps": [{"id": "a", "title": "...", "prompt": "...", "depends_on": [], '
        '"scope": ["src/module/"], "gates": [{"run": "npm test"}]}]}\n\nObjective:\n')

    async def plan(self, project_id, objective, provider="codex", model="", timeout=900):
        """Ask an orchestrator agent (read-only) to propose a pipeline; the user reviews it before start."""
        from flux.engine.json_parser import parse_llm_json
        from flux.local_agents.runtime import ChatSpec, TurnSpec
        project = self.workspace.get_project(project_id)
        if not project:
            raise ValueError("پروژه پیدا نشد.")
        chat = self.runtime.create_chat(ChatSpec(title="Orchestrator plan", provider=provider, model=model, cwd=project["path"],
                                                 access="read", project_id=project_id))
        turn = self.runtime.submit(chat["id"], TurnSpec(prompt=self.PLAN_PROMPT + objective, request_key="plan:" + uuid.uuid4().hex,
                                                        use_memory=True))
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            turn = self.runtime.turn(turn["id"])
            if turn["state"] not in {"queued", "running", "deferred"}:
                break
            await asyncio.sleep(0.5)
        if turn["state"] != "completed":
            raise RuntimeError(turn.get("error") or f"planner ended as {turn['state']}")
        data = parse_llm_json(turn["text"])
        data["project_id"] = project_id
        data.setdefault("name", "plan")
        data["name"] = re.sub(r"[^A-Za-z0-9_-]+", "-", str(data["name"]))[:60] or "plan"
        for step in data.get("steps", []):
            step.setdefault("provider", provider)
            if model:
                step.setdefault("model", model)
        return {"spec": PipelineSpec(**data).model_dump(), "planner_chat_id": chat["id"]}
