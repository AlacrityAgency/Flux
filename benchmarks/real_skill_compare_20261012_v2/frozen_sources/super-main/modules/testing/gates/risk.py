#!/usr/bin/env python3
"""testing.risk (informational): rank source files by risk = likelihood x impact (ISTQB risk level).

Likelihood signals (each normalised to 0..1):
  churn       commits touching the file in recent history            weight 0.30
  fixes       commits with fix/bug/regression wording touching it     weight 0.25
  complexity  decision points (if/for/while/case/catch/&&/||/?:)     weight 0.20
  coverage    1 - line coverage (0.5 when no report)                 weight 0.25
  +0.15 when no test file appears to target the file
Impact (1..3):
  1 base · +1 critical domain (auth, payment, permissions, data deletion, migrations, uploads...)
  · +1 entry point (routes, controllers, API handlers, pages)
Writes <project>/.superagent/testing/risk.json; the top entries are the targets for step T3.
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import testlib  # noqa: E402
from gatekit import base_parser, emit, project_root, report, work_dir  # noqa: E402


GATE = "testing.risk"
CRITICAL = re.compile(r"auth|login|logout|password|passwd|token|session|oauth|jwt|permission|role|acl|admin|payment|billing|invoice|checkout|order|refund|wallet|transfer|price|tax|migrat|delete|destroy|purge|upload|webhook|crypto|encrypt|secret|account|signup|register", re.I)
ENTRY = re.compile(r"(^|/)(routes?|controllers?|handlers?|api|endpoints?|views|pages|app/.*page\.|resolvers?|server)(/|\.|$)", re.I)
DECISIONS = re.compile(r"\b(if|elif|else if|for|while|case|catch|except)\b|&&|\|\||\?\s*[^:\s]")
FIX_WORDS = re.compile(r"\b(fix|fixes|fixed|bug|hotfix|regression|crash|broken|error|patch)\b", re.I)


def git_history(project: Path, limit: int):
    churn, fixes = Counter(), Counter()
    log = testlib.git(project, "log", f"-n{limit}", "--no-merges", "--name-only", "--format=@@%s", timeout=120)
    if not log:
        return churn, fixes, False
    subject_is_fix = False
    for line in log.splitlines():
        if line.startswith("@@"):
            subject_is_fix = bool(FIX_WORDS.search(line))
        elif line.strip():
            churn[line.strip()] += 1
            if subject_is_fix:
                fixes[line.strip()] += 1
    return churn, fixes, True


def norm(value, maximum):
    return min(1.0, value / maximum) if maximum else 0.0


def main():
    parser = base_parser("Rank source files by testing risk (likelihood x impact)")
    parser.add_argument("--top", type=int, default=15)
    parser.add_argument("--history", type=int, default=300, help="Number of recent commits to analyse")
    args = parser.parse_args()
    project = project_root(args.project)

    sources = testlib.source_files(project)
    if not sources:
        return emit(report(GATE, "NOT-TESTED", str(project), notes=["No source files found."]), args.json)

    churn, fixes, has_git = git_history(project, args.history)
    coverage = {}
    for rep in testlib.find_coverage_reports(project):
        try:
            coverage = testlib.merge_coverage([coverage, testlib.load_coverage(rep, project)])
        except Exception:
            continue
    test_tokens = set()
    for test in testlib.test_files(project):
        test_tokens.update(t for t in re.split(r"[^a-z0-9]+", test.name.lower()) if t)

    rows = []
    for path in sources:
        rel = str(path.relative_to(project))
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        rows.append({
            "file": rel,
            "loc": text.count("\n") + 1,
            "decisions": len(DECISIONS.findall(text)),
            "churn": churn.get(rel, 0),
            "fixes": fixes.get(rel, 0),
            "coverage": testlib.file_coverage(coverage.get(rel, {})),
            "has_test": path.stem.lower().split(".")[0] in test_tokens,
            "critical": bool(CRITICAL.search(rel) or CRITICAL.search(text[:4000])),
            "entry_point": bool(ENTRY.search(rel)),
        })

    max_churn = max((r["churn"] for r in rows), default=0)
    max_fix = max((r["fixes"] for r in rows), default=0)
    max_dec = max((r["decisions"] for r in rows), default=0)
    for r in rows:
        cov_gap = 0.5 if r["coverage"] is None else 1 - r["coverage"]
        likelihood = 0.30 * norm(r["churn"], max_churn) + 0.25 * norm(r["fixes"], max_fix) + 0.20 * norm(r["decisions"], max_dec) + 0.25 * cov_gap
        if not r["has_test"]:
            likelihood += 0.15
        impact = 1 + int(r["critical"]) + int(r["entry_point"])
        r["likelihood"] = round(min(likelihood, 1.0), 3)
        r["impact"] = impact
        r["risk"] = round(r["likelihood"] * impact, 3)
        reasons = []
        if r["critical"]:
            reasons.append("critical domain")
        if r["entry_point"]:
            reasons.append("entry point")
        if r["churn"]:
            reasons.append(f"{r['churn']} commits")
        if r["fixes"]:
            reasons.append(f"{r['fixes']} fix commits")
        if r["coverage"] is not None:
            reasons.append(f"coverage {round(100 * r['coverage'])}%")
        if not r["has_test"]:
            reasons.append("no matching test file")
        reasons.append(f"{r['decisions']} decision points")
        r["reasons"] = reasons
    rows.sort(key=lambda r: (-r["risk"], -r["decisions"], r["file"]))

    out = work_dir(project, "testing") / "risk.json"
    out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    notes = [] if has_git else ["No git history: churn and fix signals are zero; ranking uses complexity, coverage and impact only."]
    if not coverage:
        notes.append("No coverage report: coverage gap assumed 0.5 for every file.")
    top = [{"file": r["file"], "risk": r["risk"], "likelihood": r["likelihood"], "impact": r["impact"], "why": ", ".join(r["reasons"])} for r in rows[: args.top]]
    metrics = {"files_ranked": len(rows), "top": top}
    result = report(GATE, "PASS", str(project), [], notes, metrics, {"risk": str(out)})
    if not args.json:
        print(f"PASS: {GATE} — top {len(top)} of {len(rows)} files")
        for i, t in enumerate(top, 1):
            print(f"  {i:2}. {t['risk']:.2f}  {t['file']}  ({t['why']})")
        for n in notes:
            print(f"  note: {n}")
        return 0
    return emit(result, True)


if __name__ == "__main__":
    sys.exit(main())
