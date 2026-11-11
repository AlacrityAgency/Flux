"""Local Flux application API and chat workspace."""
import asyncio
import json
import re
import subprocess
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit
import uuid

from fastapi import FastAPI, HTTPException, Header, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field, ValidationError

from flux.settings import get_settings
from flux import __version__
from flux.storage.database import init_db
from flux.storage.repository import Repository
from flux.storage.workspace import Workspace, clean_text
from flux.providers.fake import FakeProvider
from flux.engine.profiles import PROFILES
from flux.engine.orchestrator import FluxEngine
from flux.contracts.task import TaskInput
from flux.contracts.agents import AgentSettings
from flux.budget.pricing import MODEL_PRICES
from flux.local_agents.runtime import LocalRuntime
from flux.local_agents.api import mount_local_api

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
ACTIVE = {"NEW", "VALIDATING", "PLANNING", "QUEUED", "RUNNING", "VERIFYING"}
IGNORED_CONTEXT_DIRS = {".git", ".hg", ".svn", ".venv", "venv", "node_modules", "__pycache__", "build", "dist", "coverage"}
TEXT_CONTEXT_EXTENSIONS = {".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".html", ".css", ".scss", ".json", ".yaml", ".yml", ".toml", ".ini", ".md", ".txt", ".sh", ".ps1", ".bat", ".java", ".go", ".rs", ".cs", ".cpp", ".h", ".sql"}
SENSITIVE_CONTEXT_NAMES = {".env", ".env.local", ".env.production", "id_rsa", "id_ed25519", "credentials.json", "service-account.json"}


def inspect_folder(folder_path: str):
    p = Path(folder_path).expanduser().resolve()
    if not p.exists():
        return {"exists": False, "is_dir": False, "path": str(p), "name": p.name or str(p), "total_files": 0, "total_dirs": 0, "entries": [], "error": "مسیر در سیستم یافت نشد."}
    if not p.is_dir():
        return {"exists": True, "is_dir": False, "path": str(p), "name": p.name or str(p), "total_files": 0, "total_dirs": 0, "entries": [], "error": "مسیر مشخص‌شده یک پوشه نیست."}
    entries = []
    total_files = 0
    total_dirs = 0
    try:
        for item in sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
            if item.name.startswith((".", "__")):
                continue
            if item.is_dir():
                total_dirs += 1
                if len(entries) < 50:
                    entries.append({"name": item.name, "type": "dir"})
            else:
                total_files += 1
                if len(entries) < 50:
                    entries.append({"name": item.name, "type": "file", "size": item.stat().st_size})
    except PermissionError:
        return {"exists": True, "is_dir": True, "path": str(p), "name": p.name or str(p), "total_files": 0, "total_dirs": 0, "entries": [], "error": "دسترسی به این پوشه مجاز نیست."}
    return {
        "exists": True,
        "is_dir": True,
        "path": str(p),
        "name": p.name or str(p),
        "total_files": total_files,
        "total_dirs": total_dirs,
        "entries": entries
    }


def build_project_context(project: dict) -> dict | None:
    """Create a small, safe, read-only source snapshot for project analysis."""
    root = Path(project["path"]).expanduser().resolve()
    folder_info = inspect_folder(str(root))
    if not folder_info.get("exists") or not folder_info.get("is_dir"):
        return None

    entries, excerpts = [], []
    remaining = 5_000

    def context_priority(path: Path) -> tuple[int, str]:
        relative = path.relative_to(root).as_posix().lower()
        # Code is more useful to a review than generated reports, test cache, or lockfiles.
        if "/src/" in f"/{relative}" or relative.startswith("src/"):
            return (0, relative)
        if relative.startswith(("electron-app/", "app/", "lib/")):
            return (1, relative)
        if path.name.lower() in {"readme.md", "pyproject.toml", "package.json"}:
            return (2, relative)
        if "/tests/" in f"/{relative}" or relative.startswith("tests/"):
            return (4, relative)
        return (3, relative)

    try:
        candidates = sorted(
            (path for path in root.rglob("*")
             if path.is_file()
             and not any(part.startswith(".") or part.lower() in IGNORED_CONTEXT_DIRS for part in path.relative_to(root).parts[:-1])
             and path.name.lower() not in SENSITIVE_CONTEXT_NAMES
             and path.suffix.lower() in TEXT_CONTEXT_EXTENSIONS),
            key=context_priority,
        )
        for path in candidates[:80]:
            relative = path.relative_to(root).as_posix()
            entries.append(relative)
            if len(excerpts) >= 6 or remaining <= 0 or path.stat().st_size > 128_000:
                continue
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if "\x00" in content:
                continue
            excerpt = content[:min(1_000, remaining)]
            if excerpt.strip():
                excerpts.append(f"\n--- {relative} ---\n{excerpt}")
                remaining -= len(excerpt)
    except (OSError, PermissionError):
        entries, excerpts = [], []

    manifest = "\n".join(entries[:80]) or "(No supported text files were readable.)"
    content = (
        f"Project: {project['name']}\nFolder: {root}\n"
        "This is a read-only local snapshot. Analyze only the supplied files; identify gaps rather than requesting tools.\n"
        f"Source tree (up to {len(entries)} files):\n{manifest}\n"
        f"Source excerpts (up to {len(excerpts)} files):\n{''.join(excerpts) or '(No source excerpts available.)'}"
    )
    return {"ref": f"folder:{root}", "title": f"پوشهٔ کاری {project['name']}", "content": content[:10_000]}


class SubmitRunRequest(BaseModel):
    task: dict[str, Any]
    idempotency_key: str | None = None
    conversation_id: str | None = None
    project_id: str | None = None
    use_memory: bool = True


class MemoryRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=12000)
    enabled: bool = True
    project_id: str | None = Field(default=None,max_length=100)
    status: Literal['verified','proposed','stale'] = 'verified'
    provenance: list[str] | None = Field(default=None,max_length=30)
    expected_revision: int | None = Field(default=None,ge=1)


class PreferencesRequest(BaseModel):
    daily_budget: float = Field(gt=0, le=1000, allow_inf_nan=False)
    default_budget: float = Field(gt=0, le=100, allow_inf_nan=False)
    theme: str = Field(pattern="^(dark|light)$")


class ConversationRequest(BaseModel):
    title: str = Field(min_length=1, max_length=160)


class ConversationUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    archived: bool | None = None


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    path: str = Field(min_length=1, max_length=1000)
    description: str = Field(default="", max_length=5000)
    default_criteria: str = Field(default="", max_length=5000)
    default_budget: float = Field(default=0.5, gt=0, le=100)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    path: str | None = Field(default=None, min_length=1, max_length=1000)
    description: str | None = Field(default=None, max_length=5000)
    default_criteria: str | None = Field(default=None, max_length=5000)
    default_budget: float | None = Field(default=None, gt=0, le=100)
    archived: bool | None = None


class ProjectTaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    objective: str = Field(min_length=5, max_length=12000)
    acceptance_criteria: list[str] | str = Field(default_factory=list)
    budget_cap_usd: float = Field(default=0.5, gt=0, le=100)
    priority: str = Field(default="P1", pattern="^(P0|P1|P2|P3)$")
    workflow: str = Field(default="low", pattern="^(low|medium|high|auto|team)$")


class ProjectTaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    objective: str | None = Field(default=None, min_length=5, max_length=12000)
    acceptance_criteria: list[str] | str | None = None
    budget_cap_usd: float | None = Field(default=None, gt=0, le=100)
    priority: str | None = Field(default=None, pattern="^(P0|P1|P2|P3)$")
    workflow: str | None = Field(default=None, pattern="^(low|medium|high|auto|team)$")
    status: str | None = None


class OpenFolderRequest(BaseModel):
    path: str = Field(min_length=1, max_length=1000)


def create_app(engine=None, db_path=None):
    owned = engine is None
    if owned:
        settings = get_settings()
        repo = Repository(init_db(db_path or settings.db_path))
        provider = FakeProvider()
        provider.delay_seconds = .22
        engine = FluxEngine(repo, provider)
    try:
        from flux.local_agents.gemini_api import purge_removed_provider_keys
        purge_removed_provider_keys()
    except Exception:
        pass
    workspace = Workspace(engine.repo)
    local_runtime = LocalRuntime(engine.repo, workspace)
    from flux.parallel import ParallelHub
    from flux.parallel.api import mount_parallel_api
    from flux.agentic import AgenticHub
    from flux.agentic.api import mount_agentic_api
    parallel = ParallelHub(engine.repo, workspace, local_runtime)
    agentic = AgenticHub(engine.repo, workspace, local_runtime, events=parallel.events)
    jobs = {}

    @asynccontextmanager
    async def lifespan(app):
        local_runtime.recover()
        parallel.recover()
        app.state.core.recover()
        # Never replay an in-flight provider request after an interrupted process.
        if owned:
            for record in engine.repo.list_runs(limit=10000):
                if record["status"] in ACTIVE:
                    engine.repo.update_run_status(record["run_id"], "FAILED", "اجرای قبلی قطع شده است؛ برای جلوگیری از مصرف تکراری خودکار ادامه داده نشد.")
        parallel.start()
        yield
        await parallel.stop()
        await local_runtime.close()
        for run_id, job in list(jobs.items()):
            engine.cancel_run(run_id)
            job.cancel()
        await asyncio.gather(*jobs.values(), return_exceptions=True)
        if owned:
            engine.repo.conn.close()

    app = FastAPI(title="Flux · Personal workspace", version=__version__, lifespan=lifespan)
    import os as _os
    extra_hosts = [h.strip() for h in _os.environ.get("FLUX_ALLOWED_HOSTS", "").split(",") if h.strip()]
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "[::1]", "test", "testserver", *extra_hosts])
    app.state.engine, app.state.repo, app.state.workspace = engine, engine.repo, workspace
    app.state.jobs = jobs
    app.state.local_runtime = local_runtime
    app.state.parallel = parallel
    app.state.agentic = agentic
    mount_local_api(app, local_runtime, STATIC_DIR)
    mount_parallel_api(app, parallel, STATIC_DIR)
    mount_agentic_api(app, agentic)
    from flux.core.api import mount_core_api
    mount_core_api(app,engine.repo,workspace,local_runtime)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    design_root = (Path(sys._MEIPASS)/"flux"/"design-v2" if getattr(sys,"frozen",False) else Path(__file__).resolve().parents[3]/"docs"/"design-v2")
    @app.get("/design-v2/{page}")
    async def design_preview(page: str):
        if page not in {"01-shell-home.html","02-request-contract.html","02-request-contract.js","03-10-workspace.html","03-10-workspace.js","sidebar.js"}: raise HTTPException(404,"صفحهٔ طراحی پیدا نشد.")
        path=design_root/page
        if not path.is_file(): raise HTTPException(404,"فایل طراحی داخل این نسخه موجود نیست.")
        return FileResponse(path,media_type="application/javascript" if page.endswith(".js") else "text/html")

    @app.middleware("http")
    async def local_origin(request: Request, call_next):
        token = _os.environ.get("FLUX_API_TOKEN", "")
        set_cookie = False
        if token:
            import hmac
            supplied = request.headers.get("authorization", "").removeprefix("Bearer ").strip() or request.cookies.get("flux_token", "")
            if not supplied and request.method == "GET" and request.query_params.get("token"):
                supplied, set_cookie = request.query_params["token"], True
            if not hmac.compare_digest(supplied.encode(), token.encode()):
                return JSONResponse({"detail": "توکن دسترسی دمون لازم است."}, status_code=401)
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            origin = request.headers.get("origin")
            if origin and urlsplit(origin).netloc != request.headers.get("host"):
                return JSONResponse({"detail": "درخواست باید از خود برنامه ارسال شود."}, status_code=403)
        response = await call_next(request)
        if set_cookie:
            response.set_cookie("flux_token", token, httponly=True, samesite="strict")
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        design_page=request.url.path.startswith('/design-v2/')
        style_policy = "style-src 'self' 'unsafe-inline'; " if design_page else "style-src 'self'; "
        script_policy = "script-src 'self' 'unsafe-inline'; " if design_page else "script-src 'self'; "
        response.headers["Content-Security-Policy"] = "default-src 'self'; " + script_policy + style_policy + "img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
        return response

    @app.exception_handler(ValueError)
    async def invalid_value(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=422)

    @app.exception_handler(KeyError)
    async def missing_record(request, exc):
        return JSONResponse({'detail':'رکورد پیدا نشد.'},status_code=404)

    def require_run(run_id):
        record = engine.repo.get_run(run_id)
        if not record:
            raise HTTPException(404, "این کار پیدا نشد.")
        return record

    def detail(run_id):
        record = require_run(run_id)
        task = json.loads(record["task_payload"])
        events = engine.repo.get_events(run_id, limit=500)
        calls = [dict(r) for r in engine.repo.conn.execute(
            "SELECT agent_role,model_id,status,attempt,latency_ms FROM agent_calls WHERE run_id=? ORDER BY created_at", (run_id,))]
        return {**{k: v for k, v in record.items() if k not in ("task_payload", "idempotency_key")},
                "task": task, "objective": task.get("objective", ""),
                "subtasks": engine.repo.get_subtasks(run_id), "artifacts": engine.repo.get_artifacts(run_id),
                "checks": engine.repo.get_checks(run_id), "decision": engine.repo.get_decision(run_id),
                "events": events, "calls": calls, "usage": engine.repo.get_usage_summary(run_id),
                "acceptance": workspace.acceptance(run_id),
                "reason": events[-1]["reason"] if events else "", "demo": isinstance(engine.provider, FakeProvider)}

    async def execute(run_id, project_task_id=None):
        try:
            return await engine.execute_run(run_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            record = engine.repo.get_run(run_id)
            if record and record["status"] in ACTIVE:
                engine.repo.update_run_status(run_id, "FAILED", "اجرا با خطای داخلی متوقف شد؛ داده‌های ثبت‌شده حفظ شدند.")
        finally:
            if project_task_id:
                record = engine.repo.get_run(run_id)
                if record:
                    workspace.update_project_task(project_task_id, status=record["status"])
            jobs.pop(run_id, None)

    @app.get("/")
    async def index():
        # The installed desktop shell should open the Alacrity workspace, not
        # the legacy free-chat landing page. Keep that chat available directly.
        return RedirectResponse(url="/design-v2/01-shell-home.html", status_code=307)

    @app.get("/chat", response_class=HTMLResponse)
    async def local_chat():
        return HTMLResponse(STATIC_DIR.joinpath("local.html").read_text(encoding="utf-8"))

    @app.get("/legacy", response_class=HTMLResponse)
    async def legacy_index():
        return HTMLResponse(STATIC_DIR.joinpath("index.html").read_text(encoding="utf-8"))

    @app.get("/runs")
    async def list_runs(limit: int = Query(50, ge=1, le=100)):
        return engine.repo.list_runs(limit)

    @app.post("/runs", status_code=201)
    async def submit(payload: SubmitRunRequest, background: bool = False,
                     x_idempotency_key: str | None = Header(None, alias="X-Idempotency-Key")):
        key = payload.idempotency_key or x_idempotency_key
        # Check the original payload before adding derived, versioned context.
        clean_text(json.dumps(payload.task, ensure_ascii=False), 40000)
        task_data = dict(payload.task)
        if payload.project_id:
            proj = workspace.get_project(payload.project_id)
            if not proj:
                raise HTTPException(404, "پروژهٔ انتخاب‌شده پیدا نشد.")
            task_data["project_id"] = proj["id"]
            if proj.get("path"):
                paths = task_data.get("allowed_paths") or []
                if proj["path"] not in paths:
                    task_data["allowed_paths"] = paths + [proj["path"]]
                snapshot = build_project_context(proj)
                if snapshot:
                    ctx = list(task_data.get("context") or [])
                    if not any(c.get("ref", "").startswith("folder:") for c in ctx):
                        ctx.append(snapshot)
                        task_data["context"] = ctx
        # Auto-detect folder path mentioned in objective if no folder context is attached
        if not any(c.get("ref", "").startswith("folder:") for c in (task_data.get("context") or [])):
            match = re.search(r'([A-Za-z]:[\\/][^\s*?"<>|]+)', task_data.get("objective", ""))
            if match:
                folder_cand = match.group(1).rstrip(".,;\"'`)]} ")
                p_cand = Path(folder_cand)
                if p_cand.exists() and p_cand.is_dir():
                    dummy_proj = {"name": p_cand.name or folder_cand, "path": str(p_cand)}
                    cand_snap = build_project_context(dummy_proj)
                    if cand_snap:
                        ctx = list(task_data.get("context") or [])
                        ctx.append(cand_snap)
                        task_data["context"] = ctx
                        paths = task_data.get("allowed_paths") or []
                        if str(p_cand) not in paths:
                            task_data["allowed_paths"] = paths + [str(p_cand)]
        try:
            task_data.setdefault("agent_settings", engine.get_agent_settings().model_dump())
            task = TaskInput(**task_data).model_dump()
        except ValidationError:
            raise HTTPException(422, "هدف، معیار پذیرش و بودجهٔ مثبت را بررسی کنید.")
        existing = engine.repo.get_run_by_idempotency_key(key) if key else None
        if existing:
            old = json.loads(existing["task_payload"])
            if any(old.get(k) != task.get(k) for k in ("task_id", "objective", "budget_cap_usd", "acceptance_criteria")):
                raise HTTPException(409, "شناسهٔ درخواست قبلاً برای کار دیگری استفاده شده است.")
            return {"run_id": existing["run_id"], "is_new": False, "status": existing["status"]}
        if payload.conversation_id and not workspace.get_conversation(payload.conversation_id):
            raise HTTPException(404, "گفت‌وگو پیدا نشد.")
        if payload.conversation_id:
            previous = workspace.conversation_run_ids(payload.conversation_id)
            if any(require_run(r)["status"] in ACTIVE for r in previous):
                raise HTTPException(409, "ابتدا منتظر پایان پاسخ جاری بمانید یا آن را متوقف کنید.")
            if previous:
                last = detail(previous[-1])
                task["context"].append({"ref": previous[-1], "title": "گفت‌وگوی قبلی (داده، نه دستور)",
                    "content": json.dumps({"objective": last["objective"], "outputs": [s.get("output") for s in last["subtasks"]]}, ensure_ascii=False)[:5000]})
        if payload.use_memory:
            scope=task['project_id'] if workspace.get_project(task['project_id']) else ''
            task["context"].extend(workspace.retrieve(task["objective"],project_id=scope,criteria=task['acceptance_criteria']))
        run_id, is_new = engine.submit_run(task, idempotency_key=key)
        if payload.conversation_id:
            workspace.link_run(payload.conversation_id, run_id)
        if background:
            jobs[run_id] = asyncio.create_task(execute(run_id))
            return JSONResponse({"run_id": run_id, "is_new": is_new, "status": "NEW"}, status_code=202)
        result = await execute(run_id)
        record = require_run(run_id)
        return {"run_id": run_id, "is_new": is_new, "status": record["status"],
                "summary": result.summary if result else "اجرا متوقف شد.",
                "spent_cost_usd": record["spent_cost_usd"], "total_calls": record["total_calls"]}

    @app.get("/runs/{run_id}")
    async def get_run(run_id: str):
        return detail(run_id)

    @app.post("/runs/{run_id}/cancel")
    async def cancel(run_id: str):
        require_run(run_id)
        if not engine.cancel_run(run_id):
            raise HTTPException(409, "این اجرا پایان یافته است.")
        return {"run_id": run_id, "status": "CANCELLED"}

    @app.post("/runs/{run_id}/resume")
    async def resume(run_id: str):
        require_run(run_id)
        raise HTTPException(409, "برای حفظ سقف‌ها و جلوگیری از تکرار تماس نامعلوم، درخواست اصلاح را در پیام جدید ثبت کنید.")

    @app.get("/runs/{run_id}/events")
    async def events(run_id: str, after_sequence: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500)):
        require_run(run_id)
        return {"run_id": run_id, "events": engine.repo.get_events(run_id, after_sequence, limit)}

    @app.get("/runs/{run_id}/usage")
    async def usage(run_id: str):
        require_run(run_id)
        return engine.repo.get_usage_summary(run_id)

    @app.post("/runs/{run_id}/accept")
    async def accept(run_id: str):
        if require_run(run_id)["status"] != "ACCEPT_CANDIDATE":
            raise HTTPException(409, "این خروجی هنوز آمادهٔ پذیرش نیست.")
        acceptance = workspace.accept(run_id)
        workspace.complete_project_task_for_run(run_id)
        return acceptance

    @app.get("/conversations")
    async def conversations():
        return workspace.conversations()

    @app.post("/conversations", status_code=201)
    async def create_conversation(payload: ConversationRequest):
        return workspace.create_conversation(payload.title)

    @app.get("/conversations/{ident}")
    async def conversation(ident: str):
        record = workspace.get_conversation(ident)
        if not record:
            raise HTTPException(404, "گفت‌وگو پیدا نشد.")
        return {**record, "runs": [detail(r) for r in workspace.conversation_run_ids(ident)]}

    @app.patch("/conversations/{ident}")
    async def update_conversation(ident: str, payload: ConversationUpdate):
        if not workspace.get_conversation(ident):
            raise HTTPException(404, "گفت‌وگو پیدا نشد.")
        return workspace.update_conversation(ident, **payload.model_dump())

    @app.get("/memories")
    async def memories(q: str = "",project_id: str | None=None,include_global: bool=False):
        return workspace.memories(q,project_id,include_global)

    @app.post("/memories", status_code=201)
    async def add_memory(payload: MemoryRequest):
        return workspace.save_memory(**payload.model_dump())

    @app.put("/memories/{ident}")
    async def edit_memory(ident: str, payload: MemoryRequest):
        try:
            return workspace.save_memory(**payload.model_dump(), ident=ident)
        except KeyError:
            raise HTTPException(404, "یادداشت پیدا نشد.")

    @app.delete("/memories/{ident}")
    async def remove_memory(ident: str):
        if not workspace.delete_memory(ident):
            raise HTTPException(404, "یادداشت پیدا نشد.")
        return {"deleted": True}

    # ==================== Projects & Tasks Endpoints ====================

    @app.get("/projects")
    async def list_projects(archived: bool = False):
        return workspace.projects(include_archived=archived)

    @app.post("/projects", status_code=201)
    async def create_project(payload: ProjectCreate):
        return workspace.create_project(
            name=payload.name,
            path=payload.path,
            description=payload.description,
            default_criteria=payload.default_criteria,
            default_budget=payload.default_budget
        )

    @app.get("/projects/{ident}")
    async def get_project(ident: str):
        proj = workspace.get_project(ident)
        if not proj:
            raise HTTPException(404, "پروژه پیدا نشد.")
        folder_info = inspect_folder(proj["path"])
        tasks = workspace.project_tasks(ident)
        return {**proj, "folder": folder_info, "tasks": tasks}

    @app.patch("/projects/{ident}")
    async def update_project(ident: str, payload: ProjectUpdate):
        proj = workspace.update_project(ident, **payload.model_dump(exclude_unset=True))
        if not proj:
            raise HTTPException(404, "پروژه پیدا نشد.")
        return proj

    @app.delete("/projects/{ident}")
    async def delete_project(ident: str):
        if not workspace.delete_project(ident):
            raise HTTPException(404, "پروژه پیدا نشد.")
        return {"deleted": True}

    @app.get("/projects/{ident}/tasks")
    async def list_project_tasks(ident: str):
        if not workspace.get_project(ident):
            raise HTTPException(404, "پروژه پیدا نشد.")
        return workspace.project_tasks(ident)

    @app.post("/projects/{ident}/tasks", status_code=201)
    async def add_project_task(ident: str, payload: ProjectTaskCreate):
        if not workspace.get_project(ident):
            raise HTTPException(404, "پروژه پیدا نشد.")
        criteria = payload.acceptance_criteria
        if isinstance(criteria, str):
            criteria = [c.strip() for c in criteria.split("\n") if c.strip()]
        return workspace.create_project_task(
            project_id=ident,
            title=payload.title,
            objective=payload.objective,
            acceptance_criteria=criteria,
            budget_cap_usd=payload.budget_cap_usd,
            priority=payload.priority,
            workflow=payload.workflow
        )

    @app.get("/projects/{ident}/tasks/{task_id}")
    async def get_project_task(ident: str, task_id: str):
        task = workspace.get_project_task(task_id)
        if not task or task["project_id"] != ident:
            raise HTTPException(404, "تسک پیدا نشد.")
        return task

    @app.patch("/projects/{ident}/tasks/{task_id}")
    async def update_project_task(ident: str, task_id: str, payload: ProjectTaskUpdate):
        task = workspace.get_project_task(task_id)
        if not task or task["project_id"] != ident:
            raise HTTPException(404, "تسک پیدا نشد.")
        data = payload.model_dump(exclude_unset=True)
        if "acceptance_criteria" in data and isinstance(data["acceptance_criteria"], str):
            data["acceptance_criteria"] = [c.strip() for c in data["acceptance_criteria"].split("\n") if c.strip()]
        updated = workspace.update_project_task(task_id, **data)
        return updated

    @app.delete("/projects/{ident}/tasks/{task_id}")
    async def delete_project_task(ident: str, task_id: str):
        task = workspace.get_project_task(task_id)
        if not task or task["project_id"] != ident:
            raise HTTPException(404, "تسک پیدا نشد.")
        workspace.delete_project_task(task_id)
        return {"deleted": True}

    @app.post("/projects/{ident}/tasks/{task_id}/run")
    async def run_project_task(ident: str, task_id: str):
        proj = workspace.get_project(ident)
        if not proj:
            raise HTTPException(404, "پروژه پیدا نشد.")
        task_rec = workspace.get_project_task(task_id)
        if not task_rec or task_rec["project_id"] != ident:
            raise HTTPException(404, "تسک پیدا نشد.")

        # Build context from project folder
        context = []
        snapshot = build_project_context(proj)
        if snapshot:
            context.append(snapshot)

        # Memory context if available
        context.extend(workspace.retrieve(task_rec["objective"],project_id=proj['id'],criteria=task_rec['acceptance_criteria']))

        run_task_id = f"pt_{task_id[:8]}_{uuid.uuid4().hex[:6]}"
        criteria = task_rec["acceptance_criteria"]
        if not criteria:
            criteria = ["تکمیل وظیفه با دقت و گزارش شفاف مراحل انجام‌شده."]

        task_payload = {
            "task_id": run_task_id,
            "root_id": run_task_id,
            "project_id": proj["id"],
            "human_owner": "Me",
            "objective": task_rec["objective"],
            "scope": [f"انجام تسک در پوشهٔ پروژهٔ {proj['name']}"],
            "out_of_scope": ["تغییرات خارج از محدودهٔ تعریف‌شده"],
            "acceptance_criteria": criteria,
            "dependencies": [],
            "allowed_tools": [],
            "allowed_paths": [proj["path"]],
            "artifact_refs": [],
            "budget_cap_usd": task_rec["budget_cap_usd"],
            "context": context,
            "workflow": task_rec["workflow"],
            "priority": task_rec["priority"],
            "data_class": "internal"
        }

        # Create linked conversation for visibility in chat
        chat = workspace.create_conversation(f"{proj['name']} · {task_rec['title']}")
        run_id, _ = engine.submit_run(task_payload)
        workspace.link_run(chat["id"], run_id)
        workspace.update_project_task(task_id, status="RUNNING", last_run_id=run_id)

        # Execute in background
        jobs[run_id] = asyncio.create_task(execute(run_id, project_task_id=task_id))
        return {
            "task_id": task_id,
            "run_id": run_id,
            "conversation_id": chat["id"],
            "status": "RUNNING"
        }

    @app.get("/filesystem/validate-path")
    async def validate_filesystem_path(path: str = Query(..., min_length=1)):
        return inspect_folder(path)

    @app.post("/filesystem/open-folder")
    async def open_filesystem_folder(payload: OpenFolderRequest):
        p = Path(payload.path).expanduser().resolve()
        if not p.exists():
            raise HTTPException(404, "پوشه پیدا نشد.")
        if sys.platform == "win32":
            subprocess.Popen(["explorer.exe", str(p)])
        else:
            import webbrowser
            webbrowser.open(p.as_uri())
        return {"opened": True, "path": str(p)}

    @app.post("/filesystem/pick-folder")
    async def pick_filesystem_folder():
        """Opens the Windows folder dialog on this machine; returns an empty path when cancelled."""
        if sys.platform != "win32":
            raise HTTPException(501, "انتخاب پوشه فقط در ویندوز در دسترس است؛ مسیر را دستی وارد کنید.")
        script = ("Add-Type -AssemblyName System.Windows.Forms;"
                  "$o=New-Object System.Windows.Forms.Form -Property @{TopMost=$true;ShowInTaskbar=$false};"
                  "$d=New-Object System.Windows.Forms.FolderBrowserDialog;$d.Description='پوشهٔ پروژه را انتخاب کن';"
                  "$d.ShowNewFolderButton=$false;"
                  "if($d.ShowDialog($o) -eq 'OK'){[Console]::OutputEncoding=[Text.Encoding]::UTF8;[Console]::Write($d.SelectedPath)}")
        def run():
            done = subprocess.run(["powershell", "-NoProfile", "-STA", "-Command", script], capture_output=True,
                                  timeout=600, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            return done.stdout.decode("utf-8", "replace").strip()
        try:
            path = await asyncio.to_thread(run)
        except subprocess.TimeoutExpired:
            path = ""
        return {"path": path}

    # ==================== End Projects & Tasks ====================

    ROLE_PROVIDERS = {"codex", "claude", "gapcode", "gemini", "antigravity", "deepseek-web", "gemini-web", "notebooklm"}

    def clean_role_models(raw):
        if not isinstance(raw, dict) or len(raw) > 30:
            raise ValueError("Role assignments must be an object with at most 30 roles.")
        out = {}
        for role, value in raw.items():
            if not re.fullmatch(r"[a-z0-9_-]{1,40}", str(role)):
                raise ValueError("Role id is invalid.")
            if not isinstance(value, dict) or value.get("provider") not in ROLE_PROVIDERS:
                raise ValueError("Role account is not supported.")
            model = str(value.get("model", "")).strip()
            if not re.fullmatch(r"[A-Za-z0-9_.:/\-\[\]]{0,100}", model):
                raise ValueError("Model id has unsupported characters.")
            out[role] = {"provider": value["provider"], "model": model}
        return out

    @app.get("/roles/models")
    async def get_role_models():
        return {"roles": workspace.preferences().get("role_models", {})}

    @app.put("/roles/models")
    async def put_role_models(payload: dict):
        roles = clean_role_models(payload.get("roles"))
        workspace.save_preferences({"role_models": roles})
        return {"roles": roles}

    @app.get("/preferences")
    async def preferences():
        return workspace.preferences()

    @app.put("/preferences")
    async def save_preferences(payload: PreferencesRequest):
        return workspace.save_preferences(payload.model_dump())

    @app.get("/usage")
    async def all_usage():
        return {**workspace.usage(), "demo": isinstance(engine.provider, FakeProvider)}

    @app.get("/settings/agents")
    async def agent_settings():
        return engine.get_agent_settings().model_dump()

    @app.put("/settings/agents")
    async def save_agents(payload: AgentSettings):
        return engine.save_agent_settings(payload).model_dump()

    @app.get("/models/status")
    async def models():
        fake = isinstance(engine.provider, FakeProvider)
        return {"provider_type": type(engine.provider).__name__, "demo": fake,
                "profiles": {name: profile.models for name, profile in PROFILES.items()},
                "has_api_key": False, "masked_key": "",
                "models": {mid: {"pricing": {"input_per_million_usd": price.input_per_million,
                    "output_per_million_usd": price.output_per_million},
                    "status": "demo" if fake else "active", "pricing_verified": not fake}
                    for mid, price in MODEL_PRICES.items()}}

    return app


class LazyApplication:
    """Importing the API for offline tests must not open the user's default DB."""
    def __init__(self):self.instance=None

    async def __call__(self,scope,receive,send):
        if self.instance is None:self.instance=create_app()
        await self.instance(scope,receive,send)


app = LazyApplication()
