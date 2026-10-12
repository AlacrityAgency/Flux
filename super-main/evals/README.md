# Evaluations

Two kinds of evaluation keep the skill honest. Neither grades text the agent wrote about itself.

## 1. Automated (run in CI)

| Suite | What it measures | Where |
|---|---|---|
| Gate detection | Each gate finds the seeded defects in its fixtures and stays green on clean fixtures (recall on seeded defects, no false FAIL on clean input) | `tests/test_testing_gates.py`, `tests/test_ui_gates.py`, `tests/test_a11y_gate.py`, fixtures in `tests/fixtures/` |
| Evidence ledger | STALE after code changes, NO-EVIDENCE for missing gates, attempt budget (ok → pivot-required → REJECTED) | `tests/test_testing_gates.py::LedgerVerdictTests` |
| Reference search | Expected document in the top 3 for English and Persian queries (target ≥ 90% overall, ≥ 85% per language) | `evals/rag/queries.json`, `tests/test_rag.py` |
| Docs consistency | Links resolve, manifests point to runnable gates, examples validate | `tests/test_docs.py` |

Add a fixture with a known defect whenever a gate misses one in real use, and a query to `evals/rag/queries.json` whenever a search misses.

## 2. Agent tasks (run manually against an agent)

| Task | Module |
|---|---|
| [ui-ux/opg-viewer.md](ui-ux/opg-viewer.md) | ui-ux |
| [testing/payment-service.md](testing/payment-service.md) | testing |
| [Purpose-fit and research](reasoning/protocol.md) | reasoning/product/research |

Grade agent tasks with `sa.py verdict --format json` on the agent's final project state and the checks listed in each task.
