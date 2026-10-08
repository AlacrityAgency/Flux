# Flux reasoning v6.1 — isolated experiment

`engine.py` implements prompt construction, public constraint-graph diagnostics,
checker structure checks, numeric interpretation and bounded worker execution.
`benchmark.py` implements the actual conditional controller and receipt ledger.
No production Flux files or frozen v6 files are modified.

From the Flux workspace root, with Python 3.12, pytest, numpy, tiktoken and an
authenticated account-backed Codex CLI:

```powershell
python -X utf8 -m pytest experiments/request_reasoning_v6_1_20261002/test_engine.py -q
python -X utf8 experiments/request_reasoning_v6_1_20261002/benchmark.py live
python -X utf8 experiments/request_reasoning_v6_1_20261002/benchmark.py analyze
python -X utf8 experiments/request_reasoning_v6_1_20261002/build_report.py
```

`live` resumes missing tasks, reuses existing immutable receipts, validates frozen
hashes, and never interprets reference answer values. `evaluation_only/gold.json`
is read as text solely to hash it for provenance; its JSON answer values are
parsed only by `analyze`.
The current run has one sample per task, no automatic retries, four concurrent
provider calls and a ceiling of 144 physical calls. Account usage is consumed;
no dollar-billed API client or API key is used. Billing amounts are unknown.

For a new experiment use a new directory and a new preregistered holdout. Do not
overwrite this frozen plan or tune the engine against these 24 test answers.
`make_tasks.py` is evaluation-side setup, not inference-side logic.

Outputs: `frozen-plan.json`, `model_runs/*.json` (prompt, raw events, usage),
`trials/*.json` (actual acceptance/escalation), `results.json`, `REPORT.fa.md`,
and `docs/reasoning-v6-1-20261002/Flux_Reasoning_v6_1_FA.html`.

Important boundaries:

- The graph is request-local structure, not trained weights or persistent RAG.
- A generated checker may repeat the solver's misconception. Static graph
  coverage and successful checking are not formal correctness proofs.
- v6.1 has one Luna call, then one Sol call only if rejected. v6 has two
  concurrent Luna calls, then Sol only on disagreement/failure.
- `luna_B_shared` reuses v6's B receipt. Its call/token metrics describe that
  receipt; they are not additional physical calls.
- Actual controller times include semaphore queueing. The shared B ablation
  reports just provider plus execution time. CLI overhead and cache affect
  reported tokens; no claim about API latency or dollar savings is made.
- Worker AST restrictions and timeouts are not a complete OS security sandbox.
- The canonical rounding helper is unit-tested; it is not used to decide the
  single-check v6.1 pipeline. The v6 baseline preserves its original agreement
  rule, including its tolerance for adjacent rounded answers.
