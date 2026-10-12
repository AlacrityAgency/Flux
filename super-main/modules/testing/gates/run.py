#!/usr/bin/env python3
"""testing.run: execute the project's own test suite N times and classify every test.

  passed  every run passed
  failed  every run failed          -> finding test-failure (P1)
  flaky   mixed outcomes across runs -> finding flaky-test (P1)
  skipped skipped in every run      -> reported in metrics

A suite that executes zero tests FAILS: an empty green run is not evidence.
Repeat only when checking nondeterminism or when the acceptance criteria require it.
"""

import shlex
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import testlib  # noqa: E402
from gatekit import base_parser, emit, make_finding, project_root, report, run, work_dir, is_within  # noqa: E402


GATE = "testing.run"


def parse(fmt, junit, json_out, stdout):
    if fmt == "junit":
        return testlib.parse_junit(junit) if junit.is_file() else None
    if fmt == "jest-json":
        return testlib.parse_jest_json(json_out) if json_out.is_file() else None
    if fmt == "go-json":
        return testlib.parse_go_json(stdout)
    if fmt == "unittest-json":
        import json
        if not json_out.is_file():
            return None
        data = json.loads(json_out.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or any(not isinstance(k, str) or v not in {"passed", "failed", "skipped"} for k, v in data.items()):
            raise ValueError("Invalid unittest outcomes")
        return data
    return None


def main():
    parser = base_parser("Run the project's tests repeatedly and classify failures and flaky tests")
    parser.add_argument("--runner", help="Force a runner: vitest, jest, node-test, mocha, npm-test, pytest, unittest, go, playwright")
    parser.add_argument("--cmd", help="Custom command; --junit is required for per-test PASS evidence")
    parser.add_argument("--suite", default=".", help="Runner working directory inside the project")
    parser.add_argument("--junit", help="JUnit XML written by --cmd (relative to the project)")
    parser.add_argument("--args", default="", help="Extra arguments appended to the runner command (e.g. a test file)")
    parser.add_argument("--repeat", type=int, default=1, help="Number of runs (3 for baselines, 5 for new tests)")
    parser.add_argument("--timeout", type=int, default=900, help="Seconds per run")
    parser.add_argument("--e2e", action="store_true", help="Run the end-to-end suite (Playwright) instead of unit/integration tests")
    args = parser.parse_args()
    project = project_root(args.project)
    suite = (project / args.suite).resolve()
    if not is_within(suite, project) or not suite.is_dir():
        return emit(report(GATE, "ERROR", str(project), notes=["Suite must be a directory inside the project."]), args.json)
    out_dir = work_dir(project, "testing", "runs")

    if args.cmd:
        runner = "custom"
    elif args.e2e:
        runner = testlib.e2e_runner(suite) if testlib.e2e_runner(suite) == "playwright" else None
        if not runner:
            return emit(report(GATE, "NOT-TESTED", str(project), notes=["No Playwright E2E suite found (cypress is not auto-run; pass --cmd)."]), args.json)
    else:
        candidates = testlib.detect_runners(suite)
        if args.runner:
            runner = args.runner
        elif candidates:
            runner = candidates[0]["name"]
        else:
            return emit(report(GATE, "NOT-TESTED", str(project), notes=[
                "No test runner detected (no test script, pytest/unittest tests, or go.mod). "
                "Pass --cmd '<command>' or add tests first (see testing.inventory)."]), args.json)

    all_runs, durations, notes, exit_codes, tails = [], [], [], [], []
    for attempt in range(1, max(1, args.repeat) + 1):
        junit = out_dir / f"junit-{attempt}.xml"
        json_out = out_dir / f"jest-{attempt}.json"
        for stale in (junit, json_out):
            if stale.exists():
                stale.unlink()
        if runner == "custom":
            cmd, fmt = shlex.split(args.cmd), "junit" if args.junit else "exit-code"
            if args.junit:
                if (suite / args.junit).is_symlink():
                    return emit(report(GATE, "ERROR", str(project), notes=["JUnit output may not be a symlink."]), args.json)
                junit = (suite / args.junit).resolve()
                if not is_within(junit, project) or junit.is_symlink():
                    return emit(report(GATE, "ERROR", str(project), notes=["JUnit output must stay inside the project."]), args.json)
                if junit.exists():
                    junit.unlink()
        else:
            cmd, fmt = testlib.runner_command(runner, suite, junit, json_out)
            if runner in {"pytest", "unittest"} and testlib.project_python(suite) == sys.executable:
                cmd[0] = testlib.project_python(project)
        cmd += shlex.split(args.args)
        env = {"CI": "1", "FORCE_COLOR": "0"}
        if runner == "playwright":
            env["PLAYWRIGHT_JUNIT_OUTPUT_NAME"] = str(junit)
        if not shutil.which(cmd[0]) and not Path(cmd[0]).exists():
            return emit(report(GATE, "NOT-TESTED", str(project), notes=[f"'{cmd[0]}' is not installed or not on PATH."]), args.json)
        started = time.time()
        try:
            proc = run(cmd, suite, args.timeout, env)
        except Exception as exc:  # timeout or launch failure
            return emit(report(GATE, "ERROR", str(project), notes=[f"Run {attempt} could not complete: {exc}"]), args.json)
        durations.append(round(time.time() - started, 2))
        exit_codes.append(proc.returncode)
        output = proc.stdout + proc.stderr
        tails.append(output[-2500:])
        if runner in {"pytest"} and "No module named pytest" in output:
            return emit(report(GATE, "NOT-TESTED", str(project), notes=["pytest is not installed for this Python. pip install pytest, or use --runner unittest."]), args.json)
        try:
            results = parse(fmt, junit, json_out, proc.stdout + "\n" + proc.stderr)
        except Exception as exc:
            return emit(report(GATE, "ERROR", str(suite), notes=[f"Run {attempt}: invalid test report: {exc}"],
                               metrics={"runner": runner, "durations_s": durations, "exit_codes": exit_codes}), args.json)
        if results is None and fmt != "exit-code":
            return emit(report(GATE, "ERROR", str(suite), notes=[f"Run {attempt}: expected {fmt} report is missing; exit code is not test evidence."],
                               metrics={"runner": runner, "durations_s": durations, "exit_codes": exit_codes}), args.json)
        all_runs.append(results)

    findings = []
    command_display = " ".join(cmd)
    if all(r is None for r in all_runs):
        # Exit-code-only evidence.
        failed_runs = [i + 1 for i, code in enumerate(exit_codes) if code != 0]
        notes.append("Per-test results unavailable. A successful command does not establish a passing test suite; configure JUnit output.")
        if failed_runs and len(failed_runs) < len(exit_codes):
            findings.append(make_finding(1, "testing", GATE, "flaky-suite", "P1", f"runs {failed_runs} of {len(exit_codes)} failed",
                                         {"command": command_display, "output": tails[failed_runs[0] - 1]},
                                         "The suite passes and fails on identical code.", "Rerun with a parseable runner to find the flaky test, then stabilise it."))
        elif failed_runs:
            findings.append(make_finding(1, "testing", GATE, "suite-failed", "P1", f"all {len(exit_codes)} runs exited non-zero",
                                         {"command": command_display, "output": tails[-1]},
                                         "The test suite fails.", "Read the output in evidence and fix the failing tests or code."))
        metrics = {"runner": runner, "runs": len(exit_codes), "exit_codes": exit_codes, "durations_s": durations}
        return emit(report(GATE, "FAIL" if findings else "NOT-TESTED", str(project), findings, notes, metrics), args.json)

    outcomes = {}
    for results in all_runs:
        for test_id, outcome in (results or {}).items():
            outcomes.setdefault(test_id, []).append(outcome)
    classified = {"passed": [], "failed": [], "flaky": [], "skipped": []}
    for test_id, seen in outcomes.items():
        executed = [o for o in seen if o != "skipped"]
        if not executed:
            classified["skipped"].append(test_id)
        elif all(o == "passed" for o in executed) and len(executed) == len([r for r in all_runs if r is not None]):
            classified["passed"].append(test_id)
        elif all(o == "failed" for o in executed):
            classified["failed"].append(test_id)
        else:
            classified["flaky"].append(test_id)

    for test_id in sorted(classified["failed"]):
        findings.append(make_finding(len(findings) + 1, "testing", GATE, "test-failure", "P1", f"failed in all {len(all_runs)} runs",
                                     {"test": test_id, "command": command_display, "output": tails[-1][-1200:]},
                                     "A test fails consistently.", "Fix the code or the test; reproduce with the command in evidence."))
    for test_id in sorted(classified["flaky"]):
        findings.append(make_finding(len(findings) + 1, "testing", GATE, "flaky-test", "P1", f"outcomes across runs: {outcomes[test_id]}",
                                     {"test": test_id, "command": command_display},
                                     "Non-deterministic test: erodes trust and hides real failures.",
                                     "Remove the nondeterminism (time, randomness, ordering, shared state, network, sleeps); quarantine only with an owner and a deadline."))
    executed_total = len(classified["passed"]) + len(classified["failed"]) + len(classified["flaky"])
    if executed_total == 0:
        findings.append(make_finding(len(findings) + 1, "testing", GATE, "no-tests-executed", "P1", "the runner reported zero executed tests",
                                     {"command": command_display, "output": tails[-1]},
                                     "A green run without tests proves nothing.", "Check test discovery patterns and that tests are not all skipped."))
    if classified["skipped"]:
        notes.append(f"{len(classified['skipped'])} tests skipped in every run (see testing.smells for skip markers).")
    nonzero_without_failures = [c for c in exit_codes if c != 0] and not classified["failed"] and not classified["flaky"] and executed_total
    if nonzero_without_failures:
        findings.append(make_finding(len(findings) + 1, "testing", GATE, "runner-exit-nonzero", "P2", f"exit codes {exit_codes} with no failing test",
                                     {"command": command_display, "output": tails[-1]},
                                     "The runner failed outside individual tests (threshold, setup, teardown or crash).", "Read the output tail and fix the runner error."))

    metrics = {
        "runner": runner,
        "suite": str(suite.relative_to(project)),
        "runs": len(all_runs),
        "tests": len(outcomes),
        "passed": len(classified["passed"]),
        "failed": len(classified["failed"]),
        "flaky": len(classified["flaky"]),
        "skipped": len(classified["skipped"]),
        "pass_rate": round(len(classified["passed"]) / executed_total, 3) if executed_total else 0,
        "durations_s": durations,
    }
    return emit(report(GATE, "FAIL" if findings else "PASS", str(project), findings, notes, metrics, {"results_dir": str(out_dir)}), args.json)


if __name__ == "__main__":
    sys.exit(main())
