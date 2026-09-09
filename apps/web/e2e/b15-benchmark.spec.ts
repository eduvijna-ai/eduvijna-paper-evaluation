import { test, expect } from "@playwright/test";

async function openAuthed(page: import("@playwright/test").Page, path: string) {
  await page.goto("/login");
  await page.getByTestId("login-email").fill("admin@demo.eduvijna.local");
  await page.getByTestId("login-password").fill("DemoAdmin!2026");
  await page.getByTestId("login-submit").click();
  await expect(page.getByTestId("app-shell")).toBeVisible({ timeout: 30_000 });
  await page.goto(path);
}

test.describe("B15 mock quality benchmarks", () => {
  test("workspace lists datasets, distinguishes DRAFT/LOCKED, shows run diffs", async ({
    page,
  }) => {
    await openAuthed(page, "/quality/benchmarks");
    await expect(page.getByTestId("b15-benchmark-workspace")).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByTestId("nav-quality-benchmarks")).toBeVisible();
    await expect(page.getByTestId("b15-dataset-list")).toBeVisible();
    await expect(page.getByTestId("b15-dataset-row").first()).toContainText(
      "GOLD-DEMO-001",
    );
    await expect(page.getByTestId("b15-version-list")).toBeVisible();

    const statuses = page.getByTestId("b15-version-status");
    await expect(statuses.filter({ hasText: "DRAFT" }).first()).toBeVisible();
    await expect(statuses.filter({ hasText: "LOCKED" }).first()).toBeVisible();

    // Select locked version (second row in demo fixtures)
    await page.getByTestId("b15-version-row").nth(1).click();
    await expect(page.getByTestId("b15-run-list")).toBeVisible({
      timeout: 10_000,
    });
    await expect(page.getByTestId("b15-run-row").first()).toBeVisible();
    await expect(page.getByTestId("b15-run-verdict").first()).toBeVisible();
    await expect(page.getByTestId("b15-metrics")).toBeVisible();
    await expect(page.getByTestId("b15-gate-verdict")).toBeVisible();
    await expect(page.getByTestId("b15-case-diff").first()).toBeVisible();
    await expect(page.getByTestId("b15-gold-label").first()).toContainText(
      /Human gold result/i,
    );
    await expect(page.getByTestId("b15-candidate-label").first()).toContainText(
      /Candidate AI output/i,
    );

    // Select failed run to confirm FAIL verdict still shows gold vs candidate
    const failRow = page
      .getByTestId("b15-run-row")
      .filter({ has: page.getByTestId("b15-run-verdict").filter({ hasText: "FAIL" }) });
    if ((await failRow.count()) > 0) {
      await failRow.first().click();
      await expect(page.getByTestId("b15-run-verdict").filter({ hasText: "FAIL" }).first()).toBeVisible();
      await expect(page.getByTestId("b15-gold-label").first()).toBeVisible();
      await expect(page.getByTestId("b15-candidate-label").first()).toBeVisible();
    }
  });
});
