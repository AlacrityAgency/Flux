# Task framing and decision discipline

Use before substantial work; revisit when new evidence changes the goal or assumptions.
This is a reviewable decision process, not a request for hidden chain-of-thought or verbose deliberation.

## Task contract

Record only what changes the work:

| Field | Required distinction |
|---|---|
| Outcome | What should the recipient understand, decide or accomplish? |
| Audience | Who evaluates/uses this, in what context, with what domain expectations? |
| Deliverable | Resume, portfolio, specification, prototype, production feature, report, etc. |
| Medium | Screen, mobile, print/PDF, ATS ingestion, API or operational environment |
| Facts | User-provided / locally observed / externally supported; keep these labels distinct |
| Constraints | Scope, language, budget, existing stack, operational limits and explicit choices |
| Unknowns | What could materially change the choice? Which can research answer? |
| Acceptance | Observable criteria for meaning/content and for implementation/export |

Do not infer a domain from a filename or fashionable technology when the request states another.
Missing employer dates are personal facts to recover from the user or supplied records, not web
research questions. Missing library behavior may be researched. Missing preference can often be
handled with a stated reversible default. Continue independent work when a fact remains missing.

## Select a method for the actual uncertainty

- Missing evidence: targeted retrieval and original-source reading.
- Ambiguous goal: inspect request/context; clarify only the consequential ambiguity.
- Several defensible designs: compare a small set of genuinely different options against the contract.
- Arithmetic or executable behavior: calculator, code, test or other external verifier.
- Coupled tasks: decompose by dependencies; preserve the original acceptance criteria across steps.
- Contradiction: identify competing explanations and the observation that distinguishes them.
- Straightforward reversible edit: act and perform the relevant check; no compulsory research ceremony.

For consequential decisions, keep a compact record: options, supporting evidence, strongest
counterevidence, choice, tradeoff, and what would reverse it. Do not manufacture several options
when the contract already determines the answer. More agents, longer CoT and more searches are
not automatic quality improvements. Use the [reasoning](reasoning.md) retry budget.

## Purpose-fit review before implementation

Review the proposed outline/flow/architecture as the actual recipient:

1. Does this artifact serve the requested decision, or merely exhibit what the model can build?
2. Is the most relevant evidence given the most space and prominence?
3. Which factual claim is unsupported, overstated or contradicted by the supplied material?
4. Are conventions being used as contextual guidance or mistakenly treated as universal law?
5. What would cause rejection even if all code runs and all pixels look polished?

Correct the outline and claims before investing in decoration. A CTO-facing resume may need
leadership scope and organizational outcomes; a creative portfolio may appropriately foreground
interactive work. Preserve the requested role and report evidence gaps instead of silently
changing the person's title or inventing executive experience.

## Challenge criticism as well as the draft

A user-provided critique is evidence of concerns, not proof of every assertion. Separate valid
observations, reasonable hypotheses and unsupported generalizations. For example, SQLite or a
monolith alone proves neither low usage nor national-scale reliability. Examine write concurrency,
deployment topology, operational records and measured workload. Do not add distributed services
just to make a claim sound senior. Likewise, font choice cannot demonstrate management ability.

## Final acceptance: two axes

**Fit:** audience, goal, artifact type, content hierarchy, factual support and intended medium.
**Execution:** behavior, correctness, readability, export, links, runtime and relevant tests.

Inspect the delivered artifact, not only its source or preview. Mark each material criterion
observed / failed / not checked with its evidence. A qualitative fit review is not a ledger PASS;
automated technical PASS is not a fit judgment. Resolve material failures within scope, or deliver
an accurately labelled partial result and the precise missing fact/check.
