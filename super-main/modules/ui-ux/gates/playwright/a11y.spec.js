// @ts-check
// Accessibility gate spec. Run it through modules/ui-ux/gates/a11y.py, which checks preconditions,
// sets the environment below and maps results to the PASS/FAIL/NOT-TESTED/ERROR contract.
//
// Environment:
//   TARGET_URL       live page to audit (http(s):// or file://)
//   SANDBOX_PATH     absolute path to a standalone HTML prototype
//   A11Y_RESULTS_DIR where per-viewport violation JSON is written
//   MOUNT_TIMEOUT_MS how long to wait for the sandbox to render (default 15000)
//   VISUAL_BASELINE  set to 1 to compare against a committed screenshot baseline
const { test, expect } = require('@playwright/test');
const AxeBuilder = require('@axe-core/playwright').default;
const fs = require('fs');
const path = require('path');
const { pathToFileURL } = require('url');

const WCAG_TAGS = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];
const MOUNT_SELECTOR = '#root > *, [data-component-root] > *';

const targetUrl = process.env.TARGET_URL;
const sandboxPath = process.env.SANDBOX_PATH;
const resultsDir = process.env.A11Y_RESULTS_DIR;
const mountTimeout = Number(process.env.MOUNT_TIMEOUT_MS || 15000);

function writeResults(projectName, payload) {
  if (!resultsDir) return;
  fs.mkdirSync(resultsDir, { recursive: true });
  fs.writeFileSync(path.join(resultsDir, `${projectName}.json`), JSON.stringify(payload, null, 2));
}

/** Resolve once the mount root has children, or reject on an uncaught page error or timeout. */
async function waitForMount(page, pageErrors) {
  const deadline = Date.now() + mountTimeout;
  while (Date.now() < deadline) {
    if (pageErrors.length > 0) {
      throw new Error(`Sandbox threw before mounting:\n${pageErrors.join('\n')}`);
    }
    if ((await page.locator(MOUNT_SELECTOR).count()) > 0) return;
    await page.waitForTimeout(100);
  }
  throw new Error(
    `Sandbox did not render anything inside #root or [data-component-root] within ${mountTimeout}ms.`
  );
}

test('accessibility gate', async ({ page }, testInfo) => {
  if (!targetUrl && !sandboxPath) {
    // Never skip: a skipped gate looks green to anything that only reads the exit code.
    throw new Error('NOT-TESTED: set TARGET_URL or SANDBOX_PATH (use modules/ui-ux/gates/a11y.py).');
  }

  const pageErrors = [];
  page.on('pageerror', (err) => pageErrors.push(err.message));

  if (sandboxPath) {
    await page.goto(pathToFileURL(sandboxPath).href, { waitUntil: 'domcontentloaded' });
    await waitForMount(page, pageErrors);
  } else {
    await page.goto(/** @type {string} */ (targetUrl), { waitUntil: 'load' });
    // Dev servers with long-lived connections may never go idle; idle is best-effort only.
    await page.waitForLoadState('networkidle', { timeout: 10000 }).catch(() => {});
  }

  const scan = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
  const violations = scan.violations.map((v) => ({
    id: v.id,
    impact: v.impact,
    help: v.help,
    helpUrl: v.helpUrl,
    nodes: v.nodes.map((n) => ({ target: n.target.join(' '), failureSummary: n.failureSummary })),
  }));

  writeResults(testInfo.project.name, {
    target: sandboxPath || targetUrl,
    viewport: page.viewportSize(),
    violations,
    pageErrors,
  });

  expect(pageErrors, 'uncaught page errors').toEqual([]);
  expect(violations.map((v) => v.id), 'axe-core WCAG violations').toEqual([]);

  if (process.env.VISUAL_BASELINE === '1') {
    await expect(page).toHaveScreenshot(`${testInfo.project.name}.png`, {
      maxDiffPixelRatio: 0.02,
      animations: 'disabled',
    });
  }
});
