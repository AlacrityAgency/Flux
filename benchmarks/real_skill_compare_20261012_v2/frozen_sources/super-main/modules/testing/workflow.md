# Workflow: Evidence-Driven Test Evaluation (ETEA)

Use to evaluate an application's quality and to test it: backend, frontend or both. The algorithm decides **what** to test (risk), **how** (portfolio shape and level), **when a new test is good enough** (assurance filters), and **what the verdict is** (ledger, not opinion).

Shared rules: [core/protocol.md](../../core/protocol.md) (statuses, findings, verdict) · [core/reasoning.md](../../core/reasoning.md) (decision records, attempt budget).
Background and sources: [references/strategy.md](references/strategy.md) · [references/backend.md](references/backend.md) · [references/frontend.md](references/frontend.md) · [references/test-smells.md](references/test-smells.md)

All commands: `python3 <skill>/core/bin/sa.py --project <project> gate <gate-id> -- <gate args>`. Every run is recorded in `<project>/.superagent/ledger.jsonl`.

Shortcut for the evaluation steps (T1–T3, T6–T8): `sa.py review --depth <quick|standard|thorough> [--url <page> …] [--api-url <url>] [--coverage-cmd "<cmd>"]` plans and runs every applicable gate, prints the verdict and writes `.superagent/review/worklist.md`.

The loop for T4–T5 is: **review → worklist → write the test / fix the code → `testing.accept` → review again**. Scripts measure and accept; you (the agent) plan and write. The scripts never generate tests or patch code on their own, because only the agent understands the requirements, and an unchecked generated test is worse than none.

---

## Overview

```
T0 Scope ─► T1 Inventory ─► T2 Baseline ─► T3 Risk ─► T4 Plan ─► T5 Write tests ─► T6 Harden ─► T7 Runtime gates ─► T8 Verdict
                                 ▲                                    │  (assurance filters F1-F4)            │
                                 └──────────── any code change makes earlier evidence STALE ◄─────────────────┘
```

| Depth | Steps | Required gates for the verdict |
|---|---|---|
| `quick` (small change) | T0, T2 on affected tests, T5 for the change, T8 | `testing.run`, `testing.smells` |
| `standard` (default) | T0–T5, T7, T8 | + `testing.coverage`; + `ui-ux.a11y`, `ui-ux.interaction` when there is a UI; + `testing.api` when there is an API spec |
| `thorough` (release, critical code) | all | + `testing.mutation` on top-risk files; + `testing.run -- --e2e` |

---

## T0 — Scope

1. Decide the object of evaluation: the change (diff against the base branch) or the whole application.
2. Collect the requirements you can test against: the user's request, acceptance criteria, API spec, user flows. Write them as short, checkable statements ("refund larger than payment is rejected").
3. Write a Decision Record with the chosen depth.

## T1 — Inventory

```bash
sa.py gate testing.inventory
```
Read `layers`, `runners`, `e2e`, `recommended_shape`. The shape decides the portfolio in T4:

| Shape | When (detected automatically) | Emphasis |
|---|---|---|
| **Pyramid** | backend service, library, monolith | many fast unit tests on logic → fewer integration tests on real I/O → thin E2E |
| **Trophy** | UI-centric app (React, Vue, Svelte, …) | static checks → **integration-level component tests** (largest layer) → few E2E on critical flows |
| **Honeycomb** | 3+ deployable services | **integration + contract tests** between services dominate; few implementation-detail unit tests |

If no runner is detected, set one up with the project's ecosystem defaults (vitest/jest for JS, pytest for Python, `go test`) before continuing; ask before adding dependencies.

## T2 — Baseline (before touching anything)

```bash
sa.py gate testing.run -- --repeat 3     # failing and flaky tests, zero-test detection
sa.py gate testing.smells                # focused/empty tests fail; others are reported
# run the project's tests with coverage (see references/strategy.md §5), then:
sa.py gate testing.coverage
```
- Pre-existing failures and flaky tests are **findings**, not something to hide. Never delete, skip or weaken a test to make the baseline green. If a test is wrong, say why in a Decision Record before changing it.
- A flaky test is one whose outcome changes across identical runs. Rerunning is the detection method; fixing the nondeterminism (time, randomness, order, shared state, network, fixed sleeps) is the remedy. Quarantine only with an owner and a deadline.

## T3 — Risk analysis

```bash
sa.py gate testing.risk
```
Risk level = **likelihood × impact** (ISTQB). Likelihood comes from churn, bug-fix history, complexity, coverage gaps and missing tests; impact from critical domains (auth, payments, permissions, data deletion, migrations, uploads) and entry points (routes, handlers, pages).

Build the target list:
1. Changed files ∩ top-risk files first, then the remaining changed files, then other top-risk files.
2. For each target note the requirements from T0 it implements.
3. `depth: quick` → only the changed code. `standard` → changed code + top 5 risk. `thorough` → changed code + top 15 risk.

## T4 — Plan the tests

Start from the worklist (`sa.py worklist`, also written by `review`): every task names a target, the evidence (uncovered lines, surviving mutant, failing or flaky test, untested high-risk file, UI finding) and the command that will accept the work. Work top-down: failing and flaky tests first, then P1 write-test tasks.

For every target choose the **lowest level that can observe the behaviour with confidence**, consistent with the shape from T1 (details in [backend.md](references/backend.md) and [frontend.md](references/frontend.md)):

| Behaviour | Level |
|---|---|
| Pure logic: calculations, parsing, validation rules | unit |
| Code that talks to a DB, queue, file system, HTTP handler | integration with a real or in-memory dependency (test DB, test client) |
| API shape and status codes between services or clients | contract (`testing.api` from OpenAPI; consumer-driven contracts when several consumers exist) |
| UI component behaviour | component integration test through the DOM, queried by role/label as a user would |
| Critical user journey (sign-in, checkout, data export) | E2E (Playwright), few and stable |
| Accessibility, keyboard, target size | `ui-ux.a11y`, `ui-ux.interaction` |

Derive cases with black-box techniques instead of guessing:
- **Equivalence partitions** and **boundary values** for every input (min, min−1, max, max+1, empty, null, very long, unicode/RTL text).
- **Decision tables** for rules with several conditions.
- **State transitions** for workflows (order: created → paid → refunded; invalid transitions must be rejected).
- **Error paths**: dependency down, timeout, invalid input, unauthorised user.

Write the plan as a short table: target · requirement · level · cases. That table is the test design evidence.

## T5 — Write tests with assurance filters

Write each test against the plan, then run the four filters (adapted from Meta's TestGen-LLM) in one command. A test that fails a filter is reworked or deleted; after 2 failed attempts on the same test, stop and report the gap.

```bash
sa.py gate testing.accept --scope <test-name> -- --test <new test file> --target <source file> --coverage-cmd "<coverage command>"
# bug reproduction written before the fix (must fail 5/5), then the same command without --expect-fail after the fix:
sa.py gate testing.accept --scope <bug-name> -- --test <test file> --expect-fail
```

| Filter | Check | Command |
|---|---|---|
| **F1 Builds** | The test file is collected and at least one test runs | `testing.accept` |
| **F2 Stable** | Passes **5 of 5** runs on the current code (`--expect-fail`: fails 5 of 5 before the fix) | `testing.accept` |
| **F3 Adds value** | Lines on the target become covered that were not covered with the new test set aside (needs `--coverage-cmd`; otherwise NOT-TESTED). A reproduction test counts as value. Killing a surviving mutant is checked by re-running `testing.mutation` | `testing.accept`, `testing.mutation` |
| **F4 Clean** | No smells at all in the new file, not even suspected ones | `testing.accept` |

Rules for test code:
- Assert on observable behaviour (return values, HTTP responses, rendered text, DB state), not on private implementation details.
- One behaviour per test, descriptive names (`refund_larger_than_payment_is_rejected`).
- Deterministic: inject clocks and random seeds, isolate state, no fixed sleeps; mock only true external boundaries (third-party APIs, email, payment providers).
- Bug fixes follow **reproduce → fix → keep**: write the failing test first (F2 inverse), fix the code, confirm 5/5 green.

## T6 — Harden (thorough, or when coverage is high but confidence is low)

```bash
sa.py gate testing.mutation -- --files <top risk files>
```
Requirements: JS/TS needs the Stryker **engine** in the project (`npm i -D @stryker-mutator/core` plus a runner plugin, or the default command runner using `npm test`); the Stryker IDE extension alone does not run anything. Python needs `mutmut`. A project without tests is NOT-TESTED: mutation testing measures an existing suite.
Coverage proves code ran; mutation score shows the tests would notice a fault. Each **surviving mutant** is a concrete target: write a test that fails on that mutation (mutation-guided test generation), run it through F1–F4, then re-run the gate. Target: mutation score ≥ 60% on the hardened files (raise for critical code).

## T7 — Runtime gates

Start the app with the project's own dev command, then:

```bash
# Backend with an OpenAPI spec (local URLs only)
sa.py gate testing.api -- --url http://localhost:<port>
# Frontend
sa.py gate ui-ux.a11y -- --url http://localhost:<port>/<page>
sa.py gate ui-ux.interaction -- --url http://localhost:<port>/<page>
# End-to-end suite (thorough)
sa.py gate testing.run -- --e2e
```
Audit each important page/state (empty, loaded, error, dialog open), not only the home page. If the app cannot be started, those gates are NOT-TESTED: report what is needed.

## T8 — Verdict and report

```bash
sa.py verdict --require testing.run,testing.smells,testing.coverage[,ui-ux.a11y,ui-ux.interaction,testing.api,testing.mutation] --format md
```
- The verdict is computed from the ledger: STALE evidence (code changed after the run) must be re-run; repeated failures consume the attempt budget.
- **Exit criteria** (`standard`): all tests pass, 0 flaky, 0 focused/empty tests, diff coverage ≥ 80% (≥ 90% for critical-domain files), required runtime gates PASS, no open P1 finding. `thorough` adds mutation ≥ 60% on hardened files and a passing E2E suite.
- Report with the verification summary from `--format md`, the ISO/IEC 25010 scorecard, the test plan table from T4, the tests added (with their filter results), and open findings in the finding format.

---

## Quality model mapping (ISO/IEC 25010:2023)

| Characteristic | Evidence in this skill |
|---|---|
| Functional suitability | `testing.run`, `testing.mutation`, `testing.api` |
| Reliability | flaky detection in `testing.run`, `testing.smells`, `testing.api` (no 5xx) |
| Interaction capability (usability, accessibility) | `ui-ux.a11y`, `ui-ux.interaction`, `ui-ux.tokens` |
| Maintainability (incl. testability) | `testing.coverage`, `testing.smells`, `testing.mutation`, `ui-ux.token-drift` |
| Compatibility | `testing.api` (contract), desktop + mobile viewports |
| Performance efficiency, Security, Flexibility, Safety | not yet covered by gates: report as NOT-TESTED in the summary |
