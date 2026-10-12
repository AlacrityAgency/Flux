# Frontend Testing Guide

How to apply steps T4–T7 of the [workflow](../workflow.md) to web UIs. Default portfolio shape: **trophy** (static → unit → integration (most) → E2E).

---

## 1. Layers

| Layer | Tooling (pick what the project already uses) | What it proves |
|---|---|---|
| Static | TypeScript strict mode, ESLint (incl. jsx-a11y), framework compiler | Whole classes of bugs never reach runtime |
| Unit | Vitest / Jest | Pure helpers: formatting, reducers, validation |
| Component integration (largest) | Testing Library (`@testing-library/react`, `/vue`, `/svelte`) on jsdom or Vitest browser mode | A component works the way a user operates it |
| Accessibility & interaction | `ui-ux.a11y`, `ui-ux.interaction` (desktop + mobile) | WCAG 2.2 AA rules, keyboard operation, target sizes |
| E2E | Playwright | Critical journeys across real pages, routing and backend |
| Visual (optional) | `ui-ux.a11y -- --visual` | Unintended visual changes |

## 2. Component tests: rules

- Query the DOM the way users and assistive tech do: `getByRole(name)`, `getByLabelText`, `getByText`. Use `data-testid` only when nothing semantic exists.
- Interact with `user-event` (typing, clicking, keyboard), not by calling handlers directly.
- Assert on what the user perceives: text, enabled/disabled state, ARIA state (`aria-expanded`, `aria-invalid`), navigation, network calls made (via MSW or a mocked fetch boundary).
- Wait for conditions (`findBy*`, `waitFor`, `expect.poll`), never fixed timeouts.
- Avoid snapshot-only tests; a snapshot may accompany explicit assertions but not replace them.

## 3. States every screen needs

For each screen or component in the plan, cover the states that can occur:

| State | Example assertion |
|---|---|
| Loading | spinner/skeleton has an accessible name; no layout jump when data arrives |
| Empty | helpful message and next action |
| Error | message is shown, linked to the field (`aria-describedby`), focus moves to the error summary on submit |
| Success / populated | key data visible; long names and large numbers do not break layout |
| Disabled / read-only | control not operable, still readable (contrast) |
| Permissions | actions hidden or disabled for roles that lack them |
| RTL / localisation (if `language` is fa/ar/he) | `dir="rtl"`, mirrored layout, Persian digits and dates formatted with `Intl` |

## 4. E2E with Playwright

- Few, stable, critical journeys only (sign-in, purchase, create/edit/delete core entity).
- Seed data through the API or database, not through the UI, to keep tests fast and independent.
- Use role-based locators and web-first assertions (`await expect(locator).toBeVisible()`); no `waitForTimeout`.
- Run with `sa.py gate testing.run -- --e2e`; flaky E2E tests are P1 findings, not retries.

## 5. Runtime UI gates

Run on each important page and state, desktop and mobile are covered automatically:

```bash
python3 <skill>/core/bin/sa.py gate ui-ux.a11y -- --url http://localhost:5173/settings
python3 <skill>/core/bin/sa.py gate ui-ux.interaction -- --url http://localhost:5173/settings
```

## 6. Performance (manual until a gate exists)

Core Web Vitals "good" thresholds at the 75th percentile: **LCP ≤ 2.5 s, INP ≤ 200 ms, CLS ≤ 0.1**. When performance is in scope, measure with Lighthouse or the project's RUM data and report the numbers; otherwise mark performance NOT-TESTED.
