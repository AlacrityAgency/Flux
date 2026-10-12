# Product-Agent Evaluation

Runtime regression tests are `npm run test:product` and `npm run test:page-coverage`.
They test adapters and evidence contracts, not Gemini's decision quality. Run `npm test` for
the shared backend/security/debug/browser regressions. Do not report these as model benchmarks.

## Independent Evaluation

Reserve unseen healthy and defective applications before tuning. Include root/child suites,
old mockups, rejection-test URLs, upstream validation/filtering, footer/lazy/nested-scroll defects,
role authorization, failed API effects, content claims and missing recovery flows. Do not pass
expected findings, this conversation or prior audit conclusions into the evaluated context.
Manual reviewers establish the answer key independently, including ambiguity and permitted scope.

For each model/settings/skill revision record provider, exact model id exposed by the host,
reasoning setting, tool/runtime versions, source fingerprint, environment and task. Optional
`superagent.json` agent fields (`provider`, `model`, `reasoning`) are declarations, not evidence
that the host actually honored settings. Capture provider telemetry where available; otherwise
leave model-token/reasoning duration unavailable. CLI timing is separately measured.

Compare baseline and candidate on the same tasks with repeated runs. Report sample size,
confirmed bugs/seeded bugs, false positives on healthy cases, correctly rejected hypotheses,
reproduction rate, requirement/journey coverage, citation correctness, gaps, wall time and tool calls.
Retrieval evals measure required source recall plus wrong-version/reference contamination.
Choose acceptance thresholds after baseline measurement and freeze them before final holdout runs.
Keep the existing implementation when speed improves by dropping required coverage or accuracy regresses.
Publish failures and limitations; never infer equivalence to another model from passing fixtures.

No automatic external model calls, paid-service usage, data export or private-code uploads occur
in these tests. A live Gemini/Antigravity comparison requires the user's configured host and a
fresh-context run; the CLI does not create or control that model session.
