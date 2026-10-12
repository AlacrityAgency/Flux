#!/usr/bin/env python3
"""Regression tests for defects found in the skill review (token validator and research engine)."""

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core" / "scripts"))

SPEC = importlib.util.spec_from_file_location("verify_design_system", ROOT / "modules" / "ui-ux" / "gates" / "verify_design_system.py")
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)

import notebooklm_research as nlm_engine


def color(components, space="srgb", **extra):
    return {"$type": "color", "$value": {"colorSpace": space, "components": components, **extra}}


class ColorHexConsistencyTests(unittest.TestCase):
    def test_hex_that_contradicts_components_is_rejected(self):
        errors, _ = AUDIT.audit_tokens({"c": color([1, 1, 1], hex="#000000")})
        self.assertTrue(any("hex" in e for e in errors), errors)

    def test_matching_hex_is_accepted(self):
        errors, _ = AUDIT.audit_tokens({"c": color([1, 1, 1], hex="#ffffff")})
        self.assertEqual(errors, [])

    def test_matching_hex_for_oklch_is_accepted(self):
        # oklch(0.628 0.2577 29.23) is sRGB red (#ff0000) within rounding
        errors, _ = AUDIT.audit_tokens({"c": color([0.62796, 0.25768, 29.2339], "oklch", hex="#ff0000")})
        self.assertEqual(errors, [])


class FontSizeClampTests(unittest.TestCase):
    def test_clamp_object_with_garbage_is_rejected(self):
        token = {"f": {"$type": "font-size", "$value": {"clamp": {"min": "banana", "ideal": [], "max": {}}}}}
        errors, _ = AUDIT.audit_tokens(token)
        self.assertTrue(errors)

    def test_valid_clamp_object_is_accepted(self):
        token = {"f": {"$type": "font-size", "$value": {"clamp": {"min": "1rem", "ideal": "2vw + 1rem", "max": "2.5rem"}}}}
        errors, _ = AUDIT.audit_tokens(token)
        self.assertEqual(errors, [])

    def test_clamp_with_min_above_max_is_rejected(self):
        errors, _ = AUDIT.audit_tokens({"f": {"$type": "font-size", "$value": "clamp(100rem, 1vw, 1rem)"}})
        self.assertTrue(any("min" in e for e in errors), errors)


class SurfaceEffectTests(unittest.TestCase):
    def test_arbitrary_scrim_string_is_rejected(self):
        token = {"e": {"$type": "surface-effect", "$value": {"scrim": "javascript:alert(1)"}}}
        errors, _ = AUDIT.audit_tokens(token)
        self.assertTrue(errors)

    def test_css_color_and_alias_scrims_are_accepted(self):
        tokens = {
            "ink": color([0, 0, 0]),
            "a": {"$type": "surface-effect", "$value": {"scrim": "rgba(15, 23, 42, 0.85)"}},
            "b": {"$type": "surface-effect", "$value": {"scrim": "{ink}"}},
        }
        errors, _ = AUDIT.audit_tokens(tokens)
        self.assertEqual(errors, [])


class RobustnessTests(unittest.TestCase):
    def test_one_malformed_token_does_not_abort_the_audit(self):
        tokens = {
            "bad": {"$type": "motion", "$value": {"duration": "1s", "easing": "cubic-bezier(0.1.2, 1, 0.5, 1)"}},
            "good": {"$type": "dimension", "$value": {"value": 8, "unit": "px"}},
            "also-bad": {"$type": "dimension", "$value": {"value": 8, "unit": "furlong"}},
        }
        errors, count = AUDIT.audit_tokens(tokens)
        self.assertEqual(count, 3)
        self.assertTrue(any(e.startswith("bad:") for e in errors), errors)
        self.assertTrue(any(e.startswith("also-bad:") for e in errors), errors)

    def test_alias_inside_motion_resolves_to_target_type(self):
        tokens = {
            "d": {"$type": "duration", "$value": {"value": 200, "unit": "ms"}},
            "e": {"$type": "cubicBezier", "$value": [0.2, 0, 0, 1]},
            "m": {"$type": "motion", "$value": {"duration": "{d}", "easing": "{e}"}},
        }
        errors, _ = AUDIT.audit_tokens(tokens)
        self.assertEqual(errors, [])

    def test_alias_inside_motion_to_wrong_type_is_rejected(self):
        tokens = {
            "c": color([0, 0, 0]),
            "m": {"$type": "motion", "$value": {"duration": "{c}", "easing": "ease"}},
        }
        errors, _ = AUDIT.audit_tokens(tokens)
        self.assertTrue(errors)


class CompositedContrastTests(unittest.TestCase):
    TOKENS = {
        "black": color([0, 0, 0]),
        "veil": color([1, 1, 1], alpha=0.5),
    }

    def test_translucent_background_without_backdrop_is_explained(self):
        errors, _ = AUDIT.audit_tokens(self.TOKENS, [{"foreground": "black", "background": "veil", "minRatio": 4.5}])
        self.assertTrue(any("over" in e for e in errors), errors)

    def test_translucent_background_is_composited_over_backdrop(self):
        # Browsers blend in gamma-encoded sRGB: 50% white over black is ~#808080,
        # and black text on #808080 is about 5.3:1.
        passing = [{"foreground": "black", "background": "veil", "over": "black", "minRatio": 4.5}]
        failing = [{"foreground": "black", "background": "veil", "over": "black", "minRatio": 7}]
        self.assertEqual(AUDIT.audit_tokens(self.TOKENS, passing)[0], [])
        errors, _ = AUDIT.audit_tokens(self.TOKENS, failing)
        self.assertTrue(any("below 7" in e for e in errors), errors)


class DomainDetectionTests(unittest.TestCase):
    def detect(self, task, project_dir="/nonexistent-project-dir"):
        return nlm_engine.extract_codebase_context(project_dir, user_task=task)["domain"]

    def test_substrings_do_not_trigger_domains(self):
        for task in ("student identity login page", "independent report for accidents", "restore settings panel"):
            with self.subTest(task=task):
                self.assertEqual(self.detect(task), "General Web Application")

    def test_real_domain_words_are_detected(self):
        self.assertEqual(self.detect("dental clinic scheduler"), "Dental / Healthcare Practice Management")
        self.assertEqual(self.detect("crypto trading desk"), "FinTech / High-Frequency Trading Terminal")
        self.assertEqual(self.detect("online store checkout"), "E-Commerce & Digital Merchandising")

    def test_directory_names_use_whole_words(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "students").mkdir()
            self.assertEqual(self.detect("", tmp), "General Web Application")
            (Path(tmp) / "dental-records").mkdir()
            self.assertEqual(self.detect("", tmp), "Dental / Healthcare Practice Management")


class ResearchAttemptBudgetTests(unittest.TestCase):
    @patch("notebooklm_research.run_nlm_command")
    @patch("notebooklm_research.check_auth_status")
    def test_default_budget_is_two_attempts(self, mock_auth, mock_run):
        mock_auth.return_value = {"installed": True, "authenticated": True}
        mock_run.side_effect = [MagicMock(returncode=0, stdout="Notebook ID: fixture-notebook"),
                                MagicMock(returncode=0, stdout="[]"),
                                MagicMock(returncode=0, stdout='{"answer": "No sources found", "citations": {}}'),
                                MagicMock(returncode=0, stdout='{"answer": "No sources found", "citations": {}}')]
        res = nlm_engine.execute_research_pipeline("component dilemma", forced_mode="fast", import_sources=True)
        self.assertFalse(res["success"])
        self.assertEqual(res["attempts"], 2)
        self.assertEqual(mock_run.call_count, 4)
        self.assertEqual(sum(call[0][0][:2] == ["research", "start"] for call in mock_run.call_args_list), 1)

    @patch("notebooklm_research.run_nlm_command")
    @patch("notebooklm_research.check_auth_status")
    def test_web_sources_are_not_imported_by_default(self, mock_auth, mock_run):
        mock_auth.return_value = {"installed": True, "authenticated": True}
        mock_run.return_value = MagicMock(returncode=0, stdout="No sources available. Try again later please.")
        nlm_engine.execute_research_pipeline("component dilemma", forced_mode="fast", max_retries=0)
        self.assertNotIn("--auto-import", mock_run.call_args_list[0][0][0])
        nlm_engine.execute_research_pipeline("component dilemma", forced_mode="fast", max_retries=0, import_sources=True)
        self.assertIn("--auto-import", mock_run.call_args_list[-1][0][0])


if __name__ == "__main__":
    unittest.main()
