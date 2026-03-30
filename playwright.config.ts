import { defineConfig, devices } from '@playwright/test';

const BASE_URL = process.env.BASE_URL || 'http://localhost:3000';

export default defineConfig({
  testDir: './tests/ui/specs',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',
  use: {
    baseURL: BASE_URL,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },

  projects: [
    {
      name: 'mocked',
      use: {
        ...devices['Desktop Chrome'],
        // Mocked tests use fixture data — no real API needed
      },
    },
    {
      name: 'live',
      use: {
        ...devices['Desktop Chrome'],
        // Live tests hit real localhost:3000 → localhost:8080
        baseURL: process.env.BASE_URL || 'http://localhost:3000',
      },
      grep: /\[live\]/,
    },
  ],

  // Only start the web server for the mocked project
  webServer: process.env.SKIP_WEB_SERVER ? undefined : {
    command: 'cd apps/web && npm run dev',
    port: 3000,
    reuseExistingServer: true,
    timeout: 60_000,
  },
});
