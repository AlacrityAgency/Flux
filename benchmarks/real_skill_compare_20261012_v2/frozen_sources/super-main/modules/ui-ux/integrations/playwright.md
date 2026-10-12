# Playwright + axe-core Accessibility Gate

## How to run

```bash
# Running app (dev server must be up)
python3 <skill>/core/bin/sa.py gate ui-ux.a11y -- --url http://localhost:3000

# Standalone prototype rendering into #root
python3 <skill>/core/bin/sa.py gate ui-ux.a11y -- --sandbox .superagent/sandbox/demo.html
```

| Exit | Status | Meaning |
|---|---|---|
| 0 | PASS | Audited on desktop (1280x800) and mobile (375x667); no WCAG 2.2 AA violations, no uncaught page errors |
| 1 | FAIL | Violations, uncaught page errors, or the sandbox never rendered; see `findings[]` |
| 2 | NOT-TESTED | No target, file missing, server unreachable, or Playwright/Chromium not installed; see `notes[]` |
| 3 | ERROR | The gate itself failed (no report, unexpected skips) |

Options: `--mount-timeout <ms>` (default 15000), `--visual` (screenshot comparison; first run creates baselines in `<out>/baselines`), `--out <dir>` (default `./.superagent/a11y`).
One-time setup inside the skill: `npm install --prefix <skill>` and `npx playwright install chromium`.

Automated checks cover only part of WCAG. Still check focus order, wording, and screen-reader behaviour manually for important flows.

---

## 1. Automated Accessibility Testing with Axe-core

The gate runs `@axe-core/playwright` with WCAG 2.0–2.2 Level A/AA rules. AAA criteria (e.g. 7:1 contrast, 44px targets) are not covered automatically; check them with the tokens gate and manual review when `target_compliance: WCAG_AAA`.

### Core Auditing Rules & Standards
Tags used by the gate: `wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`, `wcag22aa`.

Key checks evaluated:
1. **Color Contrast (`color-contrast`)**:
   - Minimum 4.5:1 ratio for regular text against its background.
   - Minimum 3.0:1 ratio for large text (≥ 24px, or ≥ 18.66px bold) and graphical UI elements/boundaries.
2. **Accessible Names & Semantics (`button-name`, `link-name`, `aria-roles`)**:
   - Buttons, links, and interactive controls must have accessible text names (via visible text, `aria-label`, or `aria-labelledby`).
   - Icon-only buttons must never be unlabeled.
3. **Form Controls & Labels (`label`, `select-name`)**:
   - Every input, select, and textarea must have an associated `<label for="...">` or `aria-label`.
4. **ARIA Validity (`aria-valid-attr`, `aria-required-attr`, `aria-allowed-role`)**:
   - ARIA attributes must be valid, non-redundant, and used on appropriate HTML elements.
5. **Keyboard & Focus Navigation (`tabindex`, `focus-order-semantics`)**:
   - Focus order must be logical; avoid positive `tabindex` values (`tabindex > 0`).
   - Modal dialogs must trap focus; interactive elements must possess visible focus indicators.
6. **Images & Media (`image-alt`)**:
   - Meaningful images must have descriptive `alt` text; decorative graphics must be marked `alt=""` or `aria-hidden="true"`.

---

## 2. Viewports & Visual Regression

- The gate always audits both viewports defined in `playwright.config.js` (desktop 1280x800, mobile 375x667 with touch).
- Visual comparison is opt-in (`--visual`). Baselines live with the audited project, not inside the skill. Review and commit them deliberately; a changed baseline is a design decision.
- If Playwright cannot run in the environment, the gate exits 2 (NOT-TESTED). Do not substitute a manual "looks fine" for a PASS.
