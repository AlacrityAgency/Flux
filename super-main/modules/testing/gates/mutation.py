#!/usr/bin/env python3
"""testing.mutation: does the suite detect injected faults? (mutation score on chosen files)

Coverage shows code was executed; mutation testing shows the tests would notice if it were wrong.
Run it on the high-risk files from testing.risk rather than on the whole codebase (it is slow).
Surviving mutants are reported as findings: each one is a concrete target for a new test
(the approach behind mutation-guided test generation).

Tools: StrykerJS (JS/TS) or mutmut (Python). When neither is available the gate is NOT-TESTED.
"""

import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import testlib  # noqa: E402
from gatekit import base_parser, emit, make_finding, project_root, report, run  # noqa: E402


GATE = "testing.mutation"


STRYKER_REPORT = Path("reports") / "mutation" / "mutation.json"


def stryker_available(project: Path) -> bool:
    """The Stryker engine must be installed in the project. The IDE extension alone is only a UI for it."""
    return (project / "node_modules" / ".bin" / "stryker").exists() or (project / "node_modules" / "@stryker-mutator" / "core").is_dir()


def run_stryker(project: Path, files, timeout):
    report_path = project / STRYKER_REPORT
    if report_path.exists():
        report_path.unlink()  # never read a report left over from an earlier run
    cmd = ["npx", "--no-install", "stryker", "run", "--reporters", "json,clear-text"]
    if files:
        cmd += ["--mutate", ",".join(files)]
    proc = run(cmd, project, timeout)
    if not report_path.is_file():
        return None, proc
    data = json.loads(report_path.read_text(encoding="utf-8"))
    mutants = []
    for file, info in (data.get("files") or {}).items():
        for m in info.get("mutants", []):
            loc = (m.get("location") or {}).get("start", {})
            mutants.append({"file": file, "line": loc.get("line"), "mutator": m.get("mutatorName"),
                            "replacement": m.get("replacement"), "status": m.get("status")})
    return mutants, proc


def mutmut_major(project: Path) -> int:
    out = run(["mutmut", "--version"], project, 60)
    match = re.search(r"(\d+)\.", out.stdout + out.stderr)
    return int(match.group(1)) if match else 3


def run_mutmut(project: Path, files, timeout):
    # mutmut 3 removed --paths-to-mutate; the paths come from [tool.mutmut] / setup.cfg instead.
    cmd = ["mutmut", "run"]
    if files and mutmut_major(project) < 3:
        cmd += ["--paths-to-mutate", ",".join(files)]
    proc = run(cmd, project, timeout)
    results = run(["mutmut", "results"], project, 300)
    mutants = []
    for line in (results.stdout or "").splitlines():
        match = re.match(r"\s*(\S+):\s*(killed|survived|no tests|timeout|suspicious|skipped)\s*$", line)
        if match:
            name, status = match.groups()
            mutants.append({"file": name, "line": None, "mutator": None, "replacement": None,
                            "status": {"killed": "Killed", "survived": "Survived", "no tests": "NoCoverage"}.get(status, status.title())})
    return (mutants or None), proc


def main():
    parser = base_parser("Measure mutation score on selected files")
    parser.add_argument("--files", help="Comma-separated files to mutate (default: top 5 from testing.risk)")
    parser.add_argument("--min-score", type=float, default=60.0, help="Minimum mutation score %% on the mutated files")
    parser.add_argument("--timeout", type=int, default=3600)
    args = parser.parse_args()
    project = project_root(args.project)

    files = [f.strip() for f in (args.files or "").split(",") if f.strip()]
    if not files:
        risk = project / ".superagent" / "testing" / "risk.json"
        if risk.is_file():
            files = [r["file"] for r in json.loads(risk.read_text(encoding="utf-8"))[:5]]

    js_files = [f for f in files if Path(f).suffix in testlib.JS_EXT]
    py_files = [f for f in files if f.endswith(".py")]
    tool = None
    if stryker_available(project) and (js_files or not files):
        tool, targets = "stryker", js_files
    elif shutil.which("mutmut") and (py_files or not files):
        tool, targets = "mutmut", py_files
    if not testlib.detect_runners(project):
        return emit(report(GATE, "NOT-TESTED", str(project), notes=[
            "Mutation testing measures an existing test suite, and this project has none. Write tests first (workflow T4-T5), then run this gate."]), args.json)
    if not tool:
        return emit(report(GATE, "NOT-TESTED", str(project), notes=[
            "No mutation tool available. JS/TS: npm i -D @stryker-mutator/core (plus the runner plugin, e.g. @stryker-mutator/vitest-runner). "
            "Python: pip install mutmut. Then re-run with --files from testing.risk.",
            "The Stryker IDE/VS Code extension is only a front-end; the engine must be installed in the project (it looks for node_modules/.bin/stryker)."]), args.json)

    try:
        mutants, proc = (run_stryker if tool == "stryker" else run_mutmut)(project, targets, args.timeout)
    except Exception as exc:
        return emit(report(GATE, "ERROR", str(project), notes=[f"{tool} failed to run: {exc}"]), args.json)
    if not mutants:
        return emit(report(GATE, "ERROR", str(project), notes=[f"{tool} produced no parseable results.", (proc.stdout + proc.stderr)[-2000:]]), args.json)

    killed = sum(1 for m in mutants if m["status"] in {"Killed", "Timeout"})
    survived = [m for m in mutants if m["status"] in {"Survived", "NoCoverage"}]
    scored = killed + len(survived)
    score = round(100 * killed / scored, 1) if scored else None
    findings = []
    for m in survived[:50]:
        where = f"{m['file']}:{m['line']}" if m.get("line") else m["file"]
        findings.append(make_finding(len(findings) + 1, "testing", GATE, "surviving-mutant", "P2", where,
                                     {"mutator": m.get("mutator"), "replacement": m.get("replacement"), "status": m["status"]},
                                     "A deliberate fault here goes unnoticed by the tests.",
                                     "Write a test that fails on this mutation (assert the behaviour the mutated expression controls)."))
    status = "PASS" if score is not None and score >= args.min_score else "FAIL"
    if status == "PASS":
        for f in findings:
            f["confidence"] = "suspected"  # informative targets, the gate threshold is met
    metrics = {"tool": tool, "files": ", ".join(targets) or "(tool default)", "mutants": len(mutants), "killed": killed,
               "survived": len(survived), "mutation_score": score, "min_score": args.min_score}
    return emit(report(GATE, status, str(project), findings, [], metrics), args.json)


if __name__ == "__main__":
    sys.exit(main())
