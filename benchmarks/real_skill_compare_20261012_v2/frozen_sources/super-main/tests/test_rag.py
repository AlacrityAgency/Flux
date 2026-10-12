#!/usr/bin/env python3
"""Tests for the local reference search (core/lib/rag.py), including the Persian evaluation set."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "core" / "lib"))

import rag  # noqa: E402


class RagUnitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "core").mkdir()
        (self.root / "modules" / "alpha").mkdir(parents=True)
        (self.root / "core" / "rules.md").write_text("# Evidence\nGates decide the verdict.\n", encoding="utf-8")
        (self.root / "modules" / "alpha" / "guide.md").write_text("# Buttons\nButtons need a visible focus ring.\n\n```\n# not a heading\n```\n", encoding="utf-8")
        self.db = self.root / "index.db"

    def tearDown(self):
        self.tmp.cleanup()

    def search(self, query, **kw):
        return rag.search(query, db_path=self.db, root=self.root, glossary=[], **kw)

    def test_sections_carry_their_module(self):
        results = self.search("buttons focus")
        self.assertEqual(results[0]["module"], "alpha")
        self.assertEqual(results[0]["section"], "Buttons")

    def test_code_blocks_do_not_create_headings(self):
        sections = rag.parse_sections(self.root / "modules" / "alpha" / "guide.md")
        self.assertEqual([s for s, _ in sections], ["Buttons"])

    def test_module_filter_keeps_core(self):
        self.assertTrue(all(r["module"] in {"alpha", "core"} for r in self.search("verdict buttons", module="alpha")))
        self.assertEqual(self.search("buttons", module="other"), [])

    def test_index_rebuilds_when_a_document_changes(self):
        self.assertTrue(self.search("buttons"))
        guide = self.root / "modules" / "alpha" / "guide.md"
        guide.write_text("# Sliders\nSliders need labels.\n", encoding="utf-8")
        stat = guide.stat()
        os.utime(guide, ns=(stat.st_atime_ns, stat.st_mtime_ns + 5_000_000_000))
        self.assertTrue(self.search("sliders"))
        self.assertFalse(self.search("buttons", module="alpha"))

    def test_same_size_change_with_preserved_mtime_invalidates_index(self):
        guide = self.root / "modules" / "alpha" / "guide.md"
        guide.write_text("# Entry\nMango rule.\n", encoding="utf-8")
        self.assertTrue(self.search("mango"))
        stat = guide.stat()
        guide.write_text("# Entry\nGuava rule.\n", encoding="utf-8")
        os.utime(guide, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        self.assertTrue(self.search("guava"))
        self.assertFalse(self.search("mango"))

    def test_professional_persian_queries_retrieve_relevant_guidance(self):
        cases = {
            "رزومه مدیریتی و سوابق شغلی": "modules/product/references/professional-artifacts.md",
            "مخاطب و هدف سند": "core/task-framing.md",
            "اعتبار منبع و شواهد مخالف": "core/workflows/research.md",
        }
        with tempfile.TemporaryDirectory() as tmp:
            for query, expected in cases.items():
                paths = [r["path"] for r in rag.search(query, db_path=Path(tmp) / "index.db", limit=5)]
                self.assertIn(expected, paths, query)

    def test_hostile_query_characters_are_safe(self):
        self.assertIsInstance(self.search('foo" OR bar* NEAR( ) -x'), list)

    def test_persian_normalisation_and_glossary(self):
        glossary = [(rag.normalize("دسترس‌پذیری"), ["accessibility"]), (rag.normalize("تب"), ["tabs"])]
        self.assertEqual(rag.expand_query("دسترس‌پذیري", glossary), ["accessibility"])  # Arabic yeh + ZWNJ
        self.assertEqual(rag.expand_query("تبدیل", glossary), [])  # no match inside a longer word


class RagEvaluationSet(unittest.TestCase):
    """Top-3 hit rate on evals/rag/queries.json must stay >= 90% (English and Persian queries)."""

    def test_top3_hit_rate(self):
        cases = json.loads((ROOT / "evals" / "rag" / "queries.json").read_text(encoding="utf-8"))["queries"]
        misses, by_lang = [], {}
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "index.db"
            for case in cases:
                paths = [r["path"] for r in rag.search(case["q"], module=case.get("module"), limit=3, db_path=db)]
                hit = case["expect"] in paths
                lang = case.get("lang", "en")
                by_lang.setdefault(lang, [0, 0])
                by_lang[lang][0] += hit
                by_lang[lang][1] += 1
                if not hit:
                    misses.append(f"{case['q']} -> {paths}")
        total_hits = sum(h for h, _ in by_lang.values())
        rate = total_hits / len(cases)
        self.assertGreaterEqual(len(cases), 40)
        self.assertGreaterEqual(rate, 0.9, "\n".join(misses))
        for lang, (hits, count) in by_lang.items():
            self.assertGreaterEqual(hits / count, 0.85, f"{lang}: {hits}/{count}\n" + "\n".join(misses))


if __name__ == "__main__":
    unittest.main()
