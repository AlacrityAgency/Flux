"""Falsifiable debugging experiments, not self-assessed reasoning scores."""

import hashlib
import json
import platform
import re
import subprocess
import tempfile
import time
from pathlib import Path

import ledger
from gatekit import EXIT, report, run
from project import load_config
from projectchecks import parse_checks


def case_digest(case):
    return hashlib.sha256(json.dumps(case, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def load_case(project, case_id):
    if not case_id or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", case_id):
        raise ValueError("Case id must be a lowercase slug")
    path = project / "debug-cases" / (case_id + ".json")
    if project.resolve() not in path.resolve().parents:
        raise ValueError("Case must remain inside the project")
    case = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(case, dict) or type(case.get("version")) is not int or case["version"] != 1 or case.get("id") != case_id:
        raise ValueError("Invalid case version or identity")
    allowed = {"version", "id", "hypothesis", "input", "preconditions", "oracle", "environment",
               "command", "expected", "timeout", "cleanup", "controls"}
    if set(case) - allowed:
        raise ValueError("Unknown case fields: " + ", ".join(sorted(set(case) - allowed)))
    for key in ("hypothesis", "input"):
        if not isinstance(case.get(key), str) or not case[key].strip():
            raise ValueError("Case requires " + key)
    conditions = case.get("preconditions")
    if not isinstance(conditions, list) or not conditions or any(not isinstance(x, str) or not x.strip() for x in conditions):
        raise ValueError("Record the experiment preconditions")
    oracle = case.get("oracle", {})
    if not isinstance(oracle, dict) or any(not isinstance(oracle.get(k), str) or not oracle[k].strip() for k in ("source", "reason")):
        raise ValueError("An independent oracle source and justification are required")
    if set(oracle) != {"source", "reason"}:
        raise ValueError("Oracle accepts only source and reason")
    if case.get("environment") not in {"local", "test"} or case.get("cleanup") != "temporary-data":
        raise ValueError("Experiments require local/test data and temporary-data cleanup")
    if type(case.get("timeout")) is not int or not 1 <= case["timeout"] <= 300:
        raise ValueError("Timeout must be 1..300 seconds per command")
    validate_runner(case)
    controls = case.get("controls", [])
    if not isinstance(controls, list):
        raise ValueError("Controls must be a list")
    for control in controls:
        validate_runner(control)
        if set(control) != {"command", "expected"}:
            raise ValueError("Control accepts only command and expected")
    return case


def validate_runner(value):
    if not isinstance(value, dict):
        raise ValueError("Invalid runner")
    for key in ("command", "expected"):
        items = value.get(key)
        if not isinstance(items, list) or not items or any(not isinstance(x, str) or not x.strip() for x in items):
            raise ValueError("Runner requires nonempty " + key)
    if len(set(value["expected"])) != len(value["expected"]):
        raise ValueError("Expected assertion names must be unique")


def experiment(project, case, runner):
    started = time.monotonic()
    before = ledger.fingerprint(project)
    metrics = {"command": runner["command"], "expected": runner["expected"],
               "fingerprint_before": before}
    # Data and reports get a fresh isolated directory. Commands still see the actual source.
    with tempfile.TemporaryDirectory(prefix="sa-debug-") as temporary:
        output = Path(temporary) / "checks.json"
        argv = [x.replace("{report}", str(output)).replace("{tmp}", temporary) for x in runner["command"]]
        try:
            proc = run(argv, project, case["timeout"], {"SUPERAGENT_REPORT": str(output),
                       "SUPERAGENT_DEBUG_TMP": temporary, "SUPERAGENT_ENVIRONMENT": case["environment"]})
            metrics.update({"command_exit": proc.returncode,
                            "stdout_sha256": hashlib.sha256(proc.stdout.encode()).hexdigest(),
                            "stderr_sha256": hashlib.sha256(proc.stderr.encode()).hexdigest()})
            data = json.loads(output.read_text(encoding="utf-8") if output.is_file() else proc.stdout)
            status, failures, observed = parse_checks(data, runner["expected"])
            metrics["observed"] = observed
            if observed["missing"] or observed["skipped"]:
                outcome = "UNTESTED"
            elif proc.returncode not in (0, 1) or (status == "PASS" and proc.returncode != 0):
                outcome = "INCONCLUSIVE"
            elif any(name in runner["expected"] for name in failures):
                outcome = "CONFIRMED"
            elif status == "PASS":
                outcome = "REFUTED"
            else:
                outcome = "INCONCLUSIVE"
        except FileNotFoundError:
            outcome = "UNTESTED"
            metrics["error"] = "Executable unavailable"
        except (OSError, ValueError, TypeError, subprocess.TimeoutExpired) as exc:
            outcome = "INCONCLUSIVE"
            metrics["error"] = type(exc).__name__
    metrics["duration_s"] = round(time.monotonic() - started, 3)
    metrics["fingerprint_after"] = ledger.fingerprint(project)
    if metrics["fingerprint_after"] != before:
        outcome = "INCONCLUSIVE"
        metrics["error"] = "Experiment changed project source/configuration; evidence is not a read-only reproduction"
    metrics["temporary_data_cleaned"] = not Path(temporary).exists()
    return outcome, metrics


def discover(project):
    import review
    inventory = review.detect(project)
    destination = project / ".superagent" / "debug" / "discovery.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    data = {"phase": "discover", "outcome": "UNTESTED", "fingerprint": ledger.fingerprint(project),
            "inventory": inventory, "cases": sorted(p.stem for p in (project / "debug-cases").glob("*.json")),
            "next": "Trace actual input-to-output paths and write falsifiable cases using modules/debug/workflow.md. No hypothesis has been tested."}
    destination.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return data, 2


def execute(project, phase, case_id):
    case = load_case(project, case_id)
    if load_config(project).get("environment") == "production":
        raise ValueError("Debug experiments are not authorized against production")
    digest = case_digest(case)
    prior = None
    if phase == "verify-fix":
        candidates = [r for r in ledger.load(project) if r.get("gate") == "debug.experiment"
                      and r.get("scope") == case_id and r.get("status") == "FAIL"]
        if candidates:
            record = candidates[-1]
            if ledger.intact(project, record):
                prior_report = json.loads((project / record["report"]).read_text(encoding="utf-8"))
                if prior_report["metrics"].get("case_sha256") == digest:
                    baseline_controls = prior_report["metrics"].get("controls", [])
                    if baseline_controls and all(c["outcome"] == "REFUTED" for c in baseline_controls):
                        prior = record
        if not prior or not case.get("controls") or prior["fingerprint"] == ledger.fingerprint(project):
            return {"phase": phase, "outcome": "INCONCLUSIVE", "fix_verified": False,
                    "reason": "Require intact prior CONFIRMED reproduction, unchanged case/oracle, a source change and healthy controls."}, 2
    outcome, observation = experiment(project, case, case)
    controls = []
    for runner in case.get("controls", []):
        control_outcome, control_metrics = experiment(project, case, runner)
        controls.append({"outcome": control_outcome, "observation": control_metrics})
    verified = phase == "verify-fix" and outcome == "REFUTED" and all(c["outcome"] == "REFUTED" for c in controls)
    status = "FAIL" if outcome == "CONFIRMED" else "PASS" if outcome == "REFUTED" and (phase != "verify-fix" or verified) else "NOT-TESTED"
    metrics = {"phase": phase, "outcome": outcome, "case_sha256": digest, "hypothesis": case["hypothesis"],
               "oracle": case["oracle"], "observation": observation, "controls": controls,
               "fix_verified": verified, "prior_run": prior["run"] if prior else None}
    gate = "debug.verify-fix" if phase == "verify-fix" else "debug.experiment"
    evidence = report(gate, status, str(project), metrics=metrics,
                      notes=["The oracle and named assertions require independent review. REFUTED covers tested inputs only, not absence of all bugs."])
    evidence["provenance"] = {"python": platform.python_version(), "platform": platform.system(),
                              "skill_version": (Path(__file__).resolve().parents[2] / "VERSION").read_text().strip()}
    record = ledger.append(project, gate, case["command"], evidence, observation["duration_s"],
                           observation["fingerprint_before"], case_id)
    evidence["ledger"] = record
    return evidence, EXIT[status]
