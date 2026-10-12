"""Semgrep/Trivy adapters. Scanner findings require triage, not claims of exploitability."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "core" / "lib"))
from gatekit import base_parser, emit, make_finding, project_root, report, work_dir
from project import load_config


def normalize(tool, data):
    if not isinstance(data, dict):
        raise ValueError("Expected a scanner JSON object")
    rows = []
    if tool == "semgrep":
        if data.get("errors"):
            raise ValueError("Semgrep reported scan errors")
        paths = data.get("paths", {}).get("scanned")
        if not isinstance(paths, list) or not paths or not isinstance(data.get("results"), list):
            raise ValueError("Semgrep did not report scanned paths and results")
        for hit in data["results"]:
            if not isinstance(hit, dict) or not hit.get("check_id") or not hit.get("path"):
                raise ValueError("Malformed Semgrep finding")
            rows.append({"rule": hit["check_id"], "file": hit["path"], "line": hit.get("start", {}).get("line"),
                         "severity": hit.get("extra", {}).get("severity", "UNKNOWN")})
        return rows, len(paths)
    if data.get("SchemaVersion") != 2 or not data.get("ArtifactName") or not isinstance(data.get("Results"), list) or not data["Results"]:
        raise ValueError("Trivy did not report an evaluated artifact (SchemaVersion 2)")
    for result in data["Results"]:
        for group in ("Vulnerabilities", "Misconfigurations", "Secrets"):
            for hit in result.get(group) or []:
                if group == "Misconfigurations" and hit.get("Status") == "PASS":
                    continue
                rows.append({"rule": hit.get("VulnerabilityID") or hit.get("ID") or hit.get("RuleID") or group,
                             "file": result.get("Target"), "severity": hit.get("Severity", "UNKNOWN")})
    return rows, len(data["Results"])


def main():
    parser = base_parser("Run a security scanner with machine-readable evidence")
    parser.add_argument("--tool", choices=["semgrep", "trivy"], required=True)
    args = parser.parse_args()
    gate = "security.sast" if args.tool == "semgrep" else "security.dependencies"
    project = project_root(args.project)
    exe = shutil.which(args.tool)
    if not exe:
        return emit(report(gate, "NOT-TESTED", str(project), notes=[args.tool + " is not installed."]), args.json)
    try:
        check = load_config(project).get("checks", {}).get(gate, {})
        if args.tool == "semgrep":
            rules = check.get("rules")
            rule_path = (project / rules).resolve() if isinstance(rules, str) else None
            if not rule_path or not rule_path.is_file() or project not in rule_path.parents:
                return emit(report(gate, "NOT-TESTED", str(project), notes=["Configure a project-local Semgrep rules file in checks.security.sast.rules."]), args.json)
            cmd = [exe, "scan", "--json", "--metrics", "off", "--config", str(rule_path), str(project)]
        else:
            cmd = [exe, "fs", "--format", "json", "--scanners", "vuln,misconfig,secret", "--exit-code", "0", str(project)]
        version = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=30)
        if version.returncode:
            raise ValueError("Scanner version probe failed")
        proc = subprocess.run(cmd, cwd=project, capture_output=True, text=True, timeout=check.get("timeout", 300))
        if proc.returncode:
            raise ValueError("Scanner failed to complete; process exit " + str(proc.returncode))
        rows, scanned = normalize(args.tool, json.loads(proc.stdout))
    except (OSError, ValueError, TypeError, AttributeError, subprocess.TimeoutExpired) as exc:
        return emit(report(gate, "ERROR", str(project), notes=["Scanner evidence unavailable: " + str(exc)]), args.json)
    # Never persist matched source or secret values from raw scanner reports.
    path = work_dir(project, "security") / (args.tool + ".json")
    path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    findings = [make_finding(i + 1, "security", gate, "scanner-finding", "P1" if row["severity"].upper() in {"ERROR", "HIGH", "CRITICAL"} else "P2",
                             str(row["file"]), row, "The scanner reported a security issue requiring triage; exploitability is not established.",
                             "Review the rule and affected code/dependency; fix it or justify a narrowly scoped scanner exclusion.")
                for i, row in enumerate(rows)]
    return emit(report(gate, "FAIL" if findings else "PASS", str(project), findings,
                       ["A clean scan covers configured rules and scanner scope only, not complete application security."],
                       {"tool": args.tool, "version": version.stdout.strip(), "scanned": scanned}, {"findings": str(path)}), args.json)


if __name__ == "__main__":
    sys.exit(main())
