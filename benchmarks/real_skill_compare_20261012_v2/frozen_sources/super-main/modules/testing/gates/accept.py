#!/usr/bin/env python3
"""testing.accept: assurance filters for newly written tests (workflow step T5).

Adapted from Meta's TestGen-LLM filters. A new test is accepted only if:
  F1 builds   the test file is collected and runs (at least one test executed)
  F2 stable   it passes in every one of N runs (default 5); with --expect-fail (a bug
              reproduction written before the fix) it must fail in every run instead
  F3 value    it adds coverage on the target files: coverage is measured by --coverage-cmd
              with the new test files set aside, then with them in place; a reproduction test
              (--expect-fail) counts as value by definition
  F4 clean    the new test files have no test smells, not even suspected ones

Exit: PASS when all filters pass; FAIL when a filter fails; NOT-TESTED when the runner or the
coverage measurement (F3) is unavailable.
Usage: sa.py gate testing.accept --scope <name> -- --test tests/test_payment.py --coverage-cmd "<cmd>"
"""

import json
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import smells  # noqa: E402
import testlib  # noqa: E402
from gatekit import base_parser, emit, make_finding, project_root, report, run, work_dir  # noqa: E402


GATE = "testing.accept"
RUN_GATE = Path(__file__).resolve().parent / "run.py"


def run_tests(project, tests, repeat, runner, timeout):
    cmd = [sys.executable, str(RUN_GATE), "--project", str(project), "--json", "--repeat", str(repeat), "--args", " ".join(tests)]
    if runner:
        cmd += ["--runner", runner]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"status": "ERROR", "notes": [(proc.stdout + proc.stderr)[-1500:]], "metrics": {}, "findings": []}


def covered_lines(project, targets):
    reports = testlib.find_coverage_reports(project)
    if not reports:
        return None
    coverage = testlib.merge_coverage([testlib.load_coverage(r, project) for r in reports])
    wanted = set(targets) if targets else set(coverage)
    return {f: {n for n, h in lines.items() if h > 0} for f, lines in coverage.items() if f in wanted}


def measure_gain(project, tests, coverage_cmd, targets, timeout):
    """Coverage with the new tests set aside vs. with them in place. Files are always restored."""
    hold = work_dir(project, "accept-hold")
    moved = []
    try:
        for t in tests:
            src = project / t
            dst = hold / t.replace("/", "__")
            shutil.move(str(src), str(dst))
            moved.append((dst, src))
        for r in testlib.find_coverage_reports(project):
            r.unlink()
        run(shlex.split(coverage_cmd), project, timeout)
        before = covered_lines(project, targets)
    finally:
        for dst, src in moved:
            src.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(dst), str(src))
    for r in testlib.find_coverage_reports(project):
        r.unlink()
    after_proc = run(shlex.split(coverage_cmd), project, timeout)
    after = covered_lines(project, targets)
    if after is None:
        return None, f"coverage command produced no report (exit {after_proc.returncode}): {(after_proc.stdout + after_proc.stderr)[-500:]}"
    before = before or {}
    gained = {f: sorted(lines - before.get(f, set())) for f, lines in after.items()}
    return {f: l for f, l in gained.items() if l}, None


def main():
    parser = base_parser("Assurance filters F1-F4 for newly written tests")
    parser.add_argument("--test", action="append", required=True, help="New test file (relative to the project); repeatable")
    parser.add_argument("--repeat", type=int, default=5, help="Runs for the stability filter (default 5)")
    parser.add_argument("--expect-fail", action="store_true", help="Bug reproduction written before the fix: must fail in every run")
    parser.add_argument("--coverage-cmd", help="Command that runs the suite with coverage and writes a report (needed for F3)")
    parser.add_argument("--target", action="append", help="Source file the tests are meant to cover (limits F3 to these files)")
    parser.add_argument("--runner", help="Force the test runner (see testing.run --help)")
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()
    project = project_root(args.project)

    missing = [t for t in args.test if not (project / t).is_file()]
    if missing:
        return emit(report(GATE, "ERROR", str(project), notes=[f"Test file not found: {', '.join(missing)}"]), args.json)

    filters, findings, notes = {}, [], []

    def fail(rule, condition, evidence, impact, remediation):
        findings.append(make_finding(len(findings) + 1, "testing", GATE, rule, "P1", condition, evidence, impact, remediation))

    # F1 + F2: run the new tests N times.
    result = run_tests(project, args.test, args.repeat, args.runner, args.timeout)
    m = result.get("metrics", {})
    if result.get("status") in {"NOT-TESTED", "ERROR"} and not m.get("tests"):
        return emit(report(GATE, "NOT-TESTED", str(project), notes=["F1 could not run: " + " ".join(result.get("notes", []))[:800]]), args.json)
    executed = m.get("passed", 0) + m.get("failed", 0) + m.get("flaky", 0)
    filters["F1_builds"] = "PASS" if executed > 0 else "FAIL"
    if executed == 0:
        fail("assurance-f1-not-collected", f"{', '.join(args.test)}: 0 tests executed", {"runner_notes": result.get("notes", [])},
             "The new test file is not collected or does not run.", "Check the file name pattern, imports and syntax.")
    if args.expect_fail:
        stable = executed > 0 and m.get("failed", 0) == executed
        filters["F2_stable"] = "PASS" if stable else "FAIL"
        if not stable:
            fail("assurance-f2-reproduction-not-failing", f"expected every test to fail in {args.repeat} runs; got {m}", {"metrics": m},
                 "A bug-reproduction test that passes (or flakes) before the fix does not reproduce the bug.",
                 "Make the test assert the correct behaviour that the current code violates.")
    else:
        stable = executed > 0 and m.get("failed", 0) == 0 and m.get("flaky", 0) == 0
        filters["F2_stable"] = "PASS" if stable else "FAIL"
        if not stable and executed > 0:
            fail("assurance-f2-not-stable", f"{args.repeat} runs: passed {m.get('passed')}, failed {m.get('failed')}, flaky {m.get('flaky')}",
                 {"findings": [f.get("evidence", {}).get("test") for f in result.get("findings", [])]},
                 "The new test fails or is flaky on the current code.", "Fix the test (or the code, if the test exposes a real bug); remove nondeterminism.")

    # F4: no smells at all in the new files (stricter than the suite-wide gate).
    smell_hits = []

    def add(rule, severity, confidence, rel, line, evidence, impact, remediation):
        smell_hits.append(f"{rel}:{line} {rule} ({evidence[:60]})")

    for t in args.test:
        path = project / t
        if path.suffix == ".py":
            smells.scan_py(path, t, add)
        elif path.suffix in testlib.JS_EXT:
            smells.scan_js(path, t, add)
    filters["F4_clean"] = "PASS" if not smell_hits else "FAIL"
    if smell_hits:
        fail("assurance-f4-smells", f"{len(smell_hits)} smell(s) in new tests", {"smells": smell_hits[:20]},
             "New tests must not add sleeps, empty or assertion-free tests, external calls or focus/skip markers.", "Remove the smells listed in evidence.")

    # F3: measurable value.
    if args.expect_fail:
        filters["F3_value"] = "PASS"
        notes.append("F3: a failing reproduction of a bug counts as value. After the fix, re-run without --expect-fail.")
    elif not args.coverage_cmd:
        filters["F3_value"] = "NOT-MEASURED"
        notes.append("F3 needs --coverage-cmd (e.g. \"pytest --cov=src --cov-report=xml\", \"npx vitest run --coverage --coverage.reporter=lcov\", \"npx c8 --reporter=lcov node --test\").")
    elif filters["F2_stable"] == "PASS":
        try:
            gained, problem = measure_gain(project, args.test, args.coverage_cmd, args.target, args.timeout)
        except Exception as exc:
            gained, problem = None, str(exc)
        if gained is None:
            filters["F3_value"] = "NOT-MEASURED"
            notes.append(f"F3 could not be measured: {problem}")
        elif gained:
            filters["F3_value"] = "PASS"
            notes.append("F3 coverage gained: " + "; ".join(f"{f}: {testlib.ranges(l)}" for f, l in gained.items()))
        else:
            filters["F3_value"] = "FAIL"
            fail("assurance-f3-no-new-coverage", "no line became covered that was not covered without the new tests",
                 {"targets": args.target or "all files"}, "The test duplicates existing coverage.",
                 "Target uncovered lines or surviving mutants from the worklist, or drop the test.")

    if findings:
        status = "FAIL"
    elif filters.get("F3_value") == "NOT-MEASURED":
        status = "NOT-TESTED"
    else:
        status = "PASS"
    metrics = {**filters, "tests_executed": executed, "runs": args.repeat, "mode": "reproduction" if args.expect_fail else "new-test"}
    return emit(report(GATE, status, ", ".join(args.test), findings, notes, metrics), args.json)


if __name__ == "__main__":
    sys.exit(main())
