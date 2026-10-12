#!/usr/bin/env python3
"""End-to-end tests for the accessibility gate (requires Node, Playwright and Chromium).

Exit-code contract under test: 0 PASS, 1 FAIL, 2 NOT-TESTED, 3 ERROR.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "modules" / "ui-ux" / "gates" / "a11y.py"
FIXTURES = ROOT / "tests" / "fixtures" / "a11y"


def run_gate(*args, cwd=None):
    out_dir = tempfile.mkdtemp(prefix="a11y-gate-")
    try:
        proc = subprocess.run(
            [sys.executable, str(GATE), "--json", "--out", out_dir, *args],
            capture_output=True, text=True, timeout=300, cwd=cwd or tempfile.gettempdir(),
            env={k: v for k, v in os.environ.items() if k not in {"TARGET_URL", "SANDBOX_PATH"}},
        )
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)
    try:
        report = json.loads(proc.stdout)
    except json.JSONDecodeError:
        report = {"raw_stdout": proc.stdout, "raw_stderr": proc.stderr}
    return proc.returncode, report


@unittest.skipUnless(shutil.which("npx"), "Node/npx is required for the accessibility gate tests")
class AccessibilityGateTests(unittest.TestCase):
    def test_accessible_sandbox_passes(self):
        code, report = run_gate("--sandbox", str(FIXTURES / "good.html"))
        self.assertEqual(code, 0, report)
        self.assertEqual(report["status"], "PASS")

    def test_violations_in_sandbox_fail_with_rule_ids(self):
        code, report = run_gate("--sandbox", str(FIXTURES / "bad.html"))
        self.assertEqual(code, 1, report)
        rules = {f["rule"] for f in report["findings"]}
        self.assertIn("button-name", rules)
        self.assertIn("label", rules)

    def test_violations_on_live_url_fail_every_time(self):
        url = (FIXTURES / "bad.html").as_uri()
        for attempt in (1, 2):
            with self.subTest(attempt=attempt):
                code, report = run_gate("--url", url)
                self.assertEqual(code, 1, report)
                self.assertTrue(report["findings"])

    def test_component_that_mounts_late_is_awaited(self):
        code, report = run_gate("--sandbox", str(FIXTURES / "delayed.html"))
        self.assertEqual(code, 0, report)

    def test_script_errors_fail_the_gate(self):
        code, report = run_gate("--sandbox", str(FIXTURES / "broken.html"))
        self.assertEqual(code, 1, report)

    def test_missing_target_is_not_tested(self):
        code, report = run_gate()
        self.assertEqual(code, 2, report)
        self.assertEqual(report["status"], "NOT-TESTED")

    def test_missing_sandbox_file_is_not_tested(self):
        code, report = run_gate("--sandbox", str(FIXTURES / "does-not-exist.html"))
        self.assertEqual(code, 2, report)

    def test_gate_runs_from_any_working_directory(self):
        with tempfile.TemporaryDirectory() as elsewhere:
            code, report = run_gate("--sandbox", str(FIXTURES / "good.html"), cwd=elsewhere)
        self.assertEqual(code, 0, report)


if __name__ == "__main__":
    unittest.main()
