# SUPER · Application Engineering & Verification Agent Skill

[![Version](https://img.shields.io/badge/version-5.2.0--dev-blue.svg)](package.json)
[![License](https://img.shields.io/badge/license-Proprietary-red.svg)](package.json)
[![Engine](https://img.shields.io/badge/engine-Antigravity%20%7C%20Gemini-purple.svg)](SKILL.md)
[![Status](https://img.shields.io/badge/evidence--gates-passing-brightgreen.svg)](core/protocol.md)

**SUPER** is an enterprise-grade Application Engineering Agent skill designed for high-assurance software engineering, architectural research, and rigorous evidence-driven verification. 

Unlike conventional code generation tools that stop at syntactic completion or passing tests, SUPER couples **fitness-for-purpose reasoning** with an **immutable evidence ledger**, executing deterministic verification gates across 10 specialized software engineering disciplines before approving release readiness.

---

## 🏛️ Core Philosophy: Evidence-Ledger Engineering

1. **Fitness for Purpose over Pure Aesthetics:** Passing runtime gates does not prove that the right product was built. SUPER establishes a strict task contract (audience, decision, constraints, medium) before selecting visual tokens, component frameworks, or backend stacks.
2. **Immutable Verification Ledger:** Every gate evaluation produces an audited, content-addressed run record in `.superagent/runs/`. A rendered screen is not an application; an assertion with missing coverage remains an unaccepted gap.
3. **Claims Traceability (`claims.trace`):** Technical claims in external artifacts (PDFs, Markdown case studies, OpenAPI contracts, architectural dossiers) are automatically extracted and verified against AST symbols, measured runtime telemetry, and validated error margins. Vague qualitative assertions (*"accurate"*, *"bulletproof"*) without empirical numerics are blocked.
4. **Zero-Drift Design Systems:** Native support for W3C Design Tokens Community Group (DTCG) standards, perceptual OKLCH color spaces, 100% CSS logical properties, and automated WCAG 2.2 AA/AAA accessibility checks.

---

## 🧭 Request Routing Matrix

SUPER deterministically routes incoming developer tasks into specialized workflows:

| Mode | Trigger Condition | Workflow & Gates |
| :--- | :--- | :--- |
| **`design`** | Specifications, UI/UX strategy, design system, API design | `modules/ui-ux/workflows/design.md`, W3C tokens, typography contracts |
| **`build`** | Green-field applications, microservices, or portal gateways | Contract & Data Schema $\to$ Backend Access $\to$ Connected UI $\to$ Test Suite $\to$ Ledger Verdict |
| **`change`** | Feature additions, migrations, or surgical bug fixes | Preserves local architectural conventions; diff-scoped coverage gates |
| **`audit`** | Deep review of existing codebase, live URL, or technical document | `sa.py review` for code; `claims.trace` + purpose/medium review for documents |
| **`test`** | Hardening test suites, mutation testing, API contracts | Meta TestGen-LLM filters (F1–F4), StrykerJS/mutmut mutation scoring |
| **`debug`** | Non-trivial regressions, flaky tests, memory/latency leaks | Hypothesis discovery $\to$ Negative reproduction $\to$ Oracle-verified fix |
| **`release-check`** | Production release gate validation | Strict `release_ready: true` requirement; any gap blocks deployment |

---

## 📦 The 10 Specialized Modules & Verification Gates

Each module owns specific domain guidelines and command-line verification gates prefixed by the module name:

```
super/
├── core/                  # Task framing, orchestration loop, protocol & CLI runner
│   ├── bin/sa.py          # Unified CLI entrypoint
│   ├── lib/               # Ledger, discovery, doctext, project, and review engines
│   └── workflows/         # Core application and research execution loops
├── modules/
│   ├── product/           # User flows, copy assertions, coverage & SEO contracts
│   ├── ui-ux/             # Tokens, axe-core WCAG 2.2, keyboard walk & token drift
│   ├── backend/           # API domain behavior, idempotency & duplicate delivery
│   ├── data/              # Real-database constraints, transactions & restoration
│   ├── security/          # Tenant authorization, Semgrep SAST, Trivy vulnerability scan
│   ├── testing/           # Test inventory, risk ranking, coverage, smells & mutation
│   ├── operations/        # Dependency failure resilience & k6 load thresholds
│   ├── delivery/          # Artifact build validation & rollback smoke scenarios
│   ├── claims/            # Document vs. code traceability & performance validation
│   └── debug/             # Scientific hypothesis testing & ledger experiment logs
```

### Module Gate Breakdown

| Module | Gate ID | Verification Description |
| :--- | :--- | :--- |
| **Claims** | `claims.trace` | Scans PDFs/Docs/Markdown/HTML; traces claimed metrics and file references to AST symbols and validated error rates. |
| **UI/UX** | `ui-ux.tokens` | Validates `tokens.json` against DTCG specs and declared contrast pairs. |
| | `ui-ux.a11y` | Headless Playwright + `axe-core` auditing WCAG 2.2 AA/AAA on desktop and mobile viewports. |
| | `ui-ux.interaction` | Complete keyboard navigation walk (2.4.7 visible focus, 2.1.2 traps) and minimum 24px/44px touch target sizes. |
| | `ui-ux.token-drift` | Detects arbitrary raw palette classes and hardcoded hex colors that bypass design tokens. |
| | `ui-ux.page-coverage`| Bounded scrolling with multi-segment screenshot evidence across all active viewport breakpoints. |
| **Testing** | `testing.inventory` | Maps repository test shape (Pyramid, Trophy, Honeycomb) across backend and frontend layers. |
| | `testing.risk` | Calculates risk scores: $\text{Risk} = \text{Churn} \times \text{Complexity} \times \text{Criticality} \times (1 - \text{Coverage})$. |
| | `testing.run` | Executes tests across $N$ iterations to isolate and fail on flaky tests. |
| | `testing.coverage` | Diff-coverage enforcing $\ge 80\%$ on modified lines without coverage degradation. |
| | `testing.accept` | Four-stage assurance filters (F1: Build, F2: 5/5 Stability, F3: Added Coverage, F4: Zero Smells). |
| | `testing.smells` | Identifies anti-patterns: sleepy tests, empty test bodies, assertion-free cases, and skipped suites. |
| | `testing.mutation` | High-risk mutation analysis via StrykerJS or Mutmut; surviving mutants become test targets. |
| | `testing.api` | Property-based OpenAPI contract fuzzing via Schemathesis. |
| **Security** | `security.authorization`| Negative access-control assertions, IDOR checks, and tenant-isolation boundaries. |
| | `security.sast` | Semgrep static analysis with project-scoped policy rules. |
| | `security.dependencies`| Trivy vulnerability, secret, and configuration scanner. |
| **Backend & Data** | `backend.behavior` | Business-rule assertions and deterministic domain response contracts. |
| | `backend.idempotency`| Concurrency, replay, and duplicate delivery stress tests. |
| | `data.integration` | Database transactional constraints and migration rollback integrity. |
| | `data.restore` | Disposable database restoration and record verification test. |
| **Delivery & Ops** | `operations.resilience` | Simulates third-party outages, network partitions, and verifies graceful degradation. |
| | `delivery.build` | Validates production bundle artifacts and startup checks beyond exit-code 0. |

---

## ⚡ CLI Quickstart (`sa.py`)

All verification functions are accessible via the single-source `sa.py` CLI runner:

### 1. Environment & Diagnostic Health Check
```bash
python3 core/bin/sa.py doctor
```

### 2. Project Mapping & Feature Discovery
```bash
python3 core/bin/sa.py project-map --write --json
```

### 3. Auditing Technical Documents against Code
```bash
python3 core/bin/sa.py gate claims.trace --doc RESUME.md --doc index.html --json
```

### 4. Running a Comprehensive Architecture Review
```bash
# Standard review across UI, API, and unit tests
python3 core/bin/sa.py review --mode audit --profile web-app --depth standard --url http://localhost:3000

# Strict release verification (any gap blocks release)
python3 core/bin/sa.py review --mode release-check --profile saas --depth thorough --url http://localhost:3000
```

### 5. Running Specific Gates
```bash
# Check design token adherence and color drift
python3 core/bin/sa.py gate ui-ux.token-drift --json

# Run accessibility audit on live local application
python3 core/bin/sa.py gate ui-ux.a11y --url http://localhost:8091/index.html --level AA
```

### 6. Scientific Debugging Loop
```bash
# Phase 1: Discover anomaly and formulate hypothesis
python3 core/bin/sa.py debug --phase discover --json

# Phase 2: Create isolated negative reproduction case
python3 core/bin/sa.py debug --phase reproduce --case <case_id> --json

# Phase 3: Verify fix against original oracle test
python3 core/bin/sa.py debug --phase verify-fix --case <case_id> --json
```

---

## 🧪 Automated Testing & CI

SUPER contains an extensive self-testing suite verifying gate execution, AST claim parsers, DTCG validators, and ledger integrity:

```bash
# Run complete Python test suite
npm run test:python

# Run headless browser gates (Playwright + axe-core)
npm run test:browser

# Run full CI test pipeline
npm test
```

---

## 🛠️ Requirements & Toolchain

- **Runtime:** Python $\ge 3.8$, Node.js $\ge 18$
- **Databases:** SQLite with `fts5` extension
- **Browser Automation:** Playwright Chromium (`npx playwright install chromium`)
- **Optional Specialist Engines:**
  - `stryker` (JavaScript/TypeScript mutation testing)
  - `mutmut` (Python mutation testing)
  - `schemathesis` (Property-based API contract testing)
  - `semgrep` (SAST security analysis)
  - `trivy` (Dependency & secret scanner)
  - `k6` (Load testing)

---

## 🔒 License & Confidentiality

Copyright © 2026 **Alacrity Agency**. All rights reserved.  
This software is proprietary and confidential. Unauthorized copying, reverse-engineering, distribution, or public transmission is strictly prohibited.
