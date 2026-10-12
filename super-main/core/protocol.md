# Protocol: Gates, Findings, Evidence Ledger and Verdict

Single source for result statuses, the finding format, how evidence is recorded and how the verdict is computed. Every module follows it; workflows link here instead of restating it.

---

## 1. Gate contract

A gate is a script registered in a module's `module.json`. Run gates through the ledger:

```bash
python3 <skill>/core/bin/sa.py --project <project> gate <module.gate> -- <gate arguments>
```

Each gate prints one JSON report and exits with:

| Exit | Status | Meaning |
|---|---|---|
| 0 | `PASS` | Ran against the current code; no verified finding |
| 1 | `FAIL` | Ran; at least one **verified** finding |
| 2 | `NOT-TESTED` | A prerequisite is missing (no running app, tool not installed, no report). The notes say what is needed. Never a code defect |
| 3 | `ERROR` | The gate itself broke. A skill limitation, not a code defect |

Informational gates (`testing.inventory`, `testing.risk`) report PASS when they ran; they never decide the verdict.
Skipped or zero-test runs are never PASS.

## 2. Statuses used in reports

`PASS`, `FAIL`, `NOT-TESTED`, `ERROR` as above, plus `NOT-APPLICABLE` for a check that does not apply (e.g. RTL for an English-only tool) and `STALE` for evidence recorded before the latest code change.

## 3. Finding format

Gates emit findings as JSON:

```json
{"id": "run-0001", "module": "testing", "rule": "flaky-test", "severity": "P1",
 "confidence": "verified", "condition": "...", "evidence": {"...": "..."},
 "impact": "...", "remediation": "..."}
```

- `confidence: verified` means the gate observed it directly; it fails the gate.
- `confidence: suspected` is a heuristic hit (e.g. a possible test smell); report it as a *Question / Limitation*, confirm it by reading the code, and never let it fail a gate on its own.

When you report a defect yourself (outside a gate), give the same five fields with concrete evidence; if any field cannot be backed by evidence, it is a question, not a defect:

1. **Condition**: when it happens (viewport, state, command).
2. **Evidence**: file:line, gate output or DOM selector. Check upstream handling before calling something a crash.
3. **Impact**: the real consequence for users.
4. **Reproduction**: steps or command.
5. **Remediation**: the exact change.

Severity: **P1** WCAG A/AA violation, failing or flaky test, broken flow, data loss, crash · **P2** edge case, polish, AAA-only gap · **P3** suggestion. No P0.
Do not report a deliberate, documented limit (a parser's declared scope, an optional default) as a defect unless it breaks the user's request.

## 4. Evidence ledger

`sa.py gate` appends one line per run to `<project>/.superagent/ledger.jsonl` and stores the full report in `.superagent/runs/<run>.json`. Each record carries a **fingerprint** of file paths and SHA-256 file contents (git-tracked and untracked-but-not-ignored files), not timestamps alone. Reports include the actual command, Python/platform/skill version, scope and before/after fingerprints. A source change during a run makes its evidence stale immediately.

Rules:
1. **Only gate runs are evidence.** "Looks fine" is not a result.
2. **Evidence expires on change.** A record whose fingerprint differs from the current project is `STALE` and must be re-run.
3. **Quote, do not paraphrase.** Cite the gate id, run id and exit code.
4. Add `.superagent/` to the project's `.gitignore`.
5. Reports and artifact snapshots carry content digests. Missing or edited evidence becomes
   STALE, even if source is unchanged. Old records without digests need a rerun. These local
   hashes are not tamper-proof signatures against rewriting the whole ledger.
6. Each review has its own `review_id`; its verdict, packet and worklist use only that session.
   `verdict --require` restricts the selected gate scope; unfiltered verdict retains all history.
   Target keys include full URL identity (query/fragment) or resolved file path, even for one page.
7. A failed coverage producer is evidence itself and blocks review; old reports are not reused.

Debug experiments use the same ledger through [debug workflow](../modules/debug/workflow.md),
but their CONFIRMED/REFUTED/INCONCLUSIVE/UNTESTED outcomes describe a hypothesis, not release
readiness. They must be followed by relevant application regression gates.

## 5. Attempt budget

Counted by the ledger per gate, on consecutive failing runs that share a rule:

| Failing runs | Budget state | Required action |
|---|---|---|
| 1 | `ok` | Targeted fix, re-run |
| 2 | `pivot-required` | Change approach (see [reasoning.md §4](reasoning.md)), re-run |
| 3 | `exhausted` → verdict `REJECTED` | Stop; deliver with remediation steps for a developer |

NOT-TESTED runs do not consume the budget.

## 6. Verdict

```bash
python3 <skill>/core/bin/sa.py --project <project> verdict --require <gate,gate,...> --format md
```

| Overall | Label | Exit |
|---|---|---|
| All required gates PASS on current code | `[QA-PASSED]` | 0 |
| No failure, some NOT-TESTED / ERROR | `[QA-PASSED-WITH-GAPS: …]` | 2 |
| Evidence older than the code | `[QA-STALE: …]` | 2 |
| A required gate never ran | `[QA-NO-EVIDENCE: …]` | 2 |
| A gate fails | `[QA-FAILED: …]` | 1 |
| Attempt budget exhausted | `[QA-REJECTED: …]` | 1 |

The final report quotes the label produced by `sa.py verdict`. Writing a verdict label by hand is not allowed. The `--format md` output also contains the ISO/IEC 25010 scorecard (which quality characteristics have evidence).

## 7. Application scope and release

Follow [application.md](workflows/application.md) for design/build/change/audit/test/release-check. [superagent.json](project-config.md) maps product criteria to named scenarios. Missing tools, missing expected scenarios, skipped scenarios and zero assertions cannot produce PASS. A process exit of zero alone is insufficient; review assertions separately to detect invented counts or vacuous checks.

`review --mode release-check` refuses `--skip` and produces `release_ready` only when the current required evidence passes and mapped acceptance criteria exist. This covers the configured scope, not regulatory certification, penetration-test completeness, or permission to deploy. Production deployment, destructive migrations, external scans and real payments require explicit user authorization.
