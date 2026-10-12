const { test, expect } = require('@playwright/test');
const fs = require('fs');
const path = require('path');
const { pathToFileURL } = require('url');

test('document and nested scroll coverage', async ({ page }, testInfo) => {
  test.setTimeout(240000);
  const out = process.env.A11Y_RESULTS_DIR;
  if (!out || (!process.env.TARGET_URL && !process.env.SANDBOX_PATH)) throw new Error('No coverage target/output');
  const maxSteps = Number(process.env.COVERAGE_MAX_STEPS || 30);
  const maxRegions = Number(process.env.COVERAGE_MAX_REGIONS || 12);
  const settle = Number(process.env.COVERAGE_SETTLE_MS || 300);
  const target = process.env.TARGET_URL || pathToFileURL(process.env.SANDBOX_PATH).href;
  const pageErrors = [];
  page.on('pageerror', error => pageErrors.push(error.message));
  fs.mkdirSync(out, { recursive: true });
  const payload = { target, viewport: page.viewportSize(), regions: [], screenshots: [], horizontalOverflow: [], gaps: [], pageErrors };
  await page.goto(target, { waitUntil: 'load' });
  if (process.env.SANDBOX_PATH) {
    await page.locator('#root > *, [data-component-root] > *').first().waitFor({ timeout: Number(process.env.MOUNT_TIMEOUT_MS || 15000) });
  }
  await page.waitForTimeout(settle);

  async function traverse(selector, label, capture) {
    if (selector) await page.locator(selector).scrollIntoViewIfNeeded();
    await page.evaluate(selector => {
      const node = selector ? document.querySelector(selector) : document.scrollingElement;
      if (node) node.scrollTop = 0;
    }, selector);
    let previousHeight = -1, stableBottom = 0, complete = false;
    const samples = [];
    for (let step = 0; step < maxSteps; step++) {
      await page.waitForTimeout(settle);
      const sample = await page.evaluate(selector => {
        const node = selector ? document.querySelector(selector) : document.scrollingElement;
        if (!node) return null;
        return { top: node.scrollTop, height: node.scrollHeight, viewport: node.clientHeight,
          width: node.scrollWidth, clientWidth: node.clientWidth };
      }, selector);
      if (!sample || sample.viewport <= 0) break;
      samples.push(sample);
      if (sample.width > sample.clientWidth + 2) payload.horizontalOverflow.push({ region: label, ...sample });
      if (capture) {
        const name = `${testInfo.project.name}-${label}-${step}.png`;
        await page.screenshot({ path: path.join(out, name), animations: 'disabled' });
        payload.screenshots.push(name);
      }
      const bottom = sample.top + sample.viewport >= sample.height - 2;
      stableBottom = bottom && sample.height === previousHeight ? stableBottom + 1 : 0;
      previousHeight = sample.height;
      if (stableBottom >= 2) { complete = true; break; }
      await page.evaluate(selector => {
        const node = selector ? document.querySelector(selector) : document.scrollingElement;
        if (node) node.scrollTop += Math.max(1, node.clientHeight * 0.75);
      }, selector);
    }
    if (!complete) payload.gaps.push(`${label}: did not reach a stable end within ${maxSteps} steps`);
    return { label, complete, samples };
  }

  // First reveal lazy content, then capture it from the top of the updated document.
  payload.regions.push(await traverse(null, 'reveal', false));
  payload.regions.push(await traverse(null, 'document', true));
  const regions = await page.evaluate(() => {
    const found = [];
    for (const node of document.querySelectorAll('body *')) {
      const style = getComputedStyle(node);
      const rect = node.getBoundingClientRect();
      if (node.clientHeight > 0 && rect.width > 0 && rect.height > 0 && node.scrollHeight > node.clientHeight + 2 && /auto|scroll/.test(style.overflowY)) {
        const label = `nested-${found.length}`;
        node.setAttribute('data-sa-scroll-region', label);
        found.push({ selector: `[data-sa-scroll-region="${label}"]`, label, id: node.id || null });
      }
    }
    return found;
  });
  if (regions.length > maxRegions) payload.gaps.push(`Only ${maxRegions} of ${regions.length} internal regions inspected`);
  for (const region of regions.slice(0, maxRegions)) {
    payload.regions.push({ ...await traverse(region.selector, region.label, true), id: region.id });
  }
  const observedHeight = payload.regions.find(region => region.label === 'document').samples.at(-1)?.height;
  const finalHeight = await page.evaluate(() => document.scrollingElement.scrollHeight);
  if (finalHeight !== observedHeight) payload.regions.push(await traverse(null, 'updated-document', true));
  payload.complete = payload.gaps.length === 0 && payload.regions.every(region => region.complete);
  fs.writeFileSync(path.join(out, `${testInfo.project.name}.json`), JSON.stringify(payload, null, 2));
  expect(pageErrors).toEqual([]);
});
