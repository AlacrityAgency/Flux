#!/usr/bin/env python3
"""End-to-end tests for the ui-ux gates added in phase 5: tokens wrapper, token drift, interaction."""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SA = ROOT / "core" / "bin" / "sa.py"
FIXTURES = ROOT / "tests" / "fixtures"


def gate(project, gate_id, *extra):
    cmd = [sys.executable, str(SA), "--project", str(project), "gate", gate_id, "--json"] + (["--"] + list(extra) if extra else [])
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    try:
        return proc.returncode, json.loads(proc.stdout)
    except json.JSONDecodeError:
        return proc.returncode, {"raw": proc.stdout + proc.stderr}


class TempProject(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="sa-ui-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class TokensGateTests(TempProject):
    def test_valid_tokens_with_pairs_pass(self):
        for name in ("tokens.json", "contrast-pairs.json"):
            shutil.copy(FIXTURES / "valid" / name, self.tmp / name)
        code, rep = gate(self.tmp, "ui-ux.tokens")
        self.assertEqual(code, 0, rep)
        self.assertEqual(rep["metrics"]["contrast_pairs"], 1)

    def test_low_contrast_pair_fails(self):
        shutil.copy(FIXTURES / "valid" / "tokens.json", self.tmp / "tokens.json")
        shutil.copy(FIXTURES / "invalid" / "contrast-pairs.json", self.tmp / "contrast-pairs.json")
        code, rep = gate(self.tmp, "ui-ux.tokens")
        self.assertEqual(code, 1, rep)
        self.assertEqual(rep["findings"][0]["rule"], "contrast-pair")

    def test_project_without_tokens_json_is_not_tested(self):
        code, rep = gate(self.tmp, "ui-ux.tokens")
        self.assertEqual(code, 2, rep)
        self.assertIn("token-drift", rep["notes"][0])


class TokenDriftGateTests(TempProject):
    def setUp(self):
        super().setUp()
        self.project = self.tmp / "drift"
        shutil.copytree(FIXTURES / "drift", self.project)

    def test_drift_is_reported_by_rule(self):
        code, rep = gate(self.project, "ui-ux.token-drift")
        self.assertEqual(code, 1, rep)
        rules = sorted({f["rule"] for f in rep["findings"]})
        self.assertEqual(rules, ["arbitrary-color", "arbitrary-length", "hardcoded-color", "raw-palette-class"])
        files = {f["evidence"]["file"] for f in rep["findings"]}
        self.assertNotIn("src/globals.css", files)  # custom property definitions are tokens
        self.assertNotIn("src/__tests__/Button.test.tsx", files)

    def test_baseline_ratchet_only_fails_new_drift(self):
        code, _ = gate(self.project, "ui-ux.token-drift", "--update-baseline")
        self.assertEqual(code, 0)
        code, rep = gate(self.project, "ui-ux.token-drift")
        self.assertEqual(code, 0, rep)
        (self.project / "src" / "extra.css").write_text(".new { border-color: #abcdef; }\n")
        code, rep = gate(self.project, "ui-ux.token-drift")
        self.assertEqual(code, 1, rep)
        self.assertEqual([f["evidence"]["file"] for f in rep["findings"]], ["src/extra.css"])


@unittest.skipUnless(shutil.which("npx"), "Node/npx is required for browser gates")
class InteractionGateTests(TempProject):
    def run_sandbox(self, name, *extra):
        return gate(self.tmp, "ui-ux.interaction", "--sandbox", str(FIXTURES / "a11y" / name), *extra)

    def test_accessible_page_passes(self):
        code, rep = self.run_sandbox("good.html")
        self.assertEqual(code, 0, rep)

    def test_keyboard_and_target_problems_are_found(self):
        code, rep = self.run_sandbox("interaction-bad.html")
        self.assertEqual(code, 1, rep)
        verified = {f["rule"] for f in rep["findings"] if f["confidence"] == "verified"}
        self.assertEqual(verified, {"target-size-minimum", "focus-not-visible", "positive-tabindex", "aria-widget-not-focusable"})

    def test_keyboard_trap_is_found(self):
        code, rep = self.run_sandbox("interaction-trap.html")
        self.assertEqual(code, 1, rep)
        self.assertIn("keyboard-trap", {f["rule"] for f in rep["findings"]})

    def test_aaa_level_makes_touch_size_mandatory(self):
        code, rep = self.run_sandbox("interaction-trap.html", "--level", "AAA")
        touch = [f for f in rep["findings"] if f["rule"] == "touch-target-below-44"]
        self.assertTrue(touch and touch[0]["confidence"] == "verified", rep)


if __name__ == "__main__":
    unittest.main()
