# Design Tokens

How to structure tokens so they are portable, verifiable by `ui-ux.tokens`, and enforced by `ui-ux.token-drift`.

---

## 1. Where tokens live

Use the project's existing source of truth; do not create a parallel one.

| Project has | Source of truth | Gate |
|---|---|---|
| `tokens.json` (DTCG) | the JSON file, compiled to CSS variables/Tailwind theme by a build step | `ui-ux.tokens` + `ui-ux.token-drift` |
| CSS custom properties (`:root { --primary: … }`) | the CSS file that defines them | `ui-ux.token-drift` (tokens gate is NOT-TESTED) |
| Tailwind theme / shadcn variables | `tailwind.config.*` + the CSS variables it references | `ui-ux.token-drift` |

## 2. Three layers

1. **Primitive** (raw palette and scales): `color.blue.600`, `space.4`, `font.size.300`. Never used directly by components.
2. **Semantic** (meaning): `color.text.primary`, `color.surface.base`, `color.border.input`, `color.action.primary.bg`. Components use these.
3. **Component** (optional, only where a component deviates): `button.primary.bg` → aliases a semantic token.

Dark mode and brands swap semantic aliases, not component code.

## 3. DTCG format (what the validator accepts)

```json
{
  "color": {
    "$type": "color",
    "blue": { "600": { "$value": { "colorSpace": "srgb", "components": [0.114, 0.306, 0.847], "hex": "#1d4ed8" } } },
    "text": { "primary": { "$value": { "colorSpace": "oklch", "components": [0.22, 0.02, 250] } } },
    "action": { "primary": { "bg": { "$value": "{color.blue.600}" } } }
  },
  "space": { "$type": "dimension", "4": { "$value": { "value": 16, "unit": "px" } } },
  "duration": { "$type": "duration", "fast": { "$value": { "value": 150, "unit": "ms" } } },
  "easing": { "$type": "cubicBezier", "standard": { "$value": [0.2, 0, 0, 1] } }
}
```

- Core DTCG types accepted: `color` (srgb/oklch, optional `hex` that must match the components), `dimension` (px/rem), `duration` (ms/s), `cubicBezier`, `number`, `fontFamily`, `fontWeight`; aliases `{path.to.token}`.
- Skill extension types (not DTCG; keep only if your build understands them): `font-size` (length or `clamp(min, ideal, max)` with min ≤ max), `motion` (`{duration, easing}`, values may be aliases), `surface-effect` (`blur`, `saturation`, `noise`, `backdropFilter`, `scrim`).
- Unsupported DTCG features (`$extends`, composite `typography`/`shadow` types) fail with an explicit message; handle them with your DTCG build tool.

## 4. Contrast pairs

List every text/background and boundary/background combination the UI uses in `contrast-pairs.json` next to the tokens:

```json
[
  {"foreground": "color.text.primary", "background": "color.surface.base", "minRatio": 4.5},
  {"foreground": "color.text.primary", "background": "color.surface.glass", "over": "color.surface.base", "minRatio": 4.5},
  {"foreground": "color.border.input", "background": "color.surface.base", "minRatio": 3}
]
```

`over` names the opaque surface under a translucent background (worst case: the lightest or darkest surface that can appear there). Without it, translucent pairs cannot be verified.

## 5. Scales that work

- Spacing: 4 px base (4, 8, 12, 16, 24, 32, 48, 64).
- Type: a modular scale (e.g. 1.2 or 1.25), body ≥ 16 px on mobile; Persian/Arabic body line-height 1.6–1.8.
- Radii and elevation: 3–5 steps each; more steps become noise.
- Motion: 100–300 ms for UI transitions, with reduced-motion alternatives.

## 6. Preventing drift

Run `ui-ux.token-drift` in review. On an existing codebase, record today's state once with `-- --update-baseline`; from then on only new hardcoded values fail, and the baseline can be lowered as legacy code is cleaned up.
