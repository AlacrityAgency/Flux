#!/usr/bin/env python3
"""Coverage is a mapping to named observations, not a product quality score."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "core/lib"))
import ledger
from gatekit import base_parser, emit, project_root, report, work_dir
from project import load_config

GATE = "product.coverage"


def main():
    parser = base_parser("Check each applicable product area against named scenario evidence")
    parser.add_argument("--review-id")
    args = parser.parse_args()
    project = project_root(args.project)
    try:
        config = load_config(project)
    except (OSError, ValueError) as exc:
        return emit(report(GATE, "ERROR", str(project), notes=[str(exc)]), args.json)
    if not config.get("product"):
        return emit(report(GATE, "NOT-TESTED", str(project), notes=["Define product.areas and mapped acceptance criteria in superagent.json."]), args.json)
    latest = {}
    for record in ledger.load(project):
        if args.review_id and record.get("review_id") != args.review_id:
            continue
        if record.get("scope") is None:
            latest[record["gate"]] = record
    fingerprint = ledger.fingerprint(project)
    criteria = {row["id"]: row for row in config["acceptance"]}
    evidence, gaps, failures = {}, [], []
    for name, area in config["product"]["areas"].items():
        if not area["applicable"]:
            evidence[name] = {"status": "NOT-APPLICABLE", "reason": area["reason"]}
            continue
        observations = []
        for item in area["criteria"]:
            criterion = criteria[item]
            record = latest.get(criterion["gate"])
            status = "NOT-TESTED"
            trace = criterion.get("trace", {})
            trace_complete = set(trace) == {"design", "content", "code", "tests"}
            if trace_complete:
                for reference in trace.values():
                    if reference["applicable"] and any(not (project / p).is_file() or (project / p).is_symlink() for p in reference["paths"]):
                        trace_complete = False
            if record and record["fingerprint"] == fingerprint and ledger.intact(project, record):
                data = json.loads((project / record["report"]).read_text())
                rows = data.get("metrics", {}).get("scenarios", [])
                scenario = next((r for r in rows if r["name"] == criterion["scenario"]), None)
                if scenario and scenario["status"] in {"PASS", "FAIL"} and scenario["executed"] > 0:
                    status = scenario["status"] if data["status"] in {"PASS", "FAIL"} else "NOT-TESTED"
            if not trace_complete and status == "PASS":
                status = "NOT-TESTED"
            if status == "FAIL":
                failures.append(item)
            elif status != "PASS":
                gaps.append(item)
            observations.append({"criterion": item, "gate": criterion["gate"], "scenario": criterion["scenario"],
                                 "status": status, "run": record["run"] if record else None,
                                 "trace_complete": trace_complete, "trace": trace})
        evidence[name] = {"status": "FAIL" if any(r["status"] == "FAIL" for r in observations) else
                          "NOT-TESTED" if any(r["status"] != "PASS" for r in observations) else "PASS", "criteria": observations}
    output = work_dir(project, "product") / "coverage.json"
    output.write_text(json.dumps({"areas": evidence, "source_fingerprint": fingerprint}, indent=2), encoding="utf-8")
    markdown = output.with_suffix(".md")
    lines = ["# Product Coverage and Requirement Trace", "", "| Area | Status | Criteria and observed runs |", "|---|---|---|"]
    for name, row in evidence.items():
        detail = row.get("reason", "; ".join(r["criterion"] + ":" + r["status"] + " (" + str(r["run"]) + ")" for r in row.get("criteria", [])))
        lines.append("| " + name + " | " + row["status"] + " | " + detail.replace("|", "\\|").replace("\n", " ") + " |")
    lines += ["", "See coverage.json for design/content/code/test artifact links. File existence is structural evidence; it does not establish semantic correctness."]
    markdown.write_text("\n".join(lines), encoding="utf-8")
    return emit(report(GATE, "FAIL" if failures else "NOT-TESTED" if gaps else "PASS", str(project),
                       notes=["Covers declared named assertions only. Independently review requirements, applicability reasons and assertion quality; this is not UX/clinical/legal certification."],
                       metrics={"areas": evidence, "missing": sorted(set(gaps)), "failed": sorted(set(failures))},
                       artifacts={"coverage": str(output), "matrix": str(markdown)}), args.json)


if __name__ == "__main__":
    sys.exit(main())
