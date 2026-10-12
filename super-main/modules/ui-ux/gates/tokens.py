#!/usr/bin/env python3
"""Design-token gate: validate tokens.json and declared contrast pairs.

Finds tokens.json in common locations when --tokens is not given. When the project keeps its
tokens elsewhere (CSS variables, Tailwind theme), the gate reports NOT-TESTED with that reason;
use the ui-ux.token-drift gate for those projects.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "core" / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from gatekit import base_parser, emit, make_finding, project_root, report, status_from_findings  # noqa: E402
from verify_design_system import audit_tokens, duplicate_key  # noqa: E402


GATE = "ui-ux.tokens"
CANDIDATES = ["tokens.json", "design-tokens.json", "src/tokens.json", "tokens/tokens.json", "design/tokens.json", "src/styles/tokens.json"]


def locate(project: Path, explicit):
    if explicit:
        path = Path(explicit)
        return path if path.is_absolute() else project / path
    for rel in CANDIDATES:
        if (project / rel).is_file():
            return project / rel
    return None


def display(path: Path, project: Path) -> str:
    try:
        return str(path.relative_to(project))
    except ValueError:
        return str(path)


def main():
    parser = base_parser("Validate design tokens and contrast pairs")
    parser.add_argument("--tokens", help="Path to tokens.json (relative to the project or absolute)")
    parser.add_argument("--contrast-pairs", help="Path to a contrast pairs JSON list (default: contrast-pairs.json next to the tokens)")
    args = parser.parse_args()
    project = project_root(args.project)

    tokens_path = locate(project, args.tokens)
    if tokens_path is None or not tokens_path.is_file():
        note = (f"Token file not found: {tokens_path}" if tokens_path else
                "No tokens.json found. If the project keeps tokens in CSS variables or a Tailwind theme, "
                "this gate does not apply; run ui-ux.token-drift instead.")
        return emit(report(GATE, "NOT-TESTED", str(tokens_path) if tokens_path else None, notes=[note]), args.json)

    pairs_path = Path(args.contrast_pairs) if args.contrast_pairs else tokens_path.with_name("contrast-pairs.json")
    if args.contrast_pairs and not pairs_path.is_absolute():
        pairs_path = project / pairs_path
    notes = []
    try:
        data = json.loads(tokens_path.read_text(encoding="utf-8"), object_pairs_hook=duplicate_key)
        pairs = None
        if pairs_path.is_file():
            pairs = json.loads(pairs_path.read_text(encoding="utf-8"), object_pairs_hook=duplicate_key)
        else:
            notes.append("No contrast pairs declared; text/background contrast was not checked. Add contrast-pairs.json.")
        errors, count = audit_tokens(data, pairs)
    except (OSError, ValueError) as exc:
        errors, count, pairs = [f"{tokens_path.name}: {exc}"], 0, None

    findings = []
    for message in errors:
        is_contrast = message.startswith("contrast pair")
        findings.append(make_finding(
            len(findings) + 1, "ui-ux", GATE,
            rule="contrast-pair" if is_contrast else "token-invalid",
            severity="P1" if is_contrast else "P2",
            condition=f"validating {display(tokens_path, project)}",
            evidence={"output": message},
            impact="Text/background pair below the required contrast ratio." if is_contrast else "Token value cannot be used reliably by tooling.",
            remediation="Adjust the colors or the pair's minRatio intent; for translucent backgrounds declare 'over'." if is_contrast else "Fix the token as described in evidence.",
        ))
    metrics = {"token_count": count, "contrast_pairs": len(pairs) if isinstance(pairs, list) else 0}
    return emit(report(GATE, status_from_findings(findings), str(tokens_path), findings, notes, metrics), args.json)


if __name__ == "__main__":
    sys.exit(main())
