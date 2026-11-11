"""HTTP/SSE/WebSocket API for parallel work, mounted at ``/api/parallel``."""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from typing import Literal

from flux.parallel.chapters import build_chapters
from flux.parallel.gitops import GitError
from flux.parallel.pipelines import PipelineSpec


class WorktreeCreate(BaseModel):
    project_id: str = Field(min_length=1, max_length=100)
    name: str = Field(default="", max_length=60)
    base: str = Field(default="HEAD", max_length=200, pattern=r"^[A-Za-z0-9_./~^@{}-]+$")
    scope: list[str] = Field(default_factory=list, max_length=50)
    run_setup: bool = True


class WorktreeChat(BaseModel):
    provider: Literal["codex", "claude", "gemini", "gapcode", "antigravity"] = "codex"
    model: str = Field(default="", max_length=100)
    title: str = Field(default="", max_length=160)
    access: Literal["read", "work"] = "work"


class UnshareRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class CommitRequest(BaseModel):
    message: str = Field(default="flux: worktree changes", min_length=1, max_length=300)


class WikiEntry(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    body: str = Field(min_length=1, max_length=8000)
    kind: Literal["convention", "decision", "pitfall", "fix", "note"] = "note"
    status: Literal["verified", "proposed", "retired"] = "verified"
    pinned: bool = False
    tags: list[str] = Field(default_factory=list, max_length=12)


class WikiPatch(BaseModel):
    status: Literal["verified", "proposed", "retired"]


class PlanRequest(BaseModel):
    project_id: str = Field(min_length=1, max_length=100)
    objective: str = Field(min_length=1, max_length=20000)
    provider: Literal["codex", "claude", "gemini", "gapcode", "antigravity"] = "codex"
    model: str = Field(default="", max_length=100)


class ParallelSettings(BaseModel):
    max_parallel: int = Field(ge=1, le=16)


def mount_parallel_api(app, hub, static_dir):
    router = APIRouter(prefix="/api/parallel")
    runtime = hub.runtime

    def worktree_busy(ident):
        return ident in hub.coordinator.active_worktree_ids() or bool(runtime.conn.execute(
            "SELECT 1 FROM local_turns t JOIN local_chats c ON c.id=t.chat_id WHERE c.worktree_id=? AND t.state='deferred'",
            (ident,)).fetchone())

    @router.get("/overview")
    def overview():
        return {"max_parallel": runtime.max_parallel, "running": len(runtime.jobs),
                "deferred": runtime.conn.execute("SELECT COUNT(*) FROM local_turns WHERE state='deferred'").fetchone()[0],
                "attention": hub.attention.counts(), "worktrees": hub.worktrees.list(),
                "pipelines": [{k: p[k] for k in ("id", "name", "state", "project_id")} for p in hub.pipelines.list()],
                "event_sequence": hub.events.sequence}

    @router.put("/settings")
    def settings(payload: ParallelSettings):
        runtime.max_parallel = payload.max_parallel
        return {"max_parallel": runtime.max_parallel}

    # ----- worktrees -----
    @router.get("/worktrees")
    def worktrees(project_id: str | None = None, include_removed: bool = False):
        return hub.worktrees.list(project_id, include_removed)

    @router.post("/worktrees", status_code=201)
    async def create_worktree(payload: WorktreeCreate):
        try:
            return await asyncio.to_thread(hub.worktrees.create, payload.project_id, payload.name, payload.base,
                                           payload.scope, payload.run_setup)
        except GitError as exc:
            raise HTTPException(422, str(exc))

    @router.get("/worktrees/{ident}")
    def worktree(ident: str):
        return hub.worktrees.get(ident)

    @router.delete("/worktrees/{ident}")
    async def remove_worktree(ident: str, delete_branch: bool = False):
        try:
            return await asyncio.to_thread(hub.worktrees.remove, ident, delete_branch, worktree_busy)
        except RuntimeError as exc:
            raise HTTPException(409, str(exc))

    @router.post("/worktrees/{ident}/unshare")
    def unshare(ident: str, payload: UnshareRequest):
        return hub.worktrees.unshare(ident, payload.name)

    @router.post("/worktrees/{ident}/commit")
    async def commit(ident: str, payload: CommitRequest):
        return {"commit": await asyncio.to_thread(hub.worktrees.commit_all, ident, payload.message)}

    @router.post("/worktrees/{ident}/chats", status_code=201)
    def worktree_chat(ident: str, payload: WorktreeChat):
        from flux.local_agents.runtime import ChatSpec
        item = hub.worktrees.get(ident)
        return runtime.create_chat(ChatSpec(title=payload.title or f"worktree {item['name']}", provider=payload.provider,
                                            model=payload.model, cwd=item["path"], access=payload.access,
                                            project_id=item["project_id"], worktree_id=ident))

    @router.get("/worktrees/{ident}/chapters")
    async def chapters(ident: str, patch: bool = True):
        item = hub.worktrees.get(ident)
        return await asyncio.to_thread(build_chapters, item["path"], item["base_commit"], patch)

    @router.get("/worktrees/{ident}/overlaps")
    async def overlaps(ident: str, prompt: str = "", all: bool = True):
        return await asyncio.to_thread(hub.coordinator.check, ident, prompt, not all)

    @router.post("/overlaps/scan")
    async def scan():
        return await asyncio.to_thread(hub.coordinator.scan)

    # ----- attention -----
    @router.get("/attention")
    def attention(state: str = Query("open", pattern="^(open|resolved|dismissed|all)$")):
        return {"items": hub.attention.items(state), "counts": hub.attention.counts()}

    @router.post("/attention/{ident}/resolve")
    def resolve(ident: str, dismiss: bool = False):
        return hub.attention.resolve(ident, "dismissed" if dismiss else "resolved")

    @router.post("/attention/{ident}/approve-memory")
    async def approve_memory(ident: str):
        item = hub.attention.get(ident)
        if item["kind"] != "memory":
            raise HTTPException(422, "این مورد پیشنهاد حافظه نیست.")
        entry = await asyncio.to_thread(hub.wiki.set_status, item["detail"]["repo"], item["detail"]["entry_id"], "verified")
        hub.attention.resolve(ident)
        return entry

    # ----- shared memory (git-backed wiki) -----
    @router.get("/projects/{project_id}/wiki")
    async def wiki(project_id: str, status: str | None = None):
        path = hub.repo_for_project(project_id)
        return {"head": hub.wiki.head(path), "entries": await asyncio.to_thread(hub.wiki.entries, path, status)}

    @router.post("/projects/{project_id}/wiki", status_code=201)
    async def wiki_add(project_id: str, payload: WikiEntry):
        path = hub.repo_for_project(project_id)
        return await asyncio.to_thread(hub.wiki.save, path, payload.title, payload.body, payload.kind, payload.status,
                                       payload.pinned, payload.tags, {"origin": "human"})

    @router.patch("/projects/{project_id}/wiki/{entry_id}")
    async def wiki_status(project_id: str, entry_id: str, payload: WikiPatch):
        return await asyncio.to_thread(hub.wiki.set_status, hub.repo_for_project(project_id), entry_id, payload.status)

    @router.delete("/projects/{project_id}/wiki/{entry_id}")
    async def wiki_delete(project_id: str, entry_id: str):
        return {"deleted": await asyncio.to_thread(hub.wiki.delete, hub.repo_for_project(project_id), entry_id)}

    @router.get("/projects/{project_id}/wiki-history")
    def wiki_history(project_id: str):
        return hub.wiki.history(hub.repo_for_project(project_id))

    # ----- pipelines -----
    @router.get("/pipelines")
    def pipelines(project_id: str | None = None):
        return hub.pipelines.list(project_id)

    @router.post("/pipelines", status_code=201)
    async def create_pipeline(spec: PipelineSpec, start: bool = False):
        item = hub.pipelines.create(spec)
        return await hub.pipelines.start(item["id"]) if start else item

    @router.post("/pipelines/plan")
    async def plan(payload: PlanRequest):
        try:
            return await hub.pipelines.plan(payload.project_id, payload.objective, payload.provider, payload.model)
        except RuntimeError as exc:
            raise HTTPException(409, str(exc))

    @router.get("/pipelines/{ident}")
    def pipeline(ident: str):
        return hub.pipelines.get(ident)

    @router.post("/pipelines/{ident}/start")
    async def start(ident: str):
        try:
            return await hub.pipelines.start(ident)
        except RuntimeError as exc:
            raise HTTPException(409, str(exc))

    @router.post("/pipelines/{ident}/resume")
    async def resume(ident: str):
        try:
            return await hub.pipelines.resume(ident)
        except RuntimeError as exc:
            raise HTTPException(409, str(exc))

    @router.post("/pipelines/{ident}/cancel")
    async def cancel(ident: str):
        return await hub.pipelines.cancel(ident)

    # ----- events -----
    @router.get("/events")
    def events(after: int = Query(0, ge=0)):
        return hub.events.after(after)

    @router.get("/events/stream")
    async def stream(after: int = Query(0, ge=0)):
        async def generate():
            sequence = after
            yield "retry: 2000\n\n"
            idle = 0
            while True:
                items = hub.events.after(sequence)
                for item in items:
                    sequence = item["sequence"]
                    yield f"id: {sequence}\nevent: {item['kind']}\ndata: {json.dumps(item, ensure_ascii=False)}\n\n"
                idle = 0 if items else idle + 1
                if idle and idle % 30 == 0:
                    yield ": keep-alive\n\n"
                await asyncio.sleep(0.5)
        return StreamingResponse(generate(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})

    @router.websocket("/ws")
    async def websocket(socket: WebSocket, after: int = 0):
        import hmac
        import os
        token = os.environ.get("FLUX_API_TOKEN", "")
        if token:
            supplied = (socket.headers.get("authorization", "").removeprefix("Bearer ").strip()
                        or socket.query_params.get("token", "") or socket.cookies.get("flux_token", ""))
            if not hmac.compare_digest(supplied.encode(), token.encode()):
                await socket.close(code=4401)
                return
        await socket.accept()
        sequence = after
        try:
            while True:
                for item in hub.events.after(sequence):
                    sequence = item["sequence"]
                    await socket.send_json(item)
                await asyncio.sleep(0.5)
        except (WebSocketDisconnect, RuntimeError):
            return

    app.include_router(router)

    @app.get("/attention")
    async def attention_page():
        return FileResponse(static_dir / "attention.html", media_type="text/html")
