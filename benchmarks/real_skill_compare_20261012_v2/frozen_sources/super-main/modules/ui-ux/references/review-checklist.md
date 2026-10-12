# UI Review Checklist

Each item ends with a status from [core/protocol.md §2](../../../core/protocol.md). Prefer gate evidence; where a check is manual, say so.

## 1. Target size
- Every interactive control is at least **24×24 CSS px**, or spaced so a 24px circle centred on it does not overlap another target (WCAG 2.2 SC 2.5.8, AA). Inline text links are exempt.
- Primary touch actions on mobile are **44×44 CSS px** (SC 2.5.5). Mandatory only when `target_compliance: WCAG_AAA`; otherwise advisory.
- Dense desktop controls of 24–36 px are acceptable at AA. Do not reject them for being under 44 px.
- Evidence: `ui-ux.interaction` (measured on desktop and mobile; `--level AAA` for 44 px) and axe's `target-size` rule in `ui-ux.a11y`.

## 2. Keyboard and focus
- Every control is reachable with Tab in a logical order, the focus indicator is visible (SC 2.4.7), focus is not hidden by sticky UI (SC 2.4.11), there is no keyboard trap (SC 2.1.2), and dialogs trap focus while open and return it on close.
- Evidence: `ui-ux.interaction` for reachability, visibility, obscuring and traps; dialog focus return is a manual check (open, press Escape, confirm focus is back on the trigger).

## 3. Automated WCAG rules
- Evidence: `ui-ux.a11y` on every important page and state (empty, loaded, error, dialog open).
- Automated checks cover only part of WCAG: also check headings order, link/button wording and form error messages manually.

## 4. Token integrity
- No ad-hoc colors, sizes or fonts that bypass the tokens.
- Evidence: `ui-ux.token-drift` (use `--update-baseline` once on legacy projects, then only new drift fails) and `ui-ux.tokens` when a `tokens.json` exists.

## 5. Content and states
- Loading, empty, error, success and disabled states exist where they can occur; long names, large numbers and RTL text do not break layout. See [ux-patterns.md](ux-patterns.md).

## 6. Domain reality
- Functional assets (radiographs, waveforms, order books, device schematics) appear in their real form, never as stock photos. Rules: [../domains/specialized-domains.md](../domains/specialized-domains.md). `NOT-APPLICABLE` for generic UI.

## 7. Verdict
Run `python3 <skill>/core/bin/sa.py verdict --require <gates> --format md` and quote its label. Do not write a verdict label yourself.
