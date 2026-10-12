// @ts-check
// Interaction gate spec: measured target sizes and a real keyboard walk.
// Run through modules/ui-ux/gates/interaction.py. Environment as in a11y.spec.js, plus:
//   A11Y_LEVEL  AA (default) or AAA: at AAA, mobile targets below 44x44 px are violations.
const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { pathToFileURL } = require('url');

const MOUNT_SELECTOR = '#root > *, [data-component-root] > *';
const targetUrl = process.env.TARGET_URL;
const sandboxPath = process.env.SANDBOX_PATH;
const resultsDir = process.env.A11Y_RESULTS_DIR;
const mountTimeout = Number(process.env.MOUNT_TIMEOUT_MS || 15000);
const level = (process.env.A11Y_LEVEL || 'AA').toUpperCase();

async function open(page, pageErrors) {
  if (sandboxPath) {
    await page.goto(pathToFileURL(sandboxPath).href, { waitUntil: 'domcontentloaded' });
    const deadline = Date.now() + mountTimeout;
    while (Date.now() < deadline) {
      if (pageErrors.length) throw new Error(`Sandbox threw before mounting:\n${pageErrors.join('\n')}`);
      if ((await page.locator(MOUNT_SELECTOR).count()) > 0) return;
      await page.waitForTimeout(100);
    }
    throw new Error(`Sandbox did not render inside #root within ${mountTimeout}ms.`);
  }
  await page.goto(/** @type {string} */ (targetUrl), { waitUntil: 'load' });
  await page.waitForLoadState('networkidle', { timeout: 10000 }).catch(() => {});
}

/** Runs in the page: tag interactive elements, measure them, apply SC 2.5.8 (24px or spacing). */
function measureTargets(isMobile) {
  const SELECTOR = 'a[href], button, input:not([type="hidden"]), select, textarea, summary, [role="button"], [role="link"], [role="checkbox"], [role="radio"], [role="switch"], [role="tab"], [role="menuitem"], [role="option"], [tabindex]:not([tabindex="-1"]), [contenteditable="true"]';
  const describe = (el) => {
    if (el.id) return `${el.tagName.toLowerCase()}#${el.id}`;
    const label = (el.getAttribute('aria-label') || el.textContent || el.getAttribute('name') || '').trim().replace(/\s+/g, ' ').slice(0, 30);
    const cls = typeof el.className === 'string' && el.className.trim() ? '.' + el.className.trim().split(/\s+/).slice(0, 2).join('.') : '';
    return `${el.tagName.toLowerCase()}${cls}${label ? ` "${label}"` : ''}`;
  };
  const visible = (el) => {
    const r = el.getBoundingClientRect();
    const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none' && !el.closest('[inert], [aria-hidden="true"]');
  };
  const inlineLink = (el) => {
    if (el.tagName !== 'A' || getComputedStyle(el).display !== 'inline') return false;
    const parent = el.parentElement;
    return !!parent && Array.from(parent.childNodes).some((n) => n !== el && n.nodeType === 3 && n.textContent.trim().length > 0);
  };
  const elements = Array.from(document.querySelectorAll(SELECTOR)).filter((el) => visible(el) && !el.disabled);
  elements.forEach((el, i) => el.setAttribute('data-sa-id', String(i)));
  const rects = elements.map((el) => el.getBoundingClientRect());
  const center = (r) => ({ x: r.left + r.width / 2, y: r.top + r.height / 2 });
  const distToRect = (p, r) => Math.hypot(Math.max(r.left - p.x, 0, p.x - r.right), Math.max(r.top - p.y, 0, p.y - r.bottom));

  const undersized = new Set(rects.map((r, i) => (r.width < 24 || r.height < 24) && !inlineLink(elements[i]) ? i : -1).filter((i) => i >= 0));
  const minimum = [];
  for (const i of undersized) {
    const c = center(rects[i]);
    // SC 2.5.8 spacing exception: a 24px circle centred on the target must not intersect another
    // target or the circle of another undersized target.
    const conflict = rects.some((r, j) => j !== i && (distToRect(c, r) < 12 || (undersized.has(j) && Math.hypot(c.x - center(r).x, c.y - center(r).y) < 24)));
    if (conflict) minimum.push({ target: describe(elements[i]), width: Math.round(rects[i].width), height: Math.round(rects[i].height) });
  }
  const touch = isMobile
    ? rects.map((r, i) => ({ r, i })).filter(({ r, i }) => (r.width < 44 || r.height < 44) && !inlineLink(elements[i]))
        .map(({ r, i }) => ({ target: describe(elements[i]), width: Math.round(r.width), height: Math.round(r.height) }))
    : [];
  const positiveTabindex = elements.filter((el) => Number(el.getAttribute('tabindex')) > 0).map(describe);
  const expectedTabbable = elements
    .filter((el) => el.tabIndex >= 0 && !(el.tagName === 'INPUT' && el.type === 'radio' && !el.checked && document.querySelector(`input[type="radio"][name="${el.name}"]:checked`)))
    .map((el) => el.getAttribute('data-sa-id'));
  const notFocusable = elements.filter((el) => el.tabIndex < 0 && el.getAttribute('role')).map(describe);
  return { checked: elements.length, minimum, touch, positiveTabindex, expectedTabbable, notFocusable };
}

/** Runs in the page: style snapshot used to decide whether focus is visible. */
function focusStyle(id) {
  const el = document.querySelector(`[data-sa-id="${id}"]`);
  if (!el) return null;
  const s = getComputedStyle(el);
  return [s.outlineStyle, s.outlineWidth, s.outlineColor, s.boxShadow, s.borderTopColor, s.borderBottomColor, s.borderTopWidth, s.backgroundColor, s.color, s.textDecorationLine].join('|');
}

/** Runs in the page: is the focused element at least partly visible (not covered by sticky UI)? */
function focusedState() {
  const el = document.activeElement;
  if (!el || el === document.body) return { id: null };
  const r = el.getBoundingClientRect();
  const s = getComputedStyle(el);
  const outline = s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) > 0;
  const points = [[r.left + r.width / 2, r.top + r.height / 2], [r.left + 2, r.top + 2], [r.right - 2, r.top + 2], [r.left + 2, r.bottom - 2], [r.right - 2, r.bottom - 2]];
  const uncovered = points.some(([x, y]) => {
    if (x < 0 || y < 0 || x > innerWidth || y > innerHeight) return false;
    const hit = document.elementFromPoint(x, y);
    return !!hit && (hit === el || el.contains(hit) || hit.contains(el));
  });
  return { id: el.getAttribute('data-sa-id'), tag: el.tagName.toLowerCase(), label: (el.getAttribute('aria-label') || el.textContent || '').trim().slice(0, 30), outline, obscured: !uncovered };
}

test('interaction gate', async ({ page }, testInfo) => {
  if (!targetUrl && !sandboxPath) throw new Error('NOT-TESTED: set TARGET_URL or SANDBOX_PATH (use interaction.py).');
  const pageErrors = [];
  page.on('pageerror', (err) => pageErrors.push(err.message));
  await open(page, pageErrors);

  const isMobile = testInfo.project.name === 'mobile';
  const targets = await page.evaluate(measureTargets, isMobile);
  // Keyboard checks run once, on the desktop viewport.
  const keyboard = { reached: 0, unreachable: [], focusNotVisible: [], obscured: [], trap: null,
    positiveTabindex: isMobile ? [] : targets.positiveTabindex, notFocusable: isMobile ? [] : targets.notFocusable };

  if (!isMobile) {
    const baseline = {};
    for (const id of targets.expectedTabbable) baseline[id] = await page.evaluate(focusStyle, id);
    await page.evaluate(() => { if (document.activeElement instanceof HTMLElement) document.activeElement.blur(); });
    const seen = new Set();
    let previous = null;
    let repeats = 0;
    const maxPresses = Math.min(400, targets.expectedTabbable.length * 2 + 10);
    for (let i = 0; i < maxPresses; i++) {
      await page.keyboard.press('Tab');
      const state = await page.evaluate(focusedState);
      if (!state.id) {
        if (seen.size > 0) break; // focus left the document: one full cycle done
        continue;
      }
      if (state.id === previous) {
        repeats += 1;
        if (repeats >= 3) { keyboard.trap = `${state.tag} "${state.label}"`; break; }
        continue;
      }
      repeats = 0;
      previous = state.id;
      if (seen.has(state.id)) break; // cycled back to the start
      seen.add(state.id);
      const focused = await page.evaluate(focusStyle, state.id);
      if (!state.outline && focused === baseline[state.id]) keyboard.focusNotVisible.push(`${state.tag} "${state.label}"`);
      if (state.obscured) keyboard.obscured.push(`${state.tag} "${state.label}"`);
    }
    keyboard.reached = seen.size;
    if (!keyboard.trap) {
      const missing = targets.expectedTabbable.filter((id) => !seen.has(id));
      for (const id of missing.slice(0, 20)) {
        keyboard.unreachable.push(await page.evaluate((x) => {
          const el = document.querySelector(`[data-sa-id="${x}"]`);
          return el ? `${el.tagName.toLowerCase()} "${(el.getAttribute('aria-label') || el.textContent || '').trim().slice(0, 30)}"` : x;
        }, id));
      }
    }
  }

  const payload = { level, targets: { checked: targets.checked, minimum: targets.minimum, touch: targets.touch }, keyboard, pageErrors };
  if (resultsDir) {
    fs.mkdirSync(resultsDir, { recursive: true });
    fs.writeFileSync(path.join(resultsDir, `${testInfo.project.name}.json`), JSON.stringify(payload, null, 2));
  }
  expect(pageErrors, 'uncaught page errors').toEqual([]);
});
