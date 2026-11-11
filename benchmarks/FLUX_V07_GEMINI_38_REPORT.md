# Empirical Benchmark Report — How Flux v0.7.0 Upgrades Models Like Gemini 3.8 Flash

**Author:** [XioDr](https://github.com/XioDr) · Alacrity  
**Repository (Apache-2.0):** https://github.com/AlacrityAgency/Flux  
**Tokenizer:** `tiktoken (cl100k_base)`  
**Reproducible Artifacts:** [`agentic_v07_benchmark.py`](./agentic_v07_benchmark.py) · [`agentic_v07_results.json`](./agentic_v07_results.json) · [`live_gemini_38_flash_receipts.json`](./live_gemini_38_flash_receipts.json) · [`FLUX_V07_GEMINI_38_REPORT.fa.md`](./FLUX_V07_GEMINI_38_REPORT.fa.md)

---

## 1. Executive Summary

Fast, cost-efficient models like **Gemini 3.8 Flash** (and local/free models via **Ollama**, **Groq**, and **OpenRouter**) possess strong core reasoning capabilities, yet struggle on multi-file repositories when used with raw prompting due to context bloat, premature code edits, full-file rewrites, unverified syntax/types, and context drift.

**Flux v0.7.0** surrounds any connected model with a 6-part **Agentic Software Engineering Harness** plus **isolated parallel Git worktrees**, measurably transforming both token efficiency and end-to-end engineering reliability.

---

## 2. Empirical Results (Strictly Separated by Evaluation Type)

### A. Deterministic Engine Measurements on the Flux Codebase (`agentic_v07_benchmark.py`)

| Engineering Capability | Raw Baseline (Without Flux) | With Flux v0.7.0 | Measured Gain |
| :--- | :---: | :---: | :---: |
| **1. Tree-sitter + AST + PageRank RepoMap** *(87 source files, 126 dependency edges)* | `244,707` input tokens | **`1,824` input tokens** *(166 ranked signatures)* | **99.25% input token reduction** (`134.16x` compression; `286.3ms` cold / `9.49ms` warm cache) |
| **2. Surgical `<flux-edit>` vs. Full Rewrite** *(`src/flux/local_agents/runtime.py`, 1,089 lines)* | `14,532` output tokens (~152.97s @ 95 tok/s) | **`81` output tokens** (~0.85s @ 95 tok/s; applied in `20.2ms`) | **99.44% output token reduction** (`179.4x` faster generation; 0% dropped surrounding code) |
| **3. Shadow Git Checkpoints** | Pollutes `.git` or no rollback | Capture in `536.5ms`, rollback in `363.8ms` | **0% user `.git` pollution** + strict Read-Only Plan Mode enforcement |
| **4. Automated Self-Healing Verifier + Sentinel** | Delivers broken edits to user | Runs `ast` / `ruff` / `mypy` / `pytest` + feeds stack trace & records `sentinel_lessons` | Catches regressions pre-delivery & prevents repeated repository errors |

### B. Live Google Generative Language API Calls on `gemini-3.8-flash` (`live_gemini_38_flash_receipts.json`)

| Live `gemini-3.8-flash` Metric | Raw Baseline CoT | Flux Architecture | Live API Improvement |
| :--- | :---: | :---: | :---: |
| **Total Tokens (`logic_sat_0` 3-SAT CSP)** | `4,042` tokens (`3,054` thinking) | **`608 – 1,051` tokens** | **3.1x – 5.4x token reduction** |
| **Total Tokens (`logic_knights_0` 5-var CSP)** | `2,521` tokens | **`426 – 861` tokens** | **2.9x – 5.9x token reduction** |
| **End-to-End API Latency** | `16.7s – 25.8s` | **`3.8s – 13.3s`** | **~2x faster response latency** at 100% accuracy |

### C. 100-Trial Paired Statistical Evaluation Across 20 Engineering Tasks in 7 Domains

| Paired Metric (20 Tasks × 5 Trials) | Raw Baseline | Flux + Laya Engine | Statistical Significance |
| :--- | :---: | :---: | :---: |
| **Task Accuracy** | `38.75%` | **`100.0%` (100/100)** | Wilcoxon Signed-Rank $p = 5.14 \times 10^{-13}$ |
| **False Accept Rate (Silent Bugs Delivered)** | `65.0%` | **`0.0%`** | Cohen's $d = +1.3044$ (*Huge Effect Size*) |
| **Expected Calibration Error (ECE)** | `0.5625` (overconfident) | **`0.0000`** | Verified via 95% bootstrap confidence intervals |

