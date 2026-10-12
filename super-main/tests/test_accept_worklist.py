#!/usr/bin/env python3
"""Tests for the T4-T5 loop: worklist from evidence, and the testing.accept assurance filters."""

import json
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SA = ROOT / "core" / "bin" / "sa.py"
FIXTURES = ROOT / "tests" / "fixtures" / "testing"

# Simulated coverage tool: payment.py lines 2-6 count as covered only when tests/test_payment.py exists.
FAKE_COVERAGE = textwrap.dedent("""
    import os, pathlib
    lines = ["SF:calc.py", "DA:1,1", "DA:2,1", "DA:5,1", "DA:6,1", "DA:7,1", "DA:8,1", "end_of_record", "SF:payment.py"]
    covered = os.path.exists("tests/test_payment.py")
    lines += [f"DA:{n},{1 if covered and n <= 6 else 0}" for n in range(1, 14)]
    lines.append("end_of_record")
    pathlib.Path("lcov.info").write_text("\\n".join(lines) + "\\n")
""")

GOOD_TEST = textwrap.dedent("""
    import unittest
    from payment import apply_discount

    class PaymentTests(unittest.TestCase):
        def test_full_discount_makes_price_zero(self):
            self.assertEqual(apply_discount(80, 100), 0)

        def test_discount_above_100_is_rejected(self):
            with self.assertRaises(ValueError):
                apply_discount(80, 101)
""")

SLEEPY_TEST = GOOD_TEST.replace("import unittest", "import time\nimport unittest").replace(
    "self.assertEqual(apply_discount(80, 100), 0)", "time.sleep(0.01)\n            self.assertEqual(apply_discount(80, 100), 0)")

REPRODUCTION_TEST = textwrap.dedent("""
    import unittest
    from payment import refund

    class RefundBug(unittest.TestCase):
        def test_negative_refund_is_rejected(self):
            with self.assertRaises(ValueError):
                refund({"paid": 10}, -5)
""")


def sa(project, *args):
    proc = subprocess.run([sys.executable, str(SA), "--project", str(project), *args], capture_output=True, text=True, timeout=600)
    try:
        return proc.returncode, json.loads(proc.stdout)
    except json.JSONDecodeError:
        return proc.returncode, {"raw": proc.stdout + proc.stderr}


class AcceptAndWorklistTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="sa-accept-"))
        self.project = self.tmp / "app"
        shutil.copytree(FIXTURES / "py_pass", self.project)
        (self.project / "fake_cov.py").write_text(FAKE_COVERAGE)
        self.cov = f"{sys.executable} fake_cov.py"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, name, body):
        (self.project / "tests" / name).write_text(body)
        return f"tests/{name}"

    def accept(self, *args):
        return sa(self.project, "gate", "testing.accept", "--json", "--", *args)

    def test_review_worklist_targets_untested_high_risk_file(self):
        code, data = sa(self.project, "review", "--json")
        tasks = json.loads(Path(data["worklist_json"]).read_text())["tasks"]
        payment = [t for t in tasks if t["target"] == "payment.py"]
        self.assertTrue(payment, tasks)
        self.assertEqual(payment[0]["type"], "write-test")
        self.assertIn("testing.accept", payment[0]["accept"])

    def test_good_new_test_passes_all_filters(self):
        test = self.write("test_payment.py", GOOD_TEST)
        code, rep = self.accept("--test", test, "--target", "payment.py", "--coverage-cmd", self.cov)
        self.assertEqual(code, 0, rep)
        self.assertEqual({k: v for k, v in rep["metrics"].items() if k.startswith("F")},
                         {"F1_builds": "PASS", "F2_stable": "PASS", "F3_value": "PASS", "F4_clean": "PASS"})
        self.assertIn("payment.py: 1-6", " ".join(rep["notes"]))
        self.assertTrue((self.project / test).is_file())  # set-aside files are restored

    def test_test_that_adds_no_coverage_fails_f3(self):
        test = self.write("test_calc_again.py", "import unittest\nfrom calc import add\n\nclass T(unittest.TestCase):\n    def test_add(self):\n        self.assertEqual(add(1, 2), 3)\n")
        code, rep = self.accept("--test", test, "--target", "calc.py", "--coverage-cmd", self.cov)
        self.assertEqual(code, 1, rep)
        self.assertEqual(rep["findings"][0]["rule"], "assurance-f3-no-new-coverage")

    def test_flaky_new_test_fails_f2(self):
        shutil.copy(FIXTURES / "py_fail_flaky" / "tests" / "test_mixed.py", self.project / "tests" / "test_mixed.py")
        code, rep = self.accept("--test", "tests/test_mixed.py", "--repeat", "3")
        self.assertEqual(code, 1, rep)
        self.assertIn("assurance-f2-not-stable", [f["rule"] for f in rep["findings"]])

    def test_smelly_new_test_fails_f4(self):
        test = self.write("test_payment.py", SLEEPY_TEST)
        code, rep = self.accept("--test", test, "--coverage-cmd", self.cov)
        self.assertEqual(code, 1, rep)
        self.assertIn("assurance-f4-smells", [f["rule"] for f in rep["findings"]])

    def test_without_coverage_command_value_is_not_measured(self):
        test = self.write("test_payment.py", GOOD_TEST)
        code, rep = self.accept("--test", test)
        self.assertEqual(code, 2, rep)
        self.assertEqual(rep["metrics"]["F3_value"], "NOT-MEASURED")

    def test_reproduction_test_must_fail_before_the_fix(self):
        test = self.write("test_refund_bug.py", REPRODUCTION_TEST)
        code, rep = self.accept("--test", test, "--expect-fail", "--repeat", "3")
        self.assertEqual(code, 0, rep)  # refund() accepts negative amounts today: the bug is reproduced
        payment = self.project / "payment.py"
        payment.write_text(payment.read_text().replace('    if amount > order["paid"]:', '    if amount < 0 or amount > order["paid"]:'))
        code, rep = self.accept("--test", test, "--expect-fail", "--repeat", "3")
        self.assertEqual(code, 1, rep)  # after the fix it passes, so it no longer "reproduces"
        code, rep = self.accept("--test", test, "--repeat", "3", "--coverage-cmd", self.cov)
        self.assertNotEqual(rep["metrics"]["F2_stable"], "FAIL", rep)

    def test_worklist_lists_failures_and_flaky_tests_first(self):
        project = self.tmp / "flaky"
        shutil.copytree(FIXTURES / "py_fail_flaky", project)
        sa(project, "gate", "testing.run", "--json", "--", "--repeat", "3")
        code, data = sa(project, "worklist", "--json")
        types = [t["type"] for t in data["tasks"]]
        self.assertEqual(types[:2], ["fix-code-or-test", "fix-flaky-test"])


if __name__ == "__main__":
    unittest.main()
