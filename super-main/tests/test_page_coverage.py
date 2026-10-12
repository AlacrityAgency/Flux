#!/usr/bin/env python3
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SA = ROOT / "core/bin/sa.py"
FIXTURE = ROOT / "tests/fixtures/a11y/scroll-lazy.html"


@unittest.skipUnless(shutil.which("npx"), "Node/npx required")
class PageCoverageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="sa-scroll-")
        self.project = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def gate(self, target=FIXTURE, *args):
        proc = subprocess.run([sys.executable, "-B", str(SA), "--project", str(self.project), "gate", "ui-ux.page-coverage", "--json",
                               "--", "--url", target.as_uri(), "--settle-ms", "100", *args],
                              capture_output=True, text=True, timeout=180)
        try:
            return proc.returncode, json.loads(proc.stdout)
        except ValueError:
            self.fail(proc.stdout + proc.stderr)

    def test_lazy_footer_and_internal_end_captured_on_both_viewports(self):
        code, result = self.gate()
        self.assertEqual(code, 0, result)
        directory = Path(result["artifacts"]["results"]) / "viewports"
        for name in ("desktop", "mobile"):
            data = json.loads((directory / (name + ".json")).read_text())
            self.assertTrue(data["complete"])
            document = next(row for row in data["regions"] if row["label"] == "document")
            self.assertGreater(document["samples"][-1]["height"], 2600)
            self.assertGreaterEqual(document["samples"][-1]["top"] + document["samples"][-1]["viewport"], document["samples"][-1]["height"] - 2)
            inner = next(row for row in data["regions"] if row.get("id") == "internal")
            self.assertTrue(inner["complete"])
            self.assertGreater(inner["samples"][-1]["top"], 500)
            self.assertGreater(len(data["screenshots"]), 4)
            self.assertTrue(all((directory / image).read_bytes().startswith(b'\x89PNG') for image in data["screenshots"]))

    def test_step_budget_exhaustion_is_gap_not_green(self):
        code, result = self.gate(FIXTURE, "--max-steps", "2")
        self.assertEqual((code, result["status"]), (2, "NOT-TESTED"), result)
        self.assertFalse(result["metrics"]["scroll_coverage"]["desktop"]["complete"])

    def test_horizontal_overflow_below_fold_detected(self):
        page = self.project / "overflow.html"
        page.write_text('<!doctype html><html><body style="margin:0"><div style="height:2000px"></div><div style="width:1800px">below-fold bug</div></body></html>')
        code, result = self.gate(page)
        self.assertEqual(code, 1, result)
        self.assertIn("horizontal-overflow", {f["rule"] for f in result["findings"]})


if __name__ == "__main__":
    unittest.main()
