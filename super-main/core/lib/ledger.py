"""Evidence ledger: every gate run is recorded with a fingerprint of the project files.

The verdict is computed from the ledger, never from what the agent writes about itself:
  - a record whose fingerprint differs from the current project state is STALE;
  - repeated failures of the same rule consume the attempt budget (2, then REJECTED).
"""

import hashlib
import json
import os
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from gatekit import IGNORED_DIRS


ATTEMPT_BUDGET = 2
LEDGER_NAME = "ledger.jsonl"
# Files that test and coverage tools generate. They are outputs, not code: changing them must not
# make earlier evidence stale (e.g. a coverage run writing lcov.info after the test gates ran).
GENERATED_FILES = {"lcov.info", "coverage.xml", "coverage.json", "coverage.out", "cover.out", ".coverage",
                   "junit.xml", "test-results.xml", "mutation.json", ".flaky_state"}
# Only matched at the project root, so source folders with the same name (src/reports/) still count.
GENERATED_DIRS = {"coverage", "htmlcov", "test-results", "playwright-report", ".nyc_output", ".stryker-tmp", "mutants"}
GENERATED_PREFIXES = ("reports/mutation/",)
RANK = {"REJECTED": 6, "FAILED": 5, "STALE": 4, "NO-EVIDENCE": 3, "PASSED-WITH-GAPS": 2, "PASSED": 1}


def _listed_files(project: Path) -> List[str]:
    """Tracked and untracked-but-not-ignored files (git), or a filtered walk."""
    try:
        out = subprocess.run(
            ["git", "ls-files", "-co", "--exclude-standard", "-z"], cwd=str(project),
            capture_output=True, text=True, timeout=30,
        )
        if out.returncode == 0:
            return sorted(p for p in out.stdout.split("\0") if p and not _generated(p))
    except (OSError, subprocess.TimeoutExpired):
        pass
    files = []
    for root, dirs, names in os.walk(project):
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
        for name in names:
            rel = str((Path(root) / name).relative_to(project))
            if not _generated(rel):
                files.append(rel)
    return sorted(files)


def _generated(rel: str) -> bool:
    parts = Path(rel).parts
    if not parts or parts[0] == ".superagent" or "__pycache__" in parts:
        return True
    name = parts[-1]
    if len(parts) > 1 and parts[0] in GENERATED_DIRS:
        return True
    return name in GENERATED_FILES or name.startswith(".coverage.") or rel.startswith(GENERATED_PREFIXES)


def fingerprint(project: Path) -> str:
    """Content fingerprint, including project-owned verification configuration."""
    digest = hashlib.sha256()
    for rel in _listed_files(project):
        try:
            content = (project / rel).read_bytes()
        except OSError:
            continue
        digest.update(rel.encode() + b"\0" + hashlib.sha256(content).digest())
    return digest.hexdigest()[:16]


def ledger_path(project: Path) -> Path:
    return project / ".superagent" / LEDGER_NAME


def evidence_key(gate_id: str, scope: Optional[str] = None) -> str:
    """Ledger key: the gate id, or gate@scope when one gate is run on several targets (e.g. pages)."""
    return f"{gate_id}@{scope}" if scope else gate_id


def base_gate(key: str) -> str:
    return key.split("@", 1)[0]


def artifact_digest(path: Path) -> str:
    """Hash a file or directory without accepting links to mutable external evidence."""
    if path.is_symlink() or not path.exists():
        raise ValueError("Missing or symlinked artifact")
    digest = hashlib.sha256()
    files = [path] if path.is_file() else sorted(path.rglob("*"))
    for item in files:
        if item.is_symlink():
            raise ValueError("Symlinked artifact")
        digest.update(str(item.relative_to(path) if path.is_dir() else item.name).encode() + b"\0")
        if item.is_file():
            content = hashlib.sha256()
            with item.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    content.update(chunk)
            digest.update(b"F" + content.digest())
        elif item.is_dir():
            digest.update(b"D")
        else:
            raise ValueError("Unsupported artifact type")
    return digest.hexdigest()


def intact(project: Path, record: Dict[str, Any]) -> bool:
    try:
        paths = record.get("digests", {})
        if record.get("report") not in paths or record.get("artifact_error"):
            return False
        return all(artifact_digest(project / path) == digest for path, digest in paths.items())
    except (OSError, ValueError):
        return False


def append(project: Path, gate_id: str, args: List[str], result: Dict[str, Any], duration_s: float,
           fp: Optional[str] = None, scope: Optional[str] = None,
           review_id: Optional[str] = None) -> Dict[str, Any]:
    run_id = f"r-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    runs_dir = project / ".superagent" / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    artifacts, digests, artifact_error = {}, {}, False
    for index, (name, value) in enumerate(result.get("artifacts", {}).items()):
        source = Path(value)
        if not source.is_absolute():
            source = project / source
        destination = runs_dir / run_id / str(index) / source.name
        try:
            artifact_digest(source)
            # Never copy the ledger's own run tree recursively.
            if source.resolve() == runs_dir.resolve() or source.resolve() in runs_dir.resolve().parents:
                raise ValueError("Artifact contains evidence output directory")
            destination.parent.mkdir(parents=True, exist_ok=True)
            if source.is_dir():
                shutil.copytree(source, destination)
            else:
                shutil.copy2(source, destination)
            rel = str(destination.relative_to(project))
            artifacts[name] = str(destination)
            digests[rel] = artifact_digest(destination)
        except (OSError, ValueError):
            artifact_error = True
    result["artifacts"] = artifacts
    report_path = runs_dir / f"{run_id}.json"
    report_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    digests[str(report_path.relative_to(project))] = artifact_digest(report_path)
    record = {
        "run": run_id,
        "gate": gate_id,
        "scope": scope,
        "review_id": review_id,
        "digests": digests,
        "artifact_error": artifact_error,
        "status": result.get("status"),
        "exit_code": result.get("exit_code"),
        "fingerprint": fp or fingerprint(project),
        "time": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "duration_s": round(duration_s, 2),
        "args": args,
        "rules": sorted({f.get("rule") for f in result.get("findings", []) if f.get("confidence", "verified") == "verified"}),
        "finding_count": len(result.get("findings", [])),
        "report": f".superagent/runs/{run_id}.json",
    }
    with ledger_path(project).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def load(project: Path) -> List[Dict[str, Any]]:
    path = ledger_path(project)
    if not path.is_file():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def _attempts(history: List[Dict[str, Any]]) -> int:
    """Consecutive failing runs (most recent first) that share at least one rule with the latest failure."""
    latest = history[-1]
    target = set(latest.get("rules") or ["<unnamed>"])
    count = 0
    for record in reversed(history):
        if record["status"] != "FAIL":
            break
        if target & set(record.get("rules") or ["<unnamed>"]):
            count += 1
    return count


def verdict(project: Path, gates_meta: Dict[str, Dict[str, Any]], require: Optional[List[str]] = None,
            review_id: Optional[str] = None) -> Dict[str, Any]:
    """Compute per-gate, per-module and overall verdicts from the ledger."""
    records = load(project)
    current = fingerprint(project)
    by_gate: Dict[str, List[Dict[str, Any]]] = {}
    for record in records:
        key = evidence_key(record["gate"], record.get("scope"))
        if review_id is not None and record.get("review_id") != review_id:
            continue
        if require is not None and key not in require and base_gate(key) not in require:
            continue
        by_gate.setdefault(key, []).append(record)

    gates: Dict[str, Dict[str, Any]] = {}
    for gate_id, history in by_gate.items():
        meta = gates_meta.get(base_gate(gate_id), {})
        latest = history[-1]
        fresh = latest.get("fingerprint") == current and intact(project, latest)
        state = latest["status"] if fresh else "STALE"
        entry = {
            "status": state,
            "last_status": latest["status"],
            "run": latest["run"],
            "fresh": fresh,
            "kind": meta.get("kind", "verdict"),
            "rules": latest.get("rules", []),
            "report": latest.get("report"),
        }
        if latest["status"] == "FAIL":
            full_history = [r for r in records if evidence_key(r["gate"], r.get("scope")) == gate_id]
            latest_index = next(i for i, r in enumerate(full_history) if r["run"] == latest["run"])
            attempts = _attempts(full_history[:latest_index + 1])
            entry["attempts"] = attempts
            entry["budget"] = "exhausted" if attempts > ATTEMPT_BUDGET else ("pivot-required" if attempts == ATTEMPT_BUDGET else "ok")
        gates[gate_id] = entry

    for gate_id in require or []:
        # A requirement on a gate id is met by an unscoped run or by any scoped run of that gate.
        if gate_id not in gates and not any(base_gate(k) == gate_id for k in gates):
            gates[gate_id] = {"status": "NO-EVIDENCE", "kind": gates_meta.get(base_gate(gate_id), {}).get("kind", "verdict"), "fresh": False}

    modules: Dict[str, Dict[str, Any]] = {}
    for gate_id, entry in gates.items():
        if entry["kind"] == "informational":
            continue
        module = gate_id.split(".")[0]
        bucket = modules.setdefault(module, {"gates": [], "status": "PASSED"})
        bucket["gates"].append(gate_id)
        state = _gate_state(entry)
        if RANK[state] > RANK[bucket["status"]]:
            bucket["status"] = state

    overall = "NO-EVIDENCE"
    if modules:
        overall = max((m["status"] for m in modules.values()), key=lambda s: RANK[s])
    return {
        "overall": overall,
        "label": _label(overall, gates),
        "exit_code": 0 if overall == "PASSED" else (1 if overall in {"FAILED", "REJECTED"} else 2),
        "fingerprint": current,
        "review_id": review_id,
        "modules": modules,
        "gates": gates,
        "iso25010": _iso_scorecard(gates, gates_meta),
    }


def _gate_state(entry: Dict[str, Any]) -> str:
    status = entry["status"]
    if status == "PASS":
        return "PASSED"
    if status == "FAIL":
        return "REJECTED" if entry.get("budget") == "exhausted" else "FAILED"
    if status in {"NOT-TESTED", "ERROR"}:
        return "PASSED-WITH-GAPS"
    if status == "STALE":
        return "STALE"
    return "NO-EVIDENCE"


def _label(overall: str, gates: Dict[str, Dict[str, Any]]) -> str:
    def names(*states):
        return ", ".join(sorted(g for g, e in gates.items() if e["kind"] != "informational" and e["status"] in states))

    if overall == "PASSED":
        return "[QA-PASSED]"
    if overall == "PASSED-WITH-GAPS":
        return f"[QA-PASSED-WITH-GAPS: not tested -> {names('NOT-TESTED', 'ERROR')}]"
    if overall == "STALE":
        return f"[QA-STALE: re-run after code changes -> {names('STALE')}]"
    if overall == "NO-EVIDENCE":
        return f"[QA-NO-EVIDENCE: run -> {names('NO-EVIDENCE') or 'the required gates'}]"
    if overall == "REJECTED":
        return f"[QA-REJECTED: attempt budget exhausted -> {names('FAIL')}]"
    return f"[QA-FAILED: fix and re-run -> {names('FAIL')}]"


def _iso_scorecard(gates: Dict[str, Dict[str, Any]], gates_meta: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, str]]:
    """Map gate results onto ISO/IEC 25010:2023 product quality characteristics."""
    card: Dict[str, Dict[str, str]] = {}
    for gate_id, entry in gates.items():
        for characteristic in gates_meta.get(base_gate(gate_id), {}).get("iso25010", []):
            card.setdefault(characteristic, {})[gate_id] = entry["status"]
    return card
