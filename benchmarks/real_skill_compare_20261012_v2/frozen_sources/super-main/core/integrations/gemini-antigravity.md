# Gemini / Antigravity execution adapter

This skill improves task control and evidence handling; it cannot modify model weights, guarantee
reasoning quality or force hidden thought length. Keep instructions direct and load only the
relevant references. Do not prepend the whole encyclopedia to every request.

## Host behavior

Inspect the actual tools and model controls exposed by the host. If a reasoning setting is
available, choose it according to task complexity and budget. Do not invent an Antigravity
setting or assume API `thinkingBudget`/`thinkingLevel` fields are available in its UI. For a
direct API integration, verify supported settings for the exact model and preserve tool-call
state/signatures as required by that API. This skill does not implement an API client.

Use a compact visible task contract, evidence matrix, decision and acceptance result. Do not
request a private thought transcript, fixed thousands of reasoning tokens or a simulated panel
of experts. For difficult work, improve evidence, decomposition and external verification first.
Keep alternative exploration bounded and stop when the acceptance criteria are met.

## Session handoff

Persist original goal, constraints, supported facts, unresolved questions, decisions, artifact
paths, notebook/task IDs and next check. Mark generated summaries as summaries and keep pointers
to originals. Revalidate stale sources instead of treating a past agent conclusion as fact.

## Evaluation boundary

Unit tests establish helper behavior, not Gemini improvement. Evaluate baseline and updated skill
in fresh Antigravity sessions using the same model/settings and held-out tasks. Record artifact
fitness, unsupported claims, citation correctness, defects, time and tool calls. Do not claim
better reasoning on Gemini until those runs have actually occurred. Use
[behavioral evaluation](../../evals/reasoning/protocol.md).

## Basis (checked 2026-10-11)

- [Google prompt guidance](https://ai.google.dev/gemini-api/docs/prompting-strategies): clear task,
  constraints, examples and iterative evaluation.
- [Google thinking documentation](https://ai.google.dev/gemini-api/docs/thinking): model-specific
  thinking controls; verify rather than copying parameters between models/hosts.
- [CoT faithfulness research](https://arxiv.org/abs/2305.04388): persuasive explanations need not
  faithfully identify factors behind a response.
- [Test-time compute research](https://arxiv.org/abs/2408.03314): allocation should depend on the
  problem, not a universal instruction to produce more tokens.
- [Self-correction limitations](https://arxiv.org/abs/2310.01798): use independent feedback/tests.

These sources motivate design choices; they do not demonstrate this skill's empirical efficacy.
