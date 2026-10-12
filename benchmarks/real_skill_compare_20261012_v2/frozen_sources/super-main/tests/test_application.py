"""Executable checks for full-stack planning and adversarial evidence contracts."""

import importlib.util
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core" / "lib"))
import ledger
from project import load_config, requirements
from projectchecks import parse_checks, parse_k6


def import_file(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sa = import_file("sa_application", ROOT / "core" / "bin" / "sa.py")
scan = import_file("security_scan", ROOT / "modules" / "security" / "gates" / "scan.py")
api = import_file("api_application", ROOT / "modules" / "testing" / "gates" / "api.py")


class ApplicationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name)

    def config(self, **kwargs):
        data = {"version": 1, **kwargs}
        (self.project / "superagent.json").write_text(json.dumps(data))
        return data

    def cli(self, *args):
        proc = subprocess.run([sys.executable, "-B", str(ROOT / "core" / "bin" / "sa.py"),
                               "--project", str(self.project), *args], capture_output=True, text=True, timeout=60)
        return proc, json.loads(proc.stdout) if proc.stdout.strip().startswith("{") else None

    def runner(self, payload, exit_code=0, gate="backend.behavior", expected=None):
        command = [sys.executable, "-c", "import json; print(" + repr(json.dumps(payload)) + "); raise SystemExit(" + str(exit_code) + ")"]
        self.config(checks={gate: {"command": command, "expected": expected or ["required"]}})

    def test_six_modes_are_plannable_without_side_effects(self):
        self.config(profile="saas")
        for mode in ("design", "build", "change", "audit", "test", "release-check"):
            with self.subTest(mode=mode):
                proc, data = self.cli("plan", "--mode", mode, "--json")
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertEqual(data["mode"], mode)
                self.assertIn("security.authorization", data["required"])
        self.assertFalse((self.project / ".superagent").exists())

    def test_profiles_preserve_sensitive_checks_in_quick_mode(self):
        inv = {"layers": [], "openapi_specs": [], "databases": []}
        _, _, gates = requirements({"profile": "commerce"}, inv, depth="quick")
        self.assertTrue({"backend.idempotency", "security.authorization", "data.integration", "ui-ux.journey"} <= set(gates))

    def test_release_requires_recovery_and_load_and_cannot_skip(self):
        self.config(profile="web-app")
        proc, data = self.cli("review", "--mode", "release-check", "--dry-run", "--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue({"data.restore", "operations.load", "operations.resilience", "delivery.rollback", "delivery.build"} <= set(data["plan"]["required"]))
        proc, _ = self.cli("review", "--mode", "release-check", "--skip", "security.sast", "--dry-run")
        self.assertEqual(proc.returncode, 3)

    def test_config_rejects_invalid_types_and_unmapped_acceptance(self):
        for data in ({"features": [{}]}, {"environment": []}, {"profile": {}},
                     {"acceptance": [{"id": "A", "criterion": "persist", "gate": "backend.behavior", "scenario": "missing"}]}):
            with self.subTest(data=data):
                self.config(**data)
                with self.assertRaises(ValueError):
                    load_config(self.project)

    def test_skips_and_missing_required_are_not_passes(self):
        for payload in ({"checks": [{"name": "required", "status": "SKIP", "executed": 0}]},
                        {"checks": [{"name": "unrelated", "status": "PASS", "executed": 1}]}):
            self.runner(payload)
            proc, data = self.cli("gate", "backend.behavior", "--json")
            self.assertEqual(proc.returncode, 2, proc.stderr)
            self.assertEqual(data["status"], "NOT-TESTED")

    def test_zero_assertions_and_self_assessed_verdict_are_errors(self):
        for payload in ({"status": "PASS"}, {"checks": []},
                        {"checks": [{"name": "required", "status": "PASS", "executed": 0}]}):
            self.runner(payload)
            proc, data = self.cli("gate", "backend.behavior", "--json")
            self.assertEqual(proc.returncode, 3)
            self.assertEqual(data["status"], "ERROR")

    def test_nonzero_pass_is_error_not_success(self):
        self.runner({"checks": [{"name": "required", "status": "PASS", "executed": 1}]}, exit_code=1)
        proc, data = self.cli("gate", "backend.behavior", "--json")
        self.assertEqual(proc.returncode, 3)
        self.assertEqual(data["status"], "ERROR")

    def test_stale_report_is_deleted_before_command(self):
        path = self.project / ".superagent" / "checks" / "backend.behavior" / "result.json"
        path.parent.mkdir(parents=True)
        path.write_text('{"checks":[{"name":"required","status":"PASS","executed":1}]}')
        self.config(checks={"backend.behavior": {"command": [sys.executable, "-c", "pass"], "expected": ["required"]}})
        proc, data = self.cli("gate", "backend.behavior", "--json")
        self.assertEqual(proc.returncode, 3)
        self.assertEqual(data["status"], "ERROR")

    def test_production_runner_is_not_executed(self):
        self.runner({"checks": [{"name": "required", "status": "PASS", "executed": 1}]})
        data = load_config(self.project)
        self.config(**{k: v for k, v in {**data, "environment": "production"}.items() if k != "version"})
        proc, data = self.cli("gate", "backend.behavior", "--json")
        self.assertEqual(proc.returncode, 2)
        self.assertIn("production", data["notes"][0])

    def test_real_http_database_fixture_accepts_good_rejects_known_defects(self):
        expected = ["persistence", "ownership", "idempotency", "validation"]
        for bug, scenario in ((None, None), ("ownership", "ownership"), ("replay", "idempotency"), ("persistence", "persistence")):
            command = [sys.executable, "-B", str(ROOT / "tests" / "fixtures" / "application" / "check_service.py")]
            if bug:
                command += ["--bug", bug]
            self.config(checks={"backend.behavior": {"command": command, "expected": expected}})
            proc, data = self.cli("gate", "backend.behavior", "--json")
            self.assertEqual(proc.returncode, 1 if bug else 0, proc.stderr + str(data))
            if bug:
                self.assertIn(scenario, [f["condition"] for f in data["findings"]])
            else:
                self.assertEqual(data["metrics"]["executed"], 10)
                self.assertEqual(data["provenance"]["fingerprint_before"], data["provenance"]["fingerprint_after"])

    def test_content_change_with_preserved_size_mtime_invalidates_evidence(self):
        source = self.project / "app.py"
        source.write_text("x = 1\n")
        before = ledger.fingerprint(self.project)
        stat = source.stat()
        source.write_text("x = 2\n")
        os.utime(source, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        self.assertNotEqual(before, ledger.fingerprint(self.project))

    def test_change_during_gate_is_stale_not_certified(self):
        script = self.project / "gate.py"
        script.write_text("import json\nfrom pathlib import Path\nPath(__file__).with_name('app.py').write_text('changed')\nprint(json.dumps({'gate':'backend.behavior','status':'PASS','exit_code':0,'findings':[]}))\n")
        sa.run_gate({"script_path": script}, "backend.behavior", self.project, [], 10)
        self.assertEqual(ledger.verdict(self.project, {}, ["backend.behavior"])["overall"], "STALE")

    def test_gate_process_exit_must_match_report(self):
        script = self.project / "gate.py"
        script.write_text("import json\nprint(json.dumps({'gate':'backend.behavior','status':'PASS','exit_code':0,'findings':[]}))\nraise SystemExit(1)\n")
        result, _, _ = sa.run_gate({"script_path": script}, "backend.behavior", self.project, [], 10)
        self.assertEqual(result["status"], "ERROR")

    def test_k6_requires_activity_and_named_thresholds(self):
        report = {"metrics": {"iterations": {"values": {"count": 1}},
                              "http_req_duration": {"thresholds": {"p(95)<500": {"ok": True}}}}}
        self.assertEqual(parse_k6(report, ["http_req_duration:p(95)<500"])[0], "PASS")
        self.assertEqual(parse_k6(report, ["absent"])[0], "NOT-TESTED")
        report["metrics"]["http_req_duration"]["thresholds"]["p(95)<500"]["ok"] = False
        self.assertEqual(parse_k6(report, ["http_req_duration:p(95)<500"])[0], "FAIL")
        report["metrics"]["iterations"]["values"]["count"] = 0
        with self.assertRaises(ValueError):
            parse_k6(report, [])

    def test_security_schemas_require_scanned_scope_and_redact_secrets(self):
        with self.assertRaises(ValueError):
            scan.normalize("semgrep", {"results": [], "paths": {"scanned": []}})
        rows, count = scan.normalize("semgrep", {"results": [], "paths": {"scanned": ["app.py"]}})
        self.assertEqual((rows, count), ([], 1))
        with self.assertRaises(ValueError):
            scan.normalize("trivy", {"SchemaVersion": 2, "ArtifactName": "app", "Results": []})
        rows, count = scan.normalize("trivy", {"SchemaVersion": 2, "ArtifactName": "app", "Results": [
            {"Target": "config", "Secrets": [{"RuleID": "token", "Severity": "HIGH", "Match": "do-not-store"}]}]})
        self.assertEqual(count, 1)
        self.assertNotIn("do-not-store", json.dumps(rows))

    def test_release_pass_without_acceptance_is_not_ready(self):
        args = SimpleNamespace(project=str(self.project), mode="release-check", skip=None, depth="quick",
                               url=[], sandbox=[], api_url=None, base=None, coverage_cmd=None,
                               level="AA", doc=[], profile=None, json=True, dry_run=False, timeout=30)
        plan = {"depth": "quick", "layers": [], "shape": "pyramid", "steps": [], "required": []}
        verdict = {**ledger.verdict(self.project, {}), "overall": "PASSED", "label": "[QA-PASSED]", "exit_code": 0}
        output = io.StringIO()
        with patch.object(sa.review_lib, "build_plan", return_value=plan), \
             patch.object(sa.ledger, "verdict", return_value=verdict), \
             contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
            code = sa.cmd_review(args)
        self.assertEqual(code, 2)
        self.assertFalse(json.loads(output.getvalue())["verdict"]["release_ready"])

    def test_api_contract_needs_fresh_executed_non_skipped_operations(self):
        cases = [("<testsuite><testcase name='GET /'/></testsuite>", 0, 0),
                 ("<testsuite/>", 0, 2),
                 ("<testsuite><testcase name='GET /'><skipped/></testcase></testsuite>", 0, 2),
                 ("<testsuite><testcase name='GET /'><failure/></testcase></testsuite>", 1, 1),
                 ("<testsuite><testcase name='GET /'/></testsuite>", 1, 3),
                 (None, 0, 3)]
        for xml, process_exit, expected_exit in cases:
            with self.subTest(xml=xml, process_exit=process_exit):
                def run(command, *args):
                    if "--version" in command:
                        return subprocess.CompletedProcess(command, 0, "Schemathesis 4.0.0", "")
                    self.assertIn("--report", command)
                    path = Path(command[command.index("--report-junit-path") + 1])
                    if xml:
                        path.write_text(xml)
                    return subprocess.CompletedProcess(command, process_exit, "", "")
                output = io.StringIO()
                with patch.object(api, "run", side_effect=run), patch.object(api.shutil, "which", return_value="schemathesis"), \
                     patch.object(sys, "argv", ["api", "--project", str(self.project), "--url", "http://localhost:8000",
                                                 "--spec", "openapi.json", "--json"]), contextlib.redirect_stdout(output):
                    code = api.main()
                self.assertEqual(code, expected_exit, output.getvalue())

    def test_generic_gate_rejects_duplicate_names_and_boolean_counts(self):
        row = {"name": "required", "status": "PASS", "executed": 1}
        for rows in ([row, row], [{**row, "executed": True}]):
            with self.assertRaises(ValueError):
                parse_checks({"checks": rows}, ["required"])

    def test_no_release_criterion_can_be_a_scanner_verdict(self):
        self.config(acceptance=[{"id": "A", "criterion": "Business workflow works", "gate": "security.sast", "scenario": "clean"}])
        with self.assertRaises(ValueError):
            load_config(self.project)


if __name__ == "__main__":
    unittest.main()
