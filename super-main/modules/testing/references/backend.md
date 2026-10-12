# Backend Testing Guide

How to apply steps T4–T7 of the [workflow](../workflow.md) to APIs, services and data code.

---

## 1. What to test at which level

| Code | Level | Notes |
|---|---|---|
| Domain logic (pricing, permissions, validation, state machines) | Unit | Pure functions/classes; table-driven cases from equivalence partitions and boundaries |
| Repositories / queries / migrations | Integration with a real database | Use the same engine as production (containerised Postgres/MySQL, e.g. Testcontainers) or an embedded one only when SQL dialect differences cannot matter. Roll back or truncate between tests |
| HTTP handlers / controllers | Integration via the framework's test client | FastAPI/Starlette `TestClient`, Django test client, Flask `test_client`, supertest for Express/Fastify, `httptest` for Go |
| Public API contract | Contract | `testing.api` (Schemathesis) from the OpenAPI spec: no 5xx, responses match the schema, documented status codes. Use consumer-driven contracts (e.g. Pact) when several independent clients depend on the API |
| Background jobs, queues, webhooks | Integration | Run the handler against a real/in-memory broker; assert on side effects and idempotency (deliver the same message twice) |
| Cross-service flows | Few E2E | Only critical journeys; everything else belongs in contract and integration tests |

## 2. Cases every API endpoint needs

1. **Happy path** with representative data; assert status, body shape and persisted state.
2. **Validation**: missing fields, wrong types, boundaries (0, negative, max length, empty string, unicode/RTL text), unknown fields.
3. **AuthN/AuthZ**: unauthenticated → 401; authenticated but not allowed → 403; access to another user's resource → 404/403 (no data leak).
4. **Not found / conflict**: unknown id → 404; duplicate create → 409 (or documented behaviour).
5. **Idempotency and concurrency** for writes that may be retried (payments, orders): same request twice must not double-charge.
6. **Error mapping**: dependency failure (DB down, upstream timeout) returns a controlled 5xx/503 with no stack trace or secrets in the body.
7. **Pagination and filtering** limits: page size caps, stable ordering.

## 3. Test data and isolation

- Build data with factories/builders inside the test; avoid shared mutable fixtures across tests.
- Each test owns its data and cleans up (transaction rollback, truncation, unique ids).
- Freeze time (`freezegun`, fake timers, injected clock) for anything date-based.
- Never call real third-party services (payment, email, SMS) in automated tests: stub at the HTTP boundary.

## 4. Running the API gates

```bash
# start the backend locally with the project's command, then
python3 <skill>/core/bin/sa.py gate testing.api -- --url http://localhost:8000 --spec openapi.yaml
```
`testing.api` refuses non-local URLs unless `--allow-remote` is given: generated requests can create or delete data. Point it only at local or dedicated test environments with disposable data.
The adapter recognizes Schemathesis 3.x/4.x and requires a fresh JUnit report with executed,
non-skipped operations, not merely a zero process exit. Verify the installed CLI's report options
against its [official reference](https://schemathesis.readthedocs.io/en/stable/reference/cli/).

## 5. Application-wide checks

Use the [backend](../../backend/workflow.md), [data](../../data/workflow.md), [security](../../security/workflow.md), [operations](../../operations/workflow.md) and [delivery](../../delivery/workflow.md) modules. Project-specific commands and named scenarios are configured through [superagent.json](../../../core/project-config.md); scanners have direct Semgrep/Trivy adapters. Missing tools or environments remain NOT-TESTED. No gate proves every possible vulnerability or operational failure is absent.
