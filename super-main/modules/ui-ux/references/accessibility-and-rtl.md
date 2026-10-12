# Accessibility and RTL Architecture

## 1. WCAG 2.2 Compliance Standards & Touch Target Geometry

Set target compliance explicitly based on product tiers:

| Dimension | WCAG 2.2 Level AA (baseline) | WCAG 2.2 Level AAA |
|---|---|---|
| **Target size** | **SC 2.5.8 Target Size (Minimum)**: 24×24 CSS px, or spacing so a 24px circle centred on the target does not intersect another target. Exceptions: inline links, user-agent controls, an equivalent control elsewhere, essential presentation. | **SC 2.5.5 Target Size (Enhanced)**: 44×44 CSS px. Also the recommended size for primary touch actions at any level. |
| **Text contrast** | **SC 1.4.3**: ≥ 4.5:1 body text; ≥ 3:1 large text (≥ 24px regular, or ≥ 18.66px / 14pt bold). | **SC 1.4.6**: ≥ 7:1 body text; ≥ 4.5:1 large text. |
| **Non-text contrast** | **SC 1.4.11**: ≥ 3:1 for UI component boundaries, input borders, icons that convey meaning, and focus indicators against adjacent colors. | No stricter AAA criterion exists; 3:1 still applies. |
| **Focus visible** | **SC 2.4.7 Focus Visible** (AA): a visible keyboard focus indicator. **SC 2.4.11 Focus Not Obscured (Minimum)**: the focused element is not entirely hidden by sticky headers, banners or overlays. | **SC 2.4.13 Focus Appearance**: indicator area at least a 2 CSS px perimeter around the control, with ≥ 3:1 contrast between focused and unfocused states. **SC 2.4.12**: focused element not obscured at all. |

Practical default that satisfies AA and most of AAA: `outline: 2px solid <ring token>; outline-offset: 2px;` on `:focus-visible`, with the ring token checked at ≥ 3:1 against the surrounding surface.

> **Target size policy** for this skill is defined once in [review-checklist.md §1](review-checklist.md): 24px minimum (AA), 44px for primary touch actions and for `WCAG_AAA`. Dense desktop controls of 24–36px are acceptable at AA.

---

## 2. Right-to-Left (RTL) & BiDi Localization Protocol

For applications supporting bidirectional (BiDi) scripts (Persian / Farsi, Arabic, Hebrew):

1. **CSS Logical Properties (Zero Physical Directionality)**:
   - Always replace physical CSS directions with logical equivalents:
     * `margin-left` / `margin-right` $\to$ `margin-inline-start` / `margin-inline-end`
     * `padding-left` / `padding-right` $\to$ `padding-inline-start` / `padding-inline-end`
     * `left` / `right` $\to$ `inset-inline-start` / `inset-inline-end`
     * `text-align: left` $\to$ `text-align: start`
     * `border-left` $\to$ `border-inline-start`
   - Tailwind equivalents: `ms-*`/`me-*`, `ps-*`/`pe-*`, `start-*`/`end-*`, `text-start`/`text-end`, `rounded-s-*`/`rounded-e-*`, `border-s`/`border-e`.
   - Set `dir="rtl"` and `lang="fa"` (or `ar`, `he`) on `<html>`, not on individual blocks.
2. **Typography & Script Metrics**:
   - Ensure font families provide complete glyph coverage (e.g., Vazirmatn, IRANSans, Sahel, Noto Sans Arabic).
   - Arabic/Persian scripts require increased line-height ($\ge 1.6$ to $1.8$) due to vertical ascenders and diacritics.
3. **Directional Icons vs Universal Icons**:
   - Mirror directional icons (back/forward arrows, navigation chevrons, progress meters).
   - Do NOT mirror universal or non-directional icons (audio controls, search magnifying glasses, clock faces, checkmarks).
4. **Dynamic User-Generated Content**:
   - Apply `dir="auto"` on input fields and containers displaying mixed Persian/Latin text, phone numbers, or code tokens.
   - Keep phone numbers, IBANs, codes and URLs in an LTR island: `<span dir="ltr">…</span>` (or `unicode-bidi: isolate`).
5. **Numbers, Dates & Currency (Persian)**:
   - Format with `Intl.NumberFormat('fa-IR')` / `Intl.DateTimeFormat('fa-IR-u-ca-persian')` instead of hand-written conversions.
   - Accept both Persian (۰-۹) and Latin (0-9) digits in inputs and normalise before validation.
   - Use tabular figures (`font-variant-numeric: tabular-nums`) in tables and counters so columns align.

---

## 3. Cognitive & Sensory Accommodations

- **Reduced Motion**: Mandatory `@media (prefers-reduced-motion: reduce)` disabling non-essential kinetic loops and transitions.
- **Color Independence (SC 1.4.1)**: Never convey state (errors, warnings, critical vitals) through color alone; combine with icons, text badges, or patterned borders.
