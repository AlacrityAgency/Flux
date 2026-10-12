# Application Evaluation

Run `npm run test:application`. The HTTP/SQLite fixture is evaluation-only, not a production
authentication implementation or frontend template. Each run creates an isolated database and
local HTTP server. The same assertions test the healthy service and injected ownership, replay
and persistence defects, requiring PASS for healthy and FAIL with the expected finding for each defect.

The suite separately checks missing/skipped scenarios, zero assertions, stale report replay,
nonzero process exit, production refusal, content changes with preserved timestamps, gate-time
source changes, profile planning, scanner schemas and k6 threshold/activity normalization.
External scanners and NotebookLM service calls are not executed by these deterministic fixtures.

For product evaluation add acceptance-specific frontend/API/data tests against the real stack.
Measure detection of independently seeded defects, false-positive rate, runtime and retrieval
accuracy on held-out cases before changing thresholds. Never train expectations merely to accept
the agent's current output. A fixture score does not demonstrate production or another model's equivalence.
