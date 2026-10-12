#!/usr/bin/env python3
"""testing.smells: static detection of test smells that make a suite untrustworthy.

Verified (fail the gate):   focused-test (.only / fit / fdescribe), empty-test
Suspected (reported only):  skipped-test, sleepy-test, assertion-free-test, conditional-test-logic,
                            external-network, snapshot-only
Python tests are analysed with the ast module; JS/TS tests with brace-matched blocks.
Smell names follow the test-smell literature (e.g. Empty Test, Sleepy Test, Ignored Test,
Conditional Test Logic, Mystery Guest).
"""

import ast
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import testlib  # noqa: E402
from gatekit import base_parser, emit, make_finding, project_root, report  # noqa: E402


GATE = "testing.smells"
JS_FOCUSED = re.compile(r"\b(?:(?:it|test|describe|context)\.only|fit|fdescribe)\s*\(")
JS_SKIPPED = re.compile(r"\b(?:(?:it|test|describe|context)\.(?:skip|todo)|xit|xdescribe|xtest)\s*\(")
JS_TEST_START = re.compile(r"\b(?:it|test)(?:\.(?:only|concurrent))?\s*\(\s*(['\"`])(.*?)\1\s*,\s*(?:async\s*)?(?:(?:\([^)]*\)|\w+)\s*=>|function\s*\w*\s*\([^)]*\))\s*\{")
JS_ASSERT = re.compile(r"\b(?:expect|assert|should|t\.(?:is|deepEqual|true|false|equal|throws|ok|notOk|plan)|cy\.\w+\(.*?\)\.should|toHaveScreenshot|axe)\b")
JS_SLEEP = re.compile(r"\b(?:waitForTimeout\s*\(\s*\d|setTimeout\s*\([^,]+,\s*\d{3,}|sleep\s*\(\s*\d)")
JS_CONDITIONAL = re.compile(r"^\s*(?:if\s*\(|for\s*\(|while\s*\(|switch\s*\()", re.M)
EXTERNAL_URL = re.compile(r"https?://(?!localhost|127\.0\.0\.1|0\.0\.0\.0|\[::1\]|example\.(?:com|org)|[\w.-]*\.test\b|[\w.-]*\.local\b)[\w.-]+\.[a-z]{2,}", re.I)
SNAPSHOT = re.compile(r"\.(?:toMatchSnapshot|toMatchInlineSnapshot)\s*\(")
PY_ASSERT_CALL = re.compile(r"^(?:assert\w*|fail\w*|raises|expect\w*|check\w*|verify\w*|should\w*)$")


def block_end(text: str, open_index: int) -> int:
    """Index of the brace closing the block that opens at open_index (strings and comments aware enough for tests)."""
    depth, i, quote = 0, open_index, None
    while i < len(text):
        ch = text[i]
        if quote:
            if ch == "\\":
                i += 2
                continue
            if ch == quote:
                quote = None
        elif ch in "'\"`":
            quote = ch
        elif text.startswith("//", i):
            nl = text.find("\n", i)
            i = len(text) if nl == -1 else nl
            continue
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            i = len(text) if end == -1 else end + 2
            continue
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return len(text) - 1


def line_of(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def scan_js(path: Path, rel: str, add):
    text = path.read_text(encoding="utf-8", errors="ignore")
    for m in JS_FOCUSED.finditer(text):
        add("focused-test", "P1", "verified", rel, line_of(text, m.start()), m.group(0),
            "Only the focused tests run; the rest of the suite is silently skipped.", "Remove .only / fit / fdescribe.")
    for m in JS_SKIPPED.finditer(text):
        add("skipped-test", "P3", "suspected", rel, line_of(text, m.start()), m.group(0),
            "Skipped tests give no protection and tend to rot.", "Fix and re-enable, or delete with a tracked reason.")
    for m in JS_TEST_START.finditer(text):
        start = m.end() - 1
        end = block_end(text, start)
        body = text[start + 1:end]
        name, line = m.group(2), line_of(text, m.start())
        stripped = re.sub(r"//.*|/\*[\s\S]*?\*/", "", body).strip()
        if not stripped:
            add("empty-test", "P2", "verified", rel, line, f"test '{name}' has an empty body",
                "The test always passes and checks nothing.", "Write the assertions or delete the test.")
            continue
        if not JS_ASSERT.search(body):
            add("assertion-free-test", "P2", "suspected", rel, line, f"test '{name}' has no expect/assert",
                "The test can only fail by throwing; wrong results pass.", "Assert on the observable outcome.")
        if JS_SLEEP.search(body):
            add("sleepy-test", "P2", "suspected", rel, line, f"test '{name}' waits for a fixed time",
                "Fixed waits make tests slow and flaky across machines.", "Wait for a condition (findBy*, expect.poll, waitFor) instead.")
        if JS_CONDITIONAL.search(body):
            add("conditional-test-logic", "P3", "suspected", rel, line, f"test '{name}' contains if/for/while/switch",
                "Branches inside a test hide which path was actually checked.", "Split into separate, straight-line tests (or use test.each).")
        if SNAPSHOT.search(body) and not re.search(r"\bexpect\((?!.*toMatch(?:Inline)?Snapshot)", body):
            add("snapshot-only", "P3", "suspected", rel, line, f"test '{name}' asserts only a snapshot",
                "Snapshot-only tests are often updated blindly and miss behaviour changes.", "Add explicit assertions on the behaviour that matters.")
    for m in EXTERNAL_URL.finditer(text):
        add("external-url-literal", "P3", "suspected", rel, line_of(text, m.start()), m.group(0),
            "An external URL appears in test source; no network call is established.", "Trace its use. Rejection-test input needs no network remediation.")


class PyTestVisitor(ast.NodeVisitor):
    def __init__(self, rel, add):
        self.rel, self.add = rel, add

    def visit_FunctionDef(self, node):
        self._check(node)
        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node):
        for deco in node.decorator_list:
            self._skip_decorator(deco, node)
        self.generic_visit(node)

    def _skip_decorator(self, deco, node):
        text = ast.dump(deco)
        if "skip" in text.lower() and ("unittest" in text or "pytest" in text or "'skip" in text):
            self.add("skipped-test", "P3", "suspected", self.rel, node.lineno, f"{node.name} is skipped",
                     "Skipped tests give no protection and tend to rot.", "Fix and re-enable, or delete with a tracked reason.")

    def _check(self, node):
        if not node.name.startswith("test"):
            return
        for deco in node.decorator_list:
            self._skip_decorator(deco, node)
        body = [n for n in node.body if not (isinstance(n, ast.Expr) and isinstance(getattr(n, "value", None), ast.Constant) and isinstance(n.value.value, str))]
        if not body or all(isinstance(n, ast.Pass) or (isinstance(n, ast.Expr) and isinstance(getattr(n, "value", None), ast.Constant)) for n in body):
            self.add("empty-test", "P2", "verified", self.rel, node.lineno, f"{node.name} has an empty body",
                     "The test always passes and checks nothing.", "Write the assertions or delete the test.")
            return
        has_assert, sleeps, branches = False, [], []
        for sub in ast.walk(node):
            if isinstance(sub, ast.Assert):
                has_assert = True
            elif isinstance(sub, ast.Call):
                fn = sub.func
                name = fn.attr if isinstance(fn, ast.Attribute) else fn.id if isinstance(fn, ast.Name) else ""
                if PY_ASSERT_CALL.match(name or ""):
                    has_assert = True
                if name == "sleep":
                    sleeps.append(sub.lineno)
            elif isinstance(sub, (ast.With, ast.AsyncWith)):
                for item in sub.items:
                    call = item.context_expr
                    fn = getattr(call, "func", None)
                    name = getattr(fn, "attr", None) or getattr(fn, "id", None)
                    if name and PY_ASSERT_CALL.match(name):
                        has_assert = True
            elif isinstance(sub, (ast.If, ast.For, ast.While)) and sub is not node:
                branches.append(sub.lineno)
        if not has_assert:
            self.add("assertion-free-test", "P2", "suspected", self.rel, node.lineno, f"{node.name} has no assert",
                     "The test can only fail by raising; wrong results pass.", "Assert on the observable outcome.")
        if sleeps:
            self.add("sleepy-test", "P2", "suspected", self.rel, sleeps[0], f"{node.name} calls sleep()",
                     "Fixed waits make tests slow and flaky.", "Wait for a condition or inject a fake clock.")
        if branches:
            self.add("conditional-test-logic", "P3", "suspected", self.rel, branches[0], f"{node.name} contains if/for/while",
                     "Branches inside a test hide which path was checked.", "Use pytest.mark.parametrize / subTest with straight-line bodies.")


def scan_py(path: Path, rel: str, add):
    text = path.read_text(encoding="utf-8", errors="ignore")
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        add("unparseable-test-file", "P2", "verified", rel, exc.lineno or 1, str(exc), "The test file cannot be parsed, so it cannot run.", "Fix the syntax error.")
        return
    PyTestVisitor(rel, add).visit(tree)
    for m in EXTERNAL_URL.finditer(text):
        add("external-url-literal", "P3", "suspected", rel, line_of(text, m.start()), m.group(0),
            "An external URL appears in test source; no network call is established.", "Trace its use. Rejection-test input needs no network remediation.")


def main():
    parser = base_parser("Detect test smells in the project's test files")
    parser.add_argument("--max-findings", type=int, default=200)
    args = parser.parse_args()
    project = project_root(args.project)
    files = testlib.test_files(project)
    if not files:
        return emit(report(GATE, "NOT-TESTED", str(project), notes=["No test files found."]), args.json)

    findings = []

    def add(rule, severity, confidence, rel, line, evidence, impact, remediation):
        if len(findings) < args.max_findings:
            findings.append(make_finding(len(findings) + 1, "testing", GATE, rule, severity, f"{rel}:{line}",
                                         {"file": rel, "line": line, "match": evidence[:200]}, impact, remediation, confidence))

    for path in files:
        rel = str(path.relative_to(project))
        if path.suffix == ".py":
            scan_py(path, rel, add)
        elif path.suffix in testlib.JS_EXT:
            scan_js(path, rel, add)
        elif path.suffix == ".go":
            text = path.read_text(encoding="utf-8", errors="ignore")
            for m in re.finditer(r"\bt\.Skip(?:Now|f)?\(", text):
                add("skipped-test", "P3", "suspected", rel, line_of(text, m.start()), m.group(0), "Skipped tests give no protection.", "Re-enable or delete.")
            for m in re.finditer(r"\btime\.Sleep\(", text):
                add("sleepy-test", "P2", "suspected", rel, line_of(text, m.start()), m.group(0), "Fixed waits make tests flaky.", "Synchronise on a condition or channel.")

    counts = {}
    for f in findings:
        counts[f["rule"]] = counts.get(f["rule"], 0) + 1
    metrics = {"test_files": len(files), **{f"smell:{k}": v for k, v in sorted(counts.items())}}
    status = "FAIL" if any(f["confidence"] == "verified" for f in findings) else "PASS"
    return emit(report(GATE, status, str(project), findings, [], metrics), args.json)


if __name__ == "__main__":
    sys.exit(main())
