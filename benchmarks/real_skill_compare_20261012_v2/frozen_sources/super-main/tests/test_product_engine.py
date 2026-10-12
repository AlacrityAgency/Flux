#!/usr/bin/env python3
"""Behavioural regressions for project retrieval, coverage and false-green prevention."""
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core/lib"))
import discovery
import ledger
from project import PRODUCT_AREAS, load_config
from review import build_plan

spec = importlib.util.spec_from_file_location("sa_product_cli", ROOT / "core/bin/sa.py")
sa_cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sa_cli)


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="sa-product-")
        self.project = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def cli(self, *args):
        proc = subprocess.run([sys.executable, "-B", str(ROOT / "core/bin/sa.py"), "--project", str(self.project), *args],
                              capture_output=True, text=True, timeout=120)
        try:
            return proc.returncode, json.loads(proc.stdout)
        except ValueError:
            self.fail(proc.stdout + proc.stderr)

    def gate(self, name, *args):
        return self.cli("gate", name, "--json", "--", *args)

    def write_config(self, config):
        (self.project / "superagent.json").write_text(json.dumps({"version": 1, **config}))

    def test_static_batch_overlaps_only_allowlisted_read_only_gates(self):
        gate_ids = ["testing.inventory", "testing.risk", "ui-ux.tokens", "testing.run", "ui-ux.token-drift"]
        steps = [{"gate": gate, "kind": "gate", "scope": None, "args": []} for gate in gate_ids]
        steps[-1]["args"] = ["--update-baseline"]
        lock, barrier = threading.Lock(), threading.Barrier(2)
        state = {"active": 0, "peak": 0, "started": 0}
        called = []

        def fake_run(meta, gate, project, extra, timeout, scope, review_id):
            with lock:
                state["active"] += 1
                state["started"] += 1
                ordinal = state["started"]
                state["peak"] = max(state["peak"], state["active"])
                called.append(gate)
            if ordinal <= 2:
                barrier.wait(timeout=5)
            with lock:
                state["active"] -= 1
            return gate

        with patch.object(sa_cli, "run_gate", side_effect=fake_run):
            results = sa_cli.run_static_batch({"steps": steps, "review_id": "test"},
                                             {g: {} for g in gate_ids}, self.project, 10, 2)
        self.assertEqual(state["peak"], 2)
        self.assertEqual(state["active"], 0)
        self.assertEqual(set(called), set(gate_ids[:3]))
        self.assertEqual(set(results), {0, 1, 2})

    def test_static_worker_budget_validated(self):
        for workers in (0, 5, True, "2"):
            self.write_config({"testing": {"static_workers": workers}})
            with self.assertRaises(ValueError):
                load_config(self.project)
        self.write_config({"testing": {"static_workers": 1}})
        self.assertEqual(load_config(self.project)["testing"]["static_workers"], 1)

    def test_missing_junit_cannot_pass_or_produce_green_verdict(self):
        code, result = self.gate("testing.run", "--cmd", f"{sys.executable} -c pass", "--junit", "missing.xml")
        self.assertEqual((code, result["status"]), (3, "ERROR"))
        code, verdict = self.cli("verdict", "--require", "testing.run", "--format", "json")
        self.assertNotEqual(code, 0)
        self.assertNotEqual(verdict["overall"], "PASSED")

    def test_successful_command_without_test_report_is_gap(self):
        code, result = self.gate("testing.run", "--cmd", f"{sys.executable} -c pass")
        self.assertEqual((code, result["status"]), (2, "NOT-TESTED"))

    def test_stale_junit_removed_before_custom_run(self):
        (self.project / "junit.xml").write_text('<testsuite><testcase name="old"/></testsuite>')
        code, result = self.gate("testing.run", "--cmd", f"{sys.executable} -c pass", "--junit", "junit.xml")
        self.assertEqual(code, 3, result)

    def test_malformed_custom_report_is_error(self):
        writer = self.project / "writer.py"
        writer.write_text("from pathlib import Path\nPath('junit.xml').write_text('not XML')\n")
        code, result = self.gate("testing.run", "--cmd", f"{sys.executable} writer.py", "--junit", "junit.xml")
        self.assertEqual(code, 3, result)

    def test_duplicate_junit_identity_cannot_overwrite_failed_test(self):
        writer = self.project / "writer.py"
        writer.write_text("from pathlib import Path\nPath('junit.xml').write_text('<testsuite><testcase name=\"same\"><failure/></testcase><testcase name=\"same\"/></testsuite>')\n")
        code, result = self.gate("testing.run", "--cmd", f"{sys.executable} writer.py", "--junit", "junit.xml")
        self.assertEqual(code, 3, result)

    def test_second_repeat_missing_report_is_error(self):
        writer = self.project / "writer.py"
        writer.write_text("from pathlib import Path\np=Path('.superagent/seen')\nif not p.exists():\n Path('junit.xml').write_text('<testsuite><testcase name=\"once\"/></testsuite>')\n p.touch()\n")
        code, result = self.gate("testing.run", "--cmd", f"{sys.executable} writer.py", "--junit", "junit.xml", "--repeat", "2")
        self.assertEqual(code, 3, result)

    @unittest.skipUnless(shutil.which("node"), "node required")
    def test_nested_suites_are_separately_required_and_failures_visible(self):
        shutil.copytree(ROOT / "tests/fixtures/testing/node_pass", self.project / "frontend")
        shutil.copytree(ROOT / "tests/fixtures/testing/py_pass", self.project / "backend")
        self.write_config({"testing": {"suites": [{"name": "unittest", "cwd": "backend"}, {"name": "node-test", "cwd": "frontend"}]}})
        code, result = self.cli("review", "--depth", "quick", "--json")
        self.assertEqual(code, 0, result)
        suite_gates = {k: v for k, v in result["verdict"]["gates"].items() if k.startswith("testing.run")}
        self.assertEqual(len(suite_gates), 2)
        self.assertTrue(all(v["status"] == "PASS" for v in suite_gates.values()))
        self.assertTrue((self.project / ".superagent/review/timing.json").is_file())
        (self.project / "frontend/test/broken.test.js").write_text("require('node:test')('broken',()=>{throw Error('seeded')});")
        code, result = self.cli("review", "--depth", "quick", "--json")
        self.assertEqual(code, 1, result)

    def test_automatic_child_package_discovery(self):
        for directory, pkg in (("frontend", {"scripts": {"test": "node --test"}}), ("backend", {})):
            (self.project / directory).mkdir()
            (self.project / directory / "package.json").write_text(json.dumps(pkg))
        (self.project / "backend/pyproject.toml").write_text('[project]\nname="fixture"\n')
        (self.project / "backend/requirements.txt").write_text("pytest\n")
        (self.project / "backend/test_ok.py").write_text("def test_ok(): assert True\n")
        result = discovery.build_map(self.project)
        self.assertEqual({(s["name"], s["cwd"]) for s in result["suites"]}, {("node-test", "frontend"), ("pytest", "backend")})

    def test_multiple_runner_candidates_not_silently_dropped(self):
        (self.project / "package.json").write_text(json.dumps({"devDependencies": {"jest": "1", "vitest": "1"}}))
        self.assertEqual({s["name"] for s in discovery.build_map(self.project)["suites"]}, {"jest", "vitest"})

    def test_incremental_retrieval_role_filter_and_deletion(self):
        (self.project / "src").mkdir()
        code = self.project / "src/filter.py"
        code.write_text("def low_pass(samples):\n    return samples\n")
        (self.project / "mockups").mkdir()
        (self.project / "mockups/old.md").write_text("low_pass missing old prototype")
        self.write_config({"sources": {"active": ["src"], "reference": ["mockups"], "entrypoints": ["src/filter.py"]}})
        first = discovery.search_project(self.project, "low_pass", roles=["active"])
        self.assertTrue(first["results"])
        self.assertTrue(all(r["path"] == "src/filter.py" for r in first["results"]))
        second = discovery.search_project(self.project, "low_pass")
        self.assertEqual(second["updated_files"], 0)
        old_hash = first["results"][0]["sha256"]
        code.write_text("def low_pass(samples):\n    return list(samples)\n")
        changed = discovery.search_project(self.project, "low_pass", roles=["active"])
        self.assertNotEqual(changed["results"][0]["sha256"], old_hash)
        code.unlink()
        self.assertEqual(discovery.search_project(self.project, "low_pass", roles=["active"])["results"], [])

    def test_unknown_files_not_assumed_active(self):
        (self.project / "file.py").write_text("x = 1")
        data = discovery.build_map(self.project)
        self.assertEqual(data["files"][0]["role"], "unknown")

    def test_out_of_project_sources_and_suite_rejected(self):
        for config in ({"sources": {"active": ["../outside"]}}, {"testing": {"suites": [{"name": "pytest", "cwd": "../outside"}]}}):
            self.write_config(config)
            with self.assertRaises(ValueError):
                load_config(self.project)

    def test_reference_mockup_drift_not_assigned_to_active_product(self):
        (self.project / "mockups").mkdir()
        (self.project / "mockups/old.css").write_text("body {color: #ff0000}")
        (self.project / "active.css").write_text("body {color: #00ff00}")
        self.write_config({"sources": {"active": ["active.css"], "reference": ["mockups"]}})
        code, result = self.gate("ui-ux.token-drift")
        self.assertEqual(code, 1, result)
        self.assertEqual({f["evidence"]["file"] for f in result["findings"]}, {"active.css"})

    def product_config(self):
        (self.project / "contract.md").write_text("Expected behaviour and review evidence")
        (self.project / "check.py").write_text("assert 1+1 == 2\n")
        trace = {kind: {"applicable": True, "reason": "Fixture artifact", "paths": ["contract.md" if kind in {"design", "content"} else "check.py"]} for kind in ("design", "content", "code", "tests")}
        expected = {name: "backend.behavior" for name in PRODUCT_AREAS}
        areas = {name: {"applicable": name == "backend", "reason": "Scoped fixture", "criteria": ["B"] if name == "backend" else []} for name in expected}
        argv = [sys.executable, "-c", 'import json; print(json.dumps({"checks":[{"name":"observed","status":"PASS","executed":1}]}))']
        self.write_config({"product": {"areas": areas}, "acceptance": [{"id": "B", "criterion": "Observed fixture behaviour", "gate": "backend.behavior", "scenario": "observed", "trace": trace}],
                           "checks": {"backend.behavior": {"command": argv, "expected": ["observed"]}}})

    def test_product_missing_current_evidence_is_gap_then_passing_assertion_maps(self):
        self.product_config()
        code, result = self.gate("product.coverage")
        self.assertEqual(code, 2, result)
        self.assertEqual(result["metrics"]["areas"]["research"]["status"], "NOT-APPLICABLE")
        self.assertEqual(self.gate("backend.behavior")[0], 0)
        code, result = self.gate("product.coverage")
        self.assertEqual(code, 0, result)
        self.assertTrue(Path(result["artifacts"]["matrix"]).is_file())
        self.assertEqual(self.gate("product.coverage", "--review-id", "new-session")[0], 2)

    def test_trace_and_evidence_integrity_are_required(self):
        self.product_config()
        self.gate("backend.behavior")
        (self.project / "contract.md").unlink()
        self.assertEqual(self.gate("product.coverage")[0], 2)

    def test_product_schema_rejects_missing_applicability_and_unmapped_ids(self):
        self.write_config({"product": {"areas": {}}})
        with self.assertRaises(ValueError):
            load_config(self.project)

    def test_build_requires_product_coverage_standard_tests_once(self):
        shutil.copytree(ROOT / "tests/fixtures/testing/py_pass", self.project / "pkg")
        self.write_config({"testing": {"suites": [{"name": "pytest", "cwd": "pkg"}]}})
        plan = build_plan(self.project, "standard", [], [], None, None, None, "AA", [], mode="build")
        self.assertIn("product.coverage", plan["required"])
        step = next(s for s in plan["steps"] if s["gate"] == "testing.run")
        self.assertEqual(step["args"][:2], ["--repeat", "1"])
        self.assertEqual(plan["steps"][-1]["gate"], "product.coverage")


if __name__ == "__main__":
    unittest.main()
