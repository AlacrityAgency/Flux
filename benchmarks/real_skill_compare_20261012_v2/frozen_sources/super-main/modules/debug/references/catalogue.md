# Failure Catalogue

Select from the actual data flow and requirements; this is not a mandatory scan of every project.

| Area | Probe | Independent oracle |
|---|---|---|
| False green | No tests, all skipped, filtered target, command failure + green report | Named assertions executed; process/status agree; failure blocks verdict |
| Evidence integrity | Missing/edited artifact, report from old source, overwritten scoped result | Content digest, source fingerprint, current review id |
| Target identity | Query/fragment routes; duplicate file basenames; single-page repeated runs | Full canonical target identity remains distinct |
| Invalid input | Wrong type, null/empty, NaN/Infinity, boundaries, unknown keys | Explicit schema/contract rejects invalid input without side effects |
| Dependency adapters | Supported version's actual output, stale file, progress vs final answer | Installed source and primary version-matched contract + local fixture |
| Timeout/lifecycle | Spawn child, hang, missing executable, interrupted report | Bounded failure, no false PASS, no remaining children/temp data |
| Auth and tenancy | Owner/non-owner/admin, cross-tenant ids, denied writes | Deny + persisted state unchanged; positive access still works |
| Transactions/retries | Duplicate requests, races, partial write, crash between steps | One durable effect; rollback; idempotency with real storage |
| Recovery | Dependency outage, retry exhaustion, cache staleness, backup restore | Observable failure/recovery and preserved data, not just HTTP 200 |
| UI | Keyboard path, overflow/RTL, touch target size, async errors | DOM/pixels + user journey assertions, applicable WCAG level |

Security probes are local or dedicated-test-only and within user authorization. Preserve a healthy
control for each negative probe. A surprising outcome without a clear requirement is a question,
not automatically a bug. Process isolation is not protection against malicious test code.
