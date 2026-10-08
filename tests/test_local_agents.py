"""Exercise real subprocess I/O, recovery, cancellation, and provider event contracts offline."""
import asyncio
import json
import sys

import pytest
from httpx import ASGITransport, AsyncClient

from flux.api.app import create_app
from flux.engine.orchestrator import FluxEngine
from flux.providers.fake import FakeProvider
from flux.local_agents import runtime as module
from flux.local_agents.runtime import ChatSpec, TurnSpec, EventParser, command_for, cli_environment
from flux.storage.database import init_db
from flux.storage.repository import Repository


@pytest.fixture
def local_app(tmp_path, monkeypatch):
    repo = Repository(init_db(":memory:"))
    app = create_app(FluxEngine(repo, FakeProvider()))
    runtime = app.state.local_runtime
    async def status(refresh=False):
        return {"providers": [{"id": p, "authenticated": True} for p in ("codex", "claude")]}
    monkeypatch.setattr(runtime, "status", status)
    monkeypatch.setattr(module, "find_cli", lambda _: sys.executable)
    script = tmp_path / "mock_cli.py"
    script.write_text('''import json,sys,time
prompt=sys.stdin.buffer.read().decode("utf-8")
print(json.dumps({"type":"thread.started","thread_id":"session-123"}),flush=True)
if "WAIT_FOREVER" in prompt:
    time.sleep(60)
print(json.dumps({"type":"item.completed","item":{"type":"command_execution","command":"test-command","aggregated_output":"passed","status":"completed"}}),flush=True)
print(json.dumps({"type":"item.completed","item":{"type":"agent_message","text":"سلام؛ پاسخ کامل"}}),flush=True)
print(json.dumps({"type":"turn.completed","usage":{"input_tokens":12,"output_tokens":8}}),flush=True)
''', encoding="utf-8")
    monkeypatch.setattr(module, "command_for", lambda c, e: [sys.executable, "-u", str(script)])
    yield app, runtime, tmp_path
    repo.conn.close()


async def finish(runtime, ident):
    await asyncio.wait_for(runtime.jobs[ident], 10)
    return runtime.turn(ident)


@pytest.mark.asyncio
async def test_live_process_io_session_and_idempotency(local_app):
    app, runtime, root = local_app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/local/chats", json={"cwd": str(root), "provider": "codex"})
        assert response.status_code == 201
        chat_id = response.json()["id"]
        body = {"prompt": "سلام، یک پاسخ فارسی بنویس", "request_key": "same-request"}
        first = await client.post(f"/api/local/chats/{chat_id}/turns", json=body)
        assert first.status_code == 202
        ident = first.json()["id"]
        assert (await client.post(f"/api/local/chats/{chat_id}/turns", json=body)).json()["id"] == ident
        result = await finish(runtime, ident)
        assert result["state"] == "completed" and result["text"] == "سلام؛ پاسخ کامل"
        assert result["usage"]["input_tokens"] == 12
        assert runtime.chat(chat_id)["session_id"] == "session-123"
        events = (await client.get(f"/api/local/turns/{ident}/events")).json()
        assert any(e["kind"] == "tool" and e["payload"]["output"] == "passed" for e in events)
        assert (await client.get(f"/api/local/turns/{ident}/events?after={events[-1]['sequence']}")).json() == []
        conflict = await client.post(f"/api/local/chats/{chat_id}/turns", json={**body, "prompt": "different"})
        assert conflict.status_code == 422
        assert (await client.get("/chat")).status_code == 200
        assert "/static/local.js" in (await client.get("/chat")).text
        assert (await client.post("/api/local/chats", json={"cwd": str(root / 'missing')})).status_code == 422
        assert (await client.post(f"/api/local/chats/{chat_id}/turns", json={**body,"prompt":"   "})).status_code == 422
        assert (await client.get('/api/local/chats/no-such-chat')).status_code == 404
        assert (await client.post('/api/local/chats',json={"cwd":str(root)},headers={"origin":"https://evil.example"})).status_code == 403


@pytest.mark.asyncio
async def test_cancel_owned_process_and_global_serialization(local_app):
    _, runtime, root = local_app
    chat = runtime.create_chat(ChatSpec(cwd=str(root)))
    turn = runtime.submit(chat["id"], TurnSpec(prompt="WAIT_FOREVER", request_key="cancel"))
    for _ in range(100):
        if turn["id"] in runtime.processes:
            break
        await asyncio.sleep(.01)
    process = runtime.processes[turn["id"]]
    with pytest.raises(RuntimeError):
        runtime.submit(chat["id"], TurnSpec(prompt="another turn",request_key="busy"))
    other = runtime.create_chat(ChatSpec(cwd=str(root)))
    with pytest.raises(RuntimeError):
        runtime.submit(other["id"], TurnSpec(prompt="another turn",request_key="busy2"))
    cancelled = await asyncio.wait_for(runtime.cancel(turn["id"]), 5)
    assert cancelled["state"] == "cancelled" and process.poll() is not None
    assert not runtime.jobs and not runtime.processes


@pytest.mark.asyncio
async def test_timeout_and_recovery_without_replay(local_app):
    _, runtime, root = local_app
    runtime.timeout = .15
    chat = runtime.create_chat(ChatSpec(cwd=str(root)))
    turn = runtime.submit(chat["id"], TurnSpec(prompt="WAIT_FOREVER", request_key="timeout"))
    result = await finish(runtime, turn["id"])
    assert result["state"] == "failed" and "مهلت" in result["error"]
    runtime.update(turn["id"], state="running")
    runtime.recover()
    assert runtime.turn(turn["id"])["state"] == "interrupted"
    assert not runtime.jobs


@pytest.mark.asyncio
async def test_missing_auth_never_launches_cli(local_app, monkeypatch):
    _, runtime, root = local_app
    async def no_auth(refresh=False):
        return {"providers":[{"id":"codex","authenticated":False}]}
    monkeypatch.setattr(runtime,"status",no_auth)
    monkeypatch.setattr(module.subprocess,"Popen",lambda *a,**k:pytest.fail("must not launch"))
    chat=runtime.create_chat(ChatSpec(cwd=str(root)))
    turn=runtime.submit(chat["id"],TurnSpec(prompt="hello",request_key="auth"))
    result=await finish(runtime,turn["id"])
    assert result["state"] == "failed" and "ورود" in result["error"]


def test_protocol_errors_and_claude_stream():
    parser = EventParser("codex")
    parser.feed({"type":"turn.failed","error":{"message":"usage limit"}})
    assert not parser.complete and parser.error == "usage limit"
    parser = EventParser("claude")
    parser.feed({"type":"system","session_id":"claude-session"})
    parser.feed({"type":"stream_event","event":{"delta":{"type":"text_delta","text":"سلام"}}})
    parser.feed({"type":"assistant","message":{"content":[{"type":"text","text":"سلام"}]}})
    parser.feed({"type":"result","subtype":"success","result":"سلام","usage":{"input_tokens":1},"total_cost_usd":.01})
    assert parser.complete and parser.text == "سلام" and parser.session_id == "claude-session"
    assert parser.usage["cost_scope"] == "session_estimate"
    failed = EventParser("claude")
    failed.feed({"type":"result","subtype":"error_during_execution","is_error":True,"result":"auth required"})
    assert not failed.complete and failed.error == "auth required"


def test_command_scope_resume_and_account_environment(monkeypatch, tmp_path):
    chat={"provider":"codex","model":"model-name","access":"read","session_id":"exact-session"}
    args=command_for(chat,"codex.exe")
    assert args[:4] == ["codex.exe","exec","resume","exact-session"]
    assert 'sandbox_mode="read-only"' in args and args[-1] == "-"
    chat.update(provider="claude",access="work")
    args=command_for(chat,"claude.exe")
    assert "--resume" in args and "exact-session" in args and "acceptEdits" in args
    chat.update(access="read")
    args=command_for(chat,"claude.exe")
    assert args[args.index("--tools")+1] == "Read,Glob,Grep"
    monkeypatch.setenv("ANTHROPIC_API_KEY","secret")
    monkeypatch.setenv("CLAUDECODE","1")
    assert "ANTHROPIC_API_KEY" not in cli_environment("claude")
    assert "CLAUDECODE" not in cli_environment("claude")
    assert ChatSpec(cwd=str(tmp_path)).cwd == str(tmp_path.resolve())
