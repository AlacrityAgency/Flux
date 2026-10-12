#!/usr/bin/env python3
"""ui-ux.a11y: axe-core WCAG 2.2 AA audit through Playwright on desktop (1280x800) and mobile (375x667).

Usage (normally through the ledger: sa.py gate ui-ux.a11y -- --url ...):
  python3 <skill>/modules/ui-ux/gates/a11y.py --project <dir> --url http://localhost:3000 [--json]
  python3 <skill>/modules/ui-ux/gates/a11y.py --project <dir> --sandbox .superagent/sandbox/demo.html [--json]

Exit codes: 0 PASS · 1 FAIL (violations, page errors, render failure) · 2 NOT-TESTED · 3 ERROR
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pwrunner import add_target_arguments, run_spec  # noqa: E402
from gatekit import emit, make_finding  # noqa: E402


GATE = "ui-ux.a11y"
SPEC = Path(__file__).resolve().parent / "playwright" / "a11y.spec.js"
SEVERITY = {"critical": "P1", "serious": "P1", "moderate": "P2", "minor": "P2"}


def collect(per_viewport):
    """Merge per-viewport axe results into one finding per rule."""
    by_rule = {}
    for viewport, data in per_viewport.items():
        for violation in data.get("violations", []):
            entry = by_rule.setdefault(violation["id"], {"violation": violation, "viewports": [], "nodes": []})
            entry["viewports"].append(viewport)
            for node in violation["nodes"]:
                if node["target"] not in {n["target"] for n in entry["nodes"]}:
                    entry["nodes"].append(node)
    findings = []
    for rule, entry in sorted(by_rule.items()):
        violation = entry["violation"]
        findings.append(make_finding(
            len(findings) + 1, "ui-ux", GATE, rule, SEVERITY.get(violation.get("impact"), "P2"),
            f"axe-core WCAG 2.2 AA scan on viewports: {', '.join(sorted(entry['viewports']))}",
            {"nodes": [n["target"] for n in entry["nodes"][:10]], "help_url": violation.get("helpUrl")},
            violation.get("help"),
            (entry["nodes"][0].get("failureSummary") or "").strip() if entry["nodes"] else "",
        ))
    return findings


def main():
    parser = add_target_arguments("WCAG 2.2 AA accessibility gate (axe-core + Playwright, desktop and mobile)")
    parser.add_argument("--visual", action="store_true", help="Also compare against visual baselines (created on first run)")
    parser.add_argument("--baseline-dir", help="Where visual baselines live (default: <out>/baselines)")
    args = parser.parse_args()

    extra_env, extra_cmd, notes = {}, [], []
    if args.visual:
        project = Path(args.project).expanduser().resolve()
        out_dir = Path(args.out).expanduser().resolve() if args.out else project / ".superagent" / "a11y"
        extra_env = {"VISUAL_BASELINE": "1",
                     "A11Y_SNAPSHOT_DIR": str(Path(args.baseline_dir).expanduser().resolve()) if args.baseline_dir else str(out_dir / "baselines")}
        extra_cmd = ["--update-snapshots=missing"]
        notes = ["Visual baselines were compared or created."]
    result = run_spec(args, GATE, SPEC, collect, extra_env, extra_cmd, notes)
    return emit(result, args.json)


if __name__ == "__main__":
    sys.exit(main())
