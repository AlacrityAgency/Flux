# Application Workflow

Use this workflow for full applications and existing projects. The CLI plans and verifies;
the agent writes the project's actual code following its existing conventions.

## Select the mode

| Mode | Work | Finish |
|---|---|---|
| design | Define journeys, entities, API contracts, architecture decisions and acceptance criteria | Deliver specifications; list validation still needed |
| build | Implement a new application in vertical slices | Run it locally and verify browser-to-database journeys |
| change | Modify only the requested feature in the existing application | Regression tests and affected runtime gates |
| audit | Inspect code, run applicable gates and reproduce findings | Report verified defects and untested scope; no unsolicited fixes |
| test | Add or execute tests requested by the user | Report tests and findings; edit product code only when authorized |
| release-check | Verify a dedicated release environment | All required gates must pass; gaps block release readiness |

## Intake and acceptance

Complete [task framing](../task-framing.md) before stack/layout decisions. Confirm this is an
application task; a document-only deliverable uses professional artifact review instead of
fabricated browser/API journeys. For material unknowns use [decision research](research.md).

1. Inspect the project, stack, scripts and existing tests. Preserve framework, package manager,
   deployment provider and database unless the request requires a change. Start a modular
   monolith for a new ordinary product; distributed services require a concrete operational need.
   Run `sa.py project-map --json`, verify entrypoints, then follow [product coverage](../../modules/product/workflow.md).
   Include research, UX and content before implementation; narrow changes revisit affected areas only.
2. Record profile, features, environment and acceptance criteria in project-owned
   `superagent.json` following [project configuration](../project-config.md).
   Profiles: site, web-app, saas, commerce, service. Feature inference is a starting point;
   inspect account roles, sensitive data, payments and tenancy even on quick changes.
   Full build/release requires all `product.areas` classified with reasons and acceptance mappings.
3. Define each criterion as observable behaviour, a gate and a named scenario. For example:
   task creation persists after reload; user B cannot read user A's task; a retried webhook
   produces one side effect. Include failure and recovery paths, not only happy paths.
4. Use `sa.py plan --mode <mode> --profile <profile>` for the applicable verification plan.
   Missing scenario runners and tools are visible prerequisites, not reasons to drop requirements.

## Build a vertical slice

For each journey: [backend](../../modules/backend/workflow.md) and
[data](../../modules/data/workflow.md) contract -> access rules with
[security](../../modules/security/workflow.md) -> backend implementation ->
[UI implementation](../../modules/ui-ux/workflows/implement.md) connected to the API ->
[tests](../../modules/testing/workflow.md) -> runtime verification.

Deliver complete applicable UI states: loading, empty, validation error, upstream failure,
disabled and success. Test representative long/localized text, desktop/mobile and keyboard.
Use the project's components and tokens; make visual choices appropriate to its users and domain.
Inspect screenshots for layout, assets and content; automated accessibility alone does not judge design.
Use `ui-ux.page-coverage` for bounded document/internal scrolling and lazy-content segment capture.
Inspect the segments. Named journeys still cover menus, modals, forms and role-specific states.

Use the production database engine for integration tests. Mock only external service boundaries
where practical. Label demos and mock data; never silently substitute them for working integration.
Start the local app using its scripts and return its URL. For static HTML return the local file.

## Verification and delivery

For an unexplained failure, suspicious green result or requested bug investigation, use the
[debug workflow](../../modules/debug/workflow.md) and `sa.py debug` phases. A reproduced bug
does not authorize unrelated fixes; successful fix verification still needs affected regression gates.

Run `sa.py review --mode <mode> --profile <profile> --url <page> --api-url <api>` on final code;
repeat --url for critical screens. The [operations](../../modules/operations/workflow.md) and
[delivery](../../modules/delivery/workflow.md) modules own production-readiness scenarios.
Independently review the original criteria, diff, assertions and generated review packet.
Review whether the implemented flow/content serves the intended audience and decision; inspect
the actual output medium. Record purpose-fit separately from the computed technical verdict.
Never weaken tests, skip permissions or update a screenshot baseline solely to make results green.
Report the computed verdict, covered journeys, missing checks, start command and remaining findings.
Deployment or destructive remote testing stays within the user's actual authorization.
