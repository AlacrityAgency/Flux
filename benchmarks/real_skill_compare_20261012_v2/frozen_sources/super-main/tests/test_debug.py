"""Real subprocess experiments and regressions for the six evidence defects."""

import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core" / "lib"))
import debugger
import ledger
import review
from gatekit import report, run
from projectchecks import parse_k6

SA = ROOT / "core" / "bin" / "sa.py"
RUNNER = ROOT / "tests" / "fixtures" / "debug" / "check_duration.py"
GOOD = "import math\ndef valid_duration(value):\n    return type(value) in (int, float) and math.isfinite(value) and value >= 0\n"
BUGGY = "def valid_duration(value):\n    return bool(value) if isinstance(value, str) else value >= 0\n"


class DebugTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="sa-debug-tests-")
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name)
        (self.project / "duration_app.py").write_text(BUGGY)
        self.case = {"version": 1, "id": "invalid-duration", "hypothesis": "Validator accepts a string",
                     "input": "banana", "preconditions": ["Local isolated validator; no live data"],
                     "oracle": {"source": "Motion requirement: finite nonnegative numeric duration", "reason": "Compare the result with explicit healthy contract"},
                     "environment": "local", "command": [sys.executable, "-B", str(RUNNER)],
                     "expected": ["invalid-duration-rejected"], "timeout": 5, "cleanup": "temporary-data",
                     "controls": [{"command": [sys.executable, "-B", str(RUNNER), "--control"],
                                   "expected": ["valid-duration-accepted", "negative-duration-rejected"]}]}
        self.save_case()

    def save_case(self):
        path = self.project / "debug-cases" / "invalid-duration.json"
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(self.case))

    def cli(self, *args):
        proc = subprocess.run([sys.executable, "-B", str(SA), "--project", str(self.project), *args,
                               "--json"], capture_output=True, text=True, timeout=90)
        return proc.returncode, json.loads(proc.stdout)

    def payload(self, checks, exit_code=0):
        self.case["command"] = [sys.executable, "-B", "-c", "print(" + repr(json.dumps({"checks": checks})) + "); raise SystemExit(" + str(exit_code) + ")"]
        self.save_case()

    def test_discovery_never_claims_a_tested_finding(self):
        code, data = self.cli("debug", "--phase", "discover")
        self.assertEqual(code, 2)
        self.assertEqual(data["outcome"], "UNTESTED")
        self.assertIn("invalid-duration", data["cases"])
        self.assertEqual(ledger.load(self.project), [])

    def test_seeded_bug_and_healthy_control_are_distinguished(self):
        code, data = self.cli("debug", "--phase", "reproduce", "--case", self.case["id"])
        self.assertEqual((code, data["metrics"]["outcome"]), (1, "CONFIRMED"))
        self.assertTrue(ledger.intact(self.project, data["ledger"]))
        (self.project / "duration_app.py").write_text(GOOD)
        code, data = self.cli("debug", "--phase", "reproduce", "--case", self.case["id"])
        self.assertEqual((code, data["metrics"]["outcome"]), (0, "REFUTED"))

    def test_fix_requires_baseline_same_oracle_and_passing_controls(self):
        _, baseline = self.cli("debug", "--phase", "reproduce", "--case", self.case["id"])
        (self.project / "duration_app.py").write_text(GOOD)
        code, data = self.cli("debug", "--phase", "verify-fix", "--case", self.case["id"])
        self.assertEqual(code, 0, data)
        self.assertTrue(data["metrics"]["fix_verified"])
        self.assertEqual(data["metrics"]["prior_run"], baseline["ledger"]["run"])
        self.assertEqual(len(data["metrics"]["controls"]), 1)

    def test_always_rejecting_inputs_is_not_a_verified_fix(self):
        self.cli("debug", "--phase", "reproduce", "--case", self.case["id"])
        (self.project / "duration_app.py").write_text("def valid_duration(value):\n    return False\n")
        code, data = self.cli("debug", "--phase", "verify-fix", "--case", self.case["id"])
        self.assertEqual(code, 2)
        self.assertFalse(data["metrics"]["fix_verified"])
        self.assertEqual(data["metrics"]["controls"][0]["outcome"], "CONFIRMED")

    def test_missing_baseline_or_unchanged_source_cannot_verify(self):
        for baseline in (False, True):
            if baseline:
                self.cli("debug", "--phase", "reproduce", "--case", self.case["id"])
            code, data = self.cli("debug", "--phase", "verify-fix", "--case", self.case["id"])
            self.assertEqual((code, data["outcome"]), (2, "INCONCLUSIVE"))

    def test_modified_oracle_or_removed_controls_cannot_verify(self):
        self.cli("debug", "--phase", "reproduce", "--case", self.case["id"])
        (self.project / "duration_app.py").write_text(GOOD)
        self.case["oracle"]["reason"] = "Different weakened test"
        self.save_case()
        code, data = self.cli("debug", "--phase", "verify-fix", "--case", self.case["id"])
        self.assertEqual((code, data["outcome"]), (2, "INCONCLUSIVE"))

    def test_absent_controls_cannot_verify(self):
        self.case["controls"] = []
        self.save_case()
        self.cli("debug", "--phase", "reproduce", "--case", self.case["id"])
        (self.project / "duration_app.py").write_text(GOOD)
        code, data = self.cli("debug", "--phase", "verify-fix", "--case", self.case["id"])
        self.assertEqual((code, data["outcome"]), (2, "INCONCLUSIVE"))

    def test_failing_baseline_controls_cannot_verify(self):
        (self.project / "duration_app.py").write_text("def valid_duration(value):\n    return isinstance(value, str)\n")
        _, baseline = self.cli("debug", "--phase", "reproduce", "--case", self.case["id"])
        self.assertEqual(baseline["metrics"]["outcome"], "CONFIRMED")
        self.assertEqual(baseline["metrics"]["controls"][0]["outcome"], "CONFIRMED")
        (self.project / "duration_app.py").write_text(GOOD)
        code, data = self.cli("debug", "--phase", "verify-fix", "--case", self.case["id"])
        self.assertEqual((code, data["outcome"]), (2, "INCONCLUSIVE"))

    def test_assertion_count_must_not_be_a_boolean(self):
        self.payload([{"name": "invalid-duration-rejected", "status": "PASS", "executed": True}])
        code, data = self.cli("debug", "--phase", "reproduce", "--case", self.case["id"])
        self.assertEqual((code, data["metrics"]["outcome"]), (2, "INCONCLUSIVE"))

    def test_debug_references_are_retrievable_in_persian(self):
        import rag
        db = self.project / ".superagent" / "references.sqlite3"
        db.parent.mkdir()
        rag.build_index(db)
        results = rag.search("دیباگ بازتولید فرضیه", db_path=db, module="debug", limit=5)
        self.assertTrue(results)
        self.assertTrue(any("modules/debug/" in row["path"] for row in results))
        self.assertTrue(all(row["module"] in {"debug", "core"} for row in results))

    def test_missing_or_tampered_baseline_cannot_verify(self):
        _, baseline = self.cli("debug", "--phase", "reproduce", "--case", self.case["id"])
        (self.project / baseline["ledger"]["report"]).unlink()
        (self.project / "duration_app.py").write_text(GOOD)
        code, data = self.cli("debug", "--phase", "verify-fix", "--case", self.case["id"])
        self.assertEqual((code, data["outcome"]), (2, "INCONCLUSIVE"))

    def test_missing_skipped_and_zero_assertions_never_refute(self):
        for rows, expected in (([{"name": "other", "status": "PASS", "executed": 1}], "UNTESTED"),
                               ([{"name": "invalid-duration-rejected", "status": "SKIP", "executed": 0}], "UNTESTED"),
                               ([{"name": "invalid-duration-rejected", "status": "PASS", "executed": 0}], "INCONCLUSIVE"),
                               ([], "INCONCLUSIVE")):
            self.payload(rows)
            code, data = self.cli("debug", "--phase", "reproduce", "--case", self.case["id"])
            self.assertEqual((code, data["metrics"]["outcome"]), (2, expected), data)

    def test_bad_exit_and_missing_executable_are_not_confirmed_bugs(self):
        self.payload([{"name": "invalid-duration-rejected", "status": "FAIL", "executed": 1}], 7)
        code, data = self.cli("debug", "--phase", "reproduce", "--case", self.case["id"])
        self.assertEqual((code, data["metrics"]["outcome"]), (2, "INCONCLUSIVE"))
        self.case["command"] = ["/definitely/missing/sa-debug-command"]
        self.save_case()
        code, data = self.cli("debug", "--phase", "reproduce", "--case", self.case["id"])
        self.assertEqual((code, data["metrics"]["outcome"]), (2, "UNTESTED"))

    def test_source_mutation_is_inconclusive(self):
        command = "from pathlib import Path; Path('duration_app.py').write_text('x=1'); print('{\"checks\":[{\"name\":\"invalid-duration-rejected\",\"status\":\"PASS\",\"executed\":1}]}')"
        self.case["command"] = [sys.executable, "-B", "-c", command]
        self.save_case()
        code, data = self.cli("debug", "--phase", "reproduce", "--case", self.case["id"])
        self.assertEqual((code, data["metrics"]["outcome"]), (2, "INCONCLUSIVE"))

    def test_temporary_data_is_cleaned_and_raw_output_not_stored(self):
        pointer = self.project / ".superagent" / "pointer.txt"
        pointer.parent.mkdir()
        command = "import os; from pathlib import Path; Path(" + repr(str(pointer)) + ").write_text(os.environ['SUPERAGENT_DEBUG_TMP']); print('{\"checks\":[{\"name\":\"invalid-duration-rejected\",\"status\":\"PASS\",\"executed\":1}]}')"
        self.case["command"] = [sys.executable, "-B", "-c", command]
        self.save_case()
        _, data = self.cli("debug", "--phase", "reproduce", "--case", self.case["id"])
        self.assertFalse(Path(pointer.read_text()).exists())
        observation = data["metrics"]["observation"]
        self.assertTrue(observation["temporary_data_cleaned"])
        self.assertIn("stdout_sha256", observation)
        self.assertNotIn("stdout", observation)

    def test_case_contract_refuses_production_and_path_escape(self):
        self.case["environment"] = "production"
        self.save_case()
        code, _ = self.cli("debug", "--phase", "reproduce", "--case", self.case["id"])
        self.assertEqual(code, 3)
        code, _ = self.cli("debug", "--phase", "reproduce", "--case", "../outside")
        self.assertEqual(code, 3)

    @unittest.skipUnless(os.name == "posix", "POSIX process group assertion")
    def test_timeout_stops_child_even_in_nested_session(self):
        marker = self.project / ".superagent" / "leak.txt"
        marker.parent.mkdir()
        child = "import time; from pathlib import Path; time.sleep(2); Path(" + repr(str(marker)) + ").write_text('leaked')"
        parent = "import subprocess,sys,time; subprocess.Popen([sys.executable,'-c'," + repr(child) + "],start_new_session=True); time.sleep(20)"
        self.case["command"] = [sys.executable, "-B", "-c", parent]
        self.case["timeout"] = 1
        self.save_case()
        code, data = self.cli("debug", "--phase", "reproduce", "--case", self.case["id"])
        self.assertEqual((code, data["metrics"]["outcome"]), (2, "INCONCLUSIVE"))
        time.sleep(2)
        self.assertFalse(marker.exists(), "Child survived timeout")

    @unittest.skipUnless(os.name == "posix", "POSIX timeout contract")
    def test_detached_pipe_cannot_make_timeout_wait_unbounded(self):
        proc = MagicMock(pid=12345)
        proc.communicate.side_effect = [subprocess.TimeoutExpired(["test"], 1), subprocess.TimeoutExpired(["test"], 3)]
        with patch("gatekit.subprocess.Popen", return_value=proc), patch("gatekit.subprocess.run", return_value=MagicMock(stdout="")), patch("gatekit.os.killpg"):
            with self.assertRaises(subprocess.TimeoutExpired):
                run(["test"], self.project, 1)
        self.assertEqual(proc.communicate.call_args.kwargs["timeout"], 3)
        proc.stdout.close.assert_called_once()
        proc.stderr.close.assert_called_once()
        proc.wait.assert_called_once_with(timeout=3)

    def test_report_deleted_or_modified_invalidates_pass(self):
        for action in ("modify", "delete"):
            record = ledger.append(self.project, "backend.behavior", [], report("backend.behavior", "PASS"), 0)
            path = self.project / record["report"]
            if action == "delete":
                path.unlink()
            else:
                path.write_text('{}')
            self.assertEqual(ledger.verdict(self.project, {}, ["backend.behavior"])["overall"], "STALE")

    def test_artifact_snapshots_do_not_collide_and_detect_tampering(self):
        artifact = self.project / ".superagent" / "shared.json"
        artifact.parent.mkdir()
        artifact.write_text('one')
        first = ledger.append(self.project, "ui-ux.a11y", [], report("ui-ux.a11y", "PASS", artifacts={"data": str(artifact)}), 0, scope="one")
        artifact.write_text('two')
        second = ledger.append(self.project, "ui-ux.a11y", [], report("ui-ux.a11y", "PASS", artifacts={"data": str(artifact)}), 0, scope="two")
        self.assertTrue(ledger.intact(self.project, first))
        self.assertTrue(ledger.intact(self.project, second))
        snapshot = next(p for p in first["digests"] if p != first["report"])
        (self.project / snapshot).write_text("tampered")
        self.assertFalse(ledger.intact(self.project, first))

    def test_full_target_identity_and_single_page_scope(self):
        targets = ["http://localhost:3000/#/billing", "http://localhost:3000/#/settings",
                   "http://localhost:3000/?tab=billing", "http://localhost:3000/?tab=settings",
                   str(self.project / "a/index.html"), str(self.project / "b/index.html")]
        self.assertEqual(len({review.scope_label(x) for x in targets}), len(targets))
        plan = review.build_plan(self.project, "quick", [targets[0]], [], None, None, None, "AA", [])
        self.assertTrue(next(s for s in plan["steps"] if s["gate"] == "ui-ux.a11y")["scope"])
        for i, target in enumerate(targets[:2]):
            ledger.append(self.project, "ui-ux.a11y", [], report("ui-ux.a11y", "FAIL" if i == 0 else "PASS"), 0, scope=review.scope_label(target))
        self.assertEqual(ledger.verdict(self.project, {}, ["ui-ux.a11y"])["overall"], "FAILED")

    def test_historical_failure_does_not_pollute_current_required_scope(self):
        ledger.append(self.project, "ui-ux.a11y", [], report("ui-ux.a11y", "FAIL"), 0, review_id="old")
        ledger.append(self.project, "backend.behavior", [], report("backend.behavior", "PASS"), 0, review_id="new")
        self.assertEqual(ledger.verdict(self.project, {}, ["backend.behavior"])["overall"], "PASSED")
        self.assertEqual(ledger.verdict(self.project, {}, ["backend.behavior"], "old")["overall"], "NO-EVIDENCE")
        self.assertEqual(ledger.verdict(self.project, {})["overall"], "FAILED")

    def test_review_skip_excludes_prior_failure_from_verdict_and_packet(self):
        shutil.copytree(ROOT / "tests" / "fixtures" / "testing" / "py_pass", self.project, dirs_exist_ok=True)
        ledger.append(self.project, "testing.coverage", [], report("testing.coverage", "FAIL"), 0)
        code, data = self.cli("review", "--skip", "testing.coverage")
        self.assertEqual(code, 0, data)
        self.assertNotIn("testing.coverage", data["verdict"]["gates"])
        self.assertNotIn("testing.coverage", Path(data["packet"]).read_text())

    def test_coverage_command_failure_and_no_fresh_output_block_review(self):
        shutil.copytree(ROOT / "tests" / "fixtures" / "testing" / "py_pass", self.project, dirs_exist_ok=True)
        (self.project / "lcov.info").write_text("SF:calc.py\nDA:1,1\nend_of_record\n")
        for script, expected_code, command_status in (("raise SystemExit(7)", 1, "FAIL"), ("pass", 2, "NOT-TESTED")):
            cmd = shlex.join([sys.executable, "-c", script])
            code, data = self.cli("review", "--coverage-cmd", cmd)
            self.assertEqual(code, expected_code, data)
            self.assertEqual(data["verdict"]["gates"]["testing.coverage-command"]["status"], command_status)
            self.assertEqual(data["verdict"]["gates"]["testing.coverage"]["status"], "NOT-TESTED")

    def test_k6_summary_export_boolean_means_failure(self):
        data = {"metrics": {"iterations": {"count": 3}, "http_req_duration": {"thresholds": {"p(95)<500": False}}}}
        self.assertEqual(parse_k6(data, ["http_req_duration:p(95)<500"])[0], "PASS")
        data["metrics"]["http_req_duration"]["thresholds"]["p(95)<500"] = True
        self.assertEqual(parse_k6(data, ["http_req_duration:p(95)<500"])[0], "FAIL")
        data["metrics"]["http_req_duration"]["thresholds"]["p(95)<500"] = {"ok": True}
        with self.assertRaises(ValueError):
            parse_k6(data, [])


if __name__ == "__main__":
    unittest.main()
