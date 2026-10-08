# Live local routing-policy benchmark

This is an independent pilot requested on 2026-10-06. The original six tasks
and traces behind the user's example were not available. It does not reproduce
that experiment or use Laya: the adaptive policy has a GPT-6 Luna router.

## Reproduce

```powershell
python -X utf8 benchmark.py selfcheck
python -X utf8 benchmark.py live
python -X utf8 benchmark.py analyze
```

The existing plan is frozen. `live` resumes the *same run* by keeping receipts;
it does not create independent repeat samples. For a fresh repeat, copy the
source into a new experiment directory, create empty `model_sandbox` and
`receipts` directories, run `freeze`, then `live`.

## Tasks and policies

Six newly authored deterministic tasks: record filtering; rounded invoice
arithmetic; strict half-open interval merging; idempotent account ledger;
counting Boolean assignments; globally optimal weighted-tardiness scheduling.
Prompts, policies, prices and source SHA-256 hashes were frozen before the
first benchmark solve call. Availability probes are separate setup overhead.

Four independent runs per task: Astra/max, manually selected model/high,
Luna/low with fail-triggered upgrades, and a live Luna router selecting model,
effort and verification with minimum risk floors. Retry feedback includes the
prior output and error category, not reference answers. Every physical routing
and solving call is charged to its policy's usage; no policy shares answers.

Model tools are forbidden consistently to isolate model decisions. This is a
small bounded reasoning/code-function benchmark, not a repository-level coding
agent benchmark with browsing, shell commands and multi-step tool use.

Local verification is deterministic. Code runs in a restricted subprocess with
timeouts, curated builtins, no imports and checks against independently written
reference algorithms; full checks include seeded generated inputs. Code probes
are not a proof over every possible input. Logic and scheduling use enumeration.
The adaptive policy's light checks may accept a wrong answer; the common full
audit records such false accepts rather than silently repairing them.

## Evidence and money

`receipts/` contains prompts, raw completion events, requested model/effort,
actual reported usage and measured call latency. Success requires a provider
`turn.completed` event and zero process exit code. Model/effort are requested
explicitly; these traces do not independently attest server internals.

`trials/` records actual conditional runs, retries, check levels and final full
audits. `results.json` and `REPORT.fa.md` aggregate the receipts. Real spend is
unknown because these calls use a ChatGPT account via Codex CLI. Dollar numbers
are an API-equivalent estimate using the published Standard short-context rates
at https://developers.openai.com/api/docs/pricing, with a separate no-cache
sensitivity estimate. They are not a paid API invoice or subscription cost.

CLI output token counts already include reasoning; reasoning is not added twice.
CLI input includes its system/tool overhead. Cache warmth and network scheduling
vary with execution order. The pilot has one sample per task-policy pair: any
observed ratio applies only here, not to arbitrary tasks or production traffic.
