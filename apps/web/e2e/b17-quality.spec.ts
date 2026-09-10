import { test, expect } from "@playwright/test";

async function openAuthed(page: import("@playwright/test").Page, path: string) {
  await page.goto("/login");
  await page.getByTestId("login-email").fill("admin@demo.eduvijna.local");
  await page.getByTestId("login-password").fill("DemoAdmin!2026");
  await page.getByTestId("login-submit").click();
  await expect(page.getByTestId("app-shell")).toBeVisible({ timeout: 30_000 });
  await page.goto(path);
}

test.describe("B17 mock quality psychometrics + calibration", () => {
  test("psychometrics workspace lists runs and item bands", async ({ page }) => {
    await openAuthed(page, "/quality/psychometrics");
    await expect(page.getByTestId("b17-psychometrics-workspace")).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByTestId("nav-quality-psychometrics")).toBeVisible();
    await expect(page.getByTestId("b17-psychometrics-run-list")).toBeVisible();
    await expect(page.getByTestId("b17-psychometrics-run-row").first()).toBeVisible();
    await expect(
      page.getByTestId("b17-psychometrics-run-status").first(),
    ).toContainText("COMPLETED");
    await expect(page.getByTestId("b17-psychometrics-item-row").first()).toBeVisible();
    await expect(page.getByTestId("b17-difficulty-band").first()).toBeVisible();
  });

  test("calibration workspace lists sessions and blind case", async ({ page }) => {
    await openAuthed(page, "/quality/calibration");
    await expect(page.getByTestId("b17-calibration-workspace")).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByTestId("nav-quality-calibration")).toBeVisible();
    await expect(page.getByTestId("b17-calibration-session-list")).toBeVisible();
    await expect(
      page.getByTestId("b17-calibration-session-row").first(),
    ).toBeVisible();
    await expect(page.getByTestId("b17-calibration-detail")).toBeVisible();
    await expect(page.getByTestId("b17-calibration-blind")).toBeVisible();
  });
});
