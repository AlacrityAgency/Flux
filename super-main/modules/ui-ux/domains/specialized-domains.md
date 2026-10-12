# Domain Semantics & Entity Taxonomy (Eliminating Semantic Hallucinations)

This reference defines the strict ontological reality and visual asset rules for specialized domains (Healthcare/Medicine, Dental, Biotech, Fintech, Industrial/SCADA). It serves as the primary safeguard against **Semantic Hallucinations** and **Domain Association Errors** (e.g., placing staff portraits instead of radiographic scans like OPG).

---

## 1. Domain Entity & Asset Classification Taxonomy

Every visual asset and data display in a UI mock-up belongs to a strict ontological entity category. The AI must enforce physical fidelity for each category:

### A. `diagnostic_asset / radiology_scan`
- **Definition**: Objective radiological, imaging, or laboratory diagnostic records.
  - *Examples*: OPG (Orthopantomogram / Dental Panoramic X-ray), CBCT (Cone Beam CT), Bitewing, Periapical, MRI, CT scan slices, Chest X-ray, Ultrasound, Histology slides, Retinal OCT.
- **Physical Reality & Visual Form**:
  - Rendered **strictly in grayscale / radiographic monochrome** on a deep charcoal/black canvas (`#000000` or `#0b0f19`) simulating a DICOM viewport or radiograph illuminator.
  - Must display anatomical/structural landmarks (e.g., for dental: mandibular arch, roots, crowns, bone crest; for chest: ribcage, cardiac silhouette, lung fields).
  - Include medical viewport chrome: Window/Level (contrast/brightness) sliders, measurement scale / calibration ruler (mm), pan/zoom controls, invert toggle, and orientation markers (R/L).
- **STRICT PROHIBITION**:
  > **NEVER represent a diagnostic scan with human face portraits, clinic exterior/interior stock photos, smiling patients, or doctor headshots.**

---

### B. `personnel_profile`
- **Definition**: Medical staff, clinicians, technicians, or patient profile identities.
  - *Examples*: Attending Dentist (DDS), Radiologist (MD), Dental Hygienist, Patient Identity.
- **Physical Reality & Visual Form**:
  - Compact circular avatar, professional badge, initials token (`JD`), credential chips (`DDS`, `FACS`), specialty labels, and availability status indicators.
- **Placement Boundary**:
  - Confined strictly to appointment cards, header profile menus, clinician assignment badges, and signature blocks. Never place inside imaging viewports or diagnostic viewer canvases.

---

### C. `clinical_metric / telemetry`
- **Definition**: Dynamic physiological measurements, continuous telemetry, or laboratory assays.
  - *Examples*: Heart rate waveform (ECG), SpO2 pulse oximetry, blood pressure trend, periodontal pocket depth charting (mm), HbA1c values.
- **Physical Reality & Visual Form**:
  - Live SVG/Canvas waveform sweeps, clean time-series sparklines, high-density tabular matrices with explicit clinical units (`bpm`, `mmHg`, `mg/dL`, `mm`).
  - Standardized alert levels with dual indicators (color + symbol/icon, complying with WCAG non-color dependency).

---

### D. `device_hardware / operatory_asset`
- **Definition**: Physical medical, dental, or laboratory equipment.
  - *Examples*: Panoramic X-ray machine, Autoclave sterilizer, Intraoral 3D scanner, Dental chair unit, Infusion pump.
- **Physical Reality & Visual Form**:
  - Schematic line diagrams, isometric hardware illustrations, hardware status telemetry (Online, Calibrating, Cycle 4, Error E-04), maintenance logs.

---

### E. `financial_ledger / fintech_asset`
- **Definition**: Order books, transaction journals, portfolio balances, execution logs.
- **Physical Reality & Visual Form**:
  - Tabular high-density grids, tabular numerals (`font-variant-numeric: tabular-nums`), candlestick charts with volume bars, order depth charts.
  - **PROHIBITION**: Never use photos of cash, gold bars, or handshake stock imagery.

---

## 2. Deterministic Mock Asset Fallback: Structured SVG over Stock Photos

For specialized domains, **external stock photo URLs (e.g. Unsplash, generic placeholder image services) are strictly prohibited** for functional assets. Stock libraries inevitably return smiling models, clinic lobbies, or irrelevant generic stock imagery.

Instead, the AI must generate **deterministic, semantic SVG placeholders or canvas wireframes**:

### Example: Panoramic Radiograph (OPG) SVG Mock Asset

Illustrative structure only. In a real project replace the palette classes with the project's tokens, keep HUD text at ≥ 4.5:1, give the SVG `role="img"` and an `aria-label` describing the study, and label every viewer control.

```html
<div class="relative w-full aspect-[2/1] bg-black rounded-lg border border-slate-800 overflow-hidden flex flex-col justify-between p-3 select-none">
  <!-- Viewport HUD Overlay -->
  <div class="flex items-center justify-between text-xs font-mono text-emerald-400/90 z-10">
    <span>STUDY: OPG PANORAMIC</span>
    <span>FOV: 15x9 cm | 85 kV / 10 mA</span>
    <span>R <span class="text-slate-500">|</span> L</span>
  </div>

  <!-- Simulated Radiographic Jaw Arch SVG -->
  <svg role="img" aria-label="Simulated panoramic dental radiograph" viewBox="0 0 400 200" class="absolute inset-0 w-full h-full opacity-80 pointer-events-none" preserveAspectRatio="xMidYMid meet">
    <!-- Mandibular & Maxillary Bone Density Gradients -->
    <defs>
      <radialGradient id="boneGlow" cx="50%" cy="50%" r="50%">
        <stop offset="0%" stop-color="#ffffff" stop-opacity="0.35"/>
        <stop offset="60%" stop-color="#a0aec0" stop-opacity="0.15"/>
        <stop offset="100%" stop-color="#000000" stop-opacity="0"/>
      </radialGradient>
    </defs>
    <!-- Background Anatomical Bone Arc -->
    <path d="M 50 160 Q 200 190 350 160" stroke="#718096" stroke-width="12" fill="none" opacity="0.4" stroke-linecap="round"/>
    <path d="M 70 80 Q 200 50 330 80" stroke="#718096" stroke-width="10" fill="none" opacity="0.3" stroke-linecap="round"/>
    <!-- Tooth Root & Crown Clusters (Simulated Radiopacity) -->
    <path d="M 80 140 Q 200 165 320 140" stroke="#e2e8f0" stroke-width="6" stroke-dasharray="8 4" fill="none" opacity="0.7"/>
    <path d="M 90 95 Q 200 80 310 95" stroke="#edf2f7" stroke-width="7" stroke-dasharray="9 3" fill="none" opacity="0.8"/>
    <!-- Midline soft-tissue / spine shadow (ghost image typical of panoramic radiographs) -->
    <path d="M 170 30 L 170 180 M 230 30 L 230 180" stroke="#4a5568" stroke-width="20" opacity="0.25" filter="blur(4px)"/>
  </svg>

  <!-- Viewport Tooling Footer -->
  <div class="flex items-center justify-between text-xs font-mono text-slate-400 z-10">
    <div class="flex gap-2">
      <span class="px-1.5 py-0.5 bg-slate-900 border border-slate-700 rounded text-slate-300">W: 2400</span>
      <span class="px-1.5 py-0.5 bg-slate-900 border border-slate-700 rounded text-slate-300">L: 600</span>
      <span class="px-1.5 py-0.5 bg-slate-900 border border-slate-700 rounded text-slate-300">MAG: 1.0x</span>
    </div>
    <span class="text-slate-400">SIMULATED • NOT A DIAGNOSTIC IMAGE</span>
  </div>
</div>
```

---

## 3. Disambiguation Checklist for the AI

Before generating UI for any domain entity:
1. **Name & Acronym Lookup**: What does this acronym stand for in this industry? (e.g. OPG = Orthopantomogram; CBCT = Cone Beam Computed Tomography; P&ID = Piping and Instrumentation Diagram).
2. **Physical Reality**: Is this a photo of a person, a machine, an electronic graph, or a radiographic slice?
3. **Canvas Constraints**: Does this asset require darkroom illuminator styling, calibration crosshairs, unit dimensions, or clinical controls?
4. **Zero-Stock Enforcement**: Replace any external photo URL with a semantic SVG or styled component viewport.
