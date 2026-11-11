"""End-to-end tests for the 6 Agentic Engineering capabilities (v0.7.0):
1. Smart Repo Mapping via Tree-sitter & AST (PageRank + >=70% token reduction)
2. Plan vs. Act Two-Phase Architecture (read-only guarantee + blueprint execution)
3. Automated Compiler / Linter / Test Feedback & Self-Correction Loop
4. Surgical File Edits (replace_in_file, SEARCH/REPLACE <flux-edit>, unified diff, path-jail)
5. Shadow Git Checkpoints (zero interference with project .git + 1-click rollback)
6. Context Sentinel (AGENTS.md re-injection + persistent error memory across turns)
"""
from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from flux.agentic.surgical import SurgicalEditError, apply_model_edits, apply_unified_diff, replace_in_file
from flux.api.app import create_app
from flux.engine.orchestrator import FluxEngine
from flux.local_agents import runtime as runtime_mod
from flux.providers.fake import FakeProvider
from flux.storage.database import init_db
from flux.storage.repository import Repository


def _init_sample_project(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    env = {
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "t@flux.local",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "t@flux.local",
    }
    subprocess.run(["git", "init"], cwd=str(root), check=True, capture_output=True)
    (root / "AGENTS.md").write_text(
        "# Coding Standards\n- MUST use integer cents for money calculations.\n- NEVER use float for currency.\n",
        encoding="utf-8",
    )
    pkg = root / "src" / "payments"
    pkg.mkdir(parents=True)
    padding = "\n".join(f"# Padding documentation line {i} explaining ledger settlement rules." for i in range(180))
    (pkg / "ledger.py").write_text(
        f'"""Ledger settlement core."""\n{padding}\n\n'
        "class LedgerAccount:\n"
        "    def __init__(self, owner: str, balance_cents: int = 0) -> None:\n"
        "        self.owner = owner\n"
        "        self.balance_cents = balance_cents\n\n"
        "    def deposit(self, cents: int) -> int:\n"
        "        self.balance_cents += cents\n"
        "        return self.balance_cents\n",
        encoding="utf-8",
    )
    (pkg / "service.py").write_text(
        f'"""High-level payment service."""\nfrom src.payments.ledger import LedgerAccount\n{padding}\n\n'
        "def settle_transfer(sender: LedgerAccount, receiver: LedgerAccount, cents: int) -> tuple[int, int]:\n"
        "    sender.balance_cents -= cents\n"
        "    receiver.deposit(cents)\n"
        "    return sender.balance_cents, receiver.balance_cents\n",
        encoding="utf-8",
    )
    web = root / "web"
    web.mkdir()
    (web / "checkout.ts").write_text(
        "export interface CheckoutPayload { amountCents: number; currency: string; }\n"
        + "\n".join(f"// comment line {i}" for i in range(120))
        + "\nexport function validateCheckout(p: CheckoutPayload): boolean { return p.amountCents > 0; }\n",
        encoding="utf-8",
    )
    tests_dir = root / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_service.py").write_text(
        "from src.payments.ledger import LedgerAccount\n"
        "from src.payments.service import settle_transfer\n\n"
        "def test_settle_transfer():\n"
        "    a = LedgerAccount('alice', 1000)\n"
        "    b = LedgerAccount('bob', 200)\n"
        "    assert settle_transfer(a, b, 300) == (700, 500)\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "-A"], cwd=str(root), check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.name=Test", "-c", "user.email=t@flux.local", "commit", "-m", "init"],
        cwd=str(root), check=True, capture_output=True, env={**subprocess.os.environ, **env},
    )
    return root


@pytest.fixture
def agentic_env(tmp_path, monkeypatch):
    monkeypatch.setenv("FLUX_SHADOW_ROOT", str(tmp_path / "shadow_git"))
    monkeypatch.delenv("FLUX_API_TOKEN", raising=False)
    proj_dir = _init_sample_project(tmp_path / "repo")
    db = Repository(init_db(":memory:"))
    app = create_app(FluxEngine(db, FakeProvider()))
    runtime = app.state.local_runtime
    agentic = app.state.agentic

    async def fake_status(refresh=False):
        return {"providers": [{"id": p, "authenticated": True} for p in ("codex", "claude", "gemini-api", "ollama")]}

    monkeypatch.setattr(runtime, "status", fake_status)
    monkeypatch.setattr(runtime_mod, "find_cli", lambda _: sys.executable)

    mock_cli = tmp_path / "mock_agentic_cli.py"
    mock_cli.write_text(
        '''import json, os, pathlib, sys
prompt = sys.stdin.buffer.read().decode("utf-8")
cwd = pathlib.Path.cwd()
(cwd / ".last_seen_prompt.txt").write_text(prompt, encoding="utf-8")
print(json.dumps({"type": "thread.started", "thread_id": "ag-sess-1"}), flush=True)

if "MAKE_PLAN_WITH_ROGUE_WRITE" in prompt:
    # Rogue attempt to mutate a file during Plan Mode — Flux MUST roll it back!
    (cwd / "rogue.txt").write_text("should not survive plan mode", encoding="utf-8")
    reply = """<flux-plan>
# هدف
افزودن کارمزد انتقال به `src/payments/service.py`
# سناریوهای مرزی و ریسک‌ها
- مبلغ منفی یا صفر نباید پذیرفته شود
# گام‌ها
1. بررسی امضای `settle_transfer` در `src/payments/service.py`
2. اعمال ویرایش جراحی و اجرای `tests/test_service.py`
</flux-plan>"""
elif "SELF_HEAL_DEMO" in prompt:
    if "AUTOMATED COMPILER / LINTER / TEST FEEDBACK LOOP" not in prompt:
        # First pass: introduce a bug that breaks test_settle_transfer!
        reply = """اعمال تغییر اولیه:
<flux-edit path="src/payments/service.py">
<<<<<<< SEARCH
def settle_transfer(sender: LedgerAccount, receiver: LedgerAccount, cents: int) -> tuple[int, int]:
    sender.balance_cents -= cents
    receiver.deposit(cents)
    return sender.balance_cents, receiver.balance_cents
=======
def settle_transfer(sender: LedgerAccount, receiver: LedgerAccount, cents: int) -> tuple[int, int]:
    sender.balance_cents -= (cents + 999)
    receiver.deposit(cents)
    return sender.balance_cents, receiver.balance_cents
>>>>>>> REPLACE
</flux-edit>"""
    else:
        # Self-correction pass after receiving pytest stack trace!
        reply = """خطای تست بررسی و اصلاح شد:
<flux-edit path="src/payments/service.py">
<<<<<<< SEARCH
def settle_transfer(sender: LedgerAccount, receiver: LedgerAccount, cents: int) -> tuple[int, int]:
    sender.balance_cents -= (cents + 999)
    receiver.deposit(cents)
    return sender.balance_cents, receiver.balance_cents
=======
def settle_transfer(sender: LedgerAccount, receiver: LedgerAccount, cents: int) -> tuple[int, int]:
    if cents < 0:
        raise ValueError("negative transfer")
    sender.balance_cents -= cents
    receiver.deposit(cents)
    return sender.balance_cents, receiver.balance_cents
>>>>>>> REPLACE
</flux-edit>"""
else:
    reply = "انجام شد."

print(json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": reply}}), flush=True)
print(json.dumps({"type": "turn.completed", "usage": {"input_tokens": 25, "output_tokens": 15}}), flush=True)
''',
        encoding="utf-8",
    )
    monkeypatch.setattr(runtime_mod, "command_for", lambda c, e: [sys.executable, "-u", str(mock_cli)])
    # Exclude `.last_seen_prompt.txt` from shadow git so diagnostic capture doesn't count as model edit
    (proj_dir / ".gitignore").write_text(".last_seen_prompt.txt\n", encoding="utf-8")
    subprocess.run(["git", "add", ".gitignore"], cwd=str(proj_dir), check=True, capture_output=True)
    subprocess.run(["git", "-c", "user.name=T", "-c", "user.email=t@flux.local", "commit", "-m", "ignore"], cwd=str(proj_dir), check=True, capture_output=True)
    yield app, runtime, agentic, proj_dir, tmp_path
    db.conn.close()


# ---------------------------------------------------------------------------
# 1. Tree-sitter + AST Smart Repo Mapping (>= 70% token reduction + deps)
# ---------------------------------------------------------------------------
def test_treesitter_repomap_extracts_signatures_deps_and_saves_tokens(agentic_env):
    app, runtime, agentic, proj_dir, _ = agentic_env
    rmap = agentic.repomap.build(proj_dir, prompt="settle_transfer LedgerAccount CheckoutPayload", budget_chars=2500)
    assert "tree-sitter" in rmap["engine"]
    assert "class LedgerAccount" in rmap["map"]
    assert "def settle_transfer" in rmap["map"]
    assert "validateCheckout" in rmap["map"]
    # Dependency graph resolves `from src.payments.ledger import LedgerAccount`
    assert "src/payments/ledger.py" in rmap["dependencies"].get("src/payments/service.py", [])
    # Achieves >= 70% token reduction compared to raw source files!
    assert rmap["token_reduction_pct"] >= 70.0


# ---------------------------------------------------------------------------
# 4. Surgical File Edits (replace_in_file, SEARCH/REPLACE, Unified Diff, Jail)
# ---------------------------------------------------------------------------
def test_surgical_edits_preserve_surrounding_code_and_enforce_path_jail(tmp_path):
    big_lines = [f"def helper_{i}(x: int) -> int:\n    return x + {i}\n" for i in range(250)]
    f = tmp_path / "big_module.py"
    f.write_text("\n".join(big_lines), encoding="utf-8")

    res = replace_in_file(
        tmp_path,
        "big_module.py",
        "def helper_125(x: int) -> int:\n    return x + 125",
        "def helper_125(x: int) -> int:\n    return x * 125",
    )
    assert res["changed"] is True
    assert res["token_saving_pct"] >= 95.0
    text = f.read_text(encoding="utf-8")
    assert "return x * 125" in text and "def helper_0(" in text and "def helper_249(" in text

    # Path traversal outside workspace MUST be blocked
    with pytest.raises(SurgicalEditError):
        replace_in_file(tmp_path, "../escape.py", "a", "b")

    # Unified diff patching
    subprocess.run(["git", "init"], cwd=str(tmp_path), check=True, capture_output=True)
    patch = (
        "--- a/big_module.py\n"
        "+++ b/big_module.py\n"
        "@@ -1,2 +1,2 @@\n"
        " def helper_0(x: int) -> int:\n"
        "-    return x + 0\n"
        "+    return x + 1000\n"
    )
    diff_res = apply_unified_diff(tmp_path, patch)
    assert diff_res["ok"] is True
    assert "return x + 1000" in f.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 2, 3, 5, 6. Full End-to-End: Plan Mode -> Act Mode -> Compiler/Pytest
# Self-Healing -> Context Sentinel Rules & Error Memory -> Shadow Git Rollback
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_plan_act_self_healing_shadow_checkpoints_and_sentinel(agentic_env):
    app, runtime, agentic, proj_dir, _ = agentic_env
    orig_git_head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(proj_dir), capture_output=True, text=True).stdout.strip()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # --- Phase 1: Plan Mode (strictly read-only; rogue file write is rolled back!) ---
        chat = (await client.post("/api/local/chats", json={"cwd": str(proj_dir), "provider": "codex", "mode": "plan"})).json()
        t_plan = (await client.post(f"/api/local/chats/{chat['id']}/turns", json={
            "prompt": "MAKE_PLAN_WITH_ROGUE_WRITE settle_transfer",
            "request_key": "rk-plan-1",
            "mode": "plan",
        })).json()
        await asyncio.wait_for(runtime.jobs[t_plan["id"]], 15)
        done_plan = runtime.turn(t_plan["id"])
        assert done_plan["state"] == "completed"
        assert not (proj_dir / "rogue.txt").exists(), "Plan mode MUST prevent/rollback rogue file mutations!"
        plan_id = done_plan["agentic_meta"]["plan_id"]
        plan_obj = (await client.get(f"/api/agentic/plans/{plan_id}")).json()
        assert len(plan_obj["steps"]) >= 2
        assert "src/payments/service.py" in plan_obj["target_files"]

        # Verify Context Sentinel injected AGENTS.md + Tree-sitter RepoMap into the prompt!
        seen_prompt = (proj_dir / ".last_seen_prompt.txt").read_text(encoding="utf-8")
        assert "MUST use integer cents" in seen_prompt
        assert "Repository Structural Map (Tree-sitter + AST)" in seen_prompt

        # --- Phase 2: Approve & Execute Plan in Act Mode + Self-Healing Loop! ---
        # First model pass introduces a test-breaking bug (`cents + 999`); Flux runs pytest,
        # catches the failure, feeds the stack trace back, and the model fixes it in round 1!
        t_act = (await client.post(f"/api/agentic/plans/{plan_id}/execute", json={
            "request_key": "rk-act-1",
            "prompt": "SELF_HEAL_DEMO",
        })).json()
        await asyncio.wait_for(runtime.jobs[t_act["id"]], 30)
        done_act = runtime.turn(t_act["id"])
        assert done_act["state"] == "completed"
        assert done_act["agentic_meta"]["heal_rounds"] == 1
        assert done_act["agentic_meta"]["verification"]["passed"] is True
        assert "negative transfer" in (proj_dir / "src" / "payments" / "service.py").read_text(encoding="utf-8")

        # Real project `.git` HEAD & index were NEVER polluted by Shadow Git!
        after_git_head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(proj_dir), capture_output=True, text=True).stdout.strip()
        assert after_git_head == orig_git_head

        # Context Sentinel recorded the pytest pitfall & verified self-heal lesson!
        sentinel_info = (await client.get("/api/agentic/sentinel", params={"cwd": str(proj_dir), "prompt": "settle_transfer"})).json()
        assert len(sentinel_info["lessons"]) >= 1
        assert "Past Repository Pitfalls" in sentinel_info["rendered"]

        # Next turn automatically receives the past pitfall reminder in its prompt!
        t_next = (await client.post(f"/api/local/chats/{chat['id']}/turns", json={
            "prompt": "بررسی نهایی settle_transfer",
            "request_key": "rk-next-1",
        })).json()
        await asyncio.wait_for(runtime.jobs[t_next["id"]], 15)
        next_prompt = (proj_dir / ".last_seen_prompt.txt").read_text(encoding="utf-8")
        assert "Past Repository Pitfalls" in next_prompt
        assert "MUST use integer cents" in next_prompt  # Zero Context Drift!

        # --- Shadow Git Checkpoint 1-Click Rollback ---
        cp_before = done_act["checkpoint_before"]
        assert cp_before
        cp_diff = (await client.get(f"/api/agentic/checkpoints/{cp_before}/diff")).json()
        assert "negative transfer" in cp_diff["patch"]

        restored = (await client.post(f"/api/agentic/checkpoints/{cp_before}/restore")).json()
        assert restored["restored"] is True
        assert "negative transfer" not in (proj_dir / "src" / "payments" / "service.py").read_text(encoding="utf-8")

