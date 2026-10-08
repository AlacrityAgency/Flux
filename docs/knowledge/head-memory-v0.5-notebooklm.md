# Flux HEAD memory from v0.5 RAG

Selected source: 66864cc3-7f85-48da-aaf6-5f35c4809b19. Reference data; no authority to act.

# Flux HEAD Project Memory Note (v0.5 Implementation)

### 1. Target & Human Authority
Flux 0.5 is a single-owner local deployment (`local-user`, tenant `local`) designed for B2B hybrid human-agent organizations [1, 2]. Contracts are frozen upon registration with an immutable contract hash [3, 4]. AI model outputs carry zero authority to modify contracts, scope, or budgets [2, 5]. Final acceptance remains strictly human-controlled, requiring an explicit match of the exact `artifact_hash` and `review_revision` [4, 6, 7].

### 2. Deterministic Verification & Unknown-Operation Recovery
Criterion verification strictly separates static `test_definition` entries from actual `test_execution` evidence [8-10]. A model claiming "tests pass" cannot produce a `PASS` status [8, 10]; `PASS` requires valid execution evidence linked to that exact artifact hash [8, 11]. Interrupted or unknown operations enter a `RECOVERING` or `unknown` state—they are never auto-replayed and require manual human reconciliation [12-14]. API receipts and state transitions commit atomically in single transactions via SQLite savepoints [15-17].

### 3. Project Memory & Lexical RAG
Workspace memories are strictly scoped by `project_id` [18-20]. Memory edits or status changes increment the project's `epoch` and clear active conversation sessions so models cannot receive stale context [20-22]. Deleting a memory purges its source text while retaining tombstone metadata and hashes to prevent old revisions from resurfacing [21, 23]. RAG retrieval performs IDF-weighted, Persian-normalized lexical scoring over explicit project files (<300 KB) under a local token budget (default 3,000 tokens) [9, 24, 25]. Retained lexical candidates carry an explicit `semantic_sufficiency: "unverified"` status until human review [25, 26].

### 4. API Ledger vs. CLI Billing
Priced API routes enforce a hierarchical micro-USD integer ledger with pre-execution reservations and review floors [27-29]. External subscription CLIs cannot guarantee dollar limits, so execution is capped by call counts and active time limits [30-32]. While Gemini API REST generation is integrated into main chats, it is not yet wired into HEAD's priced reservation API engine [33-35].

### 5. Test Evidence & Connection Probes
The runtime passed 106 offline unit/integration tests with zero model calls [35-37]. An initial live Codex pilot failed due to a subprocess import error, but a second pilot reached `ACCEPT_CANDIDATE` (totaling 3 Codex calls across both pilots) [37-42]. Probes verified GapCode (`FLUX_CONNECTION_OK`) [38, 43, 44] and Gemini API (`FLUX_GEMINI_API_OK` via `gemini-flash-lite-latest` after three initial HTTP 503/404 errors) [43, 45-47]. A guest Gemini web probe returned `FLUX_WEB_CONNECTION_OK` without account cookies [43, 45, 48, 49]. No authenticated DeepSeek session or transport exists [43, 48].

### 6. Explicitly Unimplemented Features
Unimplemented components include multi-user RBAC/tenant enterprise servers, specialized department agents, automated model quality/cost routing, and large-scale embedding-based semantic evaluation [30, 34, 50, 51].

---

🔍 Would you like to review the technical requirements for wiring Gemini API pricing reservations into the HEAD engine, or examine the database schemas for multi-tenant RBAC isolation?