# Claim Review: Status Taxonomy and Questions for Meaning

## 1. Status taxonomy for documents

Every metric or feature a document mentions should carry one of these labels, matching the code:

| Label | Use when | Allowed wording |
|---|---|---|
| **Active** | computed in production and used as described | "measures", "computes", "uses" |
| **Research** | computed but excluded from scores/decisions, or not validated | "recorded for research; not used in scoring" |
| **Not measured** | the system cannot measure it (sampling rate, sensor, missing data) | "not measured in this version, because …" |
| **Planned** | not implemented yet | "planned" |
| **Removed** | existed before, no longer in the code | "removed in version …" |

A document that presents research, not-measured or absent items as active features is misleading, even when the code itself is honest about them.

## 2. Questions for meaning (construct validity)

Ask for every active metric that drives a score, alert or decision:

1. **Quantity**: what does the code physically compute? (position, angle, rate, ratio, image-intensity estimate …) Point to file:line.
2. **Unit and name**: does the name match? A value in g is an acceleration, not a force; a standard deviation is not a variance; a "speed" that is always NaN on a path is not measured there.
3. **Sampling**: can the sensor and sampling rate observe the phenomenon? A ~2 Hz tracker cannot measure a 4–10 Hz tremor (Nyquist).
4. **Reference**: compared with what? The same person's baseline, a site-specific reference set, or a validated healthy population? The document must say which.
5. **Inference**: does the claimed cause (stress, drug effect, concealment, deception) follow from the measurement, or only correlate in theory? A plausible mechanism is not evidence of detection performance.
6. **Validation**: is there a study with sample size, sensitivity, specificity (or error rates), and an independent test set? Without it, claims of reliability or "hard to fake" are unverified.
7. **Sources**: are physiological or clinical statements cited and correctly summarised? (e.g. eccrine sweating is driven mainly by sympathetic *cholinergic* fibres.)

## 3. Writing the finding

- Tie each finding to one claim, the document location (page/section) and code evidence (file:line).
- Say exactly which part is unsupported (name, unit, sampling, reference, inference or validation).
- Distinguish **false** (contradicted by code or physics) from **unverified** (no evidence either way). Unverified is a question, not a defect.
- Propose the honest wording or the evidence that would settle it.

## 4. What the gate cannot do

`claims.trace` reads identifiers and container names. It cannot judge scientific meaning, read figures or tables rendered as images, or follow claims that do not name a code identifier ("we compare everyone with a healthy population"). Those need the questions in §2 and, for external science, sources checked under [core/reasoning.md §6–7](../../../core/reasoning.md).
