import { defineConfig, devices } from '@playwright/test'

// `make e2e` maps the built frontend to :8082 (see docker-compose.e2e.yml —
// :8080/:8003 stay free for `make dev`'s running stack).
const baseURL = process.env.E2E_BASE_URL ?? 'http://localhost:8082'

export default defineConfig({
  testDir: './tests',
  globalSetup: './global-setup.ts',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: [['html', { outputFolder: 'playwright-report', open: 'never' }], ['list']],
  outputDir: 'test-results',
  use: {
    baseURL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    // Local manual repro only — CI always uses the bundled Chromium below.
    ...(process.env.E2E_BROWSER_PATH
      ? { launchOptions: { executablePath: process.env.E2E_BROWSER_PATH } }
      : {}),
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
})
