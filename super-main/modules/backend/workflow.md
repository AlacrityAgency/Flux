# Backend Design, Implementation and Review

Shared loop: [application workflow](../../core/workflows/application.md).

## Architecture and contracts

Identify entities, state transitions, ownership and business invariants from user journeys.
Keep domain rules independent of HTTP and persistence where the existing code supports it.
Follow the project's framework and error convention. For new products prefer one maintainable
deployable service before adding service boundaries, queues or elaborate abstractions.

Define requests, responses, validation, status codes, limits, stable pagination and compatibility
in the project's OpenAPI contract. Prefer a single generation source over a handwritten spec
that disagrees with the handlers. Version the contract according to consumers' compatibility needs.
Use a maintained framework test client and libraries for authentication and parsing.

## Implementation

Validate at the boundary; enforce ownership and field-level permissions on the server.
Enforce business invariants in [transactions](../data/workflow.md), not just UI checks.
Bound external calls with timeouts; use retries only where the operation is safe to retry.
For jobs/webhooks/payments verify signatures where applicable, persist deduplication keys,
and test duplicate and concurrent delivery. A key in memory alone is not durable idempotency.
Use an outbox when consistency between committed data and message delivery requires it;
do not add a broker solely to satisfy this workflow. Preserve currency precision and time-zone semantics.
Separate secrets/configuration from code and sanitize client-facing errors.

## Tests and evidence

Reuse [backend testing](../testing/references/backend.md). Configure `backend.behavior` scenarios
for actual persisted effects and business-rule rejection; `backend.idempotency` for duplicate,
concurrent and out-of-order events when jobs/payments are present. `testing.api` checks the
schema separately and does not prove authorization or business correctness.
Connect the UI to these endpoints and verify reload persistence with `ui-ux.journey`.
Run the full review after final edits. Use [project configuration](../../core/project-config.md)
for project-specific commands; no configured runner means NOT-TESTED.

## Sources

Use the installed framework's version-specific official docs, the project's code and
[OpenAPI](https://spec.openapis.org/oas/) for API semantics. For vendor idempotency, consult
the actual provider's contract, such as [Stripe](https://docs.stripe.com/api/idempotent_requests).
Record URL, version/date, retrieved section and the decision it supports; research is not test evidence.
