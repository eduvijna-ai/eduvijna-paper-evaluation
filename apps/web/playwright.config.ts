import { defineConfig, devices } from "@playwright/test";

/**
 * Mock-mode Playwright suite (B0 product flows).
 * Real-backend suite: e2e/real — see playwright.real.config.ts
 */
export default defineConfig({
  testDir: "./e2e",
  testIgnore: [/\/real\//],
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  timeout: 60_000,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:3000",
    trace: "on-first-retry",
  },
  webServer: {
    command: "pnpm exec next dev --port 3000",
    url: "http://127.0.0.1:3000/login",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    env: {
      NEXT_PUBLIC_API_MODE: "mock",
    },
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
