#!/usr/bin/env python3
"""sa: single entrypoint for the skill's gates, evidence ledger, verdict and reference search.

Run from the user's project directory (or pass --project). Examples:

  python3 <skill>/core/bin/sa.py modules
  python3 <skill>/core/bin/sa.py doctor
  python3 <skill>/core/bin/sa.py gate testing.run -- --repeat 3
  python3 <skill>/core/bin/sa.py gate ui-ux.a11y -- --url http://localhost:3000
  python3 <skill>/core/bin/sa.py verdict --require ui-ux.a11y,testing.run --format md
  python3 <skill>/core/bin/sa.py review --depth thorough --url http://localhost:3000 --url http://localhost:3000/settings
  python3 <skill>/core/bin/sa.py search "دکمه دسترس‌پذیری" --module ui-ux

Gate exit codes: 0 PASS, 1 FAIL, 2 NOT-TESTED, 3 ERROR.
Verdict and review exit codes: 0 PASSED, 1 FAILED/REJECTED, 2 gaps/stale/no evidence.
"""

import argparse
import json
import platform
import shlex
import shutil
import subprocess
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SKILL_DIR / "core" / "lib"))

import ledger  # noqa: E402
import rag  # noqa: E402
import review as review_lib  # noqa: E402
from gatekit import EXIT, run, report  # noqa: E402
from project import MODES, PROFILES, load_config  # noqa: E402

LEDGER_LOCK = threading.Lock()
STATIC_GATES = {"testing.inventory", "testing.risk", "testing.smells", "ui-ux.token-drift", "ui-ux.tokens"}


def run_static_batch(plan, meta, project, timeout, workers):
    """Finish independent read-only gates before any data-changing scenario starts."""
    eligible = [(i, st) for i, st in enumerate(plan["steps"])
                if st["kind"] != "command" and st["gate"] in STATIC_GATES
                and not st["args"] and not st["scope"]]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {i: pool.submit(run_gate, meta[st["gate"]], st["gate"], project, [],
                                  timeout, None, plan["review_id"]) for i, st in eligible}
        return {i: future.result() for i, future in futures.items()}


def load_modules():
    modules = {}
    for manifest in sorted((SKILL_DIR / "modules").glob("*/module.json")):
        data = json.loads(manifest.read_text(encoding="utf-8"))
        data["dir"] = manifest.parent
        modules[data["id"]] = data
    return modules


def gates_meta(modules):
    meta = {}
    for module in modules.values():
        for gate in module.get("gates", []):
            meta[gate["id"]] = dict(gate, module=module["id"], script_path=module["dir"] / gate["script"])
    return meta


def cmd_modules(args):
    modules = load_modules()
    if args.json:
        print(json.dumps({m: {k: v for k, v in d.items() if k != "dir"} for m, d in modules.items()}, indent=2, ensure_ascii=False))
        return 0
    for module in modules.values():
        print(f"{module['id']}: {module['description']}")
        print(f"  workflow: {Path(module['dir']).relative_to(SKILL_DIR) / module['workflow']}")
        for gate in module.get("gates", []):
            kind = " (informational)" if gate.get("kind") == "informational" else ""
            print(f"  gate {gate['id']}{kind}: {gate['description']}")
    return 0


def run_gate(gate_meta, gate_id, project, extra, timeout, scope=None, review_id=None):
    """Run one gate script, record it in the ledger, and return (result, record, duration)."""
    cmd = [sys.executable, str(gate_meta["script_path"]), "--project", str(project), "--json", *gate_meta.get("args", []), *extra]
    clock_started = time.perf_counter()
    fingerprint_before = ledger.fingerprint(project)
    before_s = time.perf_counter() - clock_started
    started = time.time()
    try:
        proc = run(cmd, project, timeout)
        try:
            result = json.loads(proc.stdout)
            if not isinstance(result, dict) or result.get("gate") != gate_id or result.get("status") not in EXIT or type(result.get("exit_code")) is not int or result["exit_code"] != EXIT[result["status"]] or proc.returncode != result["exit_code"]:
                raise ValueError("Gate identity, status and process exit must agree")
        except (ValueError, TypeError):
            result = {
                "gate": gate_id, "status": "ERROR", "exit_code": EXIT["ERROR"], "findings": [],
                "notes": ["Gate did not print a valid report consistent with its process exit."],
            }
    except (OSError, subprocess.TimeoutExpired) as exc:
        result = {"gate": gate_id, "status": "ERROR", "exit_code": EXIT["ERROR"], "findings": [],
                  "notes": [f"Gate execution did not complete ({type(exc).__name__}; budget {timeout}s)."]}
    duration = time.time() - started
    fingerprint_started = time.perf_counter()
    fingerprint_after = ledger.fingerprint(project)
    after_s = time.perf_counter() - fingerprint_started
    if fingerprint_after != fingerprint_before:
        result.setdefault("notes", []).append("Project files changed while the gate ran; this evidence is stale. Ignore generated files and re-run.")
    result["provenance"] = {"python": platform.python_version(), "platform": platform.system(),
                            "skill_version": (SKILL_DIR / "VERSION").read_text().strip(),
                            "command": cmd, "scope": scope, "fingerprint_before": fingerprint_before,
                            "fingerprint_after": fingerprint_after}
    result["timing"] = {"execution_s": round(duration, 4), "fingerprint_before_s": round(before_s, 4),
                        "fingerprint_after_s": round(after_s, 4)}
    with LEDGER_LOCK:
        record = ledger.append(project, gate_id, extra, result, duration, fingerprint_before, scope, review_id)
    return result, record, duration


def print_result(gate_id, result, record, duration, max_findings):
    label = gate_id + (f"@{record['scope']}" if record.get("scope") else "")
    print(f"{result['status']}: {label}  (run {record['run']}, {duration:.1f}s)")
    for key, value in (result.get("metrics") or {}).items():
        if not isinstance(value, (dict, list)):
            print(f"  {key}: {value}")
        elif isinstance(value, list) and value and isinstance(value[0], dict) and ("file" in value[0] or "claim" in value[0]):
            label = "file" if "file" in value[0] else "claim"
            print(f"  {key}:")
            for i, row in enumerate(value[:20], 1):
                detail = ", ".join(f"{k}={v}" for k, v in row.items() if k != label)
                print(f"    {i:2}. {row[label]}  ({detail})")
    for f in result.get("findings", [])[:max_findings]:
        suspected = "" if f.get("confidence", "verified") == "verified" else " (suspected)"
        print(f"  - [{f.get('severity')}] {f.get('rule')}{suspected}: {f.get('impact')} — {f.get('condition')}")
    hidden = len(result.get("findings", [])) - max_findings
    if hidden > 0:
        print(f"  … {hidden} more findings in {record['report']}")
    for note in result.get("notes", []):
        print(f"  note: {note}")


def resolve_project(value):
    project = Path(value).expanduser().resolve()
    if not project.is_dir():
        print(f"Project directory not found: {project}", file=sys.stderr)
        return None
    return project


def cmd_gate(args, passthrough):
    meta = gates_meta(load_modules())
    if args.gate_id not in meta:
        print(f"Unknown gate '{args.gate_id}'. Known: {', '.join(sorted(meta))}", file=sys.stderr)
        return EXIT["ERROR"]
    project = resolve_project(args.project)
    if project is None:
        return EXIT["ERROR"]
    extra = [a for a in passthrough if a != "--"]
    if "--help" in extra or "-h" in extra:
        # Help is not evidence: show the gate's options without touching the ledger.
        proc = subprocess.run([sys.executable, str(meta[args.gate_id]["script_path"]), *meta[args.gate_id].get("args", []), "--help"], capture_output=True, text=True)
        print(proc.stdout or proc.stderr)
        return 0
    result, record, duration = run_gate(meta[args.gate_id], args.gate_id, project, extra, args.timeout, args.scope)
    if args.json:
        result["ledger"] = record
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print_result(args.gate_id, result, record, duration, args.max_findings)
    return int(result.get("exit_code", EXIT["ERROR"]))


def cmd_review(args):
    review_started = time.perf_counter()
    project = resolve_project(args.project)
    if project is None:
        return EXIT["ERROR"]
    meta = gates_meta(load_modules())
    skip = [g.strip() for g in (args.skip or "").split(",") if g.strip()]
    try:
        if args.mode == "release-check" and skip:
            raise ValueError("Release checks cannot skip required gates. Correct the project profile instead.")
        plan = review_lib.build_plan(project, args.depth, args.url or [], args.sandbox or [], args.api_url,
                                     args.base, args.coverage_cmd, args.level, skip, args.doc or [], args.mode, args.profile)
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return EXIT["ERROR"]
    out = sys.stderr if args.json else sys.stdout

    print(f"Review plan — depth {plan['depth']}, layers: {', '.join(plan['layers']) or 'unknown'}, shape: {plan['shape']}", file=out)
    for i, st in enumerate(plan["steps"], 1):
        label = st["gate"] + (f"@{st['scope']}" if st["scope"] else "")
        print(f"  {i:2}. {label:<34} {st['why']}", file=out)
    print(f"  required for the verdict: {', '.join(plan['required'])}", file=out)
    for hint in plan.get("hints", []):
        print(f"  hint: {hint}", file=out)
    if args.dry_run:
        if args.json:
            print(json.dumps({"plan": _plan_json(plan)}, indent=2, ensure_ascii=False))
        return 0

    plan["review_id"] = uuid.uuid4().hex
    import discovery
    map_started = time.perf_counter()
    project_map = discovery.build_map(project)
    map_path = project / ".superagent" / "project-map.json"
    map_path.parent.mkdir(parents=True, exist_ok=True)
    map_path.write_text(json.dumps(project_map, indent=2), encoding="utf-8")
    map_s = time.perf_counter() - map_started
    results = []
    coverage_ready = True
    fresh_coverage = []
    static_workers = load_config(project).get("testing", {}).get("static_workers", 2)
    static_results = run_static_batch(plan, meta, project, args.timeout, static_workers)
    for step_index, st in enumerate(plan["steps"]):
        if st["kind"] == "command":
            cmd = st["args"][0]
            started = time.time()
            command_fingerprint = ledger.fingerprint(project)
            before = {str(p): (p.stat().st_mtime_ns, ledger.artifact_digest(p))
                      for p in review_lib.testlib.find_coverage_reports(project)}
            try:
                proc = run(shlex.split(cmd), project, args.timeout)
                status = "PASS" if proc.returncode == 0 else "FAIL"
                note = "Coverage command exit: " + str(proc.returncode)
            except (OSError, subprocess.TimeoutExpired) as exc:
                status, note = "ERROR", type(exc).__name__
            fresh_coverage = [p for p in review_lib.testlib.find_coverage_reports(project)
                              if before.get(str(p)) != (p.stat().st_mtime_ns, ledger.artifact_digest(p))]
            if status == "PASS" and not fresh_coverage:
                status, note = "NOT-TESTED", "Command did not produce a fresh coverage report."
            coverage_ready = status == "PASS"
            print(f"{status}: coverage command `{cmd}` ({time.time() - started:.1f}s)", file=out)
            if status != "PASS":
                print(f"  note: {note.strip()}", file=out)
            evidence = report(st["gate"], status, str(project), notes=[note],
                              metrics={"command": shlex.split(cmd)})
            record = ledger.append(project, st["gate"], [cmd], evidence, time.time() - started,
                                   fp=command_fingerprint, review_id=plan["review_id"])
            results.append({"step": st["gate"], "status": status, "run": record["run"], "duration_s": round(time.time() - started, 4)})
            continue
        extra = st["args"]() if callable(st["args"]) else st["args"]
        if st["gate"] == "product.coverage":
            extra = list(extra) + ["--review-id", plan["review_id"]]
        if st["gate"] == "testing.coverage" and args.coverage_cmd and not coverage_ready:
            result = report(st["gate"], "NOT-TESTED", str(project), notes=["Coverage producer failed or wrote no fresh report; old evidence was not reused."])
            duration = 0
            record = ledger.append(project, st["gate"], extra, result, duration, scope=st["scope"], review_id=plan["review_id"])
        else:
            if st["gate"] == "testing.coverage" and args.coverage_cmd:
                extra = list(extra) + [v for p in fresh_coverage for v in ("--report", str(p))]
            if step_index in static_results:
                result, record, duration = static_results[step_index]
            else:
                result, record, duration = run_gate(meta[st["gate"]], st["gate"], project, extra, args.timeout, st["scope"], plan["review_id"])
        findings = result.get("findings", [])
        verified = sum(1 for f in findings if f.get("confidence", "verified") == "verified")
        label = st["gate"] + (f"@{st['scope']}" if st["scope"] else "")
        print(f"{result['status']:<10} {label:<34} {duration:6.1f}s  findings: {verified} verified, {len(findings) - verified} suspected", file=out)
        if result["status"] in {"NOT-TESTED", "ERROR"}:
            for note in result.get("notes", [])[:1]:
                print(f"           note: {note[:300]}", file=out)
        results.append({"step": label, "status": result["status"], "run": record["run"], "verified": verified,
                        "duration_s": round(duration, 4), "timing": result.get("timing", {})})

    verdict = ledger.verdict(project, meta, plan["required"], review_id=plan["review_id"])
    if args.mode == "release-check":
        mapped = bool(load_config(project).get("acceptance"))
        verdict["release_ready"] = verdict["overall"] == "PASSED" and mapped
        verdict["release_notes"] = [] if mapped else ["No mapped product acceptance criteria; release readiness is not established."]
        if not verdict["release_ready"] and verdict["exit_code"] == 0:
            verdict["exit_code"] = EXIT["NOT-TESTED"]
    verdict_md = render_markdown(verdict)
    packet = review_lib.write_packet(project, plan, verdict_md, args.base) if args.depth != "quick" else None
    worklist = review_lib.build_worklist(project, args.coverage_cmd, review_id=plan["review_id"])
    worklist_path = review_lib.write_worklist(project, worklist)
    timing = {"total_s": round(time.perf_counter() - review_started, 4), "project_map_s": round(map_s, 4),
              "static_workers": static_workers,
              "declared_agent": load_config(project).get("agent", {}),
              "steps": results, "notes": ["CLI timings exclude agent/model reasoning and research outside this command."]}
    timing_path = project / ".superagent" / "review" / "timing.json"
    timing_path.parent.mkdir(parents=True, exist_ok=True)
    timing_path.write_text(json.dumps(timing, indent=2), encoding="utf-8")
    if args.json:
        print(json.dumps({"plan": _plan_json(plan), "results": results, "verdict": verdict,
                          "packet": str(packet) if packet else None, "worklist": str(worklist_path),
                          "worklist_json": str(worklist_path.with_suffix(".json")), "tasks": len(worklist["tasks"]),
                          "timing": timing, "project_map": str(map_path)}, indent=2, ensure_ascii=False))
    else:
        print()
        print(verdict_md)
        print()
        print(f"Worklist ({len(worklist['tasks'])} tasks): {worklist_path}")
        if packet:
            print(f"Independent review packet: {packet}")
            print("Give it to a separate agent or a fresh context (core/reasoning.md §5) for the code-reading part of the review.")
    return verdict["exit_code"]


def cmd_worklist(args):
    project = resolve_project(args.project)
    if project is None:
        return EXIT["ERROR"]
    worklist = review_lib.build_worklist(project, args.coverage_cmd)
    path = review_lib.write_worklist(project, worklist)
    if args.json:
        print(json.dumps(dict(worklist, path=str(path)), indent=2, ensure_ascii=False))
    else:
        print(path.read_text(encoding="utf-8"))
    return 0


def cmd_plan(args):
    project = resolve_project(args.project)
    if project is None:
        return EXIT["ERROR"]
    try:
        config = load_config(project)
        plan = review_lib.build_plan(project, args.depth, [], [], None, None, None, "AA", [],
                                     mode=args.mode, profile=args.profile)
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return EXIT["ERROR"]
    plan["acceptance"] = config.get("acceptance", [])
    plan["workflow"] = "core/workflows/application.md"
    plan["note"] = "Plan only. The agent implements the workflow; review runs verification and never builds an app itself."
    if args.json:
        print(json.dumps(_plan_json(plan), indent=2, ensure_ascii=False))
    else:
        print(f"Mode: {args.mode}; profile: {plan['profile']}; features: {', '.join(plan['features']) or 'detect during intake'}")
        print(f"Workflow: {SKILL_DIR / plan['workflow']}")
        for st in plan["steps"]:
            print(f"  {st['gate']}: {st['why']}")
        for hint in plan["hints"]:
            print("  hint: " + hint)
    return 0


def _plan_json(plan):
    steps = [{k: (v if not callable(v) else "<computed at run time>") for k, v in st.items()} for st in plan["steps"]]
    return dict(plan, steps=steps)


def cmd_verdict(args):
    project = Path(args.project).expanduser().resolve()
    require = [g.strip() for g in args.require.split(",") if g.strip()] if args.require is not None else None
    result = ledger.verdict(project, gates_meta(load_modules()), require)
    if args.format == "json":
        print(json.dumps(result, indent=2, ensure_ascii=False))
    elif args.format == "md":
        print(render_markdown(result))
    else:
        print(result["label"])
        for gate_id, entry in sorted(result["gates"].items()):
            extra = ""
            if entry.get("budget") and entry["budget"] != "ok":
                extra = f"  [{entry['budget']}: attempts={entry['attempts']}]"
            kind = " (info)" if entry.get("kind") == "informational" else ""
            print(f"  {gate_id}{kind}: {entry['status']}{extra}")
    return result["exit_code"]


def render_markdown(result):
    lines = ["### Verification Summary", f"- **Verdict**: {result['label']}", f"- **Code fingerprint**: `{result['fingerprint']}`", "", "| Gate | Status | Run | Report |", "|---|---|---|---|"]
    if "release_ready" in result:
        lines.insert(3, "- **Release ready**: " + str(result["release_ready"]).lower())
        for note in result.get("release_notes", []):
            lines.insert(4, "- " + note)
    for gate_id, entry in sorted(result["gates"].items()):
        status = entry["status"] + (f" ({entry['budget']})" if entry.get("budget") not in (None, "ok") else "")
        lines.append(f"| {gate_id} | {status} | {entry.get('run', '—')} | {entry.get('report', '—')} |")
    if result["iso25010"]:
        lines += ["", "| ISO/IEC 25010 characteristic | Evidence |", "|---|---|"]
        for characteristic, gates in sorted(result["iso25010"].items()):
            lines.append(f"| {characteristic} | " + ", ".join(f"{g}: {s}" for g, s in sorted(gates.items())) + " |")
    return "\n".join(lines)


def cmd_search(args):
    if args.corpus == "project":
        import discovery
        project = resolve_project(args.project)
        if project is None:
            return EXIT["ERROR"]
        try:
            started = time.perf_counter()
            data = discovery.search_project(project, args.query, args.limit, args.role)
            data["duration_s"] = round(time.perf_counter() - started, 4)
            print(json.dumps(data, indent=2, ensure_ascii=False) if args.json else
                  "\n".join(f"{r['path']}:{r['start']} [{r['role']}] {r['snippet']}" for r in data["results"]) or "No project matches.")
            return 0
        except (OSError, ValueError) as exc:
            print(str(exc), file=sys.stderr)
            return EXIT["ERROR"]
    results = rag.search(args.query, module=args.module, limit=args.limit)
    if args.json:
        print(json.dumps({"query": args.query, "results": results}, indent=2, ensure_ascii=False))
        return 0
    if not results:
        terms = rag.expand_query(args.query)
        print(f"No matches for '{args.query}' (terms: {', '.join(terms) or 'none'}). Add missing Persian terms to core/rag/glossary.json.")
        return 0
    for i, r in enumerate(results, 1):
        print(f"[{i}] {r['path']} > {r['section']}  ({r['module']})")
        print(f"    {r['snippet']}")
    return 0


def cmd_doctor(args):
    checks = []

    def check(name, ok, hint=""):
        checks.append({"check": name, "ok": bool(ok), "hint": "" if ok else hint})

    check("python >= 3.8", sys.version_info >= (3, 8), "Install Python 3.8+")
    check("sqlite fts5", _has_fts5(), "Use a Python build whose sqlite3 has FTS5")
    check("node / npx", shutil.which("npx"), "Install Node.js 18+ (needed for ui-ux.a11y, ui-ux.interaction)")
    check("skill node_modules", (SKILL_DIR / "node_modules" / "@playwright" / "test").is_dir(), f"npm install --prefix {SKILL_DIR}")
    check("playwright chromium", _has_chromium(), "npx playwright install chromium")
    check("git", shutil.which("git"), "Install git (needed for diff coverage and risk churn)")
    optional = {
        "pytest": "pip install pytest pytest-cov (python projects)",
        "stryker": "npm i -D @stryker-mutator/core (JS mutation testing)",
        "mutmut": "pip install mutmut (python mutation testing)",
        "schemathesis": "pip install schemathesis (API property-based testing)",
        "semgrep": "Install Semgrep and configure project-local rules (security.sast)",
        "trivy": "Install Trivy and refresh its vulnerability database (security.dependencies)",
        "k6": "Install k6 and configure thresholds (operations.load)",
        "docker": "Install a container runtime when real-database tests use Testcontainers",
    }
    for tool, hint in optional.items():
        check(f"optional: {tool}", shutil.which(tool), hint)
    if args.json:
        print(json.dumps(checks, indent=2))
    else:
        for c in checks:
            print(f"{'ok ' if c['ok'] else 'MISSING'}  {c['check']}" + (f"  -> {c['hint']}" if c["hint"] else ""))
    required = [c for c in checks if not c["check"].startswith("optional") and not c["ok"]]
    return 0 if not required else 2


def _has_fts5():
    import sqlite3
    try:
        sqlite3.connect(":memory:").execute("CREATE VIRTUAL TABLE t USING fts5(x)")
        return True
    except sqlite3.Error:
        return False


def _has_chromium():
    cache_dirs = [Path.home() / "Library" / "Caches" / "ms-playwright", Path.home() / ".cache" / "ms-playwright"]
    return any(d.is_dir() and any(d.glob("chromium*")) for d in cache_dirs)


def cmd_index(args):
    count = rag.build_index(rag.default_db_path())
    print(f"Indexed {count} sections from core/ and modules/.")
    return 0


def cmd_debug(args):
    import debugger
    project = resolve_project(args.project)
    if project is None:
        return EXIT["ERROR"]
    try:
        if args.phase == "discover":
            result, code = debugger.discover(project)
        else:
            result, code = debugger.execute(project, args.phase, args.case)
    except (OSError, ValueError, TypeError) as exc:
        result, code = {"outcome": "INCONCLUSIVE", "error": str(exc)}, EXIT["ERROR"]
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        details = result.get("metrics", result)
        print(f"Debug {args.phase}: {details.get('outcome')}")
        if details.get("reason") or details.get("error"):
            print(details.get("reason") or details.get("error"))
        if result.get("ledger"):
            print("Evidence: " + str(project / result["ledger"]["report"]))
    return code


def cmd_project_map(args):
    import discovery
    project = resolve_project(args.project)
    if project is None:
        return EXIT["ERROR"]
    try:
        data = discovery.build_map(project)
        if args.write:
            output = project / ".superagent/project-map.json"
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(data, indent=2), encoding="utf-8")
        print(json.dumps(data, indent=2) if args.json else json.dumps({"roles": data["roles"], "suites": data["suites"], "notes": data["notes"]}, indent=2))
        return 0
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return EXIT["ERROR"]


def main():
    parser = argparse.ArgumentParser(prog="sa", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project", default=".", help="Project root (default: current directory)")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("modules", help="List modules and their gates")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("project-map", help="Map declared/unknown source roles and package test suites")
    p.add_argument("--project", dest="sub_project")
    p.add_argument("--write", action="store_true", help="Save .superagent/project-map.json")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("debug", help="Discover, reproduce and verify a fix with an unchanged independent oracle")
    p.add_argument("--phase", choices=["discover", "reproduce", "verify-fix"], default="discover")
    p.add_argument("--case", help="Case id in <project>/debug-cases/<id>.json")
    p.add_argument("--project", dest="sub_project")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("plan", help="Plan a design/build/change/audit/test/release workflow without changing project files")
    p.add_argument("--mode", choices=MODES, default="audit")
    p.add_argument("--profile", choices=sorted(PROFILES))
    p.add_argument("--depth", choices=["quick", "standard", "thorough"], default="standard")
    p.add_argument("--project", dest="sub_project")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("gate", help="Run a gate and record the result in the evidence ledger")
    p.add_argument("gate_id", help="e.g. ui-ux.a11y, testing.run")
    p.add_argument("--project", dest="sub_project", help="Project root (same as the global --project)")
    p.add_argument("--scope", help="Label when the same gate runs on several targets (e.g. one per page)")
    p.add_argument("--json", action="store_true")
    p.add_argument("--timeout", type=int, default=1800)
    p.add_argument("--max-findings", type=int, default=20)

    p = sub.add_parser("verdict", help="Compute the verdict from the evidence ledger")
    p.add_argument("--require", help="Comma-separated gate ids that must have evidence")
    p.add_argument("--project", dest="sub_project", help="Project root (same as the global --project)")
    p.add_argument("--format", choices=["text", "json", "md"], default="text")

    p = sub.add_parser("review", help="Plan and run every applicable gate for the project, then compute the verdict")
    p.add_argument("--mode", choices=[m for m in MODES if m != "design"], default="audit")
    p.add_argument("--profile", choices=sorted(PROFILES))
    p.add_argument("--project", dest="sub_project", help="Project root (same as the global --project)")
    p.add_argument("--depth", choices=["quick", "standard", "thorough"], default="standard")
    p.add_argument("--url", action="append", help="Page of the running app to audit (repeat for several pages)")
    p.add_argument("--sandbox", action="append", help="Standalone HTML prototype to audit (repeatable)")
    p.add_argument("--api-url", help="Base URL of the running backend for the API contract gate")
    p.add_argument("--doc", action="append", help="Document whose claims to audit against the code (pdf, docx, md, html); repeatable")
    p.add_argument("--base", help="Git base for diff coverage and the review packet (default: merge-base with main/master)")
    p.add_argument("--coverage-cmd", help="Command that writes a coverage report before testing.coverage runs")
    p.add_argument("--level", choices=["AA", "AAA"], default="AA", help="WCAG level for target sizes")
    p.add_argument("--skip", help="Comma-separated gate ids to leave out (they then do not count toward the verdict)")
    p.add_argument("--timeout", type=int, default=1800, help="Seconds per step")
    p.add_argument("--dry-run", action="store_true", help="Print the plan without running it")
    p.add_argument("--json", action="store_true", help="Machine-readable output on stdout (progress goes to stderr)")

    p = sub.add_parser("worklist", help="Turn the latest gate evidence into tasks with acceptance checks")
    p.add_argument("--project", dest="sub_project", help="Project root (same as the global --project)")
    p.add_argument("--coverage-cmd", help="Coverage command to embed in the testing.accept commands")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("search", help="Search the skill's references (English or Persian)")
    p.add_argument("query")
    p.add_argument("--module")
    p.add_argument("--limit", type=int, default=5)
    p.add_argument("--json", action="store_true")
    p.add_argument("--project", dest="sub_project")
    p.add_argument("--corpus", choices=["skill", "project"], default="skill")
    p.add_argument("--role", action="append", choices=["active", "test", "reference", "generated", "unknown"])

    p = sub.add_parser("doctor", help="Check which tools are available")
    p.add_argument("--json", action="store_true")

    sub.add_parser("index", help="Rebuild the reference search index")

    args, passthrough = parser.parse_known_args()
    if getattr(args, "sub_project", None):
        args.project = args.sub_project
    if args.command == "gate":
        return cmd_gate(args, passthrough)
    if passthrough:
        parser.error(f"unrecognized arguments: {' '.join(passthrough)}")
    return {"modules": cmd_modules, "project-map": cmd_project_map, "debug": cmd_debug, "plan": cmd_plan, "verdict": cmd_verdict, "review": cmd_review, "worklist": cmd_worklist, "search": cmd_search, "doctor": cmd_doctor, "index": cmd_index}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
