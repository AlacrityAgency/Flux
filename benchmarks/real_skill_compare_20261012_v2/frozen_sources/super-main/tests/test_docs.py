#!/usr/bin/env python3
"""Consistency checks for the skill's documentation, manifests and metadata."""

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = [p for p in ROOT.rglob("*.md")
        if not {"node_modules", ".superagent", "fixtures", ".git"} & set(p.relative_to(ROOT).parts)]
LINK = re.compile(r"\]\(([^)#\s]+)(#[^)]*)?\)")
REMOVED = [
    "instructions.md", "knowledge_map.json", "tokens.schema.json", "sandpack", "Sandpack", "ADVERSARIAL-QA",
    "scripts/a11y_gate.py", "search_local_docs", "sqlite_indexer", "decision-policies.md", "quality-rubric.md",
    "domain-semantics.md", "semantic_cache", "skill.yaml", "npm run test:a11y", "<skill>/scripts/",
]

sys.path.insert(0, str(ROOT / "modules" / "ui-ux" / "gates"))
from verify_design_system import audit_tokens  # noqa: E402


class DocumentationConsistencyTests(unittest.TestCase):
    def test_relative_links_resolve(self):
        broken = []
        for doc in DOCS:
            for target, _ in LINK.findall(doc.read_text(encoding="utf-8")):
                if target.startswith(("http://", "https://", "mailto:")):
                    continue
                if not (doc.parent / target).exists():
                    broken.append(f"{doc.relative_to(ROOT)} -> {target}")
        self.assertEqual(broken, [])

    def test_removed_files_and_concepts_are_not_referenced(self):
        files = DOCS + list((ROOT / "modules").rglob("*.json")) + [ROOT / "package.json"]
        hits = []
        for path in files:
            text = path.read_text(encoding="utf-8")
            hits += [f"{path.relative_to(ROOT)}: {word}" for word in REMOVED if word in text]
        self.assertEqual(hits, [])

    def test_versions_match_the_version_file(self):
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(json.loads((ROOT / "package.json").read_text())["version"], version)
        self.assertIn(f'version = "{version}"', (ROOT / "pyproject.toml").read_text())

    def test_skill_frontmatter(self):
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        match = re.match(r"^---\nname: ([a-z0-9-]+)\ndescription: (.+?)\n---\n", text, re.S)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), ROOT.name)  # Antigravity defaults the name to the folder name
        self.assertGreater(len(match.group(2)), 100)
        self.assertLess(len(text.splitlines()), 150)

    def test_module_manifests_point_to_existing_files(self):
        for manifest in (ROOT / "modules").glob("*/module.json"):
            data = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(data["id"], manifest.parent.name)
            self.assertTrue((manifest.parent / data["workflow"]).is_file(), data["workflow"])
            for gate in data["gates"]:
                with self.subTest(gate=gate["id"]):
                    self.assertTrue(gate["id"].startswith(data["id"] + "."))
                    script = manifest.parent / gate["script"]
                    self.assertTrue(script.is_file())
                    proc = subprocess.run([sys.executable, str(script), "--help"], capture_output=True, text=True, timeout=60)
                    self.assertEqual(proc.returncode, 0, proc.stderr)
                    self.assertIn("--project", proc.stdout)

    def test_knowledge_tree_paths_exist(self):
        tree = json.loads((ROOT / "modules" / "ui-ux" / "templates" / "knowledge_tree.json").read_text(encoding="utf-8"))
        paths = [c[k] for c in tree["components"].values() for k in ("primary_reference", "secondary_reference")]
        paths += [d["file"] for d in tree["domains"].values()]
        self.assertEqual([p for p in paths if not (ROOT / p).is_file()], [])

    def test_token_examples_in_docs_validate(self):
        text = (ROOT / "modules" / "ui-ux" / "references" / "tokens.md").read_text(encoding="utf-8")
        blocks = re.findall(r"```json\n(.*?)```", text, re.S)
        tokens = json.loads(blocks[0])
        errors, count = audit_tokens(tokens)
        self.assertEqual(errors, [])
        self.assertGreater(count, 3)


if __name__ == "__main__":
    unittest.main()
