#!/usr/bin/env python3
"""testing.coverage: diff coverage of changed lines (primary) and total line coverage (secondary).

Reads lcov, Cobertura XML (coverage.py / pytest-cov / many JS tools), coverage.py JSON or Go
cover profiles that the project's test run produced. Coverage of *changed* lines is the gate,
following the practice of applying coverage at changeset level rather than chasing a global number.
A report older than the newest source file is rejected as stale (NOT-TESTED).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import testlib  # noqa: E402
from gatekit import base_parser, emit, make_finding, project_root, report  # noqa: E402


GATE = "testing.coverage"
HOW_TO = (
    "Produce a report first, e.g. pytest --cov --cov-report=xml · vitest run --coverage --coverage.reporter=lcov · "
    "jest --coverage --coverageReporters=lcov · c8 --reporter=lcov node --test · go test -coverprofile=coverage.out ./..."
)


def main():
    parser = base_parser("Check diff coverage of changed lines and total coverage")
    parser.add_argument("--report", action="append", help="Coverage report path (repeatable); auto-detected otherwise")
    parser.add_argument("--base", help="Git base for the diff (default: merge-base with main/master)")
    parser.add_argument("--min-diff", type=float, default=80.0, help="Minimum %% of changed executable lines covered")
    parser.add_argument("--min-total", type=float, default=None, help="Optional minimum %% total line coverage")
    parser.add_argument("--allow-stale", action="store_true", help="Accept reports older than the source code")
    args = parser.parse_args()
    project = project_root(args.project)

    reports = [Path(r) if Path(r).is_absolute() else project / r for r in (args.report or [])] or testlib.find_coverage_reports(project)
    reports = [r for r in reports if r.is_file()]
    if not reports:
        return emit(report(GATE, "NOT-TESTED", str(project), notes=["No coverage report found. " + HOW_TO]), args.json)

    sources = testlib.source_files(project)
    newest_source = max((p.stat().st_mtime for p in sources), default=0)
    oldest_report = min(r.stat().st_mtime for r in reports)
    if oldest_report < newest_source and not args.allow_stale:
        return emit(report(GATE, "NOT-TESTED", str(project), notes=[
            "Coverage report is older than the latest source change; re-run tests with coverage. " + HOW_TO]), args.json)

    try:
        coverage = testlib.merge_coverage([testlib.load_coverage(r, project) for r in reports])
    except Exception as exc:
        return emit(report(GATE, "ERROR", str(project), notes=[f"Could not parse coverage report: {exc}"]), args.json)

    total_lines = sum(len(lines) for lines in coverage.values())
    covered_lines = sum(1 for lines in coverage.values() for h in lines.values() if h > 0)
    total_pct = round(100 * covered_lines / total_lines, 1) if total_lines else 0.0
    metrics = {"reports": ", ".join(str(r.relative_to(project)) for r in reports), "total_line_coverage": total_pct, "files_in_report": len(coverage)}
    findings, notes = [], []

    if args.min_total is not None and total_pct < args.min_total:
        findings.append(make_finding(len(findings) + 1, "testing", GATE, "total-coverage-below-threshold", "P2",
                                     f"total line coverage {total_pct}% < {args.min_total}%", {"reports": metrics["reports"]},
                                     "Large parts of the code are not exercised by any test.", "Add tests for the highest-risk uncovered files (testing.risk)."))

    if not testlib.is_git_repo(project):
        notes.append("Not a git repository: diff coverage unavailable; only total coverage was evaluated.")
    else:
        base = args.base or testlib.default_base(project)
        if not base:
            notes.append("No base branch (main/master) found; pass --base <ref> for diff coverage.")
        else:
            changed = testlib.changed_lines(project, base)
            executable, covered, uncovered_by_file, missing_files = 0, 0, {}, []
            for rel, lines in sorted(changed.items()):
                path = project / rel
                if path.suffix not in testlib.SOURCE_EXT or testlib.is_test_file(Path(rel)):
                    continue
                file_cov = coverage.get(rel)
                if file_cov is None:
                    missing_files.append(rel)
                    continue
                relevant = [n for n in lines if n in file_cov]
                executable += len(relevant)
                hit = [n for n in relevant if file_cov[n] > 0]
                covered += len(hit)
                miss = sorted(set(relevant) - set(hit))
                if miss:
                    uncovered_by_file[rel] = miss
            diff_pct = round(100 * covered / executable, 1) if executable else None
            metrics.update({"base": base[:12], "changed_executable_lines": executable, "diff_coverage": diff_pct})
            if diff_pct is not None and diff_pct < args.min_diff:
                findings.append(make_finding(len(findings) + 1, "testing", GATE, "diff-coverage-below-threshold", "P1",
                                             f"{diff_pct}% of {executable} changed executable lines covered (< {args.min_diff}%)",
                                             {"uncovered": {f: testlib.ranges(l) for f, l in uncovered_by_file.items()}},
                                             "New or changed code ships without tests exercising it.",
                                             "Write tests that execute the uncovered changed lines listed in evidence."))
            for rel in missing_files:
                findings.append(make_finding(len(findings) + 1, "testing", GATE, "changed-file-not-in-coverage", "P2",
                                             f"{rel} changed but is absent from the coverage report",
                                             {"file": rel, "changed_lines": testlib.ranges(sorted(changed[rel]))},
                                             "No test imports or executes this changed file (or it is excluded from coverage).",
                                             "Add tests that exercise it, or confirm it is intentionally excluded.", confidence="suspected"))
            if executable == 0 and not missing_files:
                notes.append("No changed executable lines relative to the base.")

    status = "FAIL" if any(f["confidence"] == "verified" for f in findings) else "PASS"
    return emit(report(GATE, status, str(project), findings, notes, metrics), args.json)


if __name__ == "__main__":
    sys.exit(main())
