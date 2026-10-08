"""Model probe + catalog tests: a scripted stand-in CLI replaces GapCode, so nothing is sent to any service."""
import json
import os
import sys
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from flux.api.app import create_app
from flux.local_agents import runtime as rt

FAKE = r'''
import json, sys
args = sys.argv[1:]
if args[:1] == ["--version"]:
    print("gapcode 0.0-test"); sys.exit(0)
if args[:2] == ["login", "status"]:
    print("Logged in using an API key - sk-test***"); sys.exit(0)
prompt = sys.stdin.read()
model = args[args.index("--model") + 1] if "--model" in args else ""
open(sys.argv[0] + ".calls", "a", encoding="utf-8").write(json.dumps({"model": model, "args": args}) + "\n")
if model == "broken-model":
    print(json.dumps({"type": "turn.failed", "error": {"message": "model not found: broken-model"}})); sys.exit(1)
print(json.dumps({"type": "thread.started", "thread_id": "t1"}))
print(json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": "OK"}}))
print(json.dumps({"type": "turn.completed", "usage": {"input_tokens": 11, "output_tokens": 2}}))
'''


@pytest.fixture
def fake_gapcode(tmp_path, monkeypatch):
    script = tmp_path / "fake_gapcode.py"
    script.write_text(FAKE, encoding="utf-8")
    launcher = tmp_path / ("fake_gapcode.bat" if os.name == "nt" else "fake_gapcode.sh")
    if os.name == "nt":
        launcher.write_text(f'@echo off\r\n"{sys.executable}" "{script}" %*\r\n', encoding="utf-8")
    else:
        launcher.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n', encoding="utf-8")
        launcher.chmod(0o755)
    monkeypatch.setenv("FLUX_GAPCODE_PATH", str(launcher))
    home = tmp_path / "gapcode-home"
    home.mkdir()
    (home / "models_cache.json").write_text(json.dumps({"models": [{"slug": "gpt-6-sol"}, {"slug": "broken-model"}]}), encoding="utf-8")
    original = rt.cli_environment
    monkeypatch.setattr(rt, "cli_environment", lambda provider: {**original(provider), "GAPCODE_HOME": str(home)})
    return script


def test_gapcode_always_gets_an_explicit_model(fake_gapcode):
    chat = {"provider": "gapcode", "model": "", "access": "read", "session_id": None}
    args = rt.command_for(chat, "gapcode.exe")
    assert args[args.index("--model") + 1] == "gpt-6-sol"
    chat["model"] = "kimi-3"
    assert rt.command_for(chat, "gapcode.exe")[rt.command_for(chat, "gapcode.exe").index("--model") + 1] == "kimi-3"


def test_gemini_cli_catalog_has_current_models():
    assert {"gemini-3.5-flash", "gemini-3.1-pro-preview", "gemini-2.5-pro"} <= set(rt.GEMINI_CLI_MODELS)
    assert all(m.startswith("gemini-") for m in rt.GEMINI_CLI_MODELS)


@pytest.mark.asyncio
async def test_probe_records_success_and_failure_and_cleans_up(engine, fake_gapcode):
    app = create_app(engine=engine)
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        ok = (await client.post("/api/local/probe", json={"provider": "gapcode", "model": "gpt-6-sol"})).json()
        assert ok["ok"], ok
        assert ok["reply"] == "OK" and ok["usage"]["input_tokens"] == 11 and ok["latency_ms"] >= 0
        bad = (await client.post("/api/local/probe", json={"provider": "gapcode", "model": "broken-model"})).json()
        assert not bad["ok"] and "broken-model" in bad["error"]
        health = (await client.get("/api/local/health")).json()["results"]
        assert {(r["model"], r["ok"]) for r in health} == {("gpt-6-sol", True), ("broken-model", False)}
        assert [c for c in (await client.get("/api/local/chats?archived=all")).json() if c["title"] == "__probe__"] == []
        assert (await client.post("/api/local/probe", json={"provider": "nope", "model": ""})).status_code == 422
