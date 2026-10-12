# UX Patterns: Flows, Forms, States, Feedback and Content

Practical rules for the parts of a UI that decide whether users succeed, beyond visual style. Use with [component-contracts.md](component-contracts.md) and [review-checklist.md](review-checklist.md).

---

## 1. Flows and navigation

- Start from the user's task: list the steps a user takes to finish it, then design screens for those steps. Remove steps that do not move the task forward.
- One primary action per screen or section; secondary actions are visually quieter. Destructive actions are never the default button.
- Show where the user is: page title that matches the navigation label, active nav item marked with `aria-current="page"`, breadcrumbs for hierarchies deeper than two levels.
- Multi-step flows show progress ("Step 2 of 4"), keep entered data when going back, and allow saving drafts for long forms.
- Every flow has an exit: cancel, back, or close returns to a sensible place without losing unsaved data silently (confirm before discarding).

## 2. Forms

| Rule | Detail |
|---|---|
| Visible labels | Every field has a persistent `<label>`; placeholders are examples, not labels |
| Group related fields | `<fieldset>` + `<legend>` for radio groups and address blocks |
| Ask less | Remove optional fields that do not change the outcome; mark optional fields, not required ones, when most are required |
| Right input type | `type="email"`, `tel`, `number` only for quantities (not for IDs, phone numbers or card numbers), `autocomplete` tokens for personal data |
| Validate kindly | Validate on blur or submit, not on every keystroke; keep the user's input; say what is wrong and how to fix it ("Use 8 or more characters"), next to the field, linked with `aria-describedby` and `aria-invalid="true"` |
| Error summary | On submit with errors, show a summary at the top listing each error as a link to its field and move focus to it |
| Submission state | Disable double-submit, show progress on the button, confirm success with a message announced via `role="status"` |
| Persian input | Accept Persian and Latin digits, normalise before validation; use `dir="auto"` on free-text fields; keep phone numbers and codes LTR |

## 3. States

Design and implement every state that can occur; an empty or error screen designed by accident is a defect.

| State | Must provide |
|---|---|
| Loading | Skeleton or spinner with an accessible name; reserve space to avoid layout shift; for > 10 s show progress or explain |
| Empty (first use) | What this area is for and the first action to take |
| Empty (no results) | Echo the query/filters and offer to clear them |
| Error | Plain-language cause, what the user can do (retry, contact), no stack traces; keep user input |
| Partial | Show what loaded and mark what failed |
| Success | Confirm outcome; offer the next logical action |
| Offline / slow network | Explain, queue or retry when possible |
| No permission | Explain why the action is unavailable instead of hiding it silently when users expect it |

## 4. Feedback and timing

- Acknowledge every action within 100 ms (pressed state, spinner); show progress for anything over 1 s.
- Use toasts (`role="status"`) for non-critical confirmations, inline messages for errors, and dialogs only for decisions that block progress.
- Do not auto-dismiss messages that require action; give enough time to read others (at least 5 s, pause on hover/focus).
- Allow undo for destructive actions where possible instead of "Are you sure?" dialogs.

## 5. Content

- Write labels as verbs for actions ("Save changes", "Delete project"), nouns for navigation.
- Use the user's vocabulary, not internal system names.
- Keep error and empty-state text specific and short; avoid blame ("Invalid input" → "Enter a date after today").
- Numbers: units next to values, thousands separators by locale (`Intl.NumberFormat`), tabular figures in tables.
- Test with realistic content: long names, long translations (German/Persian), large numbers, missing images.

## 6. Data-dense screens (tables, dashboards)

- Sorting and filtering state is visible and reflected in the URL so views can be shared.
- Tables: sticky header for long lists, right-aligned numbers, row actions reachable by keyboard, `aria-sort` on sorted columns, horizontal scroll container that is focusable when it overflows.
- Dashboards: lead with the 3–5 numbers that drive decisions; every chart has a title, units, and a text alternative or data table.
