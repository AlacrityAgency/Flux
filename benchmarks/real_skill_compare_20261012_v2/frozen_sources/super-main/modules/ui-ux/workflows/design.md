# Workflow: Design Specification

Use when the user wants a design system, tokens, visual direction or component specifications without runnable code.
Shared rules: [core/reasoning.md](../../../core/reasoning.md) · [core/protocol.md](../../../core/protocol.md)

---

## 1. Intake

Establish [audience, purpose and medium](../../../core/task-framing.md) before visual direction.
For professional artifacts, review [content fit](../../product/references/professional-artifacts.md)
first; resume/portfolio/proposal content determines hierarchy before tokens or decoration.

1. Read the parameters (SKILL.md §2) from the request; use defaults otherwise.
2. Gather context in the retrieval order of [core/reasoning.md §6](../../../core/reasoning.md):
   - the project's existing tokens, theme and components first;
   - then `python3 <skill>/core/bin/sa.py search "<query>" --module ui-ux` (skip when `depth: quick`).
3. If the product belongs to a specialised domain (healthcare, fintech, industrial), identify its functional assets with [specialized-domains.md](../domains/specialized-domains.md) before choosing visuals.
4. If a Figma link is given, extract variables and layout with [integrations/figma.md](../integrations/figma.md).

## 2. Direction

- `creative_posture: utilitarian` or `depth: quick`: use the posture's baseline from [visual-direction.md](../references/visual-direction.md); no exploration step.
- `expressive`, `avant_garde`, or `depth: thorough`: compare two directions on one representative screen using the template in [visual-direction.md §2](../references/visual-direction.md), then pick one with a reason tied to the users' tasks.

## 3. Tokens

1. Write or update the token file. If the project already keeps tokens (CSS variables, Tailwind theme, an existing `tokens.json`), extend that source instead of creating a parallel one.
2. For a `tokens.json`, use the types supported by the validator: DTCG core types (`color`, `dimension`, `duration`, `cubicBezier`, `number`, `fontFamily`, `fontWeight`) plus the skill extensions `font-size`, `motion` and `surface-effect` (not part of DTCG; keep them only if the consuming tooling understands them).
3. List the text/background pairs the UI will use in a contrast-pairs file, for example:
   ```json
   [
     {"foreground": "color.text.primary", "background": "color.surface.base", "minRatio": 4.5},
     {"foreground": "color.text.primary", "background": "color.surface.glass", "over": "color.surface.base", "minRatio": 4.5},
     {"foreground": "color.border.input", "background": "color.surface.base", "minRatio": 3}
   ]
   ```
   Use `over` whenever the background is translucent: it names the opaque surface underneath.
4. Run the gate and fix every finding before continuing:
   ```bash
   python3 <skill>/core/bin/sa.py gate ui-ux.tokens -- --tokens <path>/tokens.json --contrast-pairs <path>/contrast-pairs.json
   ```
   Token structure, layers and scales: [tokens.md](../references/tokens.md).

## 4. Deliverable

- The token file and the gate result (command + exit code).
- Contrast table generated from the pairs above (≥ 4.5:1 body text, ≥ 3:1 large text and UI boundaries; 7:1 / 4.5:1 for AAA).
- Type scale, spacing scale and motion values, with the reduced-motion behaviour.
- Component specifications following [component-contracts.md](../references/component-contracts.md), with flows, forms and states from [ux-patterns.md](../references/ux-patterns.md).
- RTL notes when `language` is `fa`, `ar` or `he` ([accessibility-and-rtl.md §2](../references/accessibility-and-rtl.md)).
