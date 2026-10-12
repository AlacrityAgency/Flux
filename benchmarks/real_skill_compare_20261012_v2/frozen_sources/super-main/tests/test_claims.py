#!/usr/bin/env python3
"""Tests for the claims module (document vs. code), PDF text extraction, and the related review/inventory changes."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SA = ROOT / "core" / "bin" / "sa.py"
FIXTURES = ROOT / "tests" / "fixtures"
sys.path.insert(0, str(ROOT / "core" / "lib"))
sys.path.insert(0, str(ROOT / "modules" / "testing" / "gates"))

import doctext  # noqa: E402
import testlib  # noqa: E402


def build_pdf(content: bytes, font: bytes, extra_objects=()) -> bytes:
    """Assemble a minimal PDF (no xref needed by the built-in parser) with one page and one font."""
    stream = zlib.compress(content)
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 5 0 R >> /ProcSet [/PDF /Text] >> /MediaBox [0 0 612 792] /Contents 4 0 R >>",
        b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(stream) + stream + b"\nendstream",
        font,
        *extra_objects,
    ]
    out = b"%PDF-1.4\n"
    for i, body in enumerate(objects, 1):
        out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    return out + b"trailer << /Root 1 0 R >>\n%%EOF\n"


def sa(project, *args):
    proc = subprocess.run([sys.executable, str(SA), "--project", str(project), *args], capture_output=True, text=True, timeout=300)
    try:
        return proc.returncode, json.loads(proc.stdout)
    except json.JSONDecodeError:
        return proc.returncode, {"raw": proc.stdout + proc.stderr}


class PdfExtractionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="sa-pdf-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_simple_font_text_and_lines(self):
        content = b"BT /F1 12 Tf 72 700 Td (stride_impact_force_g is reliable) Tj 0 -14 Td [(second) -300 (line)] TJ ET"
        pdf = self.tmp / "a.pdf"
        pdf.write_bytes(build_pdf(content, b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"))
        text, method = doctext.BuiltinPdf(pdf.read_bytes()).text(), "builtin"
        self.assertIn("stride_impact_force_g is reliable", text)
        self.assertIn("second line", text)

    def test_cid_font_with_tounicode_and_persian_presentation_forms(self):
        # Glyph codes 0001-0004 map to presentation forms of «تست» + 'x'; NFKC must fold them to plain letters.
        cmap = (b"/CIDInit /ProcSet findresource begin begincmap\n1 begincodespacerange <0000> <FFFF> endcodespacerange\n"
                b"3 beginbfchar <0001> <FE97> <0002> <FEB4> <0003> <FE96> endbfchar\n"
                b"1 beginbfrange <0004> <0005> <0078> endbfrange\nendcmap end")
        cmap_stream = zlib.compress(cmap)
        cmap_obj = b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(cmap_stream) + cmap_stream + b"\nendstream"
        font = b"<< /Type /Font /Subtype /Type0 /BaseFont /Vazir /Encoding /Identity-H /ToUnicode 6 0 R >>"
        content = b"BT /F1 12 Tf 72 700 Td <000100020003> Tj 0 -14 Td <00040005> Tj ET"
        pdf = self.tmp / "b.pdf"
        pdf.write_bytes(build_pdf(content, font, [cmap_obj]))
        text, method = doctext.extract_text(pdf)
        if method == "builtin":
            self.assertIn("تست", text)
            self.assertIn("xy", text)

    def test_markdown_and_docx(self):
        md = self.tmp / "r.md"
        md.write_text("metric_one_value here", encoding="utf-8")
        self.assertIn("metric_one_value", doctext.extract_text(md)[0])
        import zipfile
        docx = self.tmp / "r.docx"
        with zipfile.ZipFile(docx, "w") as z:
            z.writestr("word/document.xml", "<w:document><w:p><w:r><w:t>pupil_dilation_ratio</w:t></w:r></w:p></w:document>")
        self.assertIn("pupil_dilation_ratio", doctext.extract_text(docx)[0])


class ClaimsTraceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="sa-claims-"))
        self.project = self.tmp / "app"
        shutil.copytree(FIXTURES / "claims" / "app", self.project)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def trace(self, *docs):
        args = []
        for d in docs:
            args += ["--doc", d]
        return sa(self.project, "gate", "claims.trace", "--json", "--", *args)

    def test_statuses_match_the_code(self):
        code, rep = self.trace("REPORT.md")
        self.assertEqual(code, 1, rep)
        table = {r["claim"]: r["status"] for r in rep["metrics"]["table"]}
        self.assertEqual(table, {
            "blink_burst_rate": "research-only", "facial_specularity": "absent", "knee_flexion_variance_deg": "absent",
            "sit_to_stand_speed_m_s": "never-computed", "step_width_ratio": "active", "stride_impact_force_g": "research-only",
            "tremor_amplitude_mm": "not-measured",
        })

    def test_findings_respect_document_qualifiers(self):
        _, rep = self.trace("REPORT.md")
        by_claim = {}
        for f in rep["findings"]:
            by_claim.setdefault(f["evidence"].get("identifier"), []).append(f["rule"])
        self.assertNotIn("blink_burst_rate", by_claim)  # the document says "research only"
        self.assertIn("claim-absent", by_claim["facial_specularity"])
        self.assertIn("claim-not-measured", by_claim["tremor_amplitude_mm"])
        self.assertIn("claim-never-computed", by_claim["sit_to_stand_speed_m_s"])
        self.assertEqual(sorted(by_claim["stride_impact_force_g"]), ["claim-name-semantics", "claim-research-only"])
        self.assertIn("claim-name-semantics", by_claim["knee_flexion_variance_deg"])

    def test_absent_claim_reports_where_it_still_appears(self):
        _, rep = self.trace("REPORT.md")
        absent = next(f for f in rep["findings"] if f["evidence"].get("identifier") == "facial_specularity")
        self.assertEqual(absent["evidence"]["only_in"], ["tests/test_old.py"])

    def test_broken_reference_and_unsupported_performance_claim(self):
        _, rep = self.trace("REPORT.md")
        rules = {f["rule"]: f for f in rep["findings"]}
        self.assertEqual(rules["broken-file-reference"]["evidence"]["reference"], "src/vision/pupil.py")
        self.assertEqual(rules["unsupported-performance-claim"]["confidence"], "suspected")

    def test_persian_qualifier_is_recognised(self):
        _, rep = self.trace("REPORT.fa.md")
        flagged = {f["evidence"].get("identifier") for f in rep["findings"]}
        self.assertNotIn("blink_burst_rate", flagged)  # «پژوهشی است»
        self.assertIn("tremor_amplitude_mm", flagged)

    def test_missing_document_is_not_tested(self):
        code, rep = self.trace("nope.pdf")
        self.assertEqual(code, 2, rep)


class ReviewAndInventoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="sa-inv-"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_review_plans_claims_for_docs_and_hints_candidates(self):
        project = self.tmp / "app"
        shutil.copytree(FIXTURES / "claims" / "app", project)
        (project / "Feature Report.pdf").write_bytes(b"%PDF-1.4\n")
        proc = subprocess.run([sys.executable, str(SA), "--project", str(project), "review", "--dry-run", "--json"], capture_output=True, text=True, timeout=120)
        plan = json.loads(proc.stdout)["plan"]
        self.assertTrue(any("Feature Report.pdf" in h for h in plan["hints"]), plan["hints"])
        proc = subprocess.run([sys.executable, str(SA), "--project", str(project), "review", "--dry-run", "--json", "--doc", "REPORT.md"], capture_output=True, text=True, timeout=120)
        plan = json.loads(proc.stdout)["plan"]
        self.assertIn("claims.trace", [s["gate"] for s in plan["steps"]])
        trace = next(s for s in plan["steps"] if s["gate"] == "claims.trace")
        self.assertIsNotNone(trace["scope"])
        self.assertIn("claims.trace@" + trace["scope"], plan["required"])

    def test_electron_and_plain_html_apps_are_frontend(self):
        electron = self.tmp / "electron"
        electron.mkdir()
        (electron / "package.json").write_text(json.dumps({"devDependencies": {"electron": "30"}}))
        (electron / "main.js").write_text("require('electron');\n")
        code, rep = sa(electron, "gate", "testing.inventory", "--json")
        self.assertIn("frontend", rep["metrics"]["layers"])
        plain = self.tmp / "plain"
        (plain / "ui").mkdir(parents=True)
        (plain / "ui" / "index.html").write_text("<html><body><script src='app.js'></script></body></html>")
        (plain / "ui" / "app.js").write_text("console.log(1);\n")
        (plain / "engine.py").write_text("def score():\n    return 1\n")
        code, rep = sa(plain, "gate", "testing.inventory", "--json")
        self.assertEqual(rep["metrics"]["layers"], "frontend, core-logic")
        self.assertEqual(rep["metrics"]["recommended_shape"], "pyramid+trophy")

    def test_project_virtualenv_python_is_used(self):
        project = self.tmp / "venv-project"
        (project / ".venv" / "bin").mkdir(parents=True)
        os.symlink(sys.executable, project / ".venv" / "bin" / "python")
        cmd, _ = testlib.runner_command("unittest", project, project / "j.xml", project / "o.json")
        self.assertEqual(cmd[0], str(project / ".venv" / "bin" / "python"))

    def test_gate_help_is_not_recorded_as_evidence(self):
        project = self.tmp / "help"
        project.mkdir()
        proc = subprocess.run([sys.executable, str(SA), "--project", str(project), "gate", "testing.run", "--", "--help"], capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 0)
        self.assertIn("--repeat", proc.stdout)
        self.assertFalse((project / ".superagent" / "ledger.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
