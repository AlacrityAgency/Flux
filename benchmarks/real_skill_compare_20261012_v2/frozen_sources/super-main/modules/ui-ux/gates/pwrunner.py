"""Shared Playwright runner for browser-based ui-ux gates (a11y, interaction).

Handles target preconditions (--url / --sandbox), tooling checks, running one spec on the
desktop and mobile projects, and mapping Playwright's JSON report to the gate contract.
Each spec writes per-viewport JSON to $A11Y_RESULTS_DIR/<project>.json; the calling gate turns
those files into findings.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable, Dict, List, Optional

SKILL_DIR = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(SKILL_DIR / "core" / "lib"))
from gatekit import base_parser, make_finding, report, run  # noqa: E402

CONFIG = SKILL_DIR / "playwright.config.js"


def add_target_arguments(description: str):
    parser = base_parser(description)
    target = parser.add_mutually_exclusive_group()
    target.add_argument("--url", help="Live page to audit (http://, https:// or file://)")
    target.add_argument("--sandbox", help="Standalone HTML prototype rendering into #root")
    parser.add_argument("--out", help="Artifact directory (default: <project>/.superagent/<gate>)")
    parser.add_argument("--mount-timeout", type=int, default=15000, help="Sandbox render timeout in ms")
    parser.add_argument("--timeout", type=int, default=300, help="Overall Playwright timeout in seconds")
    return parser


def check_preconditions(args, gate: str):
    """Return (target_env, target_label, None) or (None, None, NOT-TESTED/ERROR report)."""
    if getattr(args, "sandbox", None):
        sandbox = Path(args.sandbox).expanduser()
        if not sandbox.is_absolute():
            sandbox = Path(args.project).expanduser().resolve() / sandbox
        sandbox = sandbox.resolve()
        if not sandbox.is_file():
            return None, None, report(gate, "NOT-TESTED", str(sandbox), notes=[f"Sandbox file not found: {sandbox}"])
        return {"SANDBOX_PATH": str(sandbox)}, str(sandbox), None
    url = getattr(args, "url", None)
    if url:
        if url.startswith("file://"):
            local = Path(urllib.request.url2pathname(url[len("file://"):]))
            if not local.is_file():
                return None, None, report(gate, "NOT-TESTED", url, notes=[f"File not found: {local}"])
        elif url.startswith(("http://", "https://")):
            try:
                urllib.request.urlopen(urllib.request.Request(url, method="GET"), timeout=5).close()
            except urllib.error.HTTPError:
                pass  # the server answered; status codes are the page's business, not a missing environment
            except (urllib.error.URLError, OSError) as exc:
                return None, None, report(gate, "NOT-TESTED", url, notes=[f"Target unreachable ({exc}). Start the dev server and retry."])
        else:
            return None, None, report(gate, "ERROR", url, notes=["--url must start with http://, https:// or file://"])
        return {"TARGET_URL": url}, url, None
    return None, None, report(gate, "NOT-TESTED", notes=["No target. Pass --url <running app> or --sandbox <standalone HTML prototype>."])


def check_tooling() -> List[str]:
    if not shutil.which("npx"):
        return ["Node.js/npx not found. Install Node.js 18+."]
    for package in (("@playwright", "test"), ("@axe-core", "playwright")):
        if not (SKILL_DIR / "node_modules" / package[0] / package[1]).is_dir():
            return [f"Playwright dependencies missing. Run: npm install --prefix {SKILL_DIR}"]
    return []


def failure_messages(pw_report: dict):
    messages = []

    def walk(suite):
        for spec in suite.get("specs", []):
            for t in spec.get("tests", []):
                for result in t.get("results", []):
                    for error in result.get("errors", []) or ([result["error"]] if result.get("error") else []):
                        messages.append((t.get("projectName"), error.get("message", "")))
        for child in suite.get("suites", []):
            walk(child)

    for suite in pw_report.get("suites", []):
        walk(suite)
    return messages


def page_error_findings(results: Dict[str, dict], gate: str, start: int) -> List[dict]:
    findings = []
    for viewport, data in sorted(results.items()):
        for err in data.get("pageErrors", []):
            findings.append(make_finding(start + len(findings), "ui-ux", gate, "uncaught-page-error", "P1", f"page load on {viewport} viewport",
                                         {"output": err[:2000]}, "The page throws at runtime; the audited DOM may not reflect the intended UI.",
                                         "Fix the runtime error, then re-run the gate."))
    return findings


def run_spec(args, gate: str, spec: Path, collect: Callable[[Dict[str, dict]], List[dict]],
             extra_env: Optional[Dict[str, str]] = None, extra_cmd: Optional[List[str]] = None,
             pass_notes: Optional[List[str]] = None) -> dict:
    env_target, target, problem = check_preconditions(args, gate)
    if problem:
        return problem
    tooling = check_tooling()
    if tooling:
        return report(gate, "NOT-TESTED", target, notes=tooling)

    project = Path(args.project).expanduser().resolve()
    out_dir = Path(args.out).expanduser().resolve() if args.out else project / ".superagent" / gate.split(".")[-1]
    out_dir.mkdir(parents=True, exist_ok=True)
    results_dir = Path(tempfile.mkdtemp(prefix="results-", dir=out_dir))
    json_report = results_dir / "playwright-report.json"

    env = {k: v for k, v in os.environ.items() if k not in {"TARGET_URL", "SANDBOX_PATH"}}
    env.update(env_target)
    env.update({"A11Y_RESULTS_DIR": str(results_dir / "viewports"), "A11Y_JSON_REPORT": str(json_report),
                "MOUNT_TIMEOUT_MS": str(args.mount_timeout)})
    env.update(extra_env or {})
    cmd = ["npx", "playwright", "test", str(spec), "--config", str(CONFIG), "--output", str(results_dir / "artifacts")] + (extra_cmd or [])
    try:
        proc = run(cmd, SKILL_DIR, args.timeout, env)
    except subprocess.TimeoutExpired:
        return report(gate, "ERROR", target, notes=[f"Playwright did not finish within {args.timeout}s."])

    combined = proc.stdout + proc.stderr
    if "Executable doesn't exist" in combined:
        return report(gate, "NOT-TESTED", target, notes=["Chromium for Playwright is not installed. Run: npx playwright install chromium"])
    if "browserType.launch" in combined:
        return report(gate, "ERROR", target, notes=["Browser launch failed; inspect environment/permissions before diagnosing the page.", combined[-1500:]])
    if not json_report.is_file():
        return report(gate, "ERROR", target, notes=["Playwright produced no JSON report.", combined[-3000:]])

    try:
        pw_report = json.loads(json_report.read_text(encoding="utf-8"))
        per_viewport = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted((results_dir / "viewports").glob("*.json"))}
        findings = collect(per_viewport)
        findings += page_error_findings(per_viewport, gate, len(findings) + 1)
    except (json.JSONDecodeError, OSError, KeyError) as exc:
        return report(gate, "ERROR", target, notes=[f"Could not parse gate results: {exc}"])

    stats = pw_report.get("stats", {})
    summary = {k: stats.get(k, 0) for k in ("expected", "unexpected", "flaky", "skipped")}
    summary["viewports"] = ", ".join(sorted(per_viewport)) or "none"
    artifacts = {"results": str(results_dir)}

    if summary["unexpected"] == 0 and summary["skipped"] == 0 and summary["expected"] > 0:
        status = "FAIL" if any(f["confidence"] == "verified" for f in findings) else "PASS"
        return report(gate, status, target, findings, pass_notes or [], summary, artifacts)
    if summary["unexpected"] > 0:
        if not any(f["confidence"] == "verified" for f in findings):
            for project_name, message in failure_messages(pw_report):
                findings.append(make_finding(len(findings) + 1, "ui-ux", gate,
                                             "visual-regression" if "screenshot" in message.lower() else "render-failure", "P1",
                                             f"{project_name} viewport", {"output": message[:2000]},
                                             "The UI could not be audited as rendered.", "Fix the rendering error shown in evidence, then re-run the gate."))
        return report(gate, "FAIL", target, findings, [], summary, artifacts)
    return report(gate, "ERROR", target, findings, ["Tests were skipped or none ran; refusing to report PASS."], summary, artifacts)
