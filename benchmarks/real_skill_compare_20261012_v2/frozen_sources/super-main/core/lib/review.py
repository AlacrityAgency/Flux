"""Review planner: choose and order the gates for a project and depth, and build the
independent-review packet.

The plan is derived from what the project is (testing.inventory detection) and the requested
depth, so no applicable gate is silently skipped: a gate whose target is missing (no URL, no
API URL) is still planned and will record NOT-TESTED, which keeps the gap visible in the verdict.
"""

import json
import hashlib
import re
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union
from urllib.parse import urlparse

SKILL_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SKILL_DIR / "modules" / "testing" / "gates"))

import testlib  # noqa: E402
from inventory import detect  # noqa: E402
from project import load_config, requirements  # noqa: E402

DEPTHS = ("quick", "standard", "thorough")
MUTATION_TARGETS = 10

ArgSpec = Union[List[str], Callable[[], List[str]]]


def scope_label(target: str) -> str:
    """Short, stable label for a page target: host/path for URLs, file name for sandboxes."""
    if "://" in target and not target.startswith("file://"):
        parsed = urlparse(target)
        label = f"{parsed.netloc}{parsed.path}".rstrip("/") or parsed.netloc
    else:
        label = Path(target.replace("file://", "")).name
    identity = target if "://" in target else str(Path(target).resolve())
    return re.sub(r"[^\w.:/-]+", "-", label)[:60] + "-" + hashlib.sha256(identity.encode()).hexdigest()[:16]


def step(gate: str, args: Optional[ArgSpec] = None, scope: Optional[str] = None, why: str = "", kind: str = "gate") -> Dict[str, Any]:
    return {"gate": gate, "args": args or [], "scope": scope, "why": why, "kind": kind}


CLAIM_DOC_EXT = {".pdf", ".docx", ".md", ".html"}
CLAIM_DOC_NAME = re.compile(r"report|spec|feature|claim|whitepaper|overview|گزارش|مستند|فیچر|ویژگی", re.I)


def candidate_documents(project: Path, limit: int = 8) -> List[str]:
    """Documents at the top of the project that probably describe features (for the claims audit hint)."""
    found = []
    for path in sorted(list(project.glob("*")) + list(project.glob("docs/*"))):
        if path.is_file() and path.suffix.lower() in CLAIM_DOC_EXT and (path.suffix.lower() in {".pdf", ".docx"} or CLAIM_DOC_NAME.search(path.name)):
            found.append(str(path.relative_to(project)))
    return found[:limit]


def build_plan(project: Path, depth: str, urls: List[str], sandboxes: List[str], api_url: Optional[str],
               base: Optional[str], coverage_cmd: Optional[str], level: str, skip: List[str],
               docs: Optional[List[str]] = None, mode: str = "audit", profile: Optional[str] = None) -> Dict[str, Any]:
    if depth not in DEPTHS:
        raise ValueError(f"depth must be one of {DEPTHS}")
    inv = detect(project)
    config = load_config(project)
    selected_profile, features, additional = requirements(config, inv, mode, profile, depth)
    layers = set(inv["layers"])
    has_ui = "frontend" in layers or "ui" in features or bool(urls or sandboxes)
    has_api_spec = bool(inv["openapi_specs"])
    has_tokens = any((project / p).is_file() for p in ("tokens.json", "design-tokens.json", "src/tokens.json", "tokens/tokens.json"))
    deep = depth != "quick"
    steps: List[Dict[str, Any]] = []

    # 1. Understand the project and where the risk is (informational, never decides the verdict).
    if deep:
        steps.append(step("testing.inventory", why="stack, layers, runners, portfolio shape"))
        steps.append(step("testing.risk", why="likelihood x impact ranking of files"))

    # 2. Functional evidence from the project's own tests.
    repeat = config.get("testing", {}).get("repeat", 3 if depth == "thorough" else 1)
    suites = config.get("testing", {}).get("suites", testlib.detect_suites(project))
    if suites:
        for suite in suites:
            scope = scope_label(suite["cwd"] + ":" + suite["name"]) if len(suites) > 1 else None
            steps.append(step("testing.run", ["--repeat", str(repeat), "--suite", suite["cwd"], "--runner", suite["name"]],
                              scope=scope, why="named suite assertions in " + suite["cwd"]))
    else:
        steps.append(step("testing.run", ["--repeat", str(repeat)], why="test discovery; missing assertions remain a gap"))
    steps.append(step("testing.smells", why="focused/empty tests and other smells"))
    if deep:
        if coverage_cmd:
            steps.append(step("testing.coverage-command", [coverage_cmd], why="produce a fresh coverage report", kind="command"))
        cov_args = ["--base", base] if base else []
        steps.append(step("testing.coverage", cov_args, why="diff coverage of changed lines"))
    if depth == "thorough":
        def mutation_args() -> List[str]:
            risk = project / ".superagent" / "testing" / "risk.json"
            if risk.is_file():
                files = [r["file"] for r in json.loads(risk.read_text(encoding="utf-8"))[:MUTATION_TARGETS]]
                return ["--files", ",".join(files)] if files else []
            return []
        steps.append(step("testing.mutation", mutation_args, why=f"mutation score on the top {MUTATION_TARGETS} risk files"))
        if inv["e2e_runner"] == "playwright":
            steps.append(step("testing.run", ["--e2e"], scope="e2e", why="end-to-end suite"))

    # 3. Backend contract.
    if deep and has_api_spec:
        steps.append(step("testing.api", ["--url", api_url] if api_url else [], why="property-based API contract test (OpenAPI)"))

    # 4. UI evidence, per page.
    if has_ui:
        targets = [("--url", u) for u in urls] + [("--sandbox", s) for s in sandboxes]
        if not targets:
            targets = [(None, None)]  # still run: records NOT-TESTED so the missing target is visible
        for flag, target in targets:
            args = [flag, target] if flag else []
            scope = scope_label(str(project / target) if flag == "--sandbox" else target) if target else None
            steps.append(step("ui-ux.page-coverage", list(args), scope, "whole-page and internal scrolling; bounded lazy-content capture"))
            steps.append(step("ui-ux.a11y", list(args), scope, "axe-core WCAG 2.2 AA, desktop + mobile"))
            inter = list(args) + (["--level", "AAA"] if level == "AAA" else [])
            steps.append(step("ui-ux.interaction", inter, scope, "keyboard walk and target sizes"))
        if deep:
            steps.append(step("ui-ux.token-drift", why="hardcoded styles that bypass tokens"))
    if has_tokens:
        steps.append(step("ui-ux.tokens", why="token validity and contrast pairs"))

    # 5. Documents describing the software: do their claims match the code?
    for doc in docs or []:
        scope = scope_label(str(project / doc))
        steps.append(step("claims.trace", ["--doc", doc], scope, "document claims vs. production code"))

    existing = {s["gate"] for s in steps}
    for gate in additional:
        if gate == "product.coverage":
            continue  # Coverage consumes observations from all preceding scenario gates.
        if gate not in existing:
            args = ["--url", api_url] if gate == "testing.api" and api_url else []
            steps.append(step(gate, args, why="required by project features, acceptance criteria or execution mode"))
    if "product.coverage" in additional:
        steps.append(step("product.coverage", why="all applicable product areas map to current observed assertions"))

    steps = [s for s in steps if s["gate"] not in skip]
    required = sorted({(f"{s['gate']}@{s['scope']}" if s["scope"] else s["gate"]) for s in steps
                       if s["gate"] not in {"testing.inventory", "testing.risk"}})
    hints = []
    if additional and not config:
        hints.append("Create superagent.json with observable acceptance criteria and configured scenario runners; missing tools/checks remain NOT-TESTED.")
    if mode == "release-check" and not config.get("acceptance"):
        hints.append("Release readiness requires mapped acceptance criteria in superagent.json.")
    if has_ui and not (urls or sandboxes):
        app_like = re.compile(r"electron|(^|/)(src|app|ui|public|renderer|web|client)(/|$)", re.I)
        pages = sorted((str(p.relative_to(project)) for p in testlib.iter_project_files(project, {".html"})
                        if not testlib.is_test_file(p.relative_to(project))),
                       key=lambda rel: (not app_like.search(rel), rel.count("/"), rel))[:6]
        hint = "UI gates have no target and will be NOT-TESTED. Pass --url <running app page> (repeatable)"
        hints.append(hint + (", or --sandbox for local pages such as: " + ", ".join(pages) if pages else "."))
    if not docs:
        candidates = candidate_documents(project)
        if candidates:
            hints.append("Documents that may describe features (audit them with --doc): " + ", ".join(candidates))
    return {"depth": depth, "mode": mode, "profile": selected_profile, "features": features, "layers": sorted(layers), "shape": inv["recommended_shape"]["shape"], "steps": steps, "required": sorted(set(required)), "hints": hints,
            "product_areas": config.get("product", {}).get("areas", {}),
            "detected": {"ui": has_ui, "api_spec": has_api_spec, "tokens": has_tokens, "e2e": inv["e2e_runner"], "runners": [r["name"] for r in suites], "suites": suites}}


def write_packet(project: Path, plan: Dict[str, Any], verdict_md: str, base: Optional[str]) -> Path:
    """Context for an independent reviewer: what changed, what the gates found, how to review."""
    out = project / ".superagent" / "review"
    out.mkdir(parents=True, exist_ok=True)
    base_ref = base or (testlib.default_base(project) if testlib.is_git_repo(project) else None)
    diff_stat, diff_patch = "", ""
    if base_ref:
        diff_stat = testlib.git(project, "diff", "--stat", base_ref) or ""
        diff_patch = testlib.git(project, "diff", "--no-color", base_ref) or ""
    untracked = testlib.git(project, "ls-files", "--others", "--exclude-standard") if base_ref else ""
    if len(diff_patch) > 60000:
        diff_patch = diff_patch[:60000] + "\n… (truncated; run git diff yourself for the rest)\n"

    findings_lines = []
    for record in _latest_records(project, plan.get("review_id")):
        report_path = project / record.get("report", "")
        if not report_path.is_file():
            continue
        report = json.loads(report_path.read_text(encoding="utf-8"))
        for f in report.get("findings", [])[:15]:
            mark = "" if f.get("confidence") == "verified" else " (suspected)"
            findings_lines.append(f"- `{record['gate']}` [{f.get('severity')}] **{f.get('rule')}**{mark}: {f.get('condition')}")

    skill = SKILL_DIR
    text = f"""# Independent Review Packet

You are reviewing work you did not write. Treat every claim in the conversation that produced it as
unverified. Base conclusions only on the diff, the code, and the gate evidence below.

## Scope
- Project: `{project}`
- Depth: `{plan['depth']}` · layers: {', '.join(plan['layers']) or 'unknown'} · test shape: {plan['shape']}
- Base: `{base_ref or 'none (not a git repo or no main/master)'}`

## Gate evidence (computed from the ledger)
{verdict_md}

## Findings reported by gates
{chr(10).join(findings_lines) or '- none'}

## What to check by reading the code (gates cannot)
1. Does the change do what was asked? Compare with the request and acceptance criteria.
2. Correctness: edge cases (empty, null, boundaries, concurrency, retries), error handling, data loss.
3. Tests: do new tests assert real behaviour, or only that code runs? Were any tests deleted, skipped or weakened?
4. Security basics: input validation, authorisation checks, secrets in code or logs.
5. UI: states (loading, empty, error), wording, heading order, focus return after dialogs ({skill}/modules/ui-ux/references/review-checklist.md).
6. Claims: if docs, reports or UI text describe what the software measures or detects, check names, units and causal or diagnostic claims ({skill}/modules/claims/references/claim-review.md).
7. Report each issue in the finding format ({skill}/core/protocol.md §3); mark anything you cannot prove as a question.
8. Read superagent.json acceptance criteria. Check that the named scenario runners assert real effects, use a real database where required, and have not weakened security or release checks.

## Changed files
```
{diff_stat.strip() or '(no diff against base)'}
```
{('Untracked files:' + chr(10) + '```' + chr(10) + untracked.strip() + chr(10) + '```') if untracked and untracked.strip() else ''}

## Diff
```diff
{diff_patch.strip() or '(empty)'}
```
"""
    path = out / "packet.md"
    path.write_text(text, encoding="utf-8")
    return path


def _latest_records(project: Path, review_id: Optional[str] = None) -> List[Dict[str, Any]]:
    import ledger
    latest: Dict[str, Dict[str, Any]] = {}
    for record in ledger.load(project):
        if review_id is not None and record.get("review_id") != review_id:
            continue
        latest[ledger.evidence_key(record["gate"], record.get("scope"))] = record
    return list(latest.values())


# ------------------------------------------------------------------------------
# Worklist: turn gate evidence into concrete tasks for the agent (workflow T4-T5)
# ------------------------------------------------------------------------------

PRIORITY = {"P1": 1, "P2": 2, "P3": 3}


def build_worklist(project: Path, coverage_cmd: Optional[str] = None, top_risk: int = 10, review_id: Optional[str] = None) -> Dict[str, Any]:
    """Collect tasks from the latest evidence of every gate. Each task names its acceptance check."""
    sa = f"python3 {SKILL_DIR}/core/bin/sa.py"
    cov = f' --coverage-cmd "{coverage_cmd}"' if coverage_cmd else ' --coverage-cmd "<command that writes a coverage report>"'
    tasks: List[Dict[str, Any]] = []

    def add(kind, priority, target, detail, accept, source):
        tasks.append({"type": kind, "priority": priority, "target": target, "detail": detail, "accept": accept, "source": source})

    def accept_new_test(target):
        return f"{sa} gate testing.accept --scope <test-name> -- --test <new test file> --target {target}{cov}"

    for record in _latest_records(project, review_id):
        report_path = project / record.get("report", "")
        if not report_path.is_file():
            continue
        rep = json.loads(report_path.read_text(encoding="utf-8"))
        gate = record["gate"]
        rerun = f"{sa} gate {gate}" + (f" --scope {record['scope']}" if record.get("scope") else "") + (" -- " + " ".join(record.get("args") or []) if record.get("args") else "")
        for f in rep.get("findings", []):
            ev, rule, sev = f.get("evidence", {}), f.get("rule"), f.get("severity", "P2")
            if gate == "testing.run" and rule == "test-failure":
                add("fix-code-or-test", sev, ev.get("test"), "Fails in every run. Decide: real bug (fix the code) or wrong test (fix it, and say why in a Decision Record).", rerun, gate)
            elif gate == "testing.run" and rule in {"flaky-test", "flaky-suite"}:
                add("fix-flaky-test", sev, ev.get("test") or "suite", f"Outcomes differ across identical runs ({f.get('condition')}). Remove time/order/randomness/shared-state/network dependence.", f"{sa} gate testing.run -- --repeat 5", gate)
            elif gate == "testing.run":
                add("fix-test-setup", sev, ev.get("command"), f.get("impact"), rerun, gate)
            elif gate == "testing.coverage" and rule == "diff-coverage-below-threshold":
                for file, lines in (ev.get("uncovered") or {}).items():
                    add("write-test", sev, file, f"Changed lines not executed by any test: {lines}", accept_new_test(file), gate)
            elif gate == "testing.coverage":
                add("write-test", sev, ev.get("file"), f"Changed file absent from coverage ({ev.get('changed_lines')}).", accept_new_test(ev.get("file")), gate)
            elif gate == "testing.mutation":
                add("write-test", sev, f.get("condition"), f"Surviving mutant ({ev.get('mutator')} → {ev.get('replacement')}): write a test that fails on this change.", accept_new_test(str(f.get("condition", "")).split(":")[0]), gate)
            elif gate == "testing.smells" and f.get("confidence") == "verified":
                add("fix-test", sev, f.get("condition"), f"{rule}: {f.get('remediation')}", f"{sa} gate testing.smells", gate)
            elif gate == "testing.smells":
                add("check-test", "P3", f.get("condition"), f"Suspected {rule}: read the test; fix if confirmed. {f.get('remediation')}", f"{sa} gate testing.smells", gate)
            elif gate.startswith("ui-ux."):
                where = ", ".join(ev.get("elements") or ev.get("nodes") or ([ev.get("file")] if ev.get("file") else []))[:300]
                add("fix-ui", sev, f"{gate}{'@' + record['scope'] if record.get('scope') else ''}", f"{rule}: {f.get('impact')} Elements: {where}. {f.get('remediation')}", rerun, gate)
            elif gate == "testing.api":
                add("fix-code", sev, rule, f"{f.get('impact')} See log: {ev.get('log')}", rerun, gate)
            else:
                kind = "fix-verified-finding" if f.get("confidence", "verified") == "verified" else "investigate"
                add(kind, sev, f.get("condition"), f"{f.get('impact')} {f.get('remediation')}", rerun, gate)
        if rep.get("status") in {"NOT-TESTED", "ERROR"}:
            add("prepare-verification", "P2", gate, "; ".join(rep.get("notes", [])), rerun, gate)

    risk_file = project / ".superagent" / "testing" / "risk.json"
    if risk_file.is_file():
        for row in json.loads(risk_file.read_text(encoding="utf-8"))[:top_risk]:
            if not row.get("has_test"):
                prio = "P1" if row.get("impact", 1) >= 2 else "P2"
                add("write-test", prio, row["file"], f"High-risk file without a matching test ({', '.join(row.get('reasons', []))}). Plan cases with partitions, boundaries, decision tables and error paths (workflow T4).", accept_new_test(row["file"]), "testing.risk")

    seen, unique = set(), []
    for t in sorted(tasks, key=lambda t: (PRIORITY.get(t["priority"], 3), t["type"] != "fix-code-or-test", str(t["target"]))):
        key = (t["type"], str(t["target"]), t["detail"][:80])
        if key not in seen:
            seen.add(key)
            unique.append(dict(t, id=f"W{len(unique) + 1:03d}"))
    return {"project": str(project), "tasks": unique}


def write_worklist(project: Path, worklist: Dict[str, Any]) -> Path:
    out = project / ".superagent" / "review"
    out.mkdir(parents=True, exist_ok=True)
    (out / "worklist.json").write_text(json.dumps(worklist, indent=2, ensure_ascii=False), encoding="utf-8")
    lines = ["# Worklist", "", "Tasks derived from gate evidence. Work top-down; each task lists the check that accepts it.",
             "New tests must pass `testing.accept` (F1 builds, F2 5/5 stable, F3 adds coverage, F4 no smells). Never delete, skip or weaken an existing test to clear a task.", ""]
    if not worklist["tasks"]:
        lines.append("No tasks: the latest evidence has no findings and no untested high-risk files.")
    for t in worklist["tasks"]:
        lines += [f"## {t['id']} [{t['priority']}] {t['type']}: `{t['target']}`", f"- {t['detail']}", f"- Accept: `{t['accept']}`", f"- Source: {t['source']}", ""]
    path = out / "worklist.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
