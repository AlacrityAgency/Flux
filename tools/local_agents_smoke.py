"""Explicit live account integration check; writes only inside a temporary workspace."""
import argparse
import asyncio
import json
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from flux.local_agents.runtime import ChatSpec, LocalRuntime, TurnSpec
from flux.storage.database import init_db
from flux.storage.repository import Repository
from flux.storage.workspace import Workspace, now


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", required=True)
    parser.add_argument("--provider", choices=["codex", "claude", "both"], default="both")
    args = parser.parse_args()
    report = {"timestamp": now(), "providers": {}}
    with tempfile.TemporaryDirectory(prefix="flux-live-check-") as folder:
        repo = Repository(init_db(str(Path(folder) / "test.db")))
        runtime = LocalRuntime(repo, Workspace(repo), timeout=180)
        report["connections"] = await runtime.status(refresh=True)
        for provider in ([args.provider] if args.provider != "both" else ["codex", "claude"]):
            root = Path(folder) / provider
            root.mkdir()
            chat = runtime.create_chat(ChatSpec(provider=provider, cwd=str(root), access="work"))
            outcomes = []
            prompts = [
                "Connection test. Use your file tools to create connection.txt in the current directory containing exactly FLUX_CONNECTION_OK. Then read it back using a tool. Reply exactly FLUX_OK. Do not modify any other file.",
                "Continue our previous connection test. Read connection.txt with a tool, verify its content is FLUX_CONNECTION_OK, and reply exactly FLUX_RESUME_OK. Do not modify any files.",
            ]
            for index, prompt in enumerate(prompts):
                turn = runtime.submit(chat["id"], TurnSpec(prompt=prompt, request_key=f"{provider}-{index}", use_memory=False))
                await runtime.jobs[turn["id"]]
                result = runtime.turn(turn["id"])
                tools = [e for e in runtime.events(turn["id"]) if e["kind"] == "tool"]
                outcomes.append({"state": result["state"], "text": result["text"], "error": result["error"],
                                 "usage": result["usage"], "tool_events": len(tools)})
                print(json.dumps({"provider": provider, "turn": index + 1, **outcomes[-1]}, ensure_ascii=False), flush=True)
                if result["state"] != "completed":
                    break
            content = (root / "connection.txt").read_text(encoding="utf-8").strip() if (root / "connection.txt").exists() else None
            report["providers"][provider] = {"turns": outcomes, "file_verified": content == "FLUX_CONNECTION_OK",
                                             "session_saved": bool(runtime.chat(chat["id"])["session_id"])}
        await runtime.close()
        repo.conn.close()
    output = Path(__file__).resolve().parents[1] / "docs/local-agents-live-check.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if not all(p["file_verified"] and len(p["turns"]) == 2 and all(t["state"] == "completed" for t in p["turns"])
               for p in report["providers"].values()):
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
