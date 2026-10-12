#!/usr/bin/env python3
"""Tests for `sa.py review`: plan selection per depth and project type, execution, scoped evidence and the review packet."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SA = ROOT / "core" / "bin" / "sa.py"
FIXTURES = ROOT / "tests" / "fixtures"
sys.path.insert(0, str(ROOT / "core" / "lib"))
from review import scope_label


def review(project, *args):
    proc = subprocess.run([sys.executable, str(SA), "--project", str(project), "review", "--json", *args],
                          capture_output=True, text=True, timeout=900)
    try:
        return proc.returncode, json.loads(proc.stdout), proc.stderr
    except json.JSONDecodeError:
        return proc.returncode, {"raw": proc.stdout}, proc.stderr


def planned(data):
    return [s["gate"] + (f"@{s['scope']}" if s["scope"] else "") for s in data["plan"]["steps"]]


def git(project, *args):
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    subprocess.run(["git", *args], cwd=project, check=True, capture_output=True, env=env)


class ReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="sa-review-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def copy(self, name, sub="testing"):
        target = self.tmp / name
        shutil.copytree(FIXTURES / sub / name, target)
        return target

    # --- planning -------------------------------------------------------------------------

    def test_plan_grows_with_depth(self):
        project = self.copy("py_pass")
        _, quick, _ = review(project, "--depth", "quick", "--dry-run")
        _, standard, _ = review(project, "--depth", "standard", "--dry-run")
        _, thorough, _ = review(project, "--depth", "thorough", "--dry-run")
        self.assertEqual(planned(quick), ["testing.run", "testing.smells"])
        self.assertEqual(planned(standard), ["testing.inventory", "testing.risk", "testing.run", "testing.smells", "testing.coverage"])
        self.assertEqual(planned(thorough), planned(standard) + ["testing.mutation"])
        self.assertNotIn("testing.risk", thorough["plan"]["required"])

    def test_frontend_without_url_still_plans_ui_gates(self):
        project = self.tmp / "web"
        project.mkdir()
        (project / "package.json").write_text(json.dumps({"dependencies": {"react": "18"}}))
        (project / "App.tsx").write_text("export const App = () => null;\n")
        _, data, _ = review(project, "--dry-run")
        steps = planned(data)
        for gate in ("ui-ux.a11y", "ui-ux.interaction", "ui-ux.token-drift"):
            self.assertIn(gate, steps)

    def test_api_spec_adds_contract_gate_and_skip_removes_it(self):
        project = self.copy("py_pass")
        (project / "openapi.yaml").write_text("openapi: 3.0.0\n")
        _, data, _ = review(project, "--dry-run")
        self.assertIn("testing.api", planned(data))
        _, data, _ = review(project, "--dry-run", "--skip", "testing.api")
        self.assertNotIn("testing.api", planned(data))
        self.assertNotIn("testing.api", data["plan"]["required"])

    def test_several_pages_get_their_own_scope(self):
        project = self.copy("py_pass")
        _, data, _ = review(project, "--dry-run", "--depth", "quick", "--url", "http://localhost:3000/", "--url", "http://localhost:3000/settings")
        steps = planned(data)
        self.assertIn("ui-ux.a11y@" + scope_label("http://localhost:3000/"), steps)
        self.assertIn("ui-ux.interaction@" + scope_label("http://localhost:3000/settings"), steps)

    # --- execution ------------------------------------------------------------------------

    def test_quick_review_passes_on_a_healthy_project(self):
        project = self.copy("py_pass")
        code, data, _ = review(project, "--depth", "quick")
        self.assertEqual(code, 0, data)
        self.assertEqual(data["verdict"]["label"], "[QA-PASSED]")
        self.assertIsNone(data["packet"])

    def test_standard_review_reports_missing_coverage_as_a_gap(self):
        project = self.copy("py_pass")
        code, data, _ = review(project)
        self.assertEqual(code, 2, data)
        self.assertEqual(data["verdict"]["overall"], "PASSED-WITH-GAPS")
        self.assertEqual(data["verdict"]["gates"]["testing.coverage"]["status"], "NOT-TESTED")
        packet = Path(data["packet"]).read_text(encoding="utf-8")
        self.assertIn("Independent Review Packet", packet)
        self.assertIn("testing.coverage", packet)

    def test_coverage_command_runs_before_the_coverage_gate(self):
        project = self.copy("py_pass")
        git(project, "init", "-q", "-b", "main")
        git(project, "add", "-A")
        git(project, "commit", "-q", "-m", "base")
        writer = "import pathlib; pathlib.Path('lcov.info').write_text('SF:calc.py\\nDA:1,1\\nend_of_record\\n')"
        cmd = f'{sys.executable} -c "{writer}"'
        code, data, _ = review(project, "--coverage-cmd", cmd)
        self.assertEqual(data["verdict"]["gates"]["testing.coverage"]["status"], "PASS", data)
        self.assertEqual(code, 0, data)

    def test_failing_project_fails_the_review_and_lists_findings_in_packet(self):
        project = self.copy("py_fail_flaky")
        code, data, _ = review(project)
        self.assertEqual(code, 1, data)
        self.assertEqual(data["verdict"]["overall"], "FAILED")
        packet = Path(data["packet"]).read_text(encoding="utf-8")
        self.assertIn("test-failure", packet)

    @unittest.skipUnless(shutil.which("npx"), "Node/npx is required for browser gates")
    def test_scoped_pages_keep_separate_evidence(self):
        project = self.copy("py_pass")
        good, bad = FIXTURES / "a11y" / "good.html", FIXTURES / "a11y" / "bad.html"
        code, data, _ = review(project, "--depth", "quick", "--sandbox", str(good), "--sandbox", str(bad))
        gates = data["verdict"]["gates"]
        self.assertEqual(gates["ui-ux.a11y@" + scope_label(str(good))]["status"], "PASS")
        self.assertEqual(gates["ui-ux.a11y@" + scope_label(str(bad))]["status"], "FAIL")
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
