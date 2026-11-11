"""End-to-end tests for the 6 open-source parallel orchestration capabilities:
1. Full environment isolation (worktrees, dynamic ports, shared dep junctions/symlinks, ephemeral DBs)
2. Proactive conflict prevention (AST symbol overlap, merge-tree conflict, runtime deferral & auto-resume)
3. Shared git-backed cross-agent memory (refs/flux/memory, capture, approval, prompt injection)
4. Attention inbox prioritization, unblocking & Diff Chapters
5. Gated DAG task pipelines (retry on gate failure, gated commit handoff, failure blocking, planner)
6. Headless daemon auth, SSE/WebSocket events, CLI ctl & Apache-2.0 license
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from starlette.testclient import TestClient

from flux.api.app import create_app
from flux.engine.orchestrator import FluxEngine
from flux.local_agents import runtime as runtime_mod
from flux.local_agents.runtime import ChatSpec, TurnSpec
from flux.parallel.gitops import GIT_IDENTITY, git
from flux.parallel.pipelines import PipelineSpec
from flux.providers.fake import FakeProvider
from flux.storage.database import init_db
from flux.storage.repository import Repository


def init_git_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    git(path, "init", "-b", "main")
    (path / "package.json").write_text('{"name":"demo","version":"1.0.0"}\n', encoding="utf-8")
    (path / "package-lock.json").write_text('{"name":"demo","lockfileVersion":3}\n', encoding="utf-8")
    (path / "src").mkdir()
    (path / "src" / "billing.py").write_text(
        "def compute_tax(amount: int) -> int:\n"
        "    return int(amount * 10 // 100)\n\n\n"
        "def format_invoice(total: int) -> str:\n"
        "    return f'USD {total}'\n",
        encoding="utf-8",
    )
    git(path, "add", "-A")
    git(path, "commit", "-m", "initial", env=GIT_IDENTITY)
    # Untracked heavy dependency dir + local .env in main checkout
    nm = path / "node_modules" / "pkg"
    nm.mkdir(parents=True)
    (nm / "index.js").write_text("module.exports = 42;\n", encoding="utf-8")
    (path / ".env").write_text("APP_SECRET_LOCAL=dev_mode\n", encoding="utf-8")
    return path


@pytest.fixture
def parallel_env(tmp_path, monkeypatch):
    monkeypatch.setenv("FLUX_WORKTREE_ROOT", str(tmp_path / "wt_root"))
    monkeypatch.delenv("FLUX_API_TOKEN", raising=False)
    repo_dir = init_git_repo(tmp_path / "sample_repo")
    db = Repository(init_db(":memory:"))
    app = create_app(FluxEngine(db, FakeProvider()))
    runtime = app.state.local_runtime
    hub = app.state.parallel

    async def fake_status(refresh=False):
        return {"providers": [{"id": p, "authenticated": True} for p in ("codex", "claude")]}

    monkeypatch.setattr(runtime, "status", fake_status)
    monkeypatch.setattr(runtime_mod, "find_cli", lambda _: sys.executable)

    agent_script = tmp_path / "mock_agent.py"
    agent_script.write_text(
        '''import json, os, pathlib, sys, time
prompt = sys.stdin.buffer.read().decode("utf-8")
cwd = pathlib.Path.cwd()
print(json.dumps({"type": "thread.started", "thread_id": "sess-" + str(os.getpid())}), flush=True)

if "SLEEP_UNTIL_FILE:" in prompt:
    marker = prompt.split("SLEEP_UNTIL_FILE:", 1)[1].splitlines()[0].strip()
    deadline = time.time() + 15
    while time.time() < deadline and not pathlib.Path(marker).exists():
        time.sleep(0.03)

if "BLOCK_FOR_APPROVAL" in prompt:
    print(json.dumps({"type": "turn.failed", "error": {"code": "approval_required", "message": "نیاز به تأیید اجرای فرمان خطرناک"}}), flush=True)
    sys.exit(1)

if "WRITE_ENV_DUMP" in prompt:
    (cwd / "seen_env.json").write_text(json.dumps({
        "PORT": os.environ.get("PORT"),
        "DATABASE_URL": os.environ.get("DATABASE_URL"),
        "PROMPT": prompt,
    }, ensure_ascii=False), encoding="utf-8")

if "EMIT_MEMORY" in prompt:
    reply = 'انجام شد.\\n<flux-memory kind="convention" title="استاندارد تست مالیات">همیشه تابع compute_tax را با اعداد صحیح تست کنید.</flux-memory>'
elif "PLAN_PIPELINE" in prompt or "You are the orchestrator." in prompt:
    reply = json.dumps({
        "name": "planned-dag",
        "steps": [
            {"id": "step1", "title": "گام اول", "prompt": "کاری کن", "depends_on": [], "gates": []},
            {"id": "step2", "title": "گام دوم", "prompt": "ادامه بده", "depends_on": ["step1"], "gates": []}
        ]
    }, ensure_ascii=False)
elif "PIPE_STEP_A" in prompt:
    # Fail gate on first attempt, fix on retry!
    val = 42 if "gate `" in prompt else 0
    (cwd / "feature_a.py").write_text(f"VALUE = {val}\\n", encoding="utf-8")
    reply = f"wrote VALUE={val}"
elif "PIPE_STEP_B" in prompt:
    sys.path.insert(0, str(cwd))
    import feature_a
    (cwd / "feature_b.py").write_text(f"DOUBLED = {feature_a.VALUE * 2}\\n", encoding="utf-8")
    reply = "built on step A"
else:
    reply = "پاسخ موفق"

print(json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": reply}}), flush=True)
print(json.dumps({"type": "turn.completed", "usage": {"input_tokens": 10, "output_tokens": 5}}), flush=True)
''',
        encoding="utf-8",
    )
    monkeypatch.setattr(runtime_mod, "command_for", lambda c, e: [sys.executable, "-u", str(agent_script)])
    project = app.state.workspace.create_project("Sample Repo", str(repo_dir))
    yield app, hub, runtime, project, repo_dir, tmp_path
    db.conn.close()


# ---------------------------------------------------------------------------
# 1. Full Environment Isolation (Ports, Junction/Symlink Deps, Ephemeral DBs)
# ---------------------------------------------------------------------------
def test_worktree_full_isolation_ports_links_and_ephemeral_postgres(parallel_env):
    app, hub, runtime, project, repo_dir, tmp_path = parallel_env
    wt1 = hub.worktrees.create(project["id"], name="agent-one", scope=["src/auth/"])
    wt2 = hub.worktrees.create(project["id"], name="agent-two", scope=["src/billing.py"])

    # Dynamic unique ports across worktrees
    assert set(wt1["ports"]) >= {"PORT", "API_PORT", "VITE_PORT", "E2E_PORT"}
    assert set(wt1["ports"].values()).isdisjoint(set(wt2["ports"].values()))

    # Isolated SQLite DB & Compose project per worktree
    assert wt1["env"]["DATABASE_URL"] != wt2["env"]["DATABASE_URL"]
    assert wt1["env"]["COMPOSE_PROJECT_NAME"] != wt2["env"]["COMPOSE_PROJECT_NAME"]
    assert (Path(wt1["path"]) / ".env").read_text(encoding="utf-8") == "APP_SECRET_LOCAL=dev_mode\n"

    # Shared node_modules linked (not copied), readable inside worktree
    nm_statuses = {l["name"]: l["status"] for l in wt1["links"]}
    assert nm_statuses.get("node_modules") == "linked"
    assert (Path(wt1["path"]) / "node_modules" / "pkg" / "index.js").is_file()
    assert hub.worktrees.link_health(wt1["id"]) == []

    # Diverging lockfile is flagged by link_health, and unshare detaches without touching main
    (Path(wt1["path"]) / "package-lock.json").write_text('{"name":"demo","lockfileVersion":3,"changed":true}\n', encoding="utf-8")
    assert hub.worktrees.link_health(wt1["id"])[0]["name"] == "node_modules"
    hub.worktrees.unshare(wt1["id"], "node_modules")
    assert not (Path(wt1["path"]) / "node_modules").exists()
    assert (repo_dir / "node_modules" / "pkg" / "index.js").is_file()  # main checkout untouched!

    # Optional Docker Postgres ephemeral container support
    started, removed = [], []

    class FakeDocker:
        def available(self):
            return True

        def run_postgres(self, name, image, port, password):
            started.append((name, image, port))
            return "cid-123"

        def remove(self, name):
            removed.append(name)

    cfg_dir = repo_dir / ".flux"
    cfg_dir.mkdir(exist_ok=True)
    (cfg_dir / "flux.json").write_text('{"isolation":{"database":"postgres"}}', encoding="utf-8")
    hub.worktrees.docker = FakeDocker()
    wt_pg = hub.worktrees.create(project["id"], name="pg-agent")
    assert wt_pg["env"]["DATABASE_URL"].startswith("postgresql://postgres:")
    assert len(started) == 1
    hub.worktrees.remove(wt_pg["id"], delete_branch=True)
    assert removed == [started[0][0]]

    # Removing wt2 keeps shared main node_modules completely intact
    hub.worktrees.remove(wt2["id"], delete_branch=True)
    assert (repo_dir / "node_modules" / "pkg" / "index.js").is_file()


# ---------------------------------------------------------------------------
# 2. Proactive Conflict Prevention & Runtime Deferral / Auto-Resume
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_proactive_overlap_detection_and_runtime_deferral(parallel_env):
    app, hub, runtime, project, repo_dir, tmp_path = parallel_env
    wt_a = hub.worktrees.create(project["id"], name="worker-a")
    wt_b = hub.worktrees.create(project["id"], name="worker-b")
    wt_c = hub.worktrees.create(project["id"], name="worker-c")

    # Worker A modifies compute_tax; Worker C modifies format_invoice (same file, different function)
    (Path(wt_a["path"]) / "src" / "billing.py").write_text(
        "def compute_tax(amount: int) -> int:\n"
        "    return int(amount * 15 // 100)\n\n\n"
        "def format_invoice(total: int) -> str:\n"
        "    return f'USD {total}'\n",
        encoding="utf-8",
    )
    (Path(wt_c["path"]) / "src" / "billing.py").write_text(
        "def compute_tax(amount: int) -> int:\n"
        "    return int(amount * 10 // 100)\n\n\n"
        "def format_invoice(total: int) -> str:\n"
        "    return f'EUR {total}'\n",
        encoding="utf-8",
    )
    # Different symbols in same file => level == "file"
    overlaps_ac = hub.coordinator.check(wt_a["id"], against_active_only=False)
    assert any(o["other"] == wt_c["id"] and o["level"] == "file" for o in overlaps_ac)

    # Worker B also modifies compute_tax => AST symbol overlap + merge-tree conflict!
    (Path(wt_b["path"]) / "src" / "billing.py").write_text(
        "def compute_tax(amount: int) -> int:\n"
        "    return int(amount * 20 // 100)\n\n\n"
        "def format_invoice(total: int) -> str:\n"
        "    return f'USD {total}'\n",
        encoding="utf-8",
    )
    overlaps_ab = [o for o in hub.coordinator.check(wt_b["id"], against_active_only=False) if o["other"] == wt_a["id"]]
    assert overlaps_ab and overlaps_ab[0]["level"] in {"symbol", "conflict"}

    # Live deferral: while Worker A is running, Worker B is automatically deferred, while Worker C runs in parallel!
    release_file = tmp_path / "release_a.flag"
    chat_a = runtime.create_chat(ChatSpec(cwd=wt_a["path"], worktree_id=wt_a["id"]))
    chat_b = runtime.create_chat(ChatSpec(cwd=wt_b["path"], worktree_id=wt_b["id"]))
    chat_c = runtime.create_chat(ChatSpec(cwd=wt_c["path"], worktree_id=wt_c["id"]))

    turn_a = runtime.submit(chat_a["id"], TurnSpec(prompt=f"SLEEP_UNTIL_FILE:{release_file}", request_key="ta"))
    turn_c = runtime.submit(chat_c["id"], TurnSpec(prompt="WRITE_ENV_DUMP", request_key="tc"))
    turn_b = runtime.submit(chat_b["id"], TurnSpec(prompt="update compute_tax", request_key="tb"))

    assert turn_b["state"] == "deferred"
    assert turn_b["hold"]["action"] == "defer"
    # Worker C does NOT conflict on symbol/conflict, so it finishes in parallel while A is still asleep!
    await asyncio.wait_for(runtime.jobs[turn_c["id"]], 10)
    assert runtime.turn(turn_c["id"])["state"] == "completed"
    seen_c = json.loads((Path(wt_c["path"]) / "seen_env.json").read_text(encoding="utf-8"))
    assert seen_c["PORT"] == str(wt_c["ports"]["PORT"])

    # Revert conflicting edit in A before A finishes so B's hold clears when A completes
    git(wt_a["path"], "checkout", "--", "src/billing.py")
    release_file.write_text("go", encoding="utf-8")
    await asyncio.wait_for(runtime.jobs[turn_a["id"]], 10)

    # Wait for B to auto-resume and complete
    for _ in range(100):
        if runtime.turn(turn_b["id"])["state"] == "completed":
            break
        await asyncio.sleep(0.05)
    assert runtime.turn(turn_b["id"])["state"] == "completed"


# ---------------------------------------------------------------------------
# 3 & 4. Shared Git Memory + Attention Inbox Priority + Diff Chapters + UI
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_shared_git_memory_attention_priority_and_diff_chapters(parallel_env):
    app, hub, runtime, project, repo_dir, tmp_path = parallel_env
    wt1 = hub.worktrees.create(project["id"], name="mem-writer")
    wt2 = hub.worktrees.create(project["id"], name="mem-reader")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Agent 1 emits a <flux-memory> lesson -> captured as proposed + inbox item
        c1 = (await client.post(f"/api/parallel/worktrees/{wt1['id']}/chats", json={"provider": "codex"})).json()
        t1 = (await client.post(f"/api/local/chats/{c1['id']}/turns", json={"prompt": "EMIT_MEMORY", "request_key": "m1"})).json()
        await asyncio.wait_for(runtime.jobs[t1["id"]], 10)

        # Working tree of repo_dir and wt1 have NO memory files (stored cleanly in refs/flux/memory)
        assert git(repo_dir, "status", "--porcelain", "--untracked-files=no").strip() == ""
        wiki_data = (await client.get(f"/api/parallel/projects/{project['id']}/wiki")).json()
        assert len(wiki_data["entries"]) == 1 and wiki_data["entries"][0]["status"] == "proposed"

        # Agent 2 gets blocked on approval -> P0 'blocked' item rises to the VERY TOP of Attention Inbox!
        c2 = (await client.post(f"/api/parallel/worktrees/{wt2['id']}/chats", json={"provider": "codex"})).json()
        t2 = (await client.post(f"/api/local/chats/{c2['id']}/turns", json={"prompt": "BLOCK_FOR_APPROVAL", "request_key": "b1"})).json()
        await asyncio.wait_for(runtime.jobs[t2["id"]], 10)
        assert runtime.turn(t2["id"])["state"] == "needs_input"

        inbox = (await client.get("/api/parallel/attention")).json()["items"]
        assert inbox[0]["priority"] == 0 and inbox[0]["label"] == "blocked" and inbox[0]["chat_id"] == c2["id"]
        mem_item = next(i for i in inbox if i["kind"] == "memory")

        # Approve memory via inbox endpoint -> becomes verified & injected into next agent turn!
        approved = await client.post(f"/api/parallel/attention/{mem_item['id']}/approve-memory")
        assert approved.status_code == 200 and approved.json()["status"] == "verified"

        # Unblock Agent 2 by sending a new turn (simulating quick-reply from Attention Inbox) -> also receives shared memory!
        t2_unblock = (await client.post(f"/api/local/chats/{c2['id']}/turns", json={
            "prompt": "WRITE_ENV_DUMP درباره compute_tax و مالیات", "request_key": "b2"
        })).json()
        await asyncio.wait_for(runtime.jobs[t2_unblock["id"]], 10)
        dumped = json.loads((Path(wt2["path"]) / "seen_env.json").read_text(encoding="utf-8"))
        assert "استاندارد تست مالیات" in dumped["PROMPT"]

        # Diff Chapters: create changes across schema, contracts, source, tests & docs and verify ordering
        wpath = Path(wt1["path"])
        (wpath / "db").mkdir()
        (wpath / "db" / "001_init.sql").write_text("CREATE TABLE orders(id INT);\n", encoding="utf-8")
        (wpath / "src" / "api").mkdir(parents=True)
        (wpath / "src" / "api" / "routes.py").write_text("ROUTES = ['/orders']\n", encoding="utf-8")
        (wpath / "src" / "billing.py").write_text("def compute_tax(amount: int) -> int:\n    return 0\n", encoding="utf-8")
        (wpath / "tests").mkdir()
        (wpath / "tests" / "test_orders.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
        (wpath / "docs").mkdir()
        (wpath / "docs" / "guide.md").write_text("# Orders\n", encoding="utf-8")

        chapters = (await client.get(f"/api/parallel/worktrees/{wt1['id']}/chapters")).json()
        keys = [c["key"] for c in chapters["chapters"]]
        assert keys == ["data", "contracts", "source", "tests", "docs"]
        assert chapters["files"] >= 5 and chapters["added"] > 0

        # Standalone /attention UI & CSP check
        ui = await client.get("/attention")
        assert ui.status_code == 200
        assert "script-src 'self';" in ui.headers["content-security-policy"]
        assert "/static/native.js" in ui.text and "/static/attention.js" in ui.text
        js_text = (await client.get("/static/attention.js")).text
        assert "innerHTML" not in js_text


# ---------------------------------------------------------------------------
# 5. Structured Gated DAG Task Pipelines & Orchestrator Plan
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_dag_pipeline_gates_retry_handoff_and_planner(parallel_env):
    app, hub, runtime, project, repo_dir, tmp_path = parallel_env

    # Reject cyclic graphs
    with pytest.raises(ValueError):
        PipelineSpec(
            name="cyclic",
            project_id=project["id"],
            steps=[
                {"id": "a", "prompt": "x", "depends_on": ["b"]},
                {"id": "b", "prompt": "y", "depends_on": ["a"]},
            ],
        )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Orchestrator AI plan endpoint
        planned = await client.post("/api/parallel/pipelines/plan", json={
            "project_id": project["id"], "objective": "PLAN_PIPELINE", "provider": "codex"
        })
        assert planned.status_code == 200
        assert [s["id"] for s in planned.json()["spec"]["steps"]] == ["step1", "step2"]

        # Gated DAG: step 'a' fails its gate on attempt 1, retries & fixes on attempt 2, commits,
        # then step 'b' branches from 'a's gated commit and verifies feature_a.VALUE == 42!
        created = await client.post("/api/parallel/pipelines?start=true", json={
            "name": "gated-release",
            "project_id": project["id"],
            "steps": [
                {
                    "id": "a",
                    "title": "Build feature A",
                    "prompt": "PIPE_STEP_A",
                    "max_attempts": 2,
                    "gates": [{"name": "verify-a", "run": 'python -c "import feature_a; assert feature_a.VALUE == 42"'}],
                },
                {
                    "id": "b",
                    "title": "Build feature B on top of A",
                    "prompt": "PIPE_STEP_B",
                    "depends_on": ["a"],
                    "gates": [{"name": "verify-b", "run": 'python -c "import feature_b; assert feature_b.DOUBLED == 84"'}],
                },
            ],
        })
        assert created.status_code == 201
        pipe_id = created.json()["id"]

        for _ in range(200):
            pipe = (await client.get(f"/api/parallel/pipelines/{pipe_id}")).json()
            if pipe["state"] in {"completed", "failed"}:
                break
            await asyncio.sleep(0.05)

        assert pipe["state"] == "completed", pipe
        steps = {s["id"]: s for s in pipe["steps"]}
        assert steps["a"]["attempt"] == 2 and steps["a"]["state"] == "passed" and steps["a"]["commit_sha"]
        assert steps["b"]["state"] == "passed" and steps["b"]["gate_results"][0]["passed"] is True


# ---------------------------------------------------------------------------
# 6. Headless Daemon Auth, WebSocket Events, CLI & Apache-2.0 License
# ---------------------------------------------------------------------------
def test_headless_daemon_token_auth_websocket_cli_and_apache_license(parallel_env, monkeypatch):
    app, hub, runtime, project, repo_dir, tmp_path = parallel_env
    root = Path(__file__).resolve().parent.parent

    # Apache-2.0 license & pyproject metadata
    license_text = (root / "LICENSE").read_text(encoding="utf-8")
    assert "Apache License" in license_text and "Version 2.0" in license_text
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert 'Apache-2.0' in pyproject and 'flux = "flux.cli:main"' in pyproject

    # Refuses non-loopback daemon bind without token
    from flux.cli import cmd_daemon
    import argparse
    with pytest.raises(SystemExit) as exc:
        cmd_daemon(argparse.Namespace(host="0.0.0.0", port=8040, uds=None, token=None, allow_host=[], max_parallel=None, log_level="warning"))
    assert exc.value.code == 2

    # Token protection on HTTP + WebSocket
    monkeypatch.setenv("FLUX_API_TOKEN", "top-secret-daemon-token")
    with TestClient(app) as client:
        assert client.get("/api/parallel/overview").status_code == 401
        ok = client.get("/api/parallel/overview", headers={"Authorization": "Bearer top-secret-daemon-token"})
        assert ok.status_code == 200 and ok.json()["max_parallel"] >= 1

        hub.events.publish("daemon.ping", {"ok": True})
        with client.websocket_connect("/api/parallel/ws?after=0&token=top-secret-daemon-token") as ws:
            msg = ws.receive_json()
            assert msg["sequence"] >= 1
