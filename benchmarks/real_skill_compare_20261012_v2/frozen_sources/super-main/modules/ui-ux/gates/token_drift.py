#!/usr/bin/env python3
"""ui-ux.token-drift: styles that bypass the design tokens.

Detects, outside token-definition files and test files:
  hardcoded-color     hex / rgb() / hsl() literals in styles, inline styles and JS style strings
  arbitrary-color     Tailwind arbitrary colors such as bg-[#123456]
  arbitrary-length    Tailwind arbitrary pixel values such as text-[13px], p-[7px]
  raw-palette-class   bg-slate-800 style classes when the project defines a semantic theme
                      (CSS variables such as --primary / --background)
Custom-property definitions (--brand: #0f172a) are token definitions and are allowed.

Ratchet: --update-baseline records today's drift in .superagent/token-drift-baseline.json;
afterwards only drift beyond the baseline fails, so legacy code does not block new work.
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "core" / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "testing" / "gates"))

from gatekit import base_parser, emit, iter_project_files, make_finding, project_root, report, work_dir  # noqa: E402
from testlib import is_test_file  # noqa: E402
from discovery import role_of  # noqa: E402
from project import load_config  # noqa: E402


GATE = "ui-ux.token-drift"
STYLE_EXT = {".css", ".scss", ".sass", ".less"}
CODE_EXT = {".js", ".jsx", ".ts", ".tsx", ".vue", ".svelte", ".html", ".astro", ".mdx"}
TOKEN_FILE = re.compile(r"(^|[./-])(tokens?|theme|themes|variables|palette|colors)([./-]|$)|tailwind\.config|\.tokens\.", re.I)
HEX = r"#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})\b"
FUNC = r"\b(?:rgba?|hsla?)\(\s*\d"
CSS_DECL = re.compile(rf"(?<![-\w])(?!--)[a-z][a-z-]*\s*:[^;{{}}]*?({HEX}|{FUNC})", re.I)
INLINE_STYLE = re.compile(rf"style\s*=\s*(?:\"[^\"]*?({HEX}|{FUNC})|'[^']*?({HEX}|{FUNC})|{{\{{[^}}]*?['\"`]({HEX}|{FUNC}))", re.I)
JS_STYLE_PROP = re.compile(rf"\b(?:color|background(?:Color)?|borderColor|fill|stroke|outlineColor|boxShadow)\s*:\s*['\"`]({HEX}|{FUNC})", re.I)
ARBITRARY_COLOR = re.compile(r"\b(?:bg|text|border(?:-[trblxy])?|ring|ring-offset|fill|stroke|from|via|to|shadow|outline|decoration|accent|caret|divide|placeholder)-\[(?:#|rgb|hsl|oklch)[^\]]*\]")
ARBITRARY_LENGTH = re.compile(r"\b(?:p[xytrblse]?|m[xytrblse]?|w|h|min-w|min-h|max-w|max-h|size|gap(?:-[xy])?|text|rounded(?:-[a-z]+)?|top|left|right|bottom|start|end|inset(?:-[xy])?|leading|tracking|space-[xy])-\[-?\d+(?:\.\d+)?px\]")
PALETTE = "slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose"
RAW_PALETTE = re.compile(rf"\b(?:bg|text|border|ring|fill|stroke|from|via|to|outline|divide|placeholder|decoration)-(?:{PALETTE})-\d{{2,3}}\b")
SEMANTIC_THEME = re.compile(r"--(?:primary|background|foreground|surface|brand|accent)\b|hsl\(var\(--|var\(--color-")


def line_of(text, index):
    return text.count("\n", 0, index) + 1


def uses_semantic_theme(project: Path) -> bool:
    for path in iter_project_files(project, STYLE_EXT | {".js", ".ts", ".cjs", ".mjs"}, max_files=4000):
        if path.suffix in STYLE_EXT or "tailwind.config" in path.name:
            try:
                if SEMANTIC_THEME.search(path.read_text(encoding="utf-8", errors="ignore")):
                    return True
            except OSError:
                continue
    return False


def scan(project: Path, semantic: bool):
    hits = []  # (file, rule, line, match)
    sources = load_config(project).get("sources", {})
    for path in iter_project_files(project, STYLE_EXT | CODE_EXT):
        rel = str(path.relative_to(project))
        role, _ = role_of(rel, sources)
        if role in {"reference", "generated"}:
            continue
        if is_test_file(Path(rel)) or TOKEN_FILE.search(path.name) or ".min." in path.name:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        patterns = []
        if path.suffix in STYLE_EXT:
            patterns.append(("hardcoded-color", CSS_DECL))
        else:
            patterns += [("hardcoded-color", INLINE_STYLE), ("hardcoded-color", JS_STYLE_PROP)]
            if path.suffix in {".vue", ".svelte", ".html", ".astro"}:
                for block in re.finditer(r"<style[^>]*>([\s\S]*?)</style>", text):
                    for m in CSS_DECL.finditer(block.group(1)):
                        hits.append((rel, "hardcoded-color", line_of(text, block.start(1) + m.start()), m.group(0).strip()[:80]))
        patterns += [("arbitrary-color", ARBITRARY_COLOR), ("arbitrary-length", ARBITRARY_LENGTH)]
        if semantic:
            patterns.append(("raw-palette-class", RAW_PALETTE))
        for rule, regex in patterns:
            for m in regex.finditer(text):
                hits.append((rel, rule, line_of(text, m.start()), m.group(0).strip()[:80]))
    # Several patterns can match the same declaration (e.g. an inline style object); count it once.
    unique, seen = [], set()
    for hit in hits:
        if (hit[0], hit[1], hit[2]) not in seen:
            seen.add((hit[0], hit[1], hit[2]))
            unique.append(hit)
    return unique


def key(hit):
    rel, rule, _, match = hit
    return f"{rel}|{rule}|{match}"


def main():
    parser = base_parser("Find styles that bypass the design tokens")
    parser.add_argument("--update-baseline", action="store_true", help="Accept current drift as the baseline (ratchet)")
    args = parser.parse_args()
    project = project_root(args.project)
    semantic = uses_semantic_theme(project)
    hits = scan(project, semantic)
    baseline_path = work_dir(project) / "token-drift-baseline.json"

    if args.update_baseline:
        baseline_path.write_text(json.dumps(Counter(key(h) for h in hits), indent=2, ensure_ascii=False), encoding="utf-8")
        return emit(report(GATE, "PASS", str(project), [], [f"Baseline recorded with {len(hits)} existing occurrences: {baseline_path}"],
                           {"occurrences": len(hits), "semantic_theme": semantic}), args.json)

    allowed = Counter(json.loads(baseline_path.read_text(encoding="utf-8"))) if baseline_path.is_file() else Counter()
    new_hits, seen = [], Counter()
    for hit in hits:
        k = key(hit)
        seen[k] += 1
        if seen[k] > allowed.get(k, 0):
            new_hits.append(hit)

    grouped = {}
    for rel, rule, line, match in new_hits:
        grouped.setdefault((rel, rule), []).append(f"{line}: {match}")
    impact = {
        "hardcoded-color": "A literal color bypasses the theme: it will not follow dark mode, brand changes or contrast fixes.",
        "arbitrary-color": "An arbitrary color class bypasses the theme tokens.",
        "arbitrary-length": "An arbitrary pixel value breaks the spacing/type scale.",
        "raw-palette-class": "A raw palette class bypasses the project's semantic theme colors.",
    }
    findings = []
    for (rel, rule), lines in sorted(grouped.items()):
        findings.append(make_finding(len(findings) + 1, "ui-ux", GATE, rule, "P2", rel, {"file": rel, "occurrences": lines[:20], "count": len(lines)},
                                     impact[rule], "Replace with the matching token (CSS variable, semantic Tailwind class or scale value)."))
    notes = []
    if baseline_path.is_file():
        notes.append(f"Baseline in use ({sum(allowed.values())} accepted occurrences); only new drift is reported.")
    metrics = {"occurrences": len(hits), "new_occurrences": len(new_hits), "semantic_theme": semantic}
    return emit(report(GATE, "FAIL" if findings else "PASS", str(project), findings, notes, metrics), args.json)


if __name__ == "__main__":
    sys.exit(main())
