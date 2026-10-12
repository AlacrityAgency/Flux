# Visual Direction & Creative Posture Architecture

Start with the user's product, domain requirements, and current design conventions. For new work, benchmark relevant industry leaders on task flow, information density, typography, imagery, and interaction. Ground every decision in user tasks and empirical accessibility criteria rather than copying arbitrary external aesthetics.

---

## 1. Visual Posture Matrix (`creative_posture`)

Visual direction is governed by a three-tiered posture matrix:

### A. `utilitarian` (Enterprise Density & Zero Noise)
- **Design Philosophy**: High cognitive efficiency, maximum data density, deterministic predictability.
- **Application**: Mission-critical enterprise tools, medical charting, trading desks, CAD/CAM interfaces, SCADA monitors.
- **Strict Prohibition**:
  > **Strictly prohibit arbitrary decorative trends**: No ungrounded bento grids, no decorative spotlight glow or bloom effects, no frosted glass surfaces, and no oversized marketing hero sections on operational dashboards.
- **Visual Baseline**: High contrast text ratios ($\ge 7:1$ preferred), crisp 1px borders (`border-slate-800`), compact spacing units (4px/8px increments), and standard native control semantics.

---

### B. `expressive` (Modern SaaS & Fluid Polish - Modular Archetypes)
- **Design Philosophy**: Refined craft, intentional visual hierarchy, fluid micro-interactions, and purposeful character.
- **Application**: Modern developer tools, creative software, analytics suites, consumer fintech, collaborative platforms.
- **Flexible Archetypes (Modular Suggestions - Adapt to Product Context)**:
  - *Editorial & Typography-First*: Expressive typographic scales (fluid clamp or modular scale), high-contrast headers, refined body typography.
  - *Warm Organic / Tactile*: Humanist color palettes, soft rounded surfaces, gentle elevation, and micro-delights.
  - *Technical Modernist & Light Brutalist*: Monospace accents, crisp border grids, stark high-contrast typography, high-density metric readouts, and silky smooth transitions.
- **Key Principles**:
  - Treat postures as modular starting archetypes rather than rigid dogmatic rules. Light-mode, dark-mode, minimal brutalist, or rich tactile aesthetics are all valid when aligned with the domain.
  - Purposeful elevation and hierarchy rather than flat monotony.
  - Fluid, responsive micro-interactions (e.g., cubic-bezier button press transitions, animated state changes).
  - Typography chosen to elevate product character while strictly preserving readability.

---

### C. `avant_garde` (Kinetic Choreography & Structural Innovation - Modular Archetypes)
- **Design Philosophy**: High-impact architectural daring, unconventional spatial systems, atmospheric composition, and bold expression.
- **Application**: AI creative studios, design showcases, luxury/editorial digital experiences, next-generation spatial tools.
- **Flexible Archetypes (Modular Suggestions - Adapt to Product Context)**:
  - *Atmospheric Luminance*: Deep obsidian or twilight canvases with directional specular highlights and localized glassmorphic panels.
  - *Stark Architectural / Neo-Brutalist Light*: Light-mode or stark monochrome layouts with massive structural gridlines, brutalist borders, monospaced data density, and high-impact typographic contrast.
  - *Sculptural & Asymmetric*: Expansive negative space contrasted with hyper-dense control clusters, breaking conventional symmetry while maintaining flawless keyboard navigation.
- **Key Principles**:
  - Daring compositional rhythm that surprises without confusing user workflows.
  - Thoughtful kinetic choreography that gives the UI physical presence and momentum.
  - Never sacrifice utility or accessibility for novelty.

---

## 2. Dual-Direction Comparison

Required when `creative_posture` is `expressive` or `avant_garde`, or when `depth: thorough`. Optional for `utilitarian` work. Compare two contrasting directions on one representative screen before implementation:

```markdown
### Architectural Direction Exploration
- **Domain**: [Target Domain / Application]
- **Creative Posture**: [expressive | avant_garde | utilitarian]

#### Direction A (Refined Modern / Structural Discipline)
- Composition & Grid: [Layout hierarchy, layout structure, spatial rhythm]
- Typography & Density: [Type family, scale, density]
- Surfaces, Color & Borders: [Palette model, border treatment, elevation]

#### Direction B (Expressive / Asymmetric / Tactile Daring)
- Composition & Grid: [Alternative layout structure, focal emphasis]
- Typography & Density: [Contrasting typographic voice, display weights]
- Surfaces, Color & Borders: [Alternative materials, atmospheric depth, kinetic touches]

#### Selected Direction & Rationale
- **Chosen Direction**: Direction [A | B]
- **Justification**: [Concrete alignment with user workflows, cognitive ergonomics, and domain goals]
```

---

## 3. Hard Accessibility Guardrails for `expressive` & `avant_garde`

Creative freedom must **never compromise accessibility compliance (WCAG 2.1/2.2 AA & AAA)**. When implementing expressive or avant-garde designs, the AI must strictly adhere to these three non-negotiable architectural guardrails:

### Guardrail 1: Deterministic Surface Scrims (Contrast Guarantee)
Any text, icon, or interactive control placed over glassmorphism (`backdrop-filter`), luminous gradients, or ambient meshes **MUST be backed by a deterministic contrast scrim**:
- Layer a mathematical alpha scrim behind text (e.g., `background: linear-gradient(180deg, rgba(15,23,42,0.85) 0%, rgba(15,23,42,0.95) 100%)`).
- Prove the contrast with the tokens gate: add a contrast pair whose `background` is the scrim token and whose `over` is the lightest surface that can appear underneath (the worst case). Required: ≥ 4.5:1 body text, ≥ 3:1 large text and UI boundaries.
- Never place body text directly over variable, un-scrimmed gradient or image backgrounds.

### Guardrail 2: Pure Decorator Isolation (`aria-hidden` & `pointer-events-none`)
Experimental visual meshes, ambient glow orbs, generative canvas backgrounds, SVG noise/grain overlays, or floating particles must be isolated from the accessibility and interaction trees:
- **Mandatory Attributes**: Every purely decorative canvas, SVG mesh, or background graphic MUST include:
  ```html
  <div class="pointer-events-none select-none" aria-hidden="true">
    <!-- Kinetic or atmospheric decoration -->
  </div>
  ```
- Decorative elements must never intercept mouse clicks, touch gestures, or keyboard focus, nor clutter screen reader navigation.

### Guardrail 3: Mandatory Reduced Motion Fallback
All kinetic choreographies, spring physics, continuous loops, or dynamic layout shifts MUST provide an accessible fallback for users with vestibular sensitivities:
```css
@media (prefers-reduced-motion: reduce) {
  *, ::before, ::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```
State changes must complete instantly when reduced motion is requested, maintaining full functional parity without vestibular disorientation.
