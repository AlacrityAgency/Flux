# Project Configuration and Scenario Reports

`superagent.json` lives in the project's root and is part of its code fingerprint. Keep it
under version control. Store only non-secret command arguments; runners obtain secrets from
the environment. `sa.py plan` reads configuration without executing commands or modifying files.

## Configuration

```json
{
  "version": 1,
  "profile": "web-app",
  "features": ["auth", "data"],
  "environment": "test",
  "acceptance": [
    {"id": "A1", "criterion": "A created task persists in the database", "gate": "backend.behavior", "scenario": "task-persistence"},
    {"id": "A2", "criterion": "User B cannot read user A's task", "gate": "security.authorization", "scenario": "cross-user-denied"}
  ],
  "checks": {
    "backend.behavior": {"command": ["python3", "tests/backend_checks.py"], "expected": ["task-persistence"]},
    "security.authorization": {"command": ["python3", "tests/auth_checks.py"], "expected": ["cross-user-denied"]},
    "security.sast": {"rules": "security/semgrep.yml", "timeout": 300}
  }
}
```

Implement the named runners in the actual project; these examples are not preinstalled tests.
Features are additive to the profile: ui, api, data, auth, tenancy, payments, jobs.
Acceptance criteria map to command-gate scenarios, not scanner results or citation counts.
Only enable features actually present or requested. Local/test/staging runners must use dedicated
data and endpoints. Generic mutating scenario gates refuse environment `production`.
An audit records missing checks; build/change creates appropriate checks as part of the feature.

## Fresh evidence contract

Each configured command is an argv array executed without a shell, in the project directory.
It must print one JSON report, or write it to `SUPERAGENT_REPORT`; `{report}` in an argv item
is replaced by that fresh path. The old report is deleted before every run.

```json
{"checks": [{"name": "task-persistence", "status": "PASS", "executed": 2}]}
```

The runner must perform assertions, report their actual outcomes and return nonzero when they fail.
Use PASS/FAIL/SKIP per scenario. `executed` is the number of assertions actually evaluated, not a
constant chosen to satisfy the adapter. Empty, duplicate, malformed or zero-assertion PASS reports
are ERROR; missing or skipped scenarios are NOT-TESTED; observed assertion failures are FAIL.
Successful exit alone is not PASS. Reviewer must inspect the runner; this format cannot prove
honesty, real database usage, coverage of all paths or correctness of arbitrary assertions.
Artifacts in `.superagent/` are excluded from the fingerprint. Ignore other generated reports explicitly.

## Tool adapters

- `security.sast`: Semgrep JSON with project-local rules, scanned paths and no scan errors.
- `security.dependencies`: Trivy filesystem JSON schema 2; dependency/config/secret findings are
  normalized without copying matched code or secret values into the ledger. Triage findings;
  a scanner observation does not establish exploitability or full ASVS compliance.
- `operations.load`: set `format: "k6"`, pass `--summary-export {report}` to the configured k6
  command, and list expected thresholds as `metric:expression` (e.g. `http_req_duration:p(95)<500`).
  A positive iteration count and evaluated boolean threshold outcomes are required. Verify the
  installed k6's export shape before use; incompatible output is ERROR, never PASS.
  The adapter supports the legacy flat `--summary-export` shape (`iterations.count`, threshold
  boolean `false` = passed), and nested `handleSummary` metrics (`iterations.values.count`,
  threshold `{ "ok": true }` = passed). Mixed formats are rejected; newer grouped/versioned
  summary formats need a separate adapter. This is not a guarantee for arbitrary k6 versions.
- `security.dast`: a project-owned ZAP adapter executes against the dedicated target, checks
  crawl/authentication coverage and maps observed results into named checks. A preexisting report
  or a login-page-only scan is insufficient. No ZAP installation is implied by this skill.
- Database/restore, build/rollback and resilience: project-owned runners because commands and
  success conditions depend on the actual engine and hosting environment. Testcontainers and
  OpenTelemetry are optional project dependencies, not automatically installed by the skill.

## Release boundary

`review --mode release-check` adds build, rollback, resilience and security scanners; applications
with data also need restore and API services need load thresholds. --skip is forbidden in this mode.
Missing prerequisites, stale evidence or unmapped acceptance criteria block `release_ready`.
The result only covers the declared project profile, targets and criteria; it is not a certificate.

## Project Map and Efficient Test Suites

Optional `sources` declares inspected roots: `active`, `reference`, `generated`, `entrypoints`
are arrays of project-relative paths. `sa.py project-map --json` preserves unknown roles;
directory conventions are hints, not proof of activation. Verify declarations using build/import
paths. Token drift excludes declared references/generated roots. Directory names alone do not
exclude files; declare inspected roots when separating old designs from the served product.
Symlinked files and out-of-project roots are not indexed. Retrieval excludes likely secret filenames;
review source selection because no filename filter can detect every secret.

`testing` accepts `repeat` (1..5), `static_workers` (1..4, default 2) and explicit `suites`:

```json
{"testing": {"repeat": 1, "static_workers": 2, "suites": [{"name": "pytest", "cwd": "backend"}, {"name": "node-test", "cwd": "frontend"}]}}
```

Automatic package detection is bounded to four nested directories and retains runner candidates.
Unused dependencies or root aggregate scripts can duplicate tests; declare suites in that case.
Review requires each detected/configured suite under a separate scope. Custom testing.run commands
need fresh JUnit for PASS; a zero-exit command without per-test outcomes remains NOT-TESTED.

Review batches the five allowlisted static gates before running sequential scenarios. Only
unscoped gates without extra arguments qualify; baseline updates and arbitrary commands never
enter the batch. Workers are bounded, evidence appends serialized, and the batch finishes before
data-changing tests begin. Use `static_workers: 1` to disable overlap. Timings record the budget;
model latency and any speedup still require an independent measurement.

## Whole Product Coverage

Build/release-check require `product.coverage`; existing narrow reviews opt in through `product`.
Define `product: {"areas": {...}}` with every area in [product workflow](../modules/product/workflow.md).
Each area is either `{ "applicable": false, "reason": "Specific reason", "criteria": [] }` or
`{ "applicable": true, "reason": "Required outcome", "criteria": ["A1"] }`.
Applicable criteria reference acceptance ids and current intact scenario evidence, not a self-rated status.

Each mapped acceptance criterion also classifies `trace.design`, `trace.content`, `trace.code`,
and `trace.tests`. Each is `{ "applicable": true, "reason": "Purpose", "paths": ["relative/file"] }`
or `{ "applicable": false, "reason": "Specific reason", "paths": [] }`.
Missing classifications/artifacts remain a gap even when a scenario passes. Existing files alone
do not prove their quality; independently inspect the design, copy and assertions.
Product-specific checks use the same named scenario contract: `product.research`, `.ux`, `.content`,
`.integrations`, `.seo`. Automated checks must not impersonate a qualitative human/model review.
Outputs `.superagent/product/coverage.json` and `.md` map areas -> criteria -> artifacts -> scenarios -> runs.
Review evaluates coverage last and restricts it to its own review_id, preventing historical green reuse.

## Browser Scope and Timing

Review plans `ui-ux.page-coverage` for each provided page. It scrolls document/internal regions,
captures overlapping segments, and repeats from the top after revealing lazy content. Step/region
limits or continuously growing content produce NOT-TESTED. Inspection of screenshots and named
form/modal/menu/error journeys remains necessary. Browser capture does not claim that those states
were exercised. Review timing.json records step and fingerprint costs; provider telemetry is separate.
Optional `agent` fields `provider`, `model`, `reasoning` record the declared host settings in timing.json;
the CLI does not verify or change provider settings. Use [evaluation protocol](../evals/product/protocol.md)
for fresh-context model comparisons and honest reporting of unavailable telemetry.
