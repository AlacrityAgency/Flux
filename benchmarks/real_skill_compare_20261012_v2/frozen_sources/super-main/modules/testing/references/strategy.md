# Test Strategy: Shapes, Risk, Assurance Filters and Metrics

Background for [../workflow.md](../workflow.md). Each section states the rule the skill applies and where it comes from.

---

## 1. Portfolio shapes

| Shape | Layers (bottom → top) | Fits | Why |
|---|---|---|---|
| Pyramid | unit (most) → integration → E2E (few) | backend services, libraries, monoliths | Fast, precise feedback on logic; I/O covered by fewer integration tests |
| Trophy | static analysis → unit → **integration (most)** → E2E | UI-centric apps (React/Vue/Svelte SPAs) | Component-integration bugs outnumber unit bugs; integration tests give the best confidence per cost |
| Honeycomb | implementation-detail (few) → **integrated/integration (most)** → integrated E2E (few) | microservices | Most risk is in service interactions, so contract and service-level integration tests matter most |
| Ice-cream cone / crab | mostly E2E/visual | avoid as a target; acceptable only for very small, UI-only projects | Slow and brittle at scale |

Guiding principle for UI tests (Testing Library): *the more your tests resemble the way your software is used, the more confidence they can give you.*

`testing.inventory` picks the shape from the detected stack; override it in a Decision Record when the product says otherwise (for example a frontend with heavy client-side business logic may warrant more unit tests).

## 2. Risk-based prioritisation

ISTQB defines risk level by **likelihood** and **impact**; testing intensity and order follow the risk level.

`testing.risk` estimates them per file:

| Signal | Weight / effect | Rationale |
|---|---|---|
| Churn (commits touching the file) | 0.30 of likelihood | Frequently changed code breaks more often |
| Bug-fix commits touching the file | 0.25 | Past defects predict future defects |
| Decision points (if/for/case/&&/…) | 0.20 | More paths, more ways to be wrong |
| Coverage gap | 0.25 | Untested code hides defects |
| No matching test file | +0.15 | Nothing guards it |
| Critical domain (auth, payments, permissions, deletion, migrations, uploads) | impact +1 | Failures cost money, data or trust |
| Entry point (routes, handlers, pages) | impact +1 | Directly user-facing |

Risk = likelihood (0–1) × impact (1–3). The ranking is a heuristic for ordering work, not a verdict.

## 3. Assurance filters for new tests

Adapted from Meta's TestGen-LLM ("Assured LLM-based Software Engineering"): candidate tests pass progressively stricter filters, and only tests with measurable value are kept. In Meta's deployment 75% of generated tests built, 57% passed reliably and 25% increased coverage, which is why filtering matters.

| Filter | TestGen-LLM | This skill |
|---|---|---|
| Builds | candidate compiles in the existing infrastructure | F1: `testing.run -- --args <file>` |
| Passes reliably | must pass on **every one of five** executions (otherwise flaky) | F2: `--repeat 5`; bug-reproducing tests must fail 5/5 before the fix |
| Improves | increases line or branch coverage | F3: coverage gain, a killed mutant, a reproduced bug or a newly covered requirement |
| — | — | F4: no test smells (`testing.smells`) |

## 4. Mutation-guided hardening

Mutation score measures the test oracle: whether tests notice a deliberately injected fault. Research comparing it with coverage finds it a stronger indicator of fault-detection ability, at a much higher compute cost, so the skill applies it to high-risk files only.

Meta's ACH system generates a few targeted mutants for a concern (e.g. privacy), then generates tests that kill the surviving ones; engineers accepted 73% of those tests. The skill's T6 step follows the same loop with StrykerJS or mutmut: surviving mutant → targeted test → filters F1–F4 → re-run.

## 5. Coverage

- Gate on **diff coverage** (changed executable lines covered / changed executable lines), default ≥ 80%; ≥ 90% for critical-domain files. Google applies coverage at the changeset/code-review level rather than chasing one global number.
- Total coverage is informational unless the project sets a floor (`--min-total`).
- Coverage is necessary, not sufficient: a test without assertions can reach 100%. Use smells (assertion-free tests) and mutation score to check test strength.

Producing reports (the coverage gate reads these files):

| Stack | Command |
|---|---|
| pytest | `pytest --cov=<pkg> --cov-report=xml` (writes `coverage.xml`) |
| Python unittest | `coverage run -m unittest && coverage xml` |
| Vitest | `vitest run --coverage --coverage.reporter=lcov` |
| Jest | `jest --coverage --coverageReporters=lcov` |
| node:test | `c8 --reporter=lcov node --test` |
| Go | `go test -coverprofile=coverage.out ./...` |

## 6. Flaky tests

Google reported that about 16% of its tests showed some flakiness and that most pass→fail transitions in post-submit were flaky rather than real regressions; Google labels a test flaky when it passes on any of up to 10 reruns of a failing run. Rerun-based detection is expensive and incomplete, so the skill: reruns baselines (`--repeat 3`), requires new tests to pass 5/5, and treats every flaky test as a P1 finding to fix rather than retry.

## 7. Exit criteria (defaults)

| Criterion | quick | standard | thorough |
|---|---|---|---|
| Failing tests | 0 | 0 | 0 |
| Flaky tests | 0 in runs made | 0 (3 runs) | 0 (3 runs) |
| Focused / empty tests | 0 | 0 | 0 |
| Diff coverage | — | ≥ 80% (critical ≥ 90%) | ≥ 80% (critical ≥ 90%) |
| Mutation score on hardened files | — | — | ≥ 60% |
| UI gates (a11y, interaction) | changed screens | PASS | PASS |
| API contract | — | PASS if spec exists | PASS |
| E2E critical flows | — | — | PASS |

---

## Sources

- Alshahwan et al., *Automated Unit Test Improvement using Large Language Models at Meta* (FSE 2024): https://arxiv.org/abs/2402.09171
- Foster et al., *Mutation-Guided LLM-based Test Generation at Meta* (FSE 2025): https://arxiv.org/abs/2501.12862
- web.dev, *Pyramid or Crab? Find a testing strategy that fits*: https://web.dev/articles/ta-strategies
- Testing Library, *Guiding Principles*: https://testing-library.com/docs/guiding-principles/
- ISTQB glossary, risk level (likelihood × impact): https://softwaretestpilot.com/istqb/glossary/risk-level
- Ivanković et al., *Code coverage at Google* (FSE 2019): https://research.google/pubs/code-coverage-at-google/
- ISO/IEC 25010:2023 product quality model (nine characteristics): https://quality.arc42.org/standards/iso-25010
- Flaky test classifiers and Google rerun data: https://arxiv.org/pdf/2401.15788
