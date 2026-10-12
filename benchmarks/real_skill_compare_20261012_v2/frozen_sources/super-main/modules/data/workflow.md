# Data Integrity and Lifecycle

Own schema, migrations, transactional correctness, retention and recovery.
Coordinate permissions with [security](../security/workflow.md), endpoints with
[backend](../backend/workflow.md) and restoration infrastructure with [delivery](../delivery/workflow.md).

## Design and implementation

Model ownership, uniqueness, foreign keys, nullability and valid state transitions explicitly.
Enforce invariants at the database where possible. Choose isolation and conflict handling from
the actual concurrent flow; test races rather than assuming a transaction prevents every race.
Bound connection pools, query size and pagination. Measure slow queries and N+1 behaviour before
adding indexes or caches. Cache invalidation must preserve access control and tenant separation.

Classify personal/sensitive data, minimize collection, define retention and deletion, and keep it
out of logs and research prompts. Choose encryption/key management appropriate to the deployment.
Map market-specific requirements to product decisions; a passing gate is not a legal certification.

Use the project's migration tool. Test empty-database setup and migration of representative old
data. For incompatible schema changes use expand/migrate/contract or document an outage plan.
Do not assume reversing a migration recovers deleted data.

## Real-database checks

Configure `data.integration` with constraint, rollback, migration and concurrency scenarios
against the production engine in a disposable database. Use Testcontainers if supported by the
project/runtime; SQLite is suitable only when it is the application's actual engine or dialect
differences cannot matter. Mocks do not establish SQL correctness.

Configure `data.restore`: create representative data, back it up, restore into a separate disposable
database and assert recovered rows/relationships. Measure recovery time and lost-data window against
project RTO/RPO; file existence alone is not restoration evidence. Operations owns alerting and the
recovery runbook; this module owns correctness of recovered data.

## Sources

Prefer official engine docs matching the installed version, including
[transaction isolation](https://www.postgresql.org/docs/current/transaction-iso.html) and
[backup/restore](https://www.postgresql.org/docs/current/backup.html) for PostgreSQL, and
[Testcontainers](https://testcontainers.com/) for disposable integration dependencies.
