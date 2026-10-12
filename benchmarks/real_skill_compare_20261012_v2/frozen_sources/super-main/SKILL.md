---
name: super
description: Research, design, build, debug and verify applications, websites and their professional content against audience, purpose and evidence. Use for product features, software/document audits, decision research and fix verification; establish meaning and acceptance before implementation.
---

# Application Engineering Agent

`<skill>` is this directory. Run commands from the user's project or pass `--project <dir>`.
Keep the user's scope, existing framework and architecture. Load only relevant module workflows.

## 0. Establish what success means

Before substantial design, research or implementation, read [task framing](core/task-framing.md).
Capture the audience, decision/action, deliverable/medium, constraints, known facts and material
unknowns in a compact task contract. For a small fix, one sentence is enough. For a complex task,
save the contract in `.superagent/brief.md`. Do this before choosing components, visual style or stack.
Judge both **fitness for purpose** and **implementation correctness**; passing runtime gates
does not establish that the right artifact was built. Fix a purpose mismatch before visual polish.

For Gemini/Antigravity, use [the host adapter](core/integrations/gemini-antigravity.md).
For research that can change a decision, use [the research workflow](core/workflows/research.md)
and [NotebookLM](core/integrations/notebooklm.md) when available. NotebookLM synthesizes sources;
the agent verifies decisive claims against originals and the user's actual context.
For resumes, portfolios, proposals or other professional artifacts, load
[professional content](modules/product/references/professional-artifacts.md). Do not route a
document-only request through application build gates or invent a CLI document mode.

## 1. Route the request

| Mode | When | Workflow |
|---|---|---|
| design | Specifications, UI/UX strategy, architecture or API design | [Application](core/workflows/application.md); [UI design](modules/ui-ux/workflows/design.md) when applicable |
| build | New working application or website | [Application](core/workflows/application.md), then applicable modules |
| change | Feature/fix in an existing app | [Application](core/workflows/application.md); preserve local conventions |
| audit | Review an existing app, code or document | App/code: `sa.py review`; documents: claims and purpose/medium review |
| test | Write/run tests for an existing app | [Testing](modules/testing/workflow.md), plus relevant specialist workflows |
| debug | Investigate a bug or suspicious test/report; verify a fix | [Debug](modules/debug/workflow.md); discover -> reproduce -> verify-fix |
| release-check | Verify production readiness in a dedicated environment | [Delivery](modules/delivery/workflow.md); required gaps block readiness |

The agent implements the code. The CLI selects verification and executes gates; it does not
generate applications itself. Full-stack work follows contract/data -> backend/access -> connected
UI -> tests -> runtime checks -> final verdict. Finish each critical journey before broadening scope.

Two primary tracks share one evidence engine: **create/change a product** and **inspect/debug
an existing product**. Load [product coverage](modules/product/workflow.md) for whole-product
requests; a narrow fix loads affected areas and dependencies only. Research, UX, UI, copy,
frontend, backend, data, security, integrations, accessibility, performance, delivery and
SEO/analytics each need an applicability decision. A rendered screen is not a completed app.

## 2. Modules and ownership

| Module | Workflow | Gates |
|---|---|---|
| product | [Research, UX, copy and product coverage](modules/product/workflow.md) | coverage, research, content, ux, integrations, seo |
| ui-ux | [design](modules/ui-ux/workflows/design.md), [implement](modules/ui-ux/workflows/implement.md), [review](modules/ui-ux/workflows/review.md) | page-coverage, a11y, interaction, token-drift, tokens, journey |
| backend | [API/domain/integrations](modules/backend/workflow.md) | behavior, idempotency |
| data | [Schema/migrations/recovery](modules/data/workflow.md) | integration, restore |
| security | [Threats/access/scanning](modules/security/workflow.md) | authorization, sast, dependencies, dast |
| testing | [Test strategy and execution](modules/testing/workflow.md) | inventory, risk, run, coverage, smells, accept, mutation, api |
| operations | [Reliability and performance](modules/operations/workflow.md) | resilience, load |
| delivery | [Build and deployment](modules/delivery/workflow.md) | build, rollback |
| claims | [Documents vs. implementation](modules/claims/workflow.md) | trace |
| debug | [Hypotheses and negative experiments](modules/debug/workflow.md) | `sa.py debug` phases; experiment records in the shared ledger |

Gate ids use the module prefix, e.g. `security.authorization`. Security is checked during API,
data and delivery work, not only at the end. Do not equate scanner success with overall security.

## 3. Plan, implement and verify

1. Identify project profile/features and original acceptance criteria. Configure project-owned
   scenario runners using [superagent.json](core/project-config.md). Profiles: site, web-app,
   saas, commerce, service. Sensitive feature checks remain required even at quick depth.
   Inspect `sa.py project-map --json`; verify entrypoints/build/imports before declaring source
   roots. Map package suites explicitly when automatic discovery is ambiguous.
2. Follow [core/reasoning.md](core/reasoning.md): Frame -> Research when needed -> Decide -> Act -> Verify fit and behavior -> Deliver.
   Record decisions at significant steps. Use the project's own tools and maintained libraries.
3. Build/change: implement actual frontend/backend integration and complete applicable states;
   start the local app and verify it. Test/audit: stay within the requested code-edit scope.
4. Review final code through the CLI; inspect screenshots and independently review requirements,
   assertions and the generated packet. Do not weaken tests or baselines to force a pass.
5. Deliver the computed technical verdict alongside the purpose-fit review, verified journeys, gaps,
   findings and local URL/start command. Neither verdict substitutes for the other.
   In release mode require `release_ready: true`; a label with gaps never authorizes publication.

```bash
python3 <skill>/core/bin/sa.py doctor
python3 <skill>/core/bin/sa.py modules
python3 <skill>/core/bin/sa.py project-map --write --json
python3 <skill>/core/bin/sa.py search "identifier" --corpus project --role active --role unknown --json
python3 <skill>/core/bin/sa.py plan --mode build --profile web-app --json
python3 <skill>/core/bin/sa.py review --mode change --profile web-app --url http://localhost:3000 --api-url http://localhost:8000
python3 <skill>/core/bin/sa.py review --mode release-check --profile saas --depth thorough --url http://localhost:3000 --api-url http://localhost:8000 --json
python3 <skill>/core/bin/sa.py gate security.authorization --json
python3 <skill>/core/bin/sa.py worklist
python3 <skill>/core/bin/sa.py debug --phase discover --json
python3 <skill>/core/bin/sa.py debug --phase reproduce --case <id> --json
python3 <skill>/core/bin/sa.py debug --phase verify-fix --case <id> --json
```

`review` starts every application audit; missing checks remain visible. Gate exit codes:
0 PASS, 1 FAIL, 2 NOT-TESTED, 3 ERROR. Review adds gaps/stale/no-evidence handling; release gaps
exit nonzero. Follow [core/protocol.md](core/protocol.md), including findings and retry budgeting.
Use --help for individual gate arguments. Optional tools are not installed automatically.

## 4. Knowledge and artifacts

Search references: `sa.py search "<query>" --module backend` (English or Persian); verify versions before use.
Follow [retrieval and research rules](core/reasoning.md). Research citations support decisions;
only observed gate executions support test verdicts. Keep credentials and personal data out of
research, command arguments and logs. Settings: depth quick/standard/thorough, UI creative_posture
utilitarian/expressive/avant_garde, WCAG AA/AAA, interface language (fa/ar/he imply RTL).
Store runtime artifacts under `<project>/.superagent/` and ignore it in the project's .gitignore.
Maintain `superagent.json` as versioned project input, not generated test output.
Whole-page checks require scrolling evidence for each target plus inspection of recorded
segments. `page-coverage` does not open hidden states or establish visual correctness; use
named journeys for those states. Never generalize one page, viewport, role or suite to the product.
Review timings are written to `.superagent/review/timing.json`; measure before adding tools.
