#!/usr/bin/env python3
"""End-to-end tests for the testing module gates and the evidence ledger (run through sa.py)."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SA = ROOT / "core" / "bin" / "sa.py"
FIXTURES = ROOT / "tests" / "fixtures" / "testing"


def sa(*args, project=None):
    cmd = [sys.executable, str(SA)] + list(args)
    if project is not None:
        cmd[2:2] = ["--project", str(project)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        data = {"raw": proc.stdout + proc.stderr}
    return proc.returncode, data


def gate(project, gate_id, *extra):
    return sa("gate", gate_id, "--json", *(["--"] + list(extra) if extra else []), project=project)


def git(project, *args):
    subprocess.run(["git", *args], cwd=project, check=True, capture_output=True,
                   env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"})


class FixtureCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="sa-testing-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def copy(self, name):
        target = self.tmp / name
        shutil.copytree(FIXTURES / name, target)
        return target


class RunGateTests(FixtureCase):
    def test_passing_python_suite(self):
        code, rep = gate(self.copy("py_pass"), "testing.run", "--repeat", "2")
        self.assertEqual(code, 0, rep)
        self.assertEqual(rep["metrics"]["passed"], 2)

    def test_failing_and_flaky_tests_are_classified(self):
        code, rep = gate(self.copy("py_fail_flaky"), "testing.run", "--repeat", "3")
        self.assertEqual(code, 1, rep)
        rules = sorted(f["rule"] for f in rep["findings"])
        self.assertEqual(rules, ["flaky-test", "test-failure"])

    def test_zero_executed_tests_fail(self):
        code, rep = gate(self.copy("node_empty"), "testing.run")
        self.assertEqual(code, 1, rep)
        self.assertIn("no-tests-executed", [f["rule"] for f in rep["findings"]])

    @unittest.skipUnless(shutil.which("node"), "node is required")
    def test_node_test_runner_with_junit(self):
        code, rep = gate(self.copy("node_pass"), "testing.run")
        self.assertEqual(code, 0, rep)
        self.assertEqual(rep["metrics"]["runner"], "node-test")
        self.assertEqual(rep["metrics"]["passed"], 2)

    def test_project_without_runner_is_not_tested(self):
        project = self.tmp / "nothing"
        project.mkdir()
        (project / "README.md").write_text("docs only")
        code, rep = gate(project, "testing.run")
        self.assertEqual(code, 2, rep)


class SmellGateTests(FixtureCase):
    def test_js_smells(self):
        code, rep = gate(self.copy("js_smells"), "testing.smells")
        self.assertEqual(code, 1, rep)
        by_rule = {f["rule"]: f for f in rep["findings"]}
        self.assertEqual(set(by_rule), {"focused-test", "empty-test", "sleepy-test", "assertion-free-test", "skipped-test", "external-url-literal"})
        self.assertEqual(by_rule["focused-test"]["confidence"], "verified")
        self.assertEqual(by_rule["sleepy-test"]["confidence"], "suspected")

    def test_python_smells(self):
        code, rep = gate(self.copy("py_smells"), "testing.smells")
        self.assertEqual(code, 1, rep)
        rules = {f["rule"] for f in rep["findings"]}
        self.assertEqual(rules, {"empty-test", "sleepy-test", "assertion-free-test", "skipped-test"})

    def test_clean_suite_passes(self):
        code, rep = gate(self.copy("py_pass"), "testing.smells")
        self.assertEqual(code, 0, rep)


class InventoryAndRiskTests(FixtureCase):
    def test_frontend_project_gets_trophy_shape(self):
        project = self.tmp / "web"
        project.mkdir()
        (project / "package.json").write_text(json.dumps({"dependencies": {"react": "18"}, "devDependencies": {"vitest": "1"}, "scripts": {"test": "vitest"}}))
        (project / "App.tsx").write_text("export const App = () => null;\n")
        code, rep = gate(project, "testing.inventory")
        self.assertEqual(code, 0, rep)
        self.assertEqual(rep["metrics"]["recommended_shape"], "trophy")
        self.assertEqual(rep["metrics"]["runners"], "vitest")

    def test_microservices_get_honeycomb_shape(self):
        project = self.tmp / "svc"
        project.mkdir()
        (project / "docker-compose.yml").write_text("services:\n  api:\n    image: a\n  worker:\n    image: b\n  billing:\n    image: c\n")
        (project / "main.go").write_text("package main\n")
        (project / "go.mod").write_text("module example.com/svc\n")
        code, rep = gate(project, "testing.inventory")
        self.assertEqual(rep["metrics"]["recommended_shape"], "honeycomb")

    def test_risk_ranks_critical_code_first(self):
        code, rep = gate(self.copy("py_pass"), "testing.risk")
        self.assertEqual(code, 0, rep)
        top = [t["file"] for t in rep["metrics"]["top"]]
        self.assertEqual(top[0], "payment.py")
        self.assertNotIn("tests/__init__.py", top)


class CoverageGateTests(FixtureCase):
    def make_repo(self):
        project = self.copy("py_pass")
        git(project, "init", "-q", "-b", "main")
        git(project, "add", "-A")
        git(project, "commit", "-q", "-m", "base")
        git(project, "switch", "-q", "-c", "feature")
        payment = project / "payment.py"
        payment.write_text(payment.read_text() + "\n\ndef fee(amount):\n    if amount > 100:\n        return 2\n    return 1\n")
        return project

    def write_lcov(self, project, covered_fee_lines):
        time.sleep(0.05)
        lines = [f"DA:{n},{1 if n in covered_fee_lines else 0}" for n in range(16, 20)]
        (project / "lcov.info").write_text("SF:payment.py\nDA:1,1\nDA:2,1\n" + "\n".join(lines) + "\nend_of_record\n")

    def test_low_diff_coverage_fails_with_uncovered_lines(self):
        project = self.make_repo()
        self.write_lcov(project, covered_fee_lines={16})
        code, rep = gate(project, "testing.coverage")
        self.assertEqual(code, 1, rep)
        finding = rep["findings"][0]
        self.assertEqual(finding["rule"], "diff-coverage-below-threshold")
        self.assertIn("payment.py", finding["evidence"]["uncovered"])

    def test_full_diff_coverage_passes(self):
        project = self.make_repo()
        self.write_lcov(project, covered_fee_lines={16, 17, 18, 19})
        code, rep = gate(project, "testing.coverage")
        self.assertEqual(code, 0, rep)
        self.assertEqual(rep["metrics"]["diff_coverage"], 100.0)

    def test_stale_report_is_not_tested(self):
        project = self.make_repo()
        self.write_lcov(project, covered_fee_lines={16, 17, 18, 19})
        time.sleep(0.05)
        (project / "calc.py").write_text((project / "calc.py").read_text() + "\n")
        code, rep = gate(project, "testing.coverage")
        self.assertEqual(code, 2, rep)

    def test_missing_report_is_not_tested(self):
        code, rep = gate(self.copy("py_pass"), "testing.coverage")
        self.assertEqual(code, 2, rep)

    def test_cobertura_report_is_parsed(self):
        project = self.make_repo()
        time.sleep(0.05)
        (project / "coverage.xml").write_text(
            '<?xml version="1.0"?><coverage><sources><source>.</source></sources><packages><package><classes>'
            '<class filename="payment.py"><lines>'
            + "".join(f'<line number="{n}" hits="1"/>' for n in range(16, 20))
            + "</lines></class></classes></package></packages></coverage>")
        code, rep = gate(project, "testing.coverage")
        self.assertEqual(code, 0, rep)


FAKE_STRYKER = """#!/usr/bin/env node
// Stand-in for StrykerJS: records its arguments and writes a report in Stryker's mutation.json schema.
const fs = require('fs');
fs.writeFileSync('stryker-args.json', JSON.stringify(process.argv.slice(2)));
if (process.env.FAKE_STRYKER_CRASH) process.exit(1);
const mutants = JSON.parse(process.env.FAKE_STRYKER_MUTANTS);
fs.mkdirSync('reports/mutation', { recursive: true });
fs.writeFileSync('reports/mutation/mutation.json', JSON.stringify({ schemaVersion: '2', files: { 'sum.js': { mutants } } }));
"""


def mutant(status, line, mutator="ArithmeticOperator", replacement="a - b"):
    return {"id": str(line), "mutatorName": mutator, "replacement": replacement, "status": status,
            "location": {"start": {"line": line, "column": 1}, "end": {"line": line, "column": 9}}}


class OptionalToolGateTests(FixtureCase):
    def stryker_project(self):
        project = self.copy("node_pass")
        bin_dir = project / "node_modules" / ".bin"
        bin_dir.mkdir(parents=True)
        fake = bin_dir / "stryker"
        fake.write_text(FAKE_STRYKER)
        fake.chmod(0o755)
        return project

    def run_mutation(self, project, mutants, crash=False):
        env = dict(os.environ, FAKE_STRYKER_MUTANTS=json.dumps(mutants))
        if crash:
            env["FAKE_STRYKER_CRASH"] = "1"
        proc = subprocess.run([sys.executable, str(SA), "--project", str(project), "gate", "testing.mutation", "--json", "--", "--files", "sum.js"],
                              capture_output=True, text=True, timeout=300, env=env)
        return proc.returncode, json.loads(proc.stdout)

    @unittest.skipUnless(shutil.which("npx"), "npx is required")
    def test_stryker_score_and_surviving_mutants(self):
        project = self.stryker_project()
        code, rep = self.run_mutation(project, [mutant("Killed", 1), mutant("Killed", 2), mutant("Timeout", 2), mutant("Survived", 2), mutant("NoCoverage", 3)])
        self.assertEqual(rep["metrics"]["mutation_score"], 60.0)  # (2 killed + 1 timeout) / 5
        self.assertEqual(code, 0, rep)
        self.assertEqual(sorted(f["condition"] for f in rep["findings"]), ["sum.js:2", "sum.js:3"])
        args = json.loads((project / "stryker-args.json").read_text())
        self.assertEqual(args[:3], ["run", "--reporters", "json,clear-text"])
        self.assertIn("sum.js", args[args.index("--mutate") + 1])

    @unittest.skipUnless(shutil.which("npx"), "npx is required")
    def test_low_mutation_score_fails(self):
        project = self.stryker_project()
        code, rep = self.run_mutation(project, [mutant("Killed", 1), mutant("Survived", 2), mutant("Survived", 3)])
        self.assertEqual(code, 1, rep)
        self.assertTrue(all(f["confidence"] == "verified" for f in rep["findings"]))

    @unittest.skipUnless(shutil.which("npx"), "npx is required")
    def test_stale_stryker_report_is_never_reused(self):
        project = self.stryker_project()
        old = project / "reports" / "mutation"
        old.mkdir(parents=True)
        (old / "mutation.json").write_text(json.dumps({"files": {"sum.js": {"mutants": [mutant("Killed", 1)]}}}))
        code, rep = self.run_mutation(project, [], crash=True)
        self.assertEqual(code, 3, rep)  # ERROR, not a PASS from yesterday's report

    def test_mutation_needs_an_existing_test_suite(self):
        project = self.tmp / "no-tests"
        project.mkdir()
        (project / "app.js").write_text("export const f = (a) => a + 1;\n")
        code, rep = gate(project, "testing.mutation", "--files", "app.js")
        self.assertEqual(code, 2, rep)
        self.assertIn("existing test suite", rep["notes"][0])

    def test_mutation_without_tools_is_not_tested(self):
        if shutil.which("mutmut"):
            self.skipTest("mutmut installed")
        code, rep = gate(self.copy("py_pass"), "testing.mutation", "--files", "payment.py")
        self.assertEqual(code, 2, rep)

    def test_api_refuses_remote_targets(self):
        project = self.copy("py_pass")
        (project / "openapi.json").write_text("{}")
        code, rep = gate(project, "testing.api", "--url", "https://api.example.org")
        self.assertEqual(code, 2, rep)
        self.assertIn("non-local", rep["notes"][0])


class LedgerVerdictTests(FixtureCase):
    def test_verdict_passes_then_goes_stale_after_a_change(self):
        project = self.copy("py_pass")
        gate(project, "testing.run")
        code, verdict = sa("verdict", "--format", "json", "--require", "testing.run", project=project)
        self.assertEqual(code, 0, verdict)
        self.assertEqual(verdict["label"], "[QA-PASSED]")
        time.sleep(0.05)
        (project / "calc.py").write_text((project / "calc.py").read_text() + "\n# changed\n")
        code, verdict = sa("verdict", "--format", "json", project=project)
        self.assertEqual(code, 2, verdict)
        self.assertEqual(verdict["gates"]["testing.run"]["status"], "STALE")

    def test_missing_required_gate_is_no_evidence(self):
        project = self.copy("py_pass")
        code, verdict = sa("verdict", "--format", "json", "--require", "testing.run,ui-ux.a11y", project=project)
        self.assertEqual(code, 2, verdict)
        self.assertEqual(verdict["overall"], "NO-EVIDENCE")

    def test_repeated_failures_consume_the_attempt_budget(self):
        project = self.copy("py_fail_flaky")
        states = []
        for _ in range(3):
            gate(project, "testing.run")
            _, verdict = sa("verdict", "--format", "json", project=project)
            states.append((verdict["overall"], verdict["gates"]["testing.run"].get("budget")))
        self.assertEqual(states[0], ("FAILED", "ok"))
        self.assertEqual(states[1], ("FAILED", "pivot-required"))
        self.assertEqual(states[2], ("REJECTED", "exhausted"))

    def test_generated_reports_do_not_make_evidence_stale_but_source_changes_do(self):
        project = self.copy("py_pass")
        (project / "src" / "reports").mkdir(parents=True)
        (project / "src" / "reports" / "views.py").write_text("x = 1\n")
        gate(project, "testing.run")
        time.sleep(0.05)
        (project / "lcov.info").write_text("SF:calc.py\nend_of_record\n")
        (project / "coverage").mkdir()
        (project / "coverage" / "index.html").write_text("<html></html>")
        _, verdict = sa("verdict", "--format", "json", project=project)
        self.assertEqual(verdict["gates"]["testing.run"]["status"], "PASS")
        (project / "src" / "reports" / "views.py").write_text("x = 2\n")
        _, verdict = sa("verdict", "--format", "json", project=project)
        self.assertEqual(verdict["gates"]["testing.run"]["status"], "STALE")

    def test_informational_gates_do_not_decide_the_verdict(self):
        project = self.copy("py_pass")
        gate(project, "testing.inventory")
        code, verdict = sa("verdict", "--format", "json", project=project)
        self.assertEqual(verdict["overall"], "NO-EVIDENCE")

    def test_iso_scorecard_maps_gates(self):
        project = self.copy("py_pass")
        gate(project, "testing.run")
        _, verdict = sa("verdict", "--format", "json", project=project)
        self.assertEqual(verdict["iso25010"]["Functional suitability"]["testing.run"], "PASS")


if __name__ == "__main__":
    unittest.main()
