"""Flux Command-Line Interface (CLI)."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from flux.api.app import app, create_app
from flux.engine.orchestrator import FluxEngine
from flux.providers.fake import FakeProvider
from flux.settings import get_settings
from flux.storage.database import init_db
from flux.storage.repository import Repository


def get_configured_engine() -> FluxEngine:
    """The legacy engine runs on the offline demo provider only; real work goes through connected accounts."""
    settings = get_settings()
    conn = init_db(settings.db_path)
    repo = Repository(conn)
    return FluxEngine(repo=repo, provider=FakeProvider())


def cmd_serve(args):
    import uvicorn
    import webbrowser
    import threading
    import time

    url = f"http://{args.host}:{args.port}"

    def open_browser():
        time.sleep(0.8)
        try:
            webbrowser.open(url)
        except Exception:
            pass

    if not args.no_browser:
        threading.Thread(target=open_browser, daemon=True).start()

    print(f"Starting Flux Engine API & Claude/Codex Web UI on {url}...")
    engine = get_configured_engine()
    api_app = create_app(engine=engine)
    uvicorn.run(api_app, host=args.host, port=args.port)


def cmd_submit(args):
    path = Path(args.file)
    if not path.exists():
        print(f"Error: Task file '{args.file}' not found.", file=sys.stderr)
        sys.exit(1)

    with open(path, "r", encoding="utf-8") as f:
        task_data = json.load(f)

    engine = get_configured_engine()
    run_id, is_new = engine.submit_run(task_data, idempotency_key=args.idempotency_key)
    print(f"Run submitted: {run_id} (New={is_new})")

    if is_new and not args.no_wait:
        print("Executing run...")
        result = asyncio.run(engine.execute_run(run_id))
        print("\n--- Execution Result ---")
        print(f"Status: {result.status}")
        print(f"Summary: {result.summary}")
        print(f"Cost Spent: ${result.spent_cost_usd:.6f}")
        print(f"Total Calls: {result.total_calls}")
        if result.decision:
            print(f"Review Decision: {result.decision.decision} (Confidence={result.decision.confidence})")
    elif not is_new:
        run = engine.repo.get_run(run_id)
        print(f"Existing run found with status: {run['status'] if run else 'UNKNOWN'}")


def cmd_status(args):
    engine = get_configured_engine()
    run = engine.repo.get_run(args.run_id)
    if not run:
        print(f"Run '{args.run_id}' not found.", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(dict(run), indent=2, ensure_ascii=False))


def cmd_usage(args):
    engine = get_configured_engine()
    usage = engine.repo.get_usage_summary(args.run_id)
    print(json.dumps(usage, indent=2, ensure_ascii=False))


def cmd_events(args):
    engine = get_configured_engine()
    events = engine.repo.get_events(args.run_id)
    for ev in events:
        print(f"[{ev['sequence']}] {ev['created_at']} | {ev['from_state']} -> {ev['to_state']} | {ev['reason']}")


def cmd_daemon(args):
    """Headless daemon: the same API without UI side effects, suitable for servers and CI."""
    import os
    import uvicorn

    if args.token:
        os.environ["FLUX_API_TOKEN"] = args.token
    loopback = args.host == "localhost" or _is_loopback(args.host)
    if not args.uds and not loopback and not os.environ.get("FLUX_API_TOKEN"):
        print("Refusing to bind a non-loopback address without --token or FLUX_API_TOKEN.", file=sys.stderr)
        sys.exit(2)
    if args.allow_host:
        os.environ["FLUX_ALLOWED_HOSTS"] = ",".join(filter(None, [os.environ.get("FLUX_ALLOWED_HOSTS", ""), *args.allow_host]))
    if args.max_parallel:
        os.environ["FLUX_MAX_PARALLEL"] = str(args.max_parallel)
    engine = get_configured_engine()
    api_app = create_app(engine=engine)
    where = args.uds or f"http://{args.host}:{args.port}"
    print(f"Flux daemon listening on {where} (headless)", flush=True)
    if args.uds:
        uvicorn.run(api_app, uds=args.uds, log_level=args.log_level)
    else:
        uvicorn.run(api_app, host=args.host, port=args.port, log_level=args.log_level)


def _is_loopback(host):
    import ipaddress
    try:
        return ipaddress.ip_address(host.strip("[]")).is_loopback
    except ValueError:
        return False


def main():
    parser = argparse.ArgumentParser(description="Flux Agentic Engine CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # daemon
    p_daemon = subparsers.add_parser("daemon", help="Run the headless daemon (API + SSE + WebSocket)")
    p_daemon.add_argument("--host", default="127.0.0.1")
    p_daemon.add_argument("--port", type=int, default=8040)
    p_daemon.add_argument("--uds", help="Listen on a Unix domain socket instead of TCP (POSIX)")
    p_daemon.add_argument("--token", help="Bearer token required for every request (or FLUX_API_TOKEN)")
    p_daemon.add_argument("--allow-host", action="append", default=[], help="Extra Host header to accept")
    p_daemon.add_argument("--max-parallel", type=int, help="Maximum agents running at once in worktrees")
    p_daemon.add_argument("--log-level", default="info")
    p_daemon.set_defaults(func=cmd_daemon)

    # ctl (client for a running daemon)
    from flux.ctl import register as register_ctl
    register_ctl(subparsers)

    # serve
    p_serve = subparsers.add_parser("serve", help="Start FastAPI service")
    p_serve.add_argument("--host", default="127.0.0.1", help="Bind host")
    p_serve.add_argument("--port", type=int, default=8040, help="Bind port")
    p_serve.add_argument("--no-browser", action="store_true", help="Run service without opening a browser")
    p_serve.set_defaults(func=cmd_serve)

    # submit
    p_sub = subparsers.add_parser("submit", help="Submit and execute a task JSON file")
    p_sub.add_argument("file", help="Path to task JSON file")
    p_sub.add_argument("--idempotency-key", help="Optional idempotency key")
    p_sub.add_argument("--no-wait", action="store_true", help="Do not wait for execution to complete")
    p_sub.set_defaults(func=cmd_submit)

    # status
    p_stat = subparsers.add_parser("status", help="Get run status")
    p_stat.add_argument("run_id", help="Run ID")
    p_stat.set_defaults(func=cmd_status)

    # usage
    p_usage = subparsers.add_parser("usage", help="Get run budget usage")
    p_usage.add_argument("run_id", help="Run ID")
    p_usage.set_defaults(func=cmd_usage)

    # events
    p_ev = subparsers.add_parser("events", help="Get run transition events")
    p_ev.add_argument("run_id", help="Run ID")
    p_ev.set_defaults(func=cmd_events)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
