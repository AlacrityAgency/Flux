#!/usr/bin/env python3
"""claims.trace: does a document's description of the software match the code?

For every metric/feature identifier (snake_case names such as stride_impact_force_g) and file
reference in the document, the gate finds its status in the production code:

  absent          not in production code (maybe only in tests/docs, or renamed)       verified
  not-measured    listed in a container named like NOT_MEASURED / unavailable           verified
  research-only   listed in a container named like RESEARCH_ONLY / experimental         verified
  never-computed  every value assigned to it is a constant (0, None, NaN)               suspected
  active          computed in production code

A non-active status is a finding unless the document itself qualifies the claim near the name
(research, experimental, not measured, removed / پژوهشی، آزمایشی، اندازه‌گیری نمی‌شود، حذف …).
It also flags name/unit contradictions (a "force" reported in g) and performance claims
("reliable", "accurate", دقت، قابل اتکا) made without validation numbers. What a metric means
scientifically is out of reach for a static gate: see modules/claims/references/claim-review.md.
"""

import ast
import difflib
import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(SKILL_DIR / "core" / "lib"))
sys.path.insert(0, str(SKILL_DIR / "modules" / "testing" / "gates"))

from doctext import extract_text  # noqa: E402
from gatekit import base_parser, emit, iter_project_files, make_finding, project_root, report, work_dir  # noqa: E402
from testlib import SOURCE_EXT, is_test_file  # noqa: E402


GATE = "claims.trace"
IDENT = re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b")
WRAPPED = re.compile(r"(\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+)\n[ \t]*\n?[ \t]*([a-z0-9]{1,4})(?=\n)")
FILE_REF = re.compile(r"\b(?:[\w.-]+/)+[\w.-]+\.(?:py|js|ts|tsx|jsx|go|rs|java|kt|cs|rb|php|vue|svelte)\b")
NOT_MEASURED_NAME = re.compile(r"not_?measured|unmeasured|unavailable|disabled|deprecated|removed|unsupported", re.I)
RESEARCH_NAME = re.compile(r"research|experimental|exploratory|shadow|preview|beta|validation_only|diagnostic_only", re.I)
DOC_EXCLUDE_DIRS = {"graphify-out", "docs", "md_files", "output"}
QUALIFIERS = [
    "research", "experimental", "exploratory", "not measured", "unmeasured", "not yet", "removed", "deprecated",
    "planned", "future", "prototype", "disabled", "proposed",
    "پژوهشی", "آزمایشی", "اکتشافی", "اندازه گیری نمی", "اندازه گیری نشده", "حذف", "برنامه ریزی", "آینده", "غیرفعال", "پیشنهادی",
]
PERF_CLAIMS = ["reliable", "accurate", "accuracy", "validated", "robust detection", "high precision",
               "قابل اتکا", "دقت بالا", "دقیق", "اعتبارسنجی شده", "تشخیص دقیق", "دشواری جعل", "غیرقابل جعل"]
PERF_EVIDENCE = re.compile(r"\b(?:sensitivity|specificity|auc|roc|f1|precision|recall|n\s*=\s*\d+|p\s*<\s*0?\.\d+|\d+(?:\.\d+)?\s*%)|حساسیت|ویژگی\s*\(specificity\)|نمونه\s*\d+", re.I)
MIN_IDENT_LEN = 8


def norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).replace("‌", " ").replace("ي", "ی").replace("ك", "ک")
    return re.sub(r"[ \t]+", " ", text).lower()


def reversed_words(text: str) -> str:
    """PDFs often store RTL words in visual order; reverse Persian/Arabic words to recover them."""
    return re.sub(r"[؀-ۿ]+", lambda m: m.group(0)[::-1], text)


def doc_variants(text: str):
    base = norm(text)
    return [base, reversed_words(base)]


def context(text: str, pos: int, fragmented: bool, window: int = 150) -> str:
    """The text that can qualify a claim: its own line, or a short window when the text is one word per line (PDF)."""
    if fragmented:
        return text[max(0, pos - window): pos + window]
    start = text.rfind("\n", 0, pos) + 1
    end = text.find("\n", pos)
    return text[start: end if end != -1 else len(text)]


def is_fragmented(text: str) -> bool:
    lines = [l for l in text.splitlines() if l.strip()]
    return bool(lines) and sum(len(l) for l in lines) / len(lines) < 20


def has_qualifier(variants, positions, fragmented):
    for variant in variants:
        for pos in positions:
            chunk = context(variant, pos, fragmented)
            for q in QUALIFIERS:
                if q in chunk or q[::-1] in chunk:
                    return q
    return None


class CodeIndex:
    """Where identifiers occur in production code, and what containers/assignments say about them."""

    def __init__(self, project: Path):
        self.project = project
        self.prod_files, self.test_files = [], []
        for path in iter_project_files(project, SOURCE_EXT):
            rel = path.relative_to(project)
            if DOC_EXCLUDE_DIRS & set(rel.parts):
                continue
            (self.test_files if is_test_file(rel) else self.prod_files).append(path)
        self.texts = {p: p.read_text(encoding="utf-8", errors="ignore") for p in self.prod_files}
        self.containers = defaultdict(list)       # ident -> [(container, file, line)]
        self.assignments = defaultdict(list)      # ident -> [(is_constant, file, line, source)]
        self.all_identifiers = set()
        for path, text in self.texts.items():
            self.all_identifiers.update(IDENT.findall(text))
            if path.suffix == ".py":
                self._index_python(path, text)
            elif path.suffix in {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}:
                self._index_js(path, text)

    def rel(self, path):
        return str(path.relative_to(self.project))

    def _index_python(self, path, text):
        try:
            tree = ast.parse(text)
        except SyntaxError:
            return
        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value is not None:
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                names = [t.id if isinstance(t, ast.Name) else t.attr if isinstance(t, ast.Attribute) else "" for t in targets]
                container = next((n for n in names if n), "")
                if container and isinstance(node.value, (ast.Set, ast.List, ast.Tuple, ast.Dict, ast.Call)):
                    for sub in ast.walk(node.value):
                        if isinstance(sub, ast.Constant) and isinstance(sub.value, str) and IDENT.fullmatch(sub.value):
                            self.containers[sub.value].append((container, self.rel(path), sub.lineno))
                for t in targets:
                    if isinstance(t, ast.Subscript):
                        key = _const_str(t.slice)
                        if key:
                            self.assignments[key].append((_is_constant(node.value), self.rel(path), node.lineno, ast.get_source_segment(text, node.value) or ""))
            if isinstance(node, ast.Dict):
                for k, v in zip(node.keys, node.values):
                    key = _const_str(k) if k is not None else None
                    if key and IDENT.fullmatch(key):
                        self.assignments[key].append((_is_constant(v), self.rel(path), k.lineno, ast.get_source_segment(text, v) or ""))

    def _index_js(self, path, text):
        for m in re.finditer(r"(?:const|let|var)\s+(\w+)\s*=\s*(?:Object\.freeze\(\s*|new Set\(\s*)?([\[{][\s\S]*?[\]}])", text):
            for ident in re.findall(r"['\"]([a-z][a-z0-9]*(?:_[a-z0-9]+)+)['\"]", m.group(2)):
                self.containers[ident].append((m.group(1), self.rel(path), text.count("\n", 0, m.start()) + 1))
        for m in re.finditer(r"['\"]?([a-z][a-z0-9]*(?:_[a-z0-9]+)+)['\"]?\s*:\s*([^,\n}]+)", text):
            value = m.group(2).strip()
            constant = bool(re.fullmatch(r"(?:-?\d+(?:\.\d+)?|null|undefined|NaN|Number\.NaN|0)", value))
            self.assignments[m.group(1)].append((constant, self.rel(path), text.count("\n", 0, m.start()) + 1, value[:60]))

    def occurrences(self, ident, limit=5):
        pattern = re.compile(rf"\b{re.escape(ident)}\b")
        hits = []
        for path, text in self.texts.items():
            for m in pattern.finditer(text):
                hits.append(f"{self.rel(path)}:{text.count(chr(10), 0, m.start()) + 1}")
                if len(hits) >= limit:
                    return hits
        return hits

    def elsewhere(self, ident, exclude=()):
        pattern = re.compile(rf"\b{re.escape(ident)}\b")
        found = []
        for path in self.test_files:
            if pattern.search(path.read_text(encoding="utf-8", errors="ignore")):
                found.append(self.rel(path))
        for path in iter_project_files(self.project, {".md"}):
            if path.resolve() in exclude:
                continue
            if pattern.search(path.read_text(encoding="utf-8", errors="ignore")):
                found.append(self.rel(path))
        return found[:5]

    def status(self, ident):
        occurrences = self.occurrences(ident)
        if not occurrences:
            return "absent", {}
        for container, file, line in self.containers.get(ident, []):
            if NOT_MEASURED_NAME.search(container):
                return "not-measured", {"container": container, "at": f"{file}:{line}"}
        for container, file, line in self.containers.get(ident, []):
            if RESEARCH_NAME.search(container):
                return "research-only", {"container": container, "at": f"{file}:{line}"}
        values = self.assignments.get(ident, [])
        if values and all(constant for constant, *_ in values):
            return "never-computed", {"assignments": [f"{f}:{ln} = {src[:40]}" for _, f, ln, src in values[:4]]}
        return "active", {"at": occurrences[:3]}


def _const_str(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if hasattr(ast, "Index") and isinstance(node, getattr(ast, "Index")):  # Python 3.8
        return _const_str(node.value)
    return None


def _is_constant(node) -> bool:
    if isinstance(node, ast.Constant):
        return node.value is None or isinstance(node.value, (int, float))
    if isinstance(node, ast.UnaryOp) and isinstance(node.operand, ast.Constant):
        return True
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "float" and node.args and isinstance(node.args[0], ast.Constant):
        return True
    if isinstance(node, ast.Attribute) and node.attr in {"nan", "NaN", "inf"}:
        return True
    if isinstance(node, ast.Name) and node.id in {"NaN", "nan", "None"}:
        return True
    return False


def semantic_notes(ident, index: CodeIndex):
    notes = []
    if "force" in ident.split("_"):
        sources = " ".join(src for _, _, _, src in index.assignments.get(ident, []))
        texts = " ".join(t for t in index.texts.values() if ident in t)
        if ident.endswith("_g") or "9.80665" in texts or "9.81" in sources:
            notes.append("name says force, but the value is expressed in g (an acceleration); a force needs mass (N)")
    if "variance" in ident.split("_"):
        close = [c for c in index.all_identifiers if c == ident.replace("variance", "std")]
        if close:
            notes.append(f"code uses '{close[0]}' (standard deviation), not a variance")
    return notes


def main():
    parser = base_parser("Check a document's feature/metric claims against the production code")
    parser.add_argument("--doc", action="append", required=True, help="Document to audit (.pdf, .md, .txt, .html, .docx); repeatable")
    parser.add_argument("--ignore", default="", help="Comma-separated identifiers to ignore (e.g. examples in the text)")
    args = parser.parse_args()
    project = project_root(args.project)
    ignore = {i.strip() for i in args.ignore.split(",") if i.strip()}

    docs = []
    for d in args.doc:
        path = Path(d).expanduser()
        path = path if path.is_absolute() else project / path
        if not path.is_file():
            return emit(report(GATE, "NOT-TESTED", str(path), notes=[f"Document not found: {path}"]), args.json)
        try:
            text, method = extract_text(path)
        except Exception as exc:
            return emit(report(GATE, "ERROR", str(path), notes=[f"Could not extract text: {exc}"]), args.json)
        docs.append((path, WRAPPED.sub(r"\1\2", text), method))

    index = CodeIndex(project)
    if not index.prod_files:
        return emit(report(GATE, "NOT-TESTED", str(project), notes=["No production source files found to check claims against."]), args.json)

    findings, rows, notes = [], [], []
    for path, text, method in docs:
        variants = doc_variants(text)
        fragmented = is_fragmented(text)
        if method in {"builtin", "pypdf", "pdftotext", "docx"} and len(text.strip()) < 200:
            notes.append(f"{path.name}: only {len(text.strip())} characters extracted ({method}); the document may be scanned images.")
        idents = sorted({i for i in IDENT.findall(text) if len(i) >= MIN_IDENT_LEN and i not in ignore})
        for ident in idents:
            positions = [m.start() for m in re.finditer(re.escape(ident), variants[0])]
            status, detail = index.status(ident)
            qualifier = has_qualifier(variants, positions, fragmented)
            semantics = semantic_notes(ident, index) if status != "absent" else []
            row = {"claim": ident, "code_status": status, "doc_qualifier": qualifier or "", **{k: v for k, v in detail.items()}}
            if status == "absent":
                close = difflib.get_close_matches(ident, index.all_identifiers, n=3, cutoff=0.75)
                row["close_matches"] = close
                row["only_in"] = index.elsewhere(ident, exclude={p.resolve() for p, _, _ in docs})
                if "variance" in ident.split("_") and any("std" in c for c in close):
                    semantics.append("closest code name uses std (standard deviation), not variance")
            rows.append(dict(row, semantics=semantics))

            if status != "active" and not qualifier:
                if status == "absent":
                    hint = f" Close matches: {', '.join(row['close_matches'])}." if row["close_matches"] else ""
                    where = f" Appears only in: {', '.join(row['only_in'])}." if row["only_in"] else ""
                    findings.append(make_finding(len(findings) + 1, "claims", GATE, "claim-absent", "P1", f"{path.name}: {ident}",
                                                 {"identifier": ident, "close_matches": row["close_matches"], "only_in": row["only_in"]},
                                                 "The document presents a metric/feature that does not exist in the production code." + where,
                                                 "Remove the claim, mark it as planned/removed, or update the name if it was renamed." + hint))
                elif status in {"not-measured", "research-only"}:
                    findings.append(make_finding(len(findings) + 1, "claims", GATE, f"claim-{status}", "P1" if status == "not-measured" else "P2",
                                                 f"{path.name}: {ident}", {"identifier": ident, **detail},
                                                 f"The code marks it {status} ({detail.get('container')}), but the document presents it without that qualification.",
                                                 f"Label it in the document as '{status}' (not used for scoring/decisions), or make the code actually use it."))
                else:
                    findings.append(make_finding(len(findings) + 1, "claims", GATE, "claim-never-computed", "P1", f"{path.name}: {ident}",
                                                 {"identifier": ident, **detail},
                                                 "Every value the code assigns to this metric is a constant (0/None/NaN): it is not actually computed.",
                                                 "Read the assignments in evidence; label the metric as not computed, or implement it.", confidence="suspected"))
            for note in semantics:
                findings.append(make_finding(len(findings) + 1, "claims", GATE, "claim-name-semantics", "P2", f"{path.name}: {ident}",
                                             {"identifier": ident, "detail": note}, f"Name and implementation disagree: {note}.",
                                             "Rename the metric or describe what is really computed (quantity and unit).", confidence="suspected"))

        for ref in sorted(set(FILE_REF.findall(text))):
            if not (project / ref).exists() and not any(str(p).endswith(ref) for p in index.prod_files):
                findings.append(make_finding(len(findings) + 1, "claims", GATE, "broken-file-reference", "P2", f"{path.name}: {ref}",
                                             {"reference": ref}, "The document cites a file that does not exist in the project.", "Fix the path or remove the reference."))

        perf_hits = [c for c in PERF_CLAIMS if any(c in v or c[::-1] in v for v in variants)]
        if perf_hits and not any(PERF_EVIDENCE.search(v) for v in variants):
            findings.append(make_finding(len(findings) + 1, "claims", GATE, "unsupported-performance-claim", "P2", path.name,
                                         {"phrases": perf_hits[:8]},
                                         "The document claims reliability/accuracy but reports no validation numbers (sensitivity, specificity, sample size, error rates).",
                                         "Add the validation study (data, n, metrics) or soften the claim to what was tested.", confidence="suspected"))

    out = work_dir(project, "claims")
    (out / "claims.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    md = ["| Claim | Code status | Qualified in document | Evidence | Notes |", "|---|---|---|---|---|"]
    for r in rows:
        evidence = r.get("container") and f"{r['container']} ({r['at']})" or ", ".join(r.get("at", []) if isinstance(r.get("at"), list) else [r.get("at", "")]) or ", ".join(r.get("assignments", [])) or ", ".join(r.get("only_in", []))
        md.append(f"| `{r['claim']}` | {r['code_status']} | {r['doc_qualifier'] or '—'} | {evidence or '—'} | {'; '.join(r['semantics']) or (', '.join(r.get('close_matches', [])) and 'close: ' + ', '.join(r['close_matches'])) or ''} |")
    (out / "claims.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    counts = defaultdict(int)
    for r in rows:
        counts[r["code_status"]] += 1
    metrics = {"documents": ", ".join(f"{p.name} ({m})" for p, _, m in docs), "claims": len(rows), **{f"status:{k}": v for k, v in sorted(counts.items())},
               "table": [{"claim": r["claim"], "status": r["code_status"], "qualified": r["doc_qualifier"] or "no"} for r in rows]}
    status = "FAIL" if any(f["confidence"] == "verified" for f in findings) else "PASS"
    return emit(report(GATE, status, ", ".join(str(p) for p, _, _ in docs), findings, notes, metrics, {"claims_table": str(out / "claims.md")}), args.json)


if __name__ == "__main__":
    sys.exit(main())
