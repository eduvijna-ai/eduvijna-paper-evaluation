import { test, expect } from "@playwright/test";

async function openAuthed(page: import("@playwright/test").Page, path: string) {
  await page.goto("/login");
  await page.getByTestId("login-email").fill("admin@demo.eduvijna.local");
  await page.getByTestId("login-password").fill("DemoAdmin!2026");
  await page.getByTestId("login-submit").click();
  await expect(page.getByTestId("app-shell")).toBeVisible({ timeout: 30_000 });
  await page.goto(path);
}

test.describe("B18 mock clustering + outcome reporting", () => {
  test("clustering workspace lists runs and cluster members", async ({ page }) => {
    await openAuthed(page, "/quality/clustering");
    await expect(page.getByTestId("b18-clustering-workspace")).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByTestId("nav-quality-clustering")).toBeVisible();
    await expect(page.getByTestId("b18-cluster-run-list")).toBeVisible();
    await expect(page.getByTestId("b18-cluster-run-row").first()).toBeVisible();
    await expect(page.getByTestId("b18-cluster-run-status").first()).toContainText(
      "COMPLETED",
    );
    await expect(page.getByTestId("b18-cluster-list")).toBeVisible();
    await expect(page.getByTestId("b18-cluster-row").first()).toBeVisible();
    await expect(page.getByTestId("b18-cluster-detail")).toBeVisible();
    await expect(page.getByTestId("b18-cluster-member-row").first()).toBeVisible();
  });

  test("outcomes workspace lists definitions and attainment metrics", async ({
    page,
  }) => {
    await openAuthed(page, "/outcomes/reporting");
    await expect(page.getByTestId("b18-outcomes-workspace")).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByTestId("nav-outcomes-reporting")).toBeVisible();
    await expect(page.getByTestId("b18-outcome-definitions")).toBeVisible();
    await expect(
      page.getByTestId("b18-outcome-definition-row").first(),
    ).toBeVisible();
    await expect(page.getByTestId("b18-outcome-type").first()).toContainText("CO");
    await expect(page.getByTestId("b18-outcome-report-list")).toBeVisible();
    await expect(page.getByTestId("b18-outcome-report-row").first()).toBeVisible();
    await expect(page.getByTestId("b18-outcome-metrics")).toBeVisible();
    await expect(page.getByTestId("b18-outcome-metric-row").first()).toBeVisible();
    await expect(page.getByTestId("b18-outcome-attainment-pct").first()).toContainText(
      "60.0%",
    );
  });
});
