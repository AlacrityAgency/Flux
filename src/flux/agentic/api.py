"""FastAPI router for the 6 Agentic Engineering capabilities, mounted at ``/api/agentic``."""
from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from flux.agentic.surgical import SurgicalEditError, apply_model_edits, apply_unified_diff, replace_in_file


class SurgicalReplaceRequest(BaseModel):
    cwd: str = Field(min_length=1, max_length=1000)
    path: str = Field(min_length=1, max_length=500)
    search: str = Field(min_length=1, max_length=100000)
    replace: str = Field(default="", max_length=100000)


class SurgicalBlocksRequest(BaseModel):
    cwd: str = Field(min_length=1, max_length=1000)
    text: str = Field(min_length=1, max_length=200000)


class UnifiedDiffRequest(BaseModel):
    cwd: str = Field(min_length=1, max_length=1000)
    patch: str = Field(min_length=1, max_length=200000)


class CheckpointCreateRequest(BaseModel):
    cwd: str = Field(min_length=1, max_length=1000)
    chat_id: str = Field(default="", max_length=100)
    label: str = Field(default="manual checkpoint", max_length=200)


class VerifyRequest(BaseModel):
    cwd: str = Field(min_length=1, max_length=1000)
    files: list[str] = Field(default_factory=list, max_length=100)
    run_tests: bool = True


class LessonCreateRequest(BaseModel):
    cwd: str = Field(min_length=1, max_length=1000)
    stage: str = Field(default="manual", max_length=60)
    symptom: str = Field(min_length=1, max_length=2000)
    files: list[str] = Field(default_factory=list, max_length=25)
    resolution: str = Field(default="", max_length=2000)


class ExecutePlanRequest(BaseModel):
    request_key: str = Field(min_length=1, max_length=100)
    prompt: str = Field(default="طرح معماری تأیید شد؛ آن را گام‌به‌گام و با ویرایش جراحی اجرا کن.", max_length=20000)


def mount_agentic_api(app, agentic):
    router = APIRouter(prefix="/api/agentic", tags=["agentic"])

    # ----- 1. Smart Repo Map (Tree-sitter + AST) -----
    @router.get("/repomap")
    async def get_repomap(
        cwd: str = Query(..., min_length=1, max_length=1000),
        prompt: str = Query("", max_length=4000),
        budget_chars: int = Query(6000, ge=500, le=50000),
    ):
        if not Path(cwd).is_dir():
            raise HTTPException(400, "پوشهٔ کاری پیدا نشد.")
        return await asyncio.to_thread(agentic.repomap.build, cwd, prompt, budget_chars)

    # ----- 2. Plan vs. Act Architecture -----
    @router.get("/plans")
    def list_plans(chat_id: str | None = None, cwd: str | None = None, limit: int = Query(30, ge=1, le=100)):
        return {"plans": agentic.plans.list(chat_id=chat_id, cwd=cwd, limit=limit)}

    @router.get("/plans/{plan_id}")
    def get_plan(plan_id: str):
        try:
            return agentic.plans.get(plan_id)
        except KeyError:
            raise HTTPException(404, "طرح پیدا نشد.")

    @router.post("/plans/{plan_id}/approve")
    def approve_plan(plan_id: str):
        try:
            plan = agentic.plans.approve(plan_id)
        except KeyError:
            raise HTTPException(404, "طرح پیدا نشد.")
        if plan.get("chat_id"):
            with agentic.runtime.conn:
                agentic.runtime.conn.execute("UPDATE local_chats SET mode='act' WHERE id=?", (plan["chat_id"],))
        return plan

    @router.post("/plans/{plan_id}/execute", status_code=202)
    async def execute_plan(plan_id: str, payload: ExecutePlanRequest):
        from flux.local_agents.runtime import TurnSpec
        try:
            plan = agentic.plans.approve(plan_id)
        except KeyError:
            raise HTTPException(404, "طرح پیدا نشد.")
        if not plan.get("chat_id"):
            raise HTTPException(400, "این طرح به گفتگوی مشخصی متصل نیست.")
        with agentic.runtime.conn:
            agentic.runtime.conn.execute("UPDATE local_chats SET mode='act' WHERE id=?", (plan["chat_id"],))
        try:
            return agentic.runtime.submit(plan["chat_id"], TurnSpec(prompt=payload.prompt, request_key=payload.request_key, mode="act"))
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(409, str(exc))

    # ----- 3. Automated Compiler / Linter / Test Feedback -----
    @router.post("/verify")
    async def verify_workspace(payload: VerifyRequest):
        if not Path(payload.cwd).is_dir():
            raise HTTPException(400, "پوشهٔ کاری پیدا نشد.")
        return await asyncio.to_thread(agentic.verifier.verify, payload.cwd, payload.files, payload.run_tests)

    # ----- 4. Surgical File Edits -----
    @router.post("/surgical/replace")
    async def surgical_replace(payload: SurgicalReplaceRequest):
        try:
            return await asyncio.to_thread(replace_in_file, payload.cwd, payload.path, payload.search, payload.replace)
        except SurgicalEditError as exc:
            raise HTTPException(422, str(exc))

    @router.post("/surgical/blocks")
    async def surgical_blocks(payload: SurgicalBlocksRequest):
        res = await asyncio.to_thread(apply_model_edits, payload.cwd, payload.text)
        if not res["ok"]:
            raise HTTPException(422, res["errors"][0]["error"])
        return res

    @router.post("/surgical/diff")
    async def surgical_diff(payload: UnifiedDiffRequest):
        try:
            return await asyncio.to_thread(apply_unified_diff, payload.cwd, payload.patch)
        except SurgicalEditError as exc:
            raise HTTPException(422, str(exc))

    # ----- 5. Shadow Git Checkpoints -----
    @router.get("/checkpoints")
    def list_checkpoints(cwd: str | None = None, chat_id: str | None = None, limit: int = Query(40, ge=1, le=200)):
        return {"checkpoints": agentic.checkpoints.list(cwd=cwd, chat_id=chat_id, limit=limit)}

    @router.post("/checkpoints", status_code=201)
    async def create_checkpoint(payload: CheckpointCreateRequest):
        try:
            return await asyncio.to_thread(agentic.checkpoints.capture, payload.cwd, payload.chat_id, "", "manual", payload.label)
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(400, str(exc))

    @router.get("/checkpoints/{checkpoint_id}/diff")
    async def checkpoint_diff(checkpoint_id: str):
        try:
            return await asyncio.to_thread(agentic.checkpoints.diff, checkpoint_id)
        except KeyError:
            raise HTTPException(404, "چک‌پوینت پیدا نشد.")

    @router.post("/checkpoints/{checkpoint_id}/restore")
    async def restore_checkpoint(checkpoint_id: str, create_backup: bool = True):
        try:
            return await asyncio.to_thread(agentic.checkpoints.restore, checkpoint_id, create_backup)
        except KeyError:
            raise HTTPException(404, "چک‌پوینت پیدا نشد.")
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(409, str(exc))

    # ----- 6. Context Sentinel (Rules + Persistent Error Memory) -----
    @router.get("/sentinel")
    async def get_sentinel(cwd: str = Query(..., min_length=1, max_length=1000), prompt: str = Query("", max_length=4000)):
        if not Path(cwd).is_dir():
            raise HTTPException(400, "پوشهٔ کاری پیدا نشد.")
        ctx = await asyncio.to_thread(agentic.sentinel.build_context, cwd, prompt)
        lessons = await asyncio.to_thread(agentic.sentinel.list_lessons, cwd)
        return {**ctx, "lessons": lessons}

    @router.post("/sentinel/lessons", status_code=201)
    def add_lesson(payload: LessonCreateRequest):
        if not Path(payload.cwd).is_dir():
            raise HTTPException(400, "پوشهٔ کاری پیدا نشد.")
        return agentic.sentinel.record_lesson(payload.cwd, payload.stage, payload.symptom, payload.files, payload.resolution)

    app.include_router(router)
