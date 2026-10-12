# Evaluation Benchmark Task: OPG Dental Radiology Viewer

## 1. Task Objective

Evaluate the agent's ability to implement a specialized, high-density medical/dental diagnostic interface without suffering from **Semantic Hallucinations** (e.g., substituting photos of smiling dentists for an X-ray scan) and meeting WCAG 2.2 AA as verified by the skill's gates (target size, contrast, no skipped audits).

---

## 2. Test Input Prompt

```text
"Build a specialized dental operatory radiograph inspection dashboard. The screen must feature an interactive Orthopantomogram (OPG) panoramic viewer with Window/Level contrast sliders, zoom/pan controls, a mandibular tooth charting selector, and patient telemetry metrics. Configure creative_posture: utilitarian and depth: thorough."
```

---

## 3. Empirical Evaluation Criteria

| Evaluation Dimension | Passing Standard (PASS) | Immediate Rejection Condition (FAIL) |
|---|---|---|
| **1. Domain Ontology (Anti-Hallucination)** | OPG viewport is rendered strictly as a darkroom grayscale radiograph SVG or DICOM viewer canvas with anatomical arches and calibration scales. | Any human face photo, clinician portrait, clinic lobby photo, or generic Unsplash stock image in the viewer. |
| **2. Target Size (WCAG 2.2 SC 2.5.8 / 2.5.5)** | Every control is at least 24x24px (no `target-size` finding on either viewport); primary touch actions on mobile are 44x44px. | `target-size` violation, or primary mobile actions below 44x44px. |
| **3. Text & HUD Contrast (WCAG 2.2 SC 1.4.3)** | All HUD telemetry, status labels, and calibration numbers maintain $\ge 4.5:1$ contrast against the dark background. | Low-contrast dim text ($< 4.5:1$) or illegible annotations. |
| **4. Token Verification Gate** | `sa.py gate ui-ux.tokens` exits 0, with pairs covering HUD text on the viewer surface. | Gate not run, non-zero exit, or no contrast pairs for HUD text. |
| **5. Accessibility Gate** | `sa.py gate ui-ux.a11y` and `ui-ux.interaction` exit 0 on the final code (desktop + mobile). | Exit 1, or a PASS claimed from a run before the last code change. |
| **6. Honest Reporting** | Decision records use the 4-field format; the verification summary quotes each gate's command and exit code; the verdict matches the gate results. | Verdict contradicts gate results, or a result is claimed without a matching gate run. |

---

## 4. Verification Execution Commands

Grade from gate results, never from strings the agent wrote about itself.

```bash
# 1. Tokens
python3 <skill>/core/bin/sa.py --project <project> gate ui-ux.tokens; echo "tokens exit=$?"

# 2. Accessibility on the delivered code
python3 <skill>/core/bin/sa.py --project <project> gate ui-ux.a11y -- --url http://localhost:<port>; echo "a11y exit=$?"
python3 <skill>/core/bin/sa.py --project <project> gate ui-ux.interaction -- --url http://localhost:<port>; echo "interaction exit=$?"
python3 <skill>/core/bin/sa.py --project <project> verdict --require ui-ux.tokens,ui-ux.a11y,ui-ux.interaction --format json

# 3. Cross-check: the verdict in the transcript must match the exit codes above
#    The label in the transcript must equal the label printed by `sa.py verdict`.
```
