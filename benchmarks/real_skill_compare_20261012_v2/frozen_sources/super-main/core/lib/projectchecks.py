"""Run project-specific scenarios; a successful process alone is never test evidence."""

import json
import math
import os
import subprocess
from pathlib import Path

from gatekit import base_parser, emit, make_finding, project_root, report, work_dir, run
from project import COMMAND_GATES, load_config


def parse_checks(data, expected):
    if not isinstance(data, dict) or not isinstance(data.get("checks"), list) or not data["checks"]:
        raise ValueError("Expected a nonempty checks array, not a self-assessed verdict")
    checks = data["checks"]
    names = set()
    for row in checks:
        if not isinstance(row, dict) or not isinstance(row.get("name"), str) or not row["name"] or row["name"] in names:
            raise ValueError("Checks require unique scenario names")
        names.add(row["name"])
        if row.get("status") not in {"PASS", "FAIL", "SKIP"}:
            raise ValueError("Unknown scenario status")
        if type(row.get("executed")) is not int or row["executed"] < 0:
            raise ValueError("Each scenario needs an integer executed count")
        if row["status"] in {"PASS", "FAIL"} and row["executed"] < 1:
            raise ValueError("A scenario cannot pass/fail with zero executed assertions")
    missing = sorted(set(expected) - names)
    failures = [r["name"] for r in checks if r["status"] == "FAIL"]
    skipped = [r["name"] for r in checks if r["status"] == "SKIP"]
    status = "FAIL" if failures else "NOT-TESTED" if missing or skipped else "PASS"
    return status, failures, {"executed": sum(r["executed"] for r in checks), "scenarios": checks,
                              "missing": missing, "skipped": skipped}


def parse_k6(data, expected):
    metrics = data.get("metrics", {}) if isinstance(data, dict) else {}
    iteration_metric = metrics.get("iterations", {})
    nested = "values" in iteration_metric
    iterations = iteration_metric.get("values", {}).get("count", 0) if nested else iteration_metric.get("count", 0)
    if type(iterations) not in (int, float) or not math.isfinite(iterations) or iterations <= 0:
        raise ValueError("k6 must execute at least one iteration")
    rows = []
    for metric, details in metrics.items():
        for threshold, outcome in details.get("thresholds", {}).items():
            if nested and isinstance(outcome, dict) and type(outcome.get("ok")) is bool:
                passed = outcome["ok"]
            elif not nested and type(outcome) is bool:
                passed = not outcome  # Legacy --summary-export stores failure, not success.
            else:
                raise ValueError("Invalid k6 threshold outcome")
            rows.append({"name": metric + ":" + threshold, "status": "PASS" if passed else "FAIL", "executed": 1})
    return parse_checks({"checks": rows}, expected)


def main(allowed):
    parser = base_parser("Execute configured project scenarios and record their observed outcomes")
    parser.add_argument("--check", choices=sorted(allowed), required=True)
    args = parser.parse_args()
    gate = args.check
    project = project_root(args.project)
    try:
        config = load_config(project)
    except (OSError, ValueError) as exc:
        return emit(report(gate, "ERROR", str(project), notes=[str(exc)]), args.json)
    check = config.get("checks", {}).get(gate)
    if not check:
        return emit(report(gate, "NOT-TESTED", str(project), notes=["Configure this gate's command and expected scenarios in superagent.json."]), args.json)
    if config.get("environment") == "production" and gate != "delivery.build":
        return emit(report(gate, "NOT-TESTED", str(project), notes=["Run these scenarios on local or dedicated test data, not production."]), args.json)
    out = work_dir(project, "checks", gate)
    output = out / "result.json"
    output.unlink(missing_ok=True)
    argv = [x.replace("{report}", str(output)) for x in check["command"]]
    env = {**os.environ, "SUPERAGENT_REPORT": str(output)}
    try:
        proc = run(argv, project, check.get("timeout", 300), env)
    except FileNotFoundError:
        return emit(report(gate, "NOT-TESTED", str(project), notes=["Configured command executable is unavailable."]), args.json)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return emit(report(gate, "ERROR", str(project), notes=[type(exc).__name__ + ": scenario runner did not complete"]), args.json)
    try:
        data = json.loads(output.read_text(encoding="utf-8") if output.is_file() else proc.stdout)
        parse = parse_k6 if check.get("format") == "k6" else parse_checks
        status, failures, metrics = parse(data, check["expected"])
        # Nonzero without observed failing assertions is a runner/environment problem.
        if proc.returncode != 0 and status != "FAIL":
            status = "ERROR"
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        return emit(report(gate, "ERROR", str(project), notes=["Runner did not provide valid fresh evidence: " + str(exc)],
                           metrics={"command_exit": proc.returncode}), args.json)
    findings = [make_finding(i + 1, gate.split(".")[0], gate, "scenario-failed", "P1", name,
                             {"scenario": name, "command_exit": proc.returncode},
                             "The configured behavioural assertion failed.", "Reproduce the named scenario and fix the implementation or explain a corrected assertion.")
                for i, name in enumerate(failures)]
    metrics.update({"command_exit": proc.returncode, "command": argv})
    # Store only normalized outcomes, not raw stdout/stderr that may contain credentials.
    output.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    notes = ["Evidence covers named assertions only; review the runner and assertions independently."]
    if metrics["missing"] or metrics["skipped"]:
        notes.append("Missing or skipped scenarios are not a pass.")
    return emit(report(gate, status, str(project), findings, notes, metrics, {"scenarios": str(output)}), args.json)
