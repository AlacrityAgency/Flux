"""``flux ctl``: a thin terminal client for a running Flux daemon (HTTP + SSE).

Configure with ``--url``/``FLUX_URL`` (default http://127.0.0.1:8040) and ``--token``/``FLUX_API_TOKEN``.
"""
from __future__ import annotations

import json
import os
import sys
import time


def _client(args):
    import httpx
    headers = {"Authorization": f"Bearer {args.token}"} if args.token else {}
    transport = httpx.HTTPTransport(uds=args.uds) if getattr(args, "uds", "") else None
    return httpx.Client(base_url=args.url.rstrip("/"), headers=headers, transport=transport, timeout=httpx.Timeout(60, read=None))


def _call(args, method, path, **kw):
    with _client(args) as client:
        response = client.request(method, path, **kw)
    if response.status_code >= 400:
        try:
            detail = response.json().get("detail")
        except ValueError:
            detail = response.text
        print(f"error {response.status_code}: {detail}", file=sys.stderr)
        sys.exit(1)
    return response.json()


def _out(args, data, render=None):
    if args.json or render is None:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        render(data)


ICONS = {"blocked": "!!", "action": "! ", "warning": "~ ", "review": "? ", "info": "  "}


def _render_attention(data):
    items = data["items"] if isinstance(data, dict) else data
    if not items:
        print("Inbox empty — no agent is waiting for you.")
    for item in items:
        where = item["worktree_id"] or item["chat_id"] or item["pipeline_id"]
        print(f"{ICONS.get(item['label'], '  ')} {item['id']}  [{item['label']:<7}] {item['title']}  {where}")


def cmd_status(args):
    def render(data):
        print(f"running {data['running']}/{data['max_parallel']}  deferred {data['deferred']}  attention {data['attention']}")
        for wt in data["worktrees"]:
            ports = " ".join(f"{k}={v}" for k, v in wt["ports"].items())
            print(f"  {wt['id']}  {wt['name']:<24} {wt['branch']:<32} {ports}")
        for p in data["pipelines"][:10]:
            print(f"  {p['id']}  pipeline {p['name']} [{p['state']}]")
    _out(args, _call(args, "GET", "/api/parallel/overview"), render)


def cmd_attention(args):
    _out(args, _call(args, "GET", "/api/parallel/attention", params={"state": "all" if args.all else "open"}), _render_attention)


def cmd_resolve(args):
    _out(args, _call(args, "POST", f"/api/parallel/attention/{args.id}/resolve", params={"dismiss": args.dismiss}))


def cmd_approve(args):
    _out(args, _call(args, "POST", f"/api/parallel/attention/{args.id}/approve-memory"))


def cmd_worktree(args):
    base = "/api/parallel/worktrees"
    if args.action == "list":
        _out(args, _call(args, "GET", base, params={"project_id": args.target} if args.target else {}))
    elif args.action == "create":
        _out(args, _call(args, "POST", base, json={"project_id": args.target, "name": args.name or "", "base": args.base,
                                                     "scope": args.scope or []}))
    elif args.action == "rm":
        _out(args, _call(args, "DELETE", f"{base}/{args.target}", params={"delete_branch": args.delete_branch}))
    elif args.action == "chapters":
        def render(data):
            print(f"{data['files']} files  +{data['added']} -{data['removed']}")
            for index, chapter in enumerate(data["chapters"], 1):
                print(f"\n{index}. {chapter['title']}  (+{chapter['added']} -{chapter['removed']}, risk {chapter['risk']})")
                for f in chapter["files"]:
                    print(f"     {f['path']}  +{f['added']} -{f['removed']}")
        _out(args, _call(args, "GET", f"{base}/{args.target}/chapters", params={"patch": False}), render)
    elif args.action == "overlaps":
        def render(items):
            if not items:
                print("No overlap with other worktrees.")
            for f in items:
                print(f"[{f['level']:<8}] {f['path']}  ↔ {f['other_name']}  {', '.join(f.get('symbols') or [])}")
        _out(args, _call(args, "GET", f"{base}/{args.target}/overlaps"), render)
    elif args.action == "chat":
        _out(args, _call(args, "POST", f"{base}/{args.target}/chats", json={"provider": args.provider, "model": args.model or ""}))


def cmd_pipeline(args):
    base = "/api/parallel/pipelines"
    if args.action == "list":
        _out(args, _call(args, "GET", base))
    elif args.action == "run":
        with open(args.target, encoding="utf-8") as handle:
            spec = json.load(handle)
        _out(args, _call(args, "POST", base, params={"start": not args.no_start}, json=spec))
    elif args.action == "show":
        def render(p):
            print(f"{p['id']}  {p['name']}  [{p['state']}]  {p['error']}")
            for tier_index, tier in enumerate(p["tiers"]):
                for step in (s for s in p["steps"] if s["id"] in tier):
                    gates = " ".join(("✓" if g["passed"] else "✗") + g["name"] for g in step.get("gate_results") or [])
                    print(f"  T{tier_index} {step['id']:<14} {step.get('state', 'pending'):<10} deps={','.join(step['depends_on']) or '-'} "
                          f"wt={step.get('worktree_id') or '-'} {gates}")
        _out(args, _call(args, "GET", f"{base}/{args.target}"), render)
    elif args.action in {"cancel", "resume", "start"}:
        _out(args, _call(args, "POST", f"{base}/{args.target}/{args.action}"))
    elif args.action == "plan":
        _out(args, _call(args, "POST", f"{base}/plan", json={"project_id": args.target, "objective": args.objective,
                                                              "provider": args.provider}))


def cmd_memory(args):
    base = f"/api/parallel/projects/{args.project}/wiki"
    if args.action == "list":
        def render(data):
            for e in data["entries"]:
                pin = "*" if e.get("pinned") else " "
                print(f"{pin} {e['id']}  [{e['kind']:<10}] [{e['status']:<8}] {e['title']}")
        _out(args, _call(args, "GET", base), render)
    elif args.action == "add":
        _out(args, _call(args, "POST", base, json={"title": args.title, "body": args.body, "kind": args.kind,
                                                     "pinned": args.pinned, "status": "verified"}))


def cmd_watch(args):
    with _client(args) as client:
        with client.stream("GET", "/api/parallel/events/stream", timeout=None) as response:
            for line in response.iter_lines():
                if line.startswith("data: "):
                    item = json.loads(line[6:])
                    stamp = time.strftime("%H:%M:%S", time.localtime(item["time"]))
                    print(f"{stamp} {item['kind']:<20} {json.dumps(item['payload'], ensure_ascii=False)[:200]}", flush=True)


def cmd_top(args):
    """Live terminal board: blocked agents first, then running work."""
    try:
        while True:
            overview = _call(args, "GET", "/api/parallel/overview")
            attention = _call(args, "GET", "/api/parallel/attention")
            sys.stdout.write("\033[2J\033[H")
            print(f"Flux — running {overview['running']}/{overview['max_parallel']}  deferred {overview['deferred']}  "
                  f"{time.strftime('%H:%M:%S')}  (Ctrl+C to exit)\n")
            _render_attention(attention)
            print("\nWorktrees:")
            for wt in overview["worktrees"]:
                print(f"  {wt['name']:<24} {wt['branch']}")
            time.sleep(args.interval)
    except KeyboardInterrupt:
        pass


def cmd_repomap(args):
    data = _call(args, "GET", "/api/agentic/repomap", params={"cwd": args.cwd, "prompt": args.prompt or "", "budget_chars": args.budget})
    if args.json:
        return _out(args, data)
    print(f"Engine: {data['engine']} | Scanned: {data['files_scanned']} | Selected: {data['files_selected']} | "
          f"Token saving: {data['token_reduction_pct']}% ({data['raw_tokens_est']} -> {data['map_tokens_est']} est tokens)\n")
    print(data["map"])


def cmd_checkpoint(args):
    if args.action == "list":
        data = _call(args, "GET", "/api/agentic/checkpoints", params={"cwd": args.target} if args.target else {})
        if args.json:
            return _out(args, data)
        for cp in data["checkpoints"]:
            print(f"{cp['id']}  {cp['stage']:<18} {cp['commit_sha'][:10]}  {cp['created_at']}  files={len(cp['files_changed'])}  {cp['label']}")
    elif args.action == "create":
        _out(args, _call(args, "POST", "/api/agentic/checkpoints", json={"cwd": args.target or ".", "label": args.label or "cli checkpoint"}))
    elif args.action == "diff":
        data = _call(args, "GET", f"/api/agentic/checkpoints/{args.target}/diff")
        print(data["patch"] if not args.json else json.dumps(data, ensure_ascii=False, indent=2))
    elif args.action == "restore":
        _out(args, _call(args, "POST", f"/api/agentic/checkpoints/{args.target}/restore"))


def cmd_verify(args):
    data = _call(args, "POST", "/api/agentic/verify", json={"cwd": args.cwd, "files": args.file or [], "run_tests": not args.no_tests})
    if args.json:
        return _out(args, data)
    print(f"Passed: {data['passed']}  Failed checks: {data['failed_checks']}")
    for chk in data["checks"]:
        print(f"  [{'OK' if chk['passed'] else 'FAIL'}] {chk['stage']} ({chk['seconds']}s)")
        if chk["output"]:
            print("    " + chk["output"].replace("\n", "\n    "))


def register(subparsers):
    ctl = subparsers.add_parser("ctl", help="Control a running Flux daemon")
    ctl.add_argument("--url", default=os.environ.get("FLUX_URL", "http://127.0.0.1:8040"))
    ctl.add_argument("--uds", default=os.environ.get("FLUX_UDS", ""), help="Unix domain socket path of the daemon")
    ctl.add_argument("--token", default=os.environ.get("FLUX_API_TOKEN", ""))
    ctl.add_argument("--json", action="store_true", help="Raw JSON output")
    sub = ctl.add_subparsers(dest="ctl_command", required=True)

    sub.add_parser("status", help="Running agents, worktrees and pipelines").set_defaults(func=cmd_status)
    p = sub.add_parser("attention", help="Prioritized inbox of agents waiting for you")
    p.add_argument("--all", action="store_true")
    p.set_defaults(func=cmd_attention)
    p = sub.add_parser("resolve", help="Resolve an inbox item")
    p.add_argument("id")
    p.add_argument("--dismiss", action="store_true")
    p.set_defaults(func=cmd_resolve)
    p = sub.add_parser("approve", help="Approve a memory proposal from the inbox")
    p.add_argument("id")
    p.set_defaults(func=cmd_approve)

    p = sub.add_parser("worktree", help="Isolated worktrees")
    p.add_argument("action", choices=["list", "create", "rm", "chapters", "overlaps", "chat"])
    p.add_argument("target", nargs="?", help="project id (list/create) or worktree id")
    p.add_argument("--name")
    p.add_argument("--base", default="HEAD")
    p.add_argument("--scope", action="append", help="Declared path/glob this agent owns (repeatable)")
    p.add_argument("--delete-branch", action="store_true")
    p.add_argument("--provider", default="codex")
    p.add_argument("--model")
    p.set_defaults(func=cmd_worktree)

    p = sub.add_parser("pipeline", help="DAG pipelines")
    p.add_argument("action", choices=["list", "run", "show", "start", "cancel", "resume", "plan"])
    p.add_argument("target", nargs="?", help="spec file (run), pipeline id, or project id (plan)")
    p.add_argument("objective", nargs="?", help="objective text (plan)")
    p.add_argument("--no-start", action="store_true")
    p.add_argument("--provider", default="codex")
    p.set_defaults(func=cmd_pipeline)

    p = sub.add_parser("memory", help="Shared git-backed project memory")
    p.add_argument("action", choices=["list", "add"])
    p.add_argument("project")
    p.add_argument("--title")
    p.add_argument("--body")
    p.add_argument("--kind", default="note", choices=["convention", "decision", "pitfall", "fix", "note"])
    p.add_argument("--pinned", action="store_true")
    p.set_defaults(func=cmd_memory)

    sub.add_parser("watch", help="Stream live events").set_defaults(func=cmd_watch)
    p = sub.add_parser("top", help="Live terminal board")
    p.add_argument("--interval", type=float, default=2.0)
    p.set_defaults(func=cmd_top)

    p = sub.add_parser("repomap", help="Tree-sitter + AST structural repository map")
    p.add_argument("cwd", nargs="?", default=".")
    p.add_argument("--prompt", default="")
    p.add_argument("--budget", type=int, default=6000)
    p.set_defaults(func=cmd_repomap)

    p = sub.add_parser("checkpoint", help="Shadow Git checkpoints & instant rollback")
    p.add_argument("action", choices=["list", "create", "diff", "restore"])
    p.add_argument("target", nargs="?")
    p.add_argument("--label", default="")
    p.set_defaults(func=cmd_checkpoint)

    p = sub.add_parser("verify", help="Run compiler, linter, typechecker and targeted tests")
    p.add_argument("cwd", nargs="?", default=".")
    p.add_argument("--file", action="append")
    p.add_argument("--no-tests", action="store_true")
    p.set_defaults(func=cmd_verify)
