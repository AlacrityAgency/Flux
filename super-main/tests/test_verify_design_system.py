#!/usr/bin/env python3
"""Regression checks for token validation results that previously gave false passes."""

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "modules" / "ui-ux" / "gates" / "verify_design_system.py"
SPEC = importlib.util.spec_from_file_location("verify_design_system", SCRIPT)
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


class TokenAuditTests(unittest.TestCase):
    def test_valid_tokens_and_inherited_alias_type(self):
        data = json.loads((ROOT / "tests/fixtures/valid/tokens.json").read_text())
        pairs = json.loads((ROOT / "tests/fixtures/valid/contrast-pairs.json").read_text())
        self.assertEqual(AUDIT.audit_tokens(data, pairs), ([], 5))

    def test_invalid_types_and_values_are_rejected(self):
        for name in ("bad-type", "bad-dimension", "circular-alias", "bad-motion", "bad-surface", "bad-font-size"):
            with self.subTest(name=name):
                data = json.loads((ROOT / f"tests/fixtures/invalid/{name}.json").read_text())
                errors, _ = AUDIT.audit_tokens(data)
                self.assertTrue(errors)

    def test_missing_alias_is_rejected(self):
        errors, _ = AUDIT.audit_tokens({"a": {"$type": "number", "$value": "{missing}"}})
        self.assertIn("alias target does not exist", " ".join(errors))

    def test_malformed_type_does_not_crash(self):
        errors, _ = AUDIT.audit_tokens({"a": {"$type": ["color"], "$value": 1}})
        self.assertIn("unsupported $type", " ".join(errors))

    def test_low_contrast_is_rejected(self):
        data = json.loads((ROOT / "tests/fixtures/valid/tokens.json").read_text())
        pairs = json.loads((ROOT / "tests/fixtures/invalid/contrast-pairs.json").read_text())
        errors, _ = AUDIT.audit_tokens(data, pairs)
        self.assertIn("below 4.5:1", " ".join(errors))

    def test_missing_file_is_not_a_pass(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--tokens", "/nonexistent/tokens.json", "--json"],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["status"], "fail")

    def test_invalid_motion_rejected(self):
        bad_token = {"motion-a": {"$type": "motion", "$value": {"duration": "banana", "easing": False}}}
        errors, _ = AUDIT.audit_tokens(bad_token)
        self.assertTrue(errors)
        self.assertIn("invalid motion duration", " ".join(errors))

    def test_invalid_motion_fuzzing_rejected(self):
        # Boolean easing, raw number without unit, invalid bezier
        cases = [
            ({"duration": "200ms", "easing": False}, "invalid easing"),
            ({"duration": 100, "easing": "ease"}, "invalid motion duration"),
            ({"duration": "200ms", "easing": "cubic-bezier(1.5, 0, 0, 1)"}, "cubic-bezier x coordinates must be in range 0..1"),
            ({"duration": "200ms", "easing": [1.5, 0, 0, 1]}, "easing curve x coordinates must be within 0..1"),
        ]
        for val, expected_err in cases:
            with self.subTest(val=val):
                errors, _ = AUDIT.audit_tokens({"m": {"$type": "motion", "$value": val}})
                self.assertTrue(errors)
                self.assertIn(expected_err, " ".join(errors))

    def test_valid_motion_accepted(self):
        good_token = {
            "motion-a": {"$type": "motion", "$value": {"duration": "250ms", "easing": "cubic-bezier(0.16, 1, 0.3, 1)"}},
            "motion-b": {"$type": "motion", "$value": {"duration": "0.3s", "easing": "ease-out"}},
        }
        errors, count = AUDIT.audit_tokens(good_token)
        self.assertEqual(errors, [])
        self.assertEqual(count, 2)

    def test_invalid_surface_effect_rejected(self):
        bad_token = {"surf-a": {"$type": "surface-effect", "$value": {"blur": "banana"}}}
        errors, _ = AUDIT.audit_tokens(bad_token)
        self.assertTrue(errors)
        self.assertIn("invalid surface-effect blur", " ".join(errors))

    def test_invalid_surface_effect_fuzzing_rejected(self):
        cases = [
            ({"noise": 2.5}, "invalid surface-effect noise opacity"),
            ({"noise": "invalid"}, "invalid surface-effect noise opacity"),
            ({"saturation": -5}, "surface-effect saturation must be a non-negative number"),
            ({"blur": 12}, "invalid surface-effect blur"),
        ]
        for val, expected_err in cases:
            with self.subTest(val=val):
                errors, _ = AUDIT.audit_tokens({"s": {"$type": "surface-effect", "$value": val}})
                self.assertTrue(errors)
                self.assertIn(expected_err, " ".join(errors))

    def test_valid_surface_effect_accepted(self):
        good_token = {
            "surf-a": {
                "$type": "surface-effect",
                "$value": {"blur": "16px", "saturation": "180%", "noise": 0.05}
            }
        }
        errors, count = AUDIT.audit_tokens(good_token)
        self.assertEqual(errors, [])
        self.assertEqual(count, 1)

    def test_invalid_font_size_clamp_rejected(self):
        bad_token = {"fs-a": {"$type": "font-size", "$value": "clamp(banana)"}}
        errors, _ = AUDIT.audit_tokens(bad_token)
        self.assertTrue(errors)
        self.assertIn("invalid clamp() syntax", " ".join(errors))

    def test_invalid_font_size_units_rejected(self):
        for bad_val in ("12foo", 12, "clamp(12px, bar, 24px)"):
            with self.subTest(bad_val=bad_val):
                errors, _ = AUDIT.audit_tokens({"fs": {"$type": "font-size", "$value": bad_val}})
                self.assertTrue(errors)

    def test_valid_font_size_clamp_accepted(self):
        good_token = {
            "fs-a": {"$type": "font-size", "$value": "clamp(1rem, 2vw + 1rem, 2.5rem)"},
            "fs-b": {"$type": "font-size", "$value": "18px"}
        }
        errors, count = AUDIT.audit_tokens(good_token)
        self.assertEqual(errors, [])
        self.assertEqual(count, 2)


if __name__ == "__main__":
    unittest.main()
