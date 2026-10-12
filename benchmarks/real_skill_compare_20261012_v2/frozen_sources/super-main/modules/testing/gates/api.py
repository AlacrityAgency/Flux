#!/usr/bin/env python3
"""testing.api: property-based API testing against the OpenAPI contract (Schemathesis).

Generates valid and edge-case requests from the spec and checks universal properties:
no 5xx responses, responses match the documented schema, status codes and content types are
documented. Needs a running backend (--url), an OpenAPI/Swagger spec and the schemathesis CLI.
Only run against local or dedicated test environments: generated requests can create data.
"""

import re
import shutil
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
import testlib  # noqa: E402
from gatekit import base_parser, emit, make_finding, project_root, report, run, work_dir  # noqa: E402


GATE = "testing.api"
LOCAL_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}


def main():
    parser = base_parser("Property-based API contract testing with Schemathesis")
    parser.add_argument("--url", help="Base URL of the running API (e.g. http://localhost:8000)")
    parser.add_argument("--spec", help="OpenAPI spec path or URL (auto-detected in the project)")
    parser.add_argument("--max-examples", type=int, default=25)
    parser.add_argument("--allow-remote", action="store_true", help="Allow a non-local URL (only for dedicated test environments)")
    parser.add_argument("--timeout", type=int, default=1800)
    args = parser.parse_args()
    project = project_root(args.project)

    spec = args.spec
    if not spec:
        found = [p for p in testlib.iter_project_files(project, {".json", ".yaml", ".yml"}) if re.match(r"^(openapi|swagger)[\w.-]*\.(json|ya?ml)$", p.name, re.I)]
        spec = str(found[0]) if found else None
    if not spec:
        return emit(report(GATE, "NOT-TESTED", str(project), notes=["No OpenAPI/Swagger spec found; pass --spec."]), args.json)
    if not args.url:
        return emit(report(GATE, "NOT-TESTED", str(project), notes=["No --url: start the backend locally and pass its base URL."]), args.json)
    host = urlparse(args.url).hostname or ""
    if host not in LOCAL_HOSTS and not host.endswith((".localhost", ".test")) and not args.allow_remote:
        return emit(report(GATE, "NOT-TESTED", args.url, notes=["Refusing to fuzz a non-local URL without --allow-remote (generated requests can modify data)."]), args.json)
    exe = shutil.which("schemathesis") or shutil.which("st")
    if not exe:
        return emit(report(GATE, "NOT-TESTED", args.url, notes=["schemathesis is not installed: pip install schemathesis"]), args.json)

    try:
        version_proc = run([exe, "--version"], project, 60)
        match = re.search(r"(\d+)\.\d+", version_proc.stdout)
        if version_proc.returncode or not match or int(match.group(1)) not in (3, 4):
            raise ValueError("Unsupported or unrecognized Schemathesis version; expected 3.x or 4.x")
        version, major = version_proc.stdout.strip(), int(match.group(1))
    except Exception as exc:
        return emit(report(GATE, "ERROR", args.url, notes=[str(exc)]), args.json)
    out_dir = work_dir(project, "testing", "api")
    url_flag = "--url" if major >= 4 else "--base-url"
    cmd = [exe, "run", spec, url_flag, args.url, "--checks", "all"]
    cmd += ["--max-examples", str(args.max_examples)] if major >= 4 else ["--hypothesis-max-examples", str(args.max_examples)]
    junit = out_dir / "junit.xml"
    junit.unlink(missing_ok=True)
    cmd += ["--report", "junit", "--report-junit-path", str(junit)] if major >= 4 else ["--junit-xml", str(junit)]
    try:
        proc = run(cmd, project, args.timeout)
    except Exception as exc:
        return emit(report(GATE, "ERROR", args.url, notes=[f"schemathesis did not complete: {exc}"]), args.json)
    output = proc.stdout + proc.stderr
    (out_dir / "schemathesis.log").write_text(output, encoding="utf-8")

    try:
        outcomes = testlib.parse_junit(junit)
    except Exception as exc:
        return emit(report(GATE, "ERROR", args.url, notes=["No valid fresh JUnit evidence: " + type(exc).__name__]), args.json)
    executed = sum(v != "skipped" for v in outcomes.values())
    skipped = sum(v == "skipped" for v in outcomes.values())
    failed = sum(v == "failed" for v in outcomes.values())
    status = "FAIL" if failed else "ERROR" if proc.returncode else "NOT-TESTED" if not executed or skipped else "PASS"

    findings = []
    if failed:
        failures = re.findall(r"^\s*(?:\d+\.\s*)?(Server error|Response violates schema|Undocumented (?:HTTP status code|Content-Type)|Unsupported method|Missing Content-Type|Negative data rejection|Positive data acceptance|[A-Z][\w ]+ violat\w+)\b.*$", output, re.M)
        rules = sorted(set(failures)) or ["api-contract-failure"]
        for rule in rules:
            findings.append(make_finding(len(findings) + 1, "testing", GATE, re.sub(r"\W+", "-", rule.lower()).strip("-"), "P1",
                                         f"schemathesis run against {args.url}", {"spec": spec, "log": str(out_dir / "schemathesis.log"), "output": output[-2000:]},
                                         "The API breaks its documented contract or crashes on generated input.",
                                         "Reproduce with the curl command printed in the log, then fix the handler or the spec."))
    metrics = {"spec": spec, "url": args.url, "schemathesis_major": major, "version": version,
               "exit_code": proc.returncode, "executed_operations": executed, "skipped_operations": skipped}
    notes = ["Evidence covers reported operations only; authorization and business invariants need separate scenarios."]
    if status == "NOT-TESTED":
        notes.append("Zero executed or skipped API operations cannot establish a complete contract pass.")
    return emit(report(GATE, status, args.url, findings, notes, metrics,
                       {"log": str(out_dir / "schemathesis.log"), "junit": str(junit)}), args.json)


if __name__ == "__main__":
    sys.exit(main())
