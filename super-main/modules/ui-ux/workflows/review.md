# Workflow: UI Review & Verification

Use to audit UI before delivery, or when the user asks for an accessibility / quality review.
Statuses, findings, ledger and verdict: [core/protocol.md](../../../core/protocol.md). Checklist: [review-checklist.md](../references/review-checklist.md).

All commands: `python3 <skill>/core/bin/sa.py --project <project> gate <gate> -- <args>`.

To run everything at once: `sa.py review --depth <depth> --url <page1> --url <page2>` (each page gets its own evidence; add `--level AAA` for 44 px targets).

---

## 1. Run the gates

| Gate | When | Arguments |
|---|---|---|
| `ui-ux.page-coverage` | Every page within the requested scope | same target; bounded document/internal scroll with lazy-content segment screenshots |
| `ui-ux.a11y` | Always for runnable UI, on every important page/state | `--url http://localhost:<port>/<page>` or `--sandbox .superagent/sandbox/<name>.html` |
| `ui-ux.interaction` | Always for runnable UI | same target; add `--level AAA` when `target_compliance: WCAG_AAA` |
| `ui-ux.token-drift` | Code review of active styles | declare inspected source/reference roots; update a legacy baseline only after reviewing and explicitly accepting its debt |
| `ui-ux.tokens` | The project has a `tokens.json` | `--tokens <path> [--contrast-pairs <path>]` |
| Testing gates | The change contains logic | follow [modules/testing/workflow.md](../../testing/workflow.md) |

- Browser gates audit desktop (1280×800) and mobile (375×667).
- Inspect the page-coverage segment screenshots, including the footer and internal scroll ends.
  PASS means scrolling evidence, not visual approval. Missing regions or infinite-scroll limits
  remain gaps. Do not cover a whole website by checking its homepage only.
- Enumerate and execute relevant form/menu/modal/error states through named journeys. Hidden
  states are not automatically opened by the scroll gate; supply project-specific assertions.
- Visual regression is opt-in: `ui-ux.a11y -- --url … --visual` (first run creates baselines under `.superagent/a11y/baselines`).
- Read findings from the gate output (rule, severity, viewport, elements, remediation). Do not paraphrase them into new claims.

## 2. Depth

- `quick`: gates for the changed screen only.
- `standard`: all applicable gates plus the checklist.
- `thorough`: as standard, plus every state of each screen (empty, loading, error, dialog open), long-content and RTL rendering, and manual checks the gates cannot do (heading order, wording, dialog focus return).

Look for reasons to reject: long text, missing data, 375 px width, keyboard only, reduced motion. Report only what you can back with evidence.

## 3. Fix loop

- FAIL → [implement.md](implement.md), fix, re-run the gate. The ledger counts attempts ([core/protocol.md §5](../../../core/protocol.md)).
- NOT-TESTED → state the missing prerequisite from the gate notes (start the dev server, install Chromium, …).
- ERROR → report as a skill limitation.

## 4. Verdict and summary

```bash
python3 <skill>/core/bin/sa.py --project <project> verdict --require ui-ux.page-coverage,ui-ux.a11y,ui-ux.interaction[,ui-ux.token-drift,ui-ux.tokens] --format md
```

Deliver the generated summary, then add:
- **Scope**: screens/components reviewed, posture, compliance level.
- **Manual checks**: what you checked by hand and the result.
- **Open findings**: in the finding format.

Never claim a guarantee (contrast, target size, keyboard support) that no gate or manual check in this session verified, and never write the verdict label yourself.
