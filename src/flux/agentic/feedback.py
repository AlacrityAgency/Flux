"""Automated Compiler, Linter, Typechecker & Test Feedback Loop.

Runs deterministic syntax, linter, typechecker, and targeted test checks immediately
after files are modified, producing structured failure diagnostics and self-correction
prompts so broken code is caught and healed before reaching the user.
"""
from __future__ import annotations

import ast
import json
import os
import py_compile
import shutil
import subprocess
import sys
import time
from pathlib import Path, PurePosixPath


def _run_cmd(argv: list[str], cwd: Path, timeout: int = 45) -> tuple[int, str, float]:
    started = time.monotonic()
    flags = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
    env = {**os.environ, "PYTHONUTF8": "1", "NO_COLOR": "1"}
    try:
        proc = subprocess.run(
            argv, cwd=str(cwd), env=env, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout, **flags,
        )
        out = ((proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")).strip()
        return proc.returncode, out[-5000:], round(time.monotonic() - started, 3)
    except subprocess.TimeoutExpired as exc:
        out = str(exc.stdout or "") + "\n[timeout]"
        return -1, out[-3000:], round(time.monotonic() - started, 3)
    except OSError as exc:
        return -2, str(exc), round(time.monotonic() - started, 3)


def _discover_related_tests(root: Path, changed_py: list[str]) -> list[str]:
    """Find fast unit tests corresponding to modified Python modules."""
    candidates: list[str] = []
    for rel in changed_py:
        p = PurePosixPath(rel)
        if p.name.startswith("test_") or p.name.endswith("_test.py"):
            if (root / rel).is_file():
                candidates.append(rel)
            continue
        stem = p.stem
        if stem == "__init__":
            stem = p.parent.name
        for pattern in (f"tests/test_{stem}.py", f"tests/**/test_{stem}.py", f"test_{stem}.py"):
            for match in root.glob(pattern):
                if match.is_file():
                    candidates.append(match.relative_to(root).as_posix())
    # If project has a small test suite (<= 6 files) and nothing matched by name, run it!
    if not candidates and (root / "tests").is_dir():
        all_tests = [p.relative_to(root).as_posix() for p in (root / "tests").rglob("test_*.py")]
        if 0 < len(all_tests) <= 6:
            candidates.extend(sorted(all_tests))
    return sorted(dict.fromkeys(candidates))[:8]


def _load_custom_checks(root: Path) -> list[dict]:
    cfg_path = root / ".flux" / "flux.json"
    if not cfg_path.is_file():
        return []
    try:
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
        raw = (data.get("agentic") or {}).get("checks") or []
        return [c for c in raw if isinstance(c, dict) and c.get("run")]
    except (OSError, ValueError):
        return []


class FeedbackVerifier:
    """Executes syntax, compiler, linter, typechecker, and targeted test gates."""

    def verify(self, cwd: str | Path, changed_files: list[str] | None = None, run_tests: bool = True) -> dict:
        root = Path(cwd).resolve()
        if not root.is_dir():
            return {"passed": True, "checks": [], "failed_checks": [], "error_summary": "", "repair_prompt": ""}

        files = [f.replace("\\", "/").lstrip("/") for f in (changed_files or []) if f]
        existing = [f for f in files if (root / f).is_file()]
        py_files = [f for f in existing if f.endswith(".py")]
        js_files = [f for f in existing if f.endswith((".js", ".mjs", ".cjs"))]
        ts_files = [f for f in existing if f.endswith((".ts", ".tsx"))]
        json_files = [f for f in existing if f.endswith(".json")]

        checks: list[dict] = []

        # 1. Python AST & Bytecode Compiler check
        if py_files:
            py_errors = []
            t0 = time.monotonic()
            for rel in py_files:
                fpath = root / rel
                try:
                    source = fpath.read_text(encoding="utf-8")
                    ast.parse(source, filename=rel)
                    py_compile.compile(str(fpath), doraise=True)
                except (SyntaxError, py_compile.PyCompileError, UnicodeDecodeError) as exc:
                    py_errors.append(f"{rel}: {exc}")
            checks.append({
                "stage": "python_compiler",
                "passed": len(py_errors) == 0,
                "seconds": round(time.monotonic() - t0, 3),
                "output": "\n".join(py_errors),
            })

        # 2. JSON syntax validation
        if json_files:
            j_errors = []
            t0 = time.monotonic()
            for rel in json_files:
                try:
                    json.loads((root / rel).read_text(encoding="utf-8"))
                except (ValueError, OSError) as exc:
                    j_errors.append(f"{rel}: {exc}")
            checks.append({
                "stage": "json_syntax",
                "passed": len(j_errors) == 0,
                "seconds": round(time.monotonic() - t0, 3),
                "output": "\n".join(j_errors),
            })

        # 3. JavaScript syntax check (`node --check`)
        node_bin = shutil.which("node")
        if js_files and node_bin:
            js_errors = []
            t0 = time.monotonic()
            for rel in js_files:
                code, out, _ = _run_cmd([node_bin, "--check", rel], root, timeout=15)
                if code != 0:
                    js_errors.append(f"{rel}:\n{out}")
            checks.append({
                "stage": "node_syntax",
                "passed": len(js_errors) == 0,
                "seconds": round(time.monotonic() - t0, 3),
                "output": "\n".join(js_errors),
            })

        # 4. Ruff linter (critical undefined names / syntax / broken imports: E9,F63,F7,F82)
        ruff_bin = shutil.which("ruff")
        if py_files and ruff_bin:
            code, out, secs = _run_cmd(
                [ruff_bin, "check", "--select", "E9,F63,F7,F82", "--output-format", "concise", *py_files],
                root, timeout=25,
            )
            if code >= 0:
                checks.append({"stage": "ruff_linter", "passed": code == 0, "seconds": secs, "output": out if code != 0 else ""})

        # 5. Mypy typechecker (when installed & configured or explicit type annotations broken)
        mypy_bin = shutil.which("mypy")
        has_mypy_cfg = (root / "mypy.ini").is_file() or (
            (root / "pyproject.toml").is_file() and "[tool.mypy]" in (root / "pyproject.toml").read_text(encoding="utf-8", errors="ignore")
        )
        if py_files and mypy_bin and has_mypy_cfg:
            code, out, secs = _run_cmd([mypy_bin, "--no-error-summary", *py_files], root, timeout=40)
            if code >= 0:
                checks.append({"stage": "mypy_typecheck", "passed": code == 0, "seconds": secs, "output": out if code != 0 else ""})

        # 6. TypeScript compiler (`tsc --noEmit`) & local ESLint
        if (ts_files or js_files) and (root / "tsconfig.json").is_file():
            local_tsc = root / "node_modules" / ".bin" / ("tsc.cmd" if os.name == "nt" else "tsc")
            tsc_bin = str(local_tsc) if local_tsc.is_file() else shutil.which("tsc")
            if tsc_bin and ts_files:
                code, out, secs = _run_cmd([tsc_bin, "--noEmit", "--pretty", "false"], root, timeout=45)
                if code >= 0:
                    checks.append({"stage": "tsc_typecheck", "passed": code == 0, "seconds": secs, "output": out if code != 0 else ""})
        if js_files or ts_files:
            local_eslint = root / "node_modules" / ".bin" / ("eslint.cmd" if os.name == "nt" else "eslint")
            if local_eslint.is_file():
                code, out, secs = _run_cmd([str(local_eslint), *(js_files + ts_files)], root, timeout=30)
                if code >= 0:
                    checks.append({"stage": "eslint", "passed": code == 0, "seconds": secs, "output": out if code != 0 else ""})

        # 7. Targeted pytest execution (only if syntax/compile passed)
        syntax_ok = all(c["passed"] for c in checks if c["stage"] in {"python_compiler", "json_syntax", "node_syntax"})
        if run_tests and syntax_ok and py_files:
            test_targets = _discover_related_tests(root, py_files)
            if test_targets:
                code, out, secs = _run_cmd(
                    [sys.executable, "-m", "pytest", "-q", "--tb=short", "-p", "no:cacheprovider", *test_targets],
                    root, timeout=60,
                )
                checks.append({
                    "stage": "pytest",
                    "targets": test_targets,
                    "passed": code == 0,
                    "seconds": secs,
                    "output": out if code != 0 else f"ok ({len(test_targets)} test file(s))",
                })

        # 8. Optional custom project checks in `.flux/flux.json` -> `agentic.checks`
        for custom in _load_custom_checks(root):
            flags = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
            t0 = time.monotonic()
            try:
                proc = subprocess.run(
                    custom["run"], shell=True, cwd=str(root), capture_output=True, text=True,
                    encoding="utf-8", errors="replace", timeout=int(custom.get("timeout", 60)), **flags,
                )
                code, out = proc.returncode, ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()[-4000:]
            except subprocess.TimeoutExpired:
                code, out = -1, "[timeout]"
            checks.append({
                "stage": custom.get("name") or "custom_check",
                "passed": code == 0,
                "seconds": round(time.monotonic() - t0, 3),
                "output": out if code != 0 else "",
            })

        failed = [c for c in checks if not c["passed"]]
        passed = len(failed) == 0
        summary = ""
        repair_prompt = ""
        if failed:
            parts = [f"[{c['stage']}]\n{c['output']}" for c in failed]
            summary = "\n\n".join(parts)[:4500]
            repair_prompt = (
                "AUTOMATED COMPILER / LINTER / TEST FEEDBACK LOOP:\n"
                "تغییر اخیر تو باعث خطای زیر در کامپایلر/لینتر/تست‌های پروژه شد؛ بدون حذف یا تضعیف تست‌ها علت اصلی را به صورت جراحی اصلاح کن:\n\n"
                f"{summary}\n"
            )
        return {
            "passed": passed,
            "files_checked": existing,
            "checks": checks,
            "failed_checks": [c["stage"] for c in failed],
            "error_summary": summary,
            "repair_prompt": repair_prompt,
        }

