import { defineConfig, devices } from "@playwright/test";

/**
 * Real A1 backend integration suite.
 * Requires API at NEXT_PUBLIC_API_BASE_URL (default http://127.0.0.1:8000)
 * seeded via `docker compose exec api python -m app.cli.seed_dev`.
 */
export default defineConfig({
  testDir: "./e2e/real",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 1,
  timeout: 120_000,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:3001",
    trace: "on-first-retry",
  },
  webServer: {
    command: "pnpm exec next dev --port 3001",
    url: "http://127.0.0.1:3001/login",
    reuseExistingServer: false,
    timeout: 120_000,
    env: {
      NEXT_PUBLIC_API_MODE: "hybrid",
      // Same-origin via Next rewrites (see next.config.ts)
      NEXT_PUBLIC_API_BASE_URL: "",
      API_UPSTREAM_URL:
        process.env.API_UPSTREAM_URL ?? "http://127.0.0.1:18000",
    },
  },
  projects: [
    {
      name: "chromium-real",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
