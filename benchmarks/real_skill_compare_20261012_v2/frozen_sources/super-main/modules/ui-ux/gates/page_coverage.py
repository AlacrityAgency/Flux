#!/usr/bin/env python3
"""Observe bounded document and nested scroll coverage; never claim interaction coverage."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pwrunner import add_target_arguments, run_spec
from gatekit import emit, make_finding

GATE = "ui-ux.page-coverage"


def collect(results):
    findings = []
    for viewport, data in results.items():
        if data.get("horizontalOverflow"):
            findings.append(make_finding(len(findings) + 1, "ui-ux", GATE, "horizontal-overflow", "P2", viewport,
                                         {"measurements": data["horizontalOverflow"]},
                                         "Rendered content exceeds the viewport horizontally.",
                                         "Inspect the recorded screenshots and fix the offending layout or document intentional scrolling."))
    return findings


def main():
    parser = add_target_arguments("Scroll the whole page and visible internal regions, with bounded screenshot coverage")
    parser.add_argument("--max-steps", type=int, default=30)
    parser.add_argument("--max-regions", type=int, default=12)
    parser.add_argument("--settle-ms", type=int, default=300)
    args = parser.parse_args()
    if not 2 <= args.max_steps <= 100 or not 1 <= args.max_regions <= 30 or not 100 <= args.settle_ms <= 2000:
        parser.error("max-steps: 2..100, max-regions: 1..30, settle-ms: 100..2000")
    result = run_spec(args, GATE, Path(__file__).parent / "playwright/page_coverage.spec.js", collect,
                      extra_env={"COVERAGE_MAX_STEPS": str(args.max_steps), "COVERAGE_MAX_REGIONS": str(args.max_regions),
                                 "COVERAGE_SETTLE_MS": str(args.settle_ms)},
                      pass_notes=["PASS covers observed scrolling and overflow checks only. Inspect segment screenshots; hidden/modal/form states need named journeys. Late content beyond the configured settle budget is not guaranteed."])
    if result.get("artifacts", {}).get("results"):
        import json
        rows = {p.stem: json.loads(p.read_text()) for p in (Path(result["artifacts"]["results"]) / "viewports").glob("*.json")}
        complete = set(rows) == {"desktop", "mobile"} and all(r.get("complete") is True for r in rows.values())
        result["metrics"]["scroll_coverage"] = {name: {"complete": r.get("complete"), "regions": len(r.get("regions", [])),
                                                       "screenshots": len(r.get("screenshots", [])), "gaps": r.get("gaps", [])}
                                                for name, r in rows.items()}
        if not complete and result["status"] == "PASS":
            result.update(status="NOT-TESTED", exit_code=2)
            result["notes"].append("Scroll coverage is incomplete: budget reached, content kept growing, or viewport evidence is missing.")
    return emit(result, args.json)


if __name__ == "__main__":
    sys.exit(main())
