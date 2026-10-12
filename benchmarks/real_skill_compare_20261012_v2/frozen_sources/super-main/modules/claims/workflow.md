# Workflow: Claims Audit (documents vs. code)

Use when a document describes what the software does or measures: feature reports, READMEs, specs, product sheets, research write-ups, slide decks exported to PDF, or UI text that names metrics. The question is not "does the code work" (that is the testing module) but **"is what we say about the code true?"**

Shared rules: [core/protocol.md](../../core/protocol.md) · [core/reasoning.md](../../core/reasoning.md). Reference: [references/claim-review.md](references/claim-review.md).

---

## C1 — Trace (automatic)

```bash
python3 <skill>/core/bin/sa.py --project <project> gate claims.trace -- --doc "<document.pdf|.md|.docx|.html>"
# or as part of a full review:
python3 <skill>/core/bin/sa.py --project <project> review --doc "<document>"
```

The gate extracts every metric/feature identifier and file reference from the document (PDF text is extracted without external tools; Persian/RTL text is normalised) and finds each one in the **production** code:

| Status | Meaning | Finding unless the document qualifies it |
|---|---|---|
| `active` | computed in production code | none (meaning still needs C2) |
| `research-only` | listed in a container named like `RESEARCH_ONLY` / `experimental` | P2, verified |
| `not-measured` | listed in a container named like `NOT_MEASURED` / `unavailable` | P1, verified |
| `never-computed` | only ever assigned constants (0, None, NaN) | P1, suspected |
| `absent` | not in production code (close matches and test/doc-only mentions are reported) | P1, verified |

"Qualified" means the document itself says, near the name, that the item is research, experimental, not measured, planned or removed (English or Persian). The gate also reports:
- **name/unit contradictions** (suspected), e.g. a `*_force_g` metric that is an acceleration in g, or a `variance` name whose code computes a standard deviation;
- **broken file references**;
- **performance claims without validation numbers** (suspected): "reliable", "accurate", «دقت»، «قابل اتکا»، «دشواری جعل» with no sensitivity, specificity, sample size or error rates in the document.

Output: findings in the ledger, plus `.superagent/claims/claims.md` (one row per claim: status, qualifier, evidence file:line).

## C2 — Meaning (reviewer, not automatic)

A static gate can show *that* a metric is computed, not that it **means** what the document says. For every `active` claim that supports a decision (score, alert, diagnosis), answer the questions in [claim-review.md §2](references/claim-review.md): what is physically computed, in which unit, against which reference, with what validation, and whether the document's causal or clinical interpretation follows from it. Use the finding format; anything you cannot prove is a question, not a defect.

## C3 — Report

1. Quote the gate result and `claims.md` table.
2. Add C2 findings, each tied to a claim and to code evidence (file:line).
3. Recommend the smallest honest correction: label each claim as active / research / not measured / removed in the document, rename misleading metrics, and either add validation evidence or soften performance claims.
4. Do not edit the document or the code unless the user asks.
