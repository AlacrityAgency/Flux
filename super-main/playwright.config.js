// @ts-check
const { defineConfig, devices } = require('@playwright/test');

// Gates call Playwright with A11Y_JSON_REPORT set so results can be parsed from a file
// instead of stdout. Retries stay at 0: a gate must not hide flaky results.
const jsonReport = process.env.A11Y_JSON_REPORT;

module.exports = defineConfig({
  testDir: '.',
  testMatch: /.*\.spec\.(js|ts)/,
  testIgnore: ['**/node_modules/**', '**/.superagent/**'],
  fullyParallel: true,
  forbidOnly: true,
  retries: 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: jsonReport ? [['json', { outputFile: jsonReport }]] : process.env.CI ? [['github'], ['list']] : 'list',
  // Visual baselines belong to the audited project, not to the skill directory.
  ...(process.env.A11Y_SNAPSHOT_DIR
    ? { snapshotPathTemplate: `${process.env.A11Y_SNAPSHOT_DIR}/{projectName}{ext}` }
    : {}),
  use: {
    headless: true,
    trace: 'retain-on-failure',
  },
  projects: [
    {
      name: 'desktop',
      use: { ...devices['Desktop Chrome'], viewport: { width: 1280, height: 800 } },
    },
    {
      name: 'mobile',
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 375, height: 667 },
        deviceScaleFactor: 2,
        isMobile: true,
        hasTouch: true,
      },
    },
  ],
});
