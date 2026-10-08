# Flux + real local Laya: paired Senior / GOAT experiment

This experiment adds the user's existing Flux algorithms to two independently
executed policies. It does not modify the Flux server or previous frozen experiments.

Pipeline:

```
task -> local Laya front -> Flux v5 evidence selection -> context admission
     -> selected model/effort -> direct JSON or v6.1 graph + solve/check
     -> restricted local execution -> task verifier -> local Laya end
     -> accept OR stronger model, at most two escalations
```

Senior starts with Luna low; Laya selects verification, subject to risk floors.
GOAT delegates model, effort, verification to Laya. The end layer can escalate
even a passing result. A deterministic guard prevents accepting failed results.
Probabilities are recorded, not treated as calibrated estimates of correctness.

Reused actual Flux code: `request_memory_v5_20261002` Snapshot/Request/retrieve,
`src/flux/core/context.py` admission, `request_reasoning_v6_1_20261002/engine.py`
graph and checker audits. The v6.1 prompt and restricted worker are adapted for
JSON dictionary results. Arithmetic, SAT counts, and scheduling use programs;
extraction and Python function tasks use direct structured output. No gold
answers, task verifier implementations, or other policies' answers enter model
prompts. This is a whole-stack ablation; it does not isolate component effects.

The same six frozen synthetic tasks from `router_policy_20261006` are used.
Fresh baseline and enhanced calls run in shuffled arm order, two tasks at once.
No replay across arms. Existing identical receipts support interrupt/resume.
Each task/policy is sampled once; this is a pilot, not a general benchmark claim.

These tasks are self-contained: v5 uses an empty scoped snapshot and selects
zero archive units. This is real memory routing, but measures zero RAG savings.
Do not claim the previous large-archive compression percentages on these tasks.

Laya: `convaiinnovations/laya`, multilingual, revision
`7b928d828b7b0e022f929d9bd2e44165aa270148`. Weights verified against Hub LFS
SHA256 in `checkpoint-provenance.json`. Runs locally on CUDA with eager backend.
`.venv` inherits the existing torch 2.6.0+cu124 installation and has pinned
laya 0.3.28 / transformers 4.57.6. Source and checkpoint hashes are in plan.json.
SDK may repair tokenizer metadata during first load; smoke precedes freeze.

Use from this directory:

```
.venv/Scripts/python.exe -X utf8 benchmark.py selfcheck
.venv/Scripts/python.exe -X utf8 benchmark.py smoke
.venv/Scripts/python.exe -X utf8 benchmark.py freeze
.venv/Scripts/python.exe -X utf8 benchmark.py live
.venv/Scripts/python.exe -X utf8 benchmark.py analyze
```

CLI calls use the connected ChatGPT account and fresh read-only sessions, with
tools forbidden in the prompt and any observed tool use rejected. JSON events
and exact prompts are retained. `turn.completed` is required for success.
Account quota usage is not a dollar invoice. Standard API rates are used only
for an equivalent cost estimate. Missing usage is unknown, never zero; no exact
reduction ratio is asserted when any relevant call lacks usage. Output includes
reasoning tokens, which must not be counted twice. Visible prompt tokens and
total provider tokens are separate: Codex adds opaque context and caching.

Laya encoder tokens, inference time and GPU memory are separate from provider
tokens. Local inference has no paid API charge; electricity/hardware cost is
unpriced. The restricted Python worker is not an OS sandbox and has no hard RAM
limit. It is for synthetic trusted benchmark inputs, not arbitrary production
execution. Every final answer undergoes the same independent full audit.

Primary sources: https://github.com/NandhaKishorM/laya,
https://huggingface.co/convaiinnovations/laya,
https://developers.openai.com/api/docs/pricing.
