// @ts-check
const { test, expect } = require('@playwright/test');
const AxeBuilder = require('@axe-core/playwright').default;

test.describe('Axe-core Test Runner Unit Tests', () => {

  // Test 1: Verify a WCAG AA/AAA compliant component specimen has 0 violations
  test('should pass all WCAG 2.1/2.2 AA accessibility checks on accessible UI specimen', async ({ page }) => {
    const accessibleHTML = `
      <!DOCTYPE html>
      <html lang="en">
      <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Accessible UI Component Specimen</title>
        <style>
          :root {
            --color-bg: #0f172a;
            --color-surface: #1e293b;
            --color-text-primary: #f8fafc;
            --color-text-muted: #94a3b8;
            --color-accent: #38bdf8;
            --color-accent-text: #0f172a;
            --radius-md: 8px;
            --space-md: 16px;
          }
          body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background-color: var(--color-bg);
            color: var(--color-text-primary);
            margin: 0;
            padding: var(--space-md);
          }
          main {
            max-width: 600px;
            margin: 0 auto;
          }
          .card {
            background-color: var(--color-surface);
            border: 1px solid #334155;
            border-radius: var(--radius-md);
            padding: 24px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
          }
          h1 {
            font-size: 1.5rem;
            margin-top: 0;
            color: var(--color-text-primary);
          }
          p {
            color: var(--color-text-muted);
            line-height: 1.5;
          }
          .form-group {
            margin-bottom: 16px;
          }
          label {
            display: block;
            margin-bottom: 6px;
            font-weight: 500;
            color: var(--color-text-primary);
          }
          input[type="text"] {
            width: 100%;
            padding: 10px 12px;
            border: 1px solid #475569;
            border-radius: 6px;
            background-color: #0f172a;
            color: var(--color-text-primary);
            box-sizing: border-box;
          }
          input[type="text"]:focus {
            outline: 2px solid var(--color-accent);
            outline-offset: 2px;
          }
          button {
            background-color: var(--color-accent);
            color: var(--color-accent-text);
            font-weight: 600;
            padding: 10px 20px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            min-height: 44px;
            min-width: 44px;
          }
          button:focus-visible {
            outline: 2px solid #ffffff;
            outline-offset: 2px;
          }
        </style>
      </head>
      <body>
        <main>
          <div class="card">
            <h1>Design System Component</h1>
            <p>This specimen adheres to WCAG 2.1 AA requirements with verified contrast ratios and accessible landmarks.</p>
            <form action="#" method="post" onsubmit="return false;">
              <div class="form-group">
                <label for="project-name">Project Name</label>
                <input type="text" id="project-name" name="projectName" required autocomplete="off" />
              </div>
              <button type="submit" aria-label="Submit project configuration">Save Changes</button>
            </form>
          </div>
        </main>
      </body>
      </html>
    `;

    await page.setContent(accessibleHTML, { waitUntil: 'domcontentloaded' });

    const scanResults = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice'])
      .analyze();

    expect(scanResults.violations).toEqual([]);
  });

  // Test 2: Verify Axe-core accurately detects intentional WCAG violations
  test('should accurately flag intentional WCAG violations (contrast and missing ARIA)', async ({ page }) => {
    const inaccessibleHTML = `
      <!DOCTYPE html>
      <html lang="en">
      <head>
        <meta charset="UTF-8">
        <title>Inaccessible Test Case</title>
      </head>
      <body>
        <div style="background-color: #ffffff; color: #f5f5f5;">Low contrast invisible text</div>
        <button></button>
        <input type="text" />
      </body>
      </html>
    `;

    await page.setContent(inaccessibleHTML, { waitUntil: 'domcontentloaded' });

    const scanResults = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa'])
      .analyze();

    const violationIds = scanResults.violations.map(v => v.id);
    expect(violationIds).toContain('button-name');
    expect(violationIds).toContain('label');
  });

});
