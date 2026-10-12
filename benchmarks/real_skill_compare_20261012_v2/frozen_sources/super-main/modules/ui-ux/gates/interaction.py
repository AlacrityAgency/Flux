#!/usr/bin/env python3
"""ui-ux.interaction: keyboard walk and measured target sizes in a real browser.

Keyboard (desktop viewport): every tabbable control is reached, focus is visible (SC 2.4.7),
focus is not hidden behind sticky UI (SC 2.4.11), no keyboard trap (SC 2.1.2), no positive
tabindex, and ARIA widgets (role=button etc.) are focusable.
Target size (both viewports): SC 2.5.8 24x24 px or spacing exception; with --level AAA, mobile
targets under 44x44 px (SC 2.5.5) are violations, otherwise they are advisory.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pwrunner import add_target_arguments, run_spec  # noqa: E402
from gatekit import emit, make_finding  # noqa: E402


GATE = "ui-ux.interaction"
SPEC = Path(__file__).resolve().parent / "playwright" / "interaction.spec.js"


def collect_for(level):
    def collect(per_viewport):
        findings = []

        def add(rule, severity, condition, items, impact, remediation, confidence="verified"):
            findings.append(make_finding(len(findings) + 1, "ui-ux", GATE, rule, severity, condition,
                                         {"elements": items[:15], "count": len(items)}, impact, remediation, confidence))

        for viewport, data in sorted(per_viewport.items()):
            targets = data.get("targets", {})
            if targets.get("minimum"):
                add("target-size-minimum", "P1", f"{viewport} viewport (WCAG 2.2 SC 2.5.8)",
                    [f"{t['target']} {t['width']}x{t['height']}px" for t in targets["minimum"]],
                    "Targets smaller than 24x24 px sit too close to other targets and are easy to miss.",
                    "Make the control at least 24x24 px (padding or min-height/min-width) or add spacing.")
            if targets.get("touch"):
                aaa = level == "AAA"
                add("touch-target-below-44", "P1" if aaa else "P2", f"{viewport} viewport (WCAG 2.2 SC 2.5.5, 44x44 px)",
                    [f"{t['target']} {t['width']}x{t['height']}px" for t in targets["touch"]],
                    "Touch targets under 44x44 px are hard to hit on phones.",
                    "Use 44 px (h-11 / min-h-[44px]) for primary touch actions.",
                    confidence="verified" if aaa else "suspected")
            kb = data.get("keyboard", {})
            if kb.get("trap"):
                add("keyboard-trap", "P1", f"{viewport} viewport (SC 2.1.2)", [kb["trap"]],
                    "Keyboard users cannot move focus away from this element.", "Let Tab and Shift+Tab leave the component; trap focus only inside open modals with an Escape exit.")
            if kb.get("unreachable"):
                add("keyboard-unreachable", "P1", f"{viewport} viewport (SC 2.1.1)", kb["unreachable"],
                    "Controls that cannot be reached with Tab are unusable without a mouse.", "Use native elements or give custom widgets tabindex=0 and key handlers.")
            if kb.get("focusNotVisible"):
                add("focus-not-visible", "P1", f"{viewport} viewport (SC 2.4.7)", kb["focusNotVisible"],
                    "Keyboard users cannot see where focus is.", "Add a :focus-visible style (e.g. 2px outline with >= 3:1 contrast); never remove outline without a replacement.")
            if kb.get("obscured"):
                add("focus-obscured", "P1", f"{viewport} viewport (SC 2.4.11)", kb["obscured"],
                    "The focused control is hidden behind other content (sticky header, banner, overlay).", "Add scroll-padding/scroll-margin or move the overlay so focus stays visible.")
            if kb.get("positiveTabindex"):
                add("positive-tabindex", "P2", f"{viewport} viewport", kb["positiveTabindex"],
                    "Positive tabindex breaks the natural focus order.", "Remove tabindex > 0; fix the DOM order instead.")
            if kb.get("notFocusable"):
                add("aria-widget-not-focusable", "P1", f"{viewport} viewport (SC 2.1.1)", kb["notFocusable"],
                    "Elements announced as interactive (role=button, tab, ...) cannot receive keyboard focus.", "Add tabindex=0 and Enter/Space handlers, or use a native <button>.")
        return findings
    return collect


def main():
    parser = add_target_arguments("Keyboard walk and target-size measurement (desktop + mobile)")
    parser.add_argument("--level", choices=["AA", "AAA"], default="AA", help="AAA makes 44x44 px mobile targets mandatory")
    args = parser.parse_args()
    result = run_spec(args, GATE, SPEC, collect_for(args.level), {"A11Y_LEVEL": args.level})
    return emit(result, args.json)


if __name__ == "__main__":
    sys.exit(main())
