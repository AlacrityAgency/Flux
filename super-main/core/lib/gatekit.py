"""Shared helpers for gates: report format, findings, exit codes and command execution.

Every gate prints one JSON report (with --json) and exits with:
  0 PASS · 1 FAIL · 2 NOT-TESTED · 3 ERROR
Informational gates (inventory, risk) use PASS when they ran successfully.
"""

import argparse
import json
import os
import signal
import subprocess
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


EXIT = {"PASS": 0, "FAIL": 1, "NOT-TESTED": 2, "ERROR": 3}
SKILL_DIR = Path(__file__).resolve().parents[2]
IGNORED_DIRS = {
    ".git", ".hg", ".svn", "node_modules", ".superagent", "dist", "build", "out", ".next", ".nuxt",
    ".svelte-kit", "__pycache__", ".venv", "venv", "env", ".tox", ".mypy_cache", ".pytest_cache",
    ".ruff_cache", "coverage", "htmlcov", ".nyc_output", "test-results", "playwright-report",
    "target", ".gradle", ".idea", ".vscode", "vendor", ".cache", ".turbo", ".parcel-cache",
}


def base_parser(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--project", default=".", help="Project root to evaluate (default: current directory)")
    parser.add_argument("--json", action="store_true", help="Print the machine-readable gate report")
    return parser


def project_root(value: str) -> Path:
    return Path(value).expanduser().resolve()


def is_within(path: Path, root: Path) -> bool:
    path, root = path.resolve(), root.resolve()
    return path == root or root in path.parents


def work_dir(project: Path, *parts: str) -> Path:
    """Directory for gate artifacts inside the audited project (never inside the skill)."""
    path = project.joinpath(".superagent", *parts)
    path.mkdir(parents=True, exist_ok=True)
    return path


def make_finding(index: int, module: str, gate: str, rule: str, severity: str, condition: str,
                 evidence: Dict[str, Any], impact: str, remediation: str, confidence: str = "verified") -> Dict[str, Any]:
    return {
        "id": f"{gate.split('.')[-1]}-{index:04d}",
        "module": module,
        "rule": rule,
        "severity": severity,
        "confidence": confidence,
        "condition": condition,
        "evidence": evidence,
        "impact": impact,
        "remediation": remediation,
    }


def report(gate: str, status: str, target: Optional[str] = None, findings: Optional[List[dict]] = None,
           notes: Optional[List[str]] = None, metrics: Optional[Dict[str, Any]] = None,
           artifacts: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    if status not in EXIT:
        raise ValueError(f"unknown status {status}")
    return {
        "gate": gate,
        "status": status,
        "exit_code": EXIT[status],
        "target": target,
        "metrics": metrics or {},
        "findings": findings or [],
        "notes": notes or [],
        "artifacts": artifacts or {},
    }


def status_from_findings(findings: Iterable[dict]) -> str:
    """FAIL when at least one verified finding exists; suspected findings never fail a gate."""
    return "FAIL" if any(f.get("confidence", "verified") == "verified" for f in findings) else "PASS"


def emit(result: Dict[str, Any], as_json: bool) -> int:
    if as_json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"{result['status']}: {result['gate']}" + (f" on {result['target']}" if result.get("target") else ""))
        for key, value in result.get("metrics", {}).items():
            if not isinstance(value, (dict, list)):
                print(f"  {key}: {value}")
        for f in result["findings"]:
            suffix = "" if f.get("confidence") == "verified" else " (suspected)"
            print(f"  - [{f['severity']}] {f['rule']}{suffix}: {f['impact']} — {f['condition']}")
        for note in result["notes"]:
            print(f"  note: {note}")
    return result["exit_code"]


def run(cmd: List[str], cwd: Path, timeout: int, env: Optional[Dict[str, str]] = None) -> subprocess.CompletedProcess:
    merged = dict(os.environ)
    if env:
        merged.update(env)
    nested = os.environ.get("_SUPERAGENT_RUN_GROUP") == "1"
    merged["_SUPERAGENT_RUN_GROUP"] = "1"
    proc = subprocess.Popen(cmd, cwd=str(cwd), env=merged, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, start_new_session=(os.name == "posix" and not nested))
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
        return subprocess.CompletedProcess(cmd, proc.returncode, stdout, stderr)
    except BaseException:
        # The gate may spawn a server or another runner. Kill its group, not just the wrapper.
        if os.name == "posix":
            try:
                table = subprocess.run(["ps", "-eo", "pid=,ppid="], capture_output=True,
                                       text=True, timeout=3)
                pairs = [tuple(map(int, line.split())) for line in table.stdout.splitlines() if line.strip()]
                descendants = {proc.pid}
                while True:
                    expanded = descendants | {pid for pid, parent in pairs if parent in descendants}
                    if expanded == descendants:
                        break
                    descendants = expanded
                # Nested gates may own a separate process group; catch them while parents live.
                for pid in descendants - {proc.pid}:
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
            except (OSError, ValueError, subprocess.TimeoutExpired):
                pass
            try:
                os.killpg(os.getpgrp() if nested else proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        else:
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, timeout=10)
        try:
            proc.communicate(timeout=3)
        except subprocess.TimeoutExpired:
            # A detached process can retain the pipe even after the runner is dead.
            proc.stdout.close()
            proc.stderr.close()
            proc.wait(timeout=3)
        raise


def iter_project_files(project: Path, suffixes: Optional[Iterable[str]] = None, max_files: int = 20000):
    """Yield source files, skipping dependency, build and cache directories."""
    wanted = {s.lower() for s in suffixes} if suffixes else None
    count = 0
    for root, dirs, files in os.walk(project):
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS and not d.startswith(".") and not (Path(root) / d).is_symlink()]
        for name in files:
            path = Path(root) / name
            if path.is_symlink():
                continue
            if wanted is not None and path.suffix.lower() not in wanted:
                continue
            yield path
            count += 1
            if count >= max_files:
                return
