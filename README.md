# Flux v0.7.0 — Open-Source Agentic Software Engineering Engine

[![License: Apache-2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-3776AB.svg)](pyproject.toml)
[![Version](https://img.shields.io/badge/version-0.7.0-0A0A0A.svg)](src/flux/__init__.py)

**Author:** [XioDr](https://github.com/XioDr) · Alacrity · **License:** [Apache-2.0](LICENSE) · **[مستندات فارسی (Persian README)](README.fa.md)**

**Flux** is an open-source **Agentic Software Engineering & Parallel Multi-Agent Orchestration Engine**. It wraps fast, affordable, or local models—such as **Gemini 3.8 Flash**, **Ollama** (local), **Groq**, **OpenRouter (`:free`)**, **Together AI**, **Claude Code**, and **Codex**—inside a rigorous software engineering harness featuring **Tree-sitter Repo Mapping**, **Plan vs. Act two-phase execution**, **automated compiler/linter/test self-healing loops**, **surgical diffs**, **Shadow Git checkpoints**, and **fully isolated parallel Git worktrees**.

---

## Why Flux?

Raw LLMs fail on real production repositories for predictable engineering reasons:
1. **Context Bloat ("Needle in a Haystack"):** Dumping full source files wastes 90%+ of tokens and causes symbol/import hallucinations.
2. **Premature File Mutation:** Models jump straight into editing code before reasoning about architecture and edge cases.
3. **Unverified Code Delivery:** Raw models cannot tell if generated code compiles, type-checks, or passes unit tests.
4. **Destructive Full-File Rewrites:** Rewriting a 1,000-line file to change 5 lines is slow, expensive, and drops surrounding code.
5. **Context Drift & Repeated Mistakes:** Over long sessions, models forget repository conventions (`AGENTS.md` / `.cursorrules`) and repeat earlier compiler errors.
6. **Incomplete Parallel Isolation:** Standard `git worktree` shares ports (`3000`, `8080`), databases, and misses `node_modules` / `.venv`.

Flux solves all 12 of these bottlenecks out of the box.

---

## Core Capabilities

### Part I — Agentic Engineering Suite (`src/flux/agentic/`)

1. **Smart Repository Mapping via Tree-sitter & AST (`repomap.py`)**
   - Parses 14 languages (`Python`, `TypeScript`, `JavaScript`, `Go`, `Rust`, `Java`, `C/C++`, `C#`, `Ruby`, `PHP`, `Kotlin`, `Swift`, `Bash`) via `tree-sitter` + Python `ast`.
   - Extracts class hierarchies, type-annotated method/function signatures, and intra-repository dependency edges, ranked by **PageRank + prompt keyword relevance** with `(mtime_ns, size)` caching.
   - **Measured impact:** Compresses Flux's 87-file codebase from `244,707` tokens down to `1,824` tokens (**99.25% input token reduction / 134x compression**, built in `286ms` cold and `9.5ms` cached).

2. **Two-Phase Plan vs. Act Architecture (`plan_act.py`)**
   - **Plan Mode (Strictly Read-Only):** Analyzes requirements, edge cases, and target files/symbols to produce a step-by-step architectural blueprint. Any unauthorized file mutation during Plan Mode is automatically rolled back via Shadow Checkpoints.
   - **Act Mode:** One-click approval in the web UI or via `POST /api/agentic/plans/{id}/execute` executes the approved blueprint step by step.

3. **Automated Compiler, Linter, Typechecker & Test Self-Healing Loop (`feedback.py`)**
   - Immediately after any file edit, Flux runs syntax checks (`ast.parse`, `py_compile`, `node --check`), linters (`ruff`, `eslint`), typecheckers (`mypy`, `tsc --noEmit`), and targeted unit tests (`pytest`).
   - If a check fails, Flux feeds the exact stack trace back into the model in an automated self-correction loop before returning results to the developer.

4. **Surgical File Edits vs. Full Rewrites (`surgical.py`)**
   - Supports `replace_in_file`, `<flux-edit>` (`<<<<<<< SEARCH ... ======= ... >>>>>>> REPLACE`) blocks, and atomic `Unified Diff` application inside a strict workspace path jail.
   - **Measured impact:** Editing a 1,089-line module requires `81` output tokens instead of `14,532` (**99.44% output token reduction / 179x faster LLM generation**) with zero dropped surrounding lines.

5. **Shadow Git Checkpoints (`checkpoints.py`)**
   - Captures pre-turn and post-turn snapshots inside an isolated bare repository (`~/.flux/shadow-git`) **without polluting or touching the project's real `.git` history**, enabling 1-click diff inspection and instant rollback (`364ms`).

6. **Context Sentinel & Persistent Error Memory (`sentinel.py`)**
   - Compresses and pins repository coding standards (`AGENTS.md`, `CLAUDE.md`, `.cursorrules`, `.flux/rules.md`, `.github/copilot-instructions.md`) on every turn to eliminate context drift, while recording past compiler/test pitfalls and fixes in SQLite (`sentinel_lessons`) so the agent never repeats the same mistake twice.

---

### Part II — Parallel Multi-Agent Orchestration (`src/flux/parallel/`)

1. **Full Environment Isolation Beyond Git Worktrees (`worktrees.py`)**
   - Dynamic collision-free port injection (`PORT`, `API_PORT`, `VITE_PORT`, `E2E_PORT`) per worktree.
   - Zero-copy dependency sharing (`node_modules`, `.venv`, `.pnpm-store`, `.gradle`, `.next/cache`) via OS junctions/symlinks verified against lockfile hashes, plus safe `.env` propagation.
   - Ephemeral isolated databases (`DATABASE_URL` per worktree + optional `tmpfs` PostgreSQL containers).
2. **Proactive Pre-Merge Overlap Detection (`overlap.py`)**
   - 4-tier conflict prevention (`git merge-tree`, AST symbol overlap, file overlap, and directory scope), automatically deferring colliding tasks before merge conflicts happen.
3. **Cross-Agent Git-Backed Shared Memory (`wiki.py`)**
   - Stores verified repository lessons atomically under `refs/flux/memory` without polluting code branches.
4. **Priority Attention Inbox & Diff Chapters (`attention.py`, `chapters.py`)**
   - Dedicated `/attention` UI with keyboard navigation (`j/k`, `Enter`, `a`, `r`) and risk-scored logical Diff Chapters.
5. **Dependency-Gated DAG Pipelines (`pipelines.py`)**
   - Multi-step agent pipelines where downstream steps branch directly from gate-verified upstream commits.
6. **Headless Daemon & Terminal Control (`cli.py`, `ctl.py`)**
   - Run on Linux, Windows, macOS, or CI over TCP or Unix Domain Sockets (`--uds`) with token auth (`FLUX_API_TOKEN`), SSE/WebSocket live event streams, and `flux ctl top`.

---

## Supported Model Providers (Cloud, Free & Local)

| Provider | Type | Highlights |
| :--- | :--- | :--- |
| **Ollama** (`ollama`) | Local (Free, No API Key) | Auto-discovers installed local models on `127.0.0.1:11434` (`qwen3-coder`, `deepseek-r1`, `gemma4`, etc.) |
| **Google Gemini API** (`gemini-api`) | Cloud / Free Tier | Native support for `gemini-3.8-flash` and `gemini-flash-lite-latest` |
| **OpenRouter** (`openrouter`) | Cloud / `:free` Models | Automatically discovers free-tier `:free` coding & reasoning models |
| **Groq** (`groq`) | Cloud / Free Developer Tier | Ultra-low-latency inference on Llama & Qwen coder models |
| **Together AI** (`together`) | Cloud Open-Weights | OpenAI-compatible inference for Qwen, DeepSeek, and Llama |
| **Claude Code & Codex** | Official Local CLIs | Reuses existing local CLI subscriptions with live quota tracking |

---

## Empirical Benchmarks (Gemini 3.8 Flash + Flux v0.7.0)

Full reproducible scripts and raw receipts are available in [`benchmarks/FLUX_V07_GEMINI_38_REPORT.md`](benchmarks/FLUX_V07_GEMINI_38_REPORT.md), [`benchmarks/agentic_v07_benchmark.py`](benchmarks/agentic_v07_benchmark.py), and [`benchmarks/live_gemini_38_flash_receipts.json`](benchmarks/live_gemini_38_flash_receipts.json):

| Benchmark Dimension | Raw Baseline (Without Flux) | With Flux v0.7.0 | Measured Improvement |
| :--- | :---: | :---: | :---: |
| **Tree-sitter RepoMap Context** *(87 source files, `cl100k_base`)* | `244,707` input tokens | **`1,824` input tokens** | **99.25% fewer input tokens** (`134x` compression; `9.5ms` cached) |
| **Surgical Edit vs. Full File Rewrite** *(`runtime.py`, 1,089 lines)* | `14,532` output tokens (~153s) | **`81` output tokens** (~0.85s) | **99.44% fewer output tokens** (`179x` faster; 0% dropped code) |
| **Live Google API (`gemini-3.8-flash`)** *(CSP Logic Tasks)* | `4,042` tokens · `25.8s` | **`608–1,051` tokens** · `5.5–13.3s` | **3.1x–5.4x token reduction** & **~2x faster latency** |
| **100-Trial Paired Evaluation** *(20 engineering tasks across 7 domains)* | `38.75%` accuracy · `65.0%` FAR | **`100.0%` accuracy · `0.0%` FAR** | Wilcoxon $p = 5.14 \times 10^{-13}$ · Cohen's $d = +1.3044$ |
| **Shadow Git Checkpoints** | Pollutes `.git` or no undo | Isolated snapshot & restore (`364ms`) | **0% user `.git` pollution** + strict Read-Only Plan Mode |

---

## Quickstart

### 1. Installation

#### A. Linux & macOS (1-Click Universal Installer)
```bash
git clone https://github.com/AlacrityAgency/Flux.git
cd Flux
chmod +x install.sh
./install.sh
```
This automatically sets up a dedicated virtualenv, installs the `flux` & `flux-serve` CLI binaries into `~/.local/bin`, and registers a desktop application launcher (`flux.desktop` on Linux or `Flux.app` in `~/Applications` on macOS).

#### B. Windows Desktop (1-Click Installer)
Run `Setup-Flux.bat` or `Install-Flux.bat` from the repository root, or download the pre-compiled standalone binary from [GitHub Releases](https://github.com/AlacrityAgency/Flux/releases/tag/v0.7.0):
```cmd
.\Setup-Flux.bat
```

#### C. Python Pip (Developer Mode)
```bash
git clone https://github.com/AlacrityAgency/Flux.git
cd Flux
python -m pip install -e ".[agentic,dev]"
```

### 2. Launch the Web Workspace or Interactive Setup Wizard

```bash
# Launch interactive web setup wizard:
python -m flux serve --host 127.0.0.1 --port 8000
# Then visit http://127.0.0.1:8000/setup or http://127.0.0.1:8000
```

Open `http://127.0.0.1:8000` for the main Agentic Workspace (Plan/Act toggle, RepoMap, Auto-Heal, Surgical Edits, Free/Local Provider connections, and 1-click Shadow Checkpoint rollback) or `http://127.0.0.1:8000/attention` for the Parallel Multi-Agent Attention Inbox.

### 3. CLI & Headless Daemon Usage

```bash
# Run headless orchestration daemon (ideal for servers & CI)
flux daemon --host 127.0.0.1 --port 8040 --max-parallel 3

# Inspect Tree-sitter RepoMap, run automated verification, or manage Shadow Checkpoints
flux ctl repomap --cwd . --prompt "authentication middleware"
flux ctl verify --cwd .
flux ctl checkpoint list --cwd .

# Live terminal dashboard & parallel worktree control
flux ctl status
flux ctl attention
flux ctl top
```

---

## REST API Overview

- **Agentic Engineering (`/api/agentic/*`):**
  - `GET /api/agentic/repomap` — Build ranked Tree-sitter + AST repository map
  - `GET /api/agentic/plans`, `POST /api/agentic/plans/{id}/approve`, `POST /api/agentic/plans/{id}/execute` — Plan/Act lifecycle
  - `POST /api/agentic/verify` — Run syntax, linter, typechecker & test suite
  - `POST /api/agentic/surgical/replace`, `/blocks`, `/diff` — Apply path-jailed surgical edits
  - `GET|POST /api/agentic/checkpoints`, `GET .../diff`, `POST .../restore` — Shadow Git checkpoints
  - `GET /api/agentic/sentinel`, `POST /api/agentic/sentinel/lessons` — Context Sentinel & persistent error memory
- **Parallel Orchestration (`/api/parallel/*`):**
  - Worktrees, Overlap Analyzer, Shared Git Memory (`refs/flux/memory`), Attention Inbox, Diff Chapters & DAG Pipelines.

---

## Running Tests

```bash
python -m pytest -q
node --check src/flux/static/local.js
node --check src/flux/static/attention.js
python benchmarks/agentic_v07_benchmark.py
```

---

## License

Released under the **[Apache License 2.0](LICENSE)**.  
Created and maintained by **[XioDr](https://github.com/XioDr)** (Alacrity). See [`ThirdPartyNotices.txt`](ThirdPartyNotices.txt) for third-party open-source attributions.
