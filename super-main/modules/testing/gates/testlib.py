"""Shared detection and parsing helpers for the testing gates (stdlib only)."""

import json
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "core" / "lib"))
from gatekit import iter_project_files, is_within  # noqa: E402


SOURCE_EXT = {".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue", ".svelte", ".go", ".rb", ".java", ".kt", ".cs", ".php", ".rs"}
JS_EXT = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
TEST_FILE = re.compile(r"(^test_.*\.py$|_test\.py$|_test\.go$|\.(test|spec)\.[cm]?[jt]sx?$|Test\.java$|Tests?\.cs$|_spec\.rb$)")
DEFAULT_NPM_TEST = "no test specified"


# ------------------------------------------------------------------------------
# Project inventory
# ------------------------------------------------------------------------------

def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def package_json(project: Path) -> dict:
    return read_json(project / "package.json")


def js_deps(pkg: dict) -> Dict[str, str]:
    deps: Dict[str, str] = {}
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        deps.update(pkg.get(key) or {})
    return deps


def python_requirements(project: Path) -> str:
    text = ""
    for name in ("requirements.txt", "requirements-dev.txt", "pyproject.toml", "setup.cfg", "Pipfile", "setup.py"):
        path = project / name
        if path.is_file():
            try:
                text += path.read_text(encoding="utf-8", errors="ignore").lower() + "\n"
            except OSError:
                pass
    return text


TEST_DIRS = {"tests", "test", "__tests__", "spec", "specs", "e2e", "__mocks__"}


def is_test_file(path: Path) -> bool:
    if TEST_FILE.search(path.name):
        return True
    return bool(TEST_DIRS & set(path.parts[:-1]))


def test_files(project: Path) -> List[Path]:
    return [p for p in iter_project_files(project, SOURCE_EXT) if is_test_file(p.relative_to(project))]


def source_files(project: Path) -> List[Path]:
    return [p for p in iter_project_files(project, SOURCE_EXT) if not is_test_file(p.relative_to(project))]


VENV_PYTHONS = (".venv/bin/python", "venv/bin/python", "env/bin/python", ".venv/Scripts/python.exe", "venv/Scripts/python.exe")


def project_python(project: Path) -> str:
    """The project's own interpreter (virtualenv) when present, so its dependencies and pytest are used."""
    for rel in VENV_PYTHONS:
        candidate = project / rel
        if candidate.is_file():
            return str(candidate)
    return sys.executable


def pytest_importable(project: Optional[Path] = None) -> bool:
    python = project_python(project) if project else sys.executable
    try:
        return subprocess.run([python, "-c", "import pytest"], capture_output=True, timeout=60).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def detect_runners(project: Path) -> List[Dict[str, str]]:
    """Return candidate test runners in priority order with the command that produces parseable results."""
    runners: List[Dict[str, str]] = []
    pkg = package_json(project)
    deps = js_deps(pkg)
    test_script = (pkg.get("scripts") or {}).get("test", "")
    if pkg:
        if "vitest" in deps or "vitest" in test_script:
            runners.append({"name": "vitest", "layer": "js"})
        if "jest" in deps or re.search(r"\bjest\b", test_script):
            runners.append({"name": "jest", "layer": "js"})
        if "node --test" in test_script:
            runners.append({"name": "node-test", "layer": "js"})
        if "mocha" in deps or "mocha" in test_script:
            runners.append({"name": "mocha", "layer": "js"})
        if test_script and DEFAULT_NPM_TEST not in test_script and not any(r["layer"] == "js" for r in runners):
            runners.append({"name": "npm-test", "layer": "js"})
    pyreq = python_requirements(project)
    py_tests = any(p.suffix == ".py" for p in test_files(project))
    if "pytest" in pyreq or (project / "pytest.ini").is_file() or (project / "conftest.py").is_file():
        runners.append({"name": "pytest", "layer": "python"})
    elif py_tests:
        runners.append({"name": "pytest" if pytest_importable(project) else "unittest", "layer": "python"})
    if (project / "go.mod").is_file():
        runners.append({"name": "go", "layer": "go"})
    return runners


def e2e_runner(project: Path) -> Optional[str]:
    deps = js_deps(package_json(project))
    if "@playwright/test" in deps or any((project / n).is_file() for n in ("playwright.config.ts", "playwright.config.js")):
        return "playwright"
    if "cypress" in deps:
        return "cypress"
    return None


def detect_suites(project: Path) -> List[Dict[str, str]]:
    """Discover bounded package roots without silently dropping runner candidates."""
    manifests = {"package.json", "pyproject.toml", "requirements.txt", "pytest.ini", "setup.cfg", "go.mod"}
    roots = {project}
    for path in iter_project_files(project):
        if path.name in manifests and len(path.relative_to(project).parts) <= 5 and not path.is_symlink():
            roots.add(path.parent)
    py_roots = {root for root in roots if any((root / name).is_file() for name in manifests - {"package.json", "go.mod"})}
    suites = []
    for root in sorted(roots):
        for runner in detect_runners(root):
            layer = runner["layer"]
            # Recursive Python test discovery at a parent would duplicate a child suite.
            if layer == "python" and root not in py_roots and any(child != root and is_within(child, root) for child in py_roots):
                continue
            suites.append({**runner, "cwd": str(root.relative_to(project))})
    return suites


def runner_command(name: str, project: Path, junit: Path, json_out: Path) -> Tuple[List[str], str]:
    """Return (command, result_format). Formats: junit, jest-json, go-json, unittest-json, exit-code."""
    py = project_python(project)
    if name == "vitest":
        return ["npx", "--no-install", "vitest", "run", "--reporter=default", "--reporter=junit", f"--outputFile.junit={junit}"], "junit"
    if name == "jest":
        return ["npx", "--no-install", "jest", "--ci", "--json", f"--outputFile={json_out}"], "jest-json"
    if name == "node-test":
        return ["node", "--test", "--test-reporter=spec", "--test-reporter-destination=stdout",
                "--test-reporter=junit", f"--test-reporter-destination={junit}"], "junit"
    if name == "mocha":
        return ["npx", "--no-install", "mocha", "--reporter", "xunit", "--reporter-option", f"output={junit}"], "junit"
    if name == "npm-test":
        return ["npm", "test", "--silent"], "exit-code"
    if name == "pytest":
        return [py, "-m", "pytest", "-q", "-p", "no:cacheprovider", f"--junitxml={junit}"], "junit"
    if name == "unittest":
        return [py, str(Path(__file__).resolve().parent / "unittest_json.py"), "--out", str(json_out)], "unittest-json"
    if name == "go":
        return ["go", "test", "-json", "./..."], "go-json"
    if name == "playwright":
        return ["npx", "--no-install", "playwright", "test", "--reporter=junit"], "junit"
    raise ValueError(f"unknown runner {name}")


# ------------------------------------------------------------------------------
# Result parsers: each returns {test_id: outcome} with outcome in passed/failed/skipped
# ------------------------------------------------------------------------------

def parse_junit(path: Path) -> Dict[str, str]:
    results: Dict[str, str] = {}
    root = ET.parse(str(path)).getroot()
    if root.tag not in {"testsuite", "testsuites"}:
        raise ValueError("Expected JUnit testsuite/testsuites root")
    for case in root.iter("testcase"):
        name = case.get("name", "?")
        cls = case.get("classname") or case.get("file") or ""
        test_id = f"{cls}::{name}" if cls else name
        if test_id in results:
            raise ValueError("Duplicate JUnit test identity: " + test_id)
        if case.find("failure") is not None or case.find("error") is not None:
            outcome = "failed"
        elif case.find("skipped") is not None:
            outcome = "skipped"
        else:
            outcome = "passed"
        results[test_id] = outcome
    return results


def parse_jest_json(path: Path) -> Dict[str, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("testResults"), list):
        raise ValueError("Expected Jest testResults array")
    results: Dict[str, str] = {}
    for suite in data.get("testResults", []):
        file = suite.get("name") or suite.get("testFilePath") or ""
        for test in suite.get("assertionResults", []):
            status = test.get("status")
            outcome = {"passed": "passed", "failed": "failed"}.get(status, "skipped")
            results[f"{file}::{test.get('fullName') or test.get('title')}"] = outcome
    return results


def parse_go_json(text: str) -> Dict[str, str]:
    results: Dict[str, str] = {}
    for line in text.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("Test") and event.get("Action") in {"pass", "fail", "skip"}:
            outcome = {"pass": "passed", "fail": "failed", "skip": "skipped"}[event["Action"]]
            results[f"{event.get('Package', '')}::{event['Test']}"] = outcome
    return results


# ------------------------------------------------------------------------------
# Coverage: {relative_path: {line: hits}}
# ------------------------------------------------------------------------------

COVERAGE_CANDIDATES = [
    "coverage/lcov.info", "lcov.info", "coverage/lcov/lcov.info",
    "coverage.xml", "coverage/cobertura-coverage.xml", "coverage/coverage.xml",
    "coverage.json",
    "coverage.out", "cover.out",
]


def find_coverage_reports(project: Path) -> List[Path]:
    return [project / rel for rel in COVERAGE_CANDIDATES if (project / rel).is_file()]


def _rel(project: Path, filename: str, roots: Optional[List[str]] = None) -> str:
    path = Path(filename)
    candidates = [path] if path.is_absolute() else [project / path] + [Path(r) / path for r in (roots or [])]
    for cand in candidates:
        try:
            return str(cand.resolve().relative_to(project))
        except (ValueError, OSError):
            continue
    return str(path).lstrip("./")


def parse_lcov(path: Path, project: Path) -> Dict[str, Dict[int, int]]:
    data: Dict[str, Dict[int, int]] = {}
    current: Optional[Dict[int, int]] = None
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.startswith("SF:"):
            current = data.setdefault(_rel(project, line[3:].strip()), {})
        elif line.startswith("DA:") and current is not None:
            parts = line[3:].split(",")
            if len(parts) >= 2 and parts[0].isdigit():
                current[int(parts[0])] = max(current.get(int(parts[0]), 0), int(float(parts[1])))
        elif line == "end_of_record":
            current = None
    return data


def parse_cobertura(path: Path, project: Path) -> Dict[str, Dict[int, int]]:
    root = ET.parse(str(path)).getroot()
    roots = [s.text.strip() for s in root.iter("source") if s.text]
    data: Dict[str, Dict[int, int]] = {}
    for cls in root.iter("class"):
        rel = _rel(project, cls.get("filename", ""), roots)
        lines = data.setdefault(rel, {})
        for line in cls.iter("line"):
            number, hits = int(line.get("number", 0)), int(float(line.get("hits", 0)))
            lines[number] = max(lines.get(number, 0), hits)
    return data


def parse_coveragepy_json(path: Path, project: Path) -> Dict[str, Dict[int, int]]:
    raw = read_json(path)
    data: Dict[str, Dict[int, int]] = {}
    for filename, info in (raw.get("files") or {}).items():
        lines = {n: 1 for n in info.get("executed_lines", [])}
        lines.update({n: 0 for n in info.get("missing_lines", [])})
        data[_rel(project, filename)] = lines
    return data


def parse_go_cover(path: Path, project: Path) -> Dict[str, Dict[int, int]]:
    module = ""
    gomod = project / "go.mod"
    if gomod.is_file():
        match = re.search(r"^module\s+(\S+)", gomod.read_text(encoding="utf-8"), re.M)
        module = match.group(1) if match else ""
    data: Dict[str, Dict[int, int]] = {}
    for line in path.read_text(encoding="utf-8").splitlines()[1:]:
        match = re.match(r"(.+?):(\d+)\.\d+,(\d+)\.\d+ \d+ (\d+)$", line)
        if not match:
            continue
        name, start, end, hits = match.group(1), int(match.group(2)), int(match.group(3)), int(match.group(4))
        if module and name.startswith(module + "/"):
            name = name[len(module) + 1:]
        lines = data.setdefault(name, {})
        for n in range(start, end + 1):
            lines[n] = max(lines.get(n, 0), hits)
    return data


def load_coverage(report: Path, project: Path) -> Dict[str, Dict[int, int]]:
    name = report.name
    if name.endswith(".info"):
        return parse_lcov(report, project)
    if name.endswith(".xml"):
        return parse_cobertura(report, project)
    if name.endswith(".json"):
        return parse_coveragepy_json(report, project)
    if name.endswith(".out"):
        return parse_go_cover(report, project)
    raise ValueError(f"unsupported coverage report: {report}")


def merge_coverage(reports: List[Dict[str, Dict[int, int]]]) -> Dict[str, Dict[int, int]]:
    merged: Dict[str, Dict[int, int]] = {}
    for rep in reports:
        for file, lines in rep.items():
            target = merged.setdefault(file, {})
            for n, hits in lines.items():
                target[n] = max(target.get(n, 0), hits)
    return merged


def file_coverage(lines: Dict[int, int]) -> Optional[float]:
    return (sum(1 for h in lines.values() if h > 0) / len(lines)) if lines else None


# ------------------------------------------------------------------------------
# Git helpers
# ------------------------------------------------------------------------------

def git(project: Path, *args: str, timeout: int = 60) -> Optional[str]:
    try:
        out = subprocess.run(["git", *args], cwd=str(project), capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout if out.returncode == 0 else None


def is_git_repo(project: Path) -> bool:
    return (git(project, "rev-parse", "--is-inside-work-tree") or "").strip() == "true"


def default_base(project: Path) -> Optional[str]:
    for ref in ("origin/main", "origin/master", "main", "master"):
        if git(project, "rev-parse", "--verify", "--quiet", ref) is not None:
            merge_base = git(project, "merge-base", ref, "HEAD")
            if merge_base:
                return merge_base.strip()
    return None


HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def changed_lines(project: Path, base: str) -> Dict[str, Set[int]]:
    """Lines added or modified relative to base, including uncommitted and untracked files."""
    changed: Dict[str, Set[int]] = {}
    diff = git(project, "diff", "-U0", "--no-color", "--no-ext-diff", base) or ""
    current = None
    for line in diff.splitlines():
        if line.startswith("+++ "):
            target = line[4:].strip()
            current = None if target == "/dev/null" else target[2:] if target.startswith("b/") else target
            if current:
                changed.setdefault(current, set())
        elif current and line.startswith("@@"):
            match = HUNK.match(line)
            if match:
                start, count = int(match.group(1)), int(match.group(2) or 1)
                changed[current].update(range(start, start + count))
    for rel in (git(project, "ls-files", "--others", "--exclude-standard") or "").splitlines():
        path = project / rel
        if path.suffix in SOURCE_EXT and path.is_file():
            try:
                count = len(path.read_text(encoding="utf-8", errors="ignore").splitlines())
            except OSError:
                continue
            changed[rel] = set(range(1, count + 1))
    return {f: lines for f, lines in changed.items() if lines}


def ranges(lines: List[int]) -> str:
    """Compact '3-5, 9' style rendering of sorted line numbers."""
    out, start, prev = [], None, None
    for n in sorted(lines):
        if start is None:
            start = prev = n
        elif n == prev + 1:
            prev = n
        else:
            out.append(f"{start}-{prev}" if start != prev else str(start))
            start = prev = n
    if start is not None:
        out.append(f"{start}-{prev}" if start != prev else str(start))
    return ", ".join(out)
