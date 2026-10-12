# Workflow: Implementation

Use when the user wants runnable UI: a change in an existing codebase or a standalone prototype.
Shared rules: [core/reasoning.md](../../../core/reasoning.md) · [core/protocol.md](../../../core/protocol.md)

---

## 1. Choose the pathway

### A. Existing codebase (default when the workspace contains an app)
- Edit the project's files in place, following its framework, folder structure, styling system and tokens.
- Do not add a parallel styling system, a new component library or a new token file unless the user asks.
- Verify against the running app: `python3 <skill>/core/bin/sa.py gate ui-ux.a11y -- --url http://localhost:<port>` and `... gate ui-ux.interaction -- --url ...`.
  Find the port from the project's dev script or the running server; if nothing is running, start the dev server with the project's own command or report NOT-TESTED.

### B. Standalone prototype (only when the user asks for an isolated demo or specimen)
- Write a single HTML file to `<project>/.superagent/sandbox/<name>.html` that renders into `<div id="root">` (or an element with `data-component-root`).
- Prefer plain HTML/CSS/JS. If React is needed, load pinned versions with Subresource Integrity, for example
  `https://unpkg.com/react@18.3.1/umd/react.production.min.js` with an `integrity` attribute; never load unpinned `@latest` URLs.
- Verify: `python3 <skill>/core/bin/sa.py gate ui-ux.a11y -- --sandbox .superagent/sandbox/<name>.html` (and `ui-ux.interaction` with the same target).

## 2. Ground the work

- Follow the retrieval order in [core/reasoning.md §6](../../../core/reasoning.md).
- For standard controls with no equivalent in the project, start from `modules/ui-ux/templates/components.json` (button, dialog, input, card) and adapt to the project's theme. A template is a starting point; it does not replace the gate.
- Component-specific rules (states, ARIA, keyboard): `modules/ui-ux/templates/knowledge_tree.json` → the mapped reference.

## 3. Guardrails while writing code

- **Target size:** see [review-checklist.md §1](../references/review-checklist.md): 24px minimum, 44px for primary touch actions.
- **Tokens:** use the project's tokens or semantic theme classes; no hex literals or arbitrary values such as `text-[13px]` (checked by `ui-ux.token-drift`, see [tokens.md](../references/tokens.md)).
- **States and forms:** implement the states that can occur (hover, focus-visible, disabled, loading, error, empty) and follow the form rules in [ux-patterns.md](../references/ux-patterns.md).
- **Keyboard:** everything reachable with Tab; visible `:focus-visible`; dialogs trap and restore focus.
- **RTL:** logical properties (`margin-inline-start`, Tailwind `ms-*`/`me-*`/`start-*`/`end-*`); see [accessibility-and-rtl.md §2](../references/accessibility-and-rtl.md).
- **Motion:** honour `prefers-reduced-motion` (Tailwind `motion-reduce:`).
- **Domain assets:** for specialised domains (healthcare, fintech, industrial) follow [specialized-domains.md](../domains/specialized-domains.md); never use stock photos for functional assets.

## 4. After every change

Write a Decision Record, then go to [review.md](review.md). Any code change makes earlier gate results STALE ([core/protocol.md §4](../../../core/protocol.md)).
If the change has logic worth testing (forms, state, data handling), also follow the testing module: [modules/testing/workflow.md](../../testing/workflow.md).
When a gate keeps failing, follow the attempt budget in [core/protocol.md §5](../../../core/protocol.md).

## 5. Connected application flows

For a real application follow [the full-stack workflow](../../../core/workflows/application.md), not the standalone prototype pathway. Generate or share API types with the backend; implement session expiry, unauthorized, retry, optimistic rollback and server-side validation states. Configure `ui-ux.journey` for critical browser flows against the actual test API and database, including reload persistence. Save and inspect desktop/mobile screenshots; test keyboard and RTL where required. Accessibility scans alone do not establish correct visual layout or business behaviour.
