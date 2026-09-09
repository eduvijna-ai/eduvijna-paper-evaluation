import { test, expect } from "@playwright/test";

async function openAuthed(page: import("@playwright/test").Page, path: string) {
  await page.goto("/login");
  await page.getByTestId("login-email").fill("admin@demo.eduvijna.local");
  await page.getByTestId("login-password").fill("DemoAdmin!2026");
  await page.getByTestId("login-submit").click();
  await expect(page.getByTestId("app-shell")).toBeVisible({ timeout: 30_000 });
  await page.goto(path);
}

test.describe("B12 mock student analytics", () => {
  test("demo student shows all four B12 sections", async ({ page }) => {
    await openAuthed(page, "/analytics/students/student-demo-001");
    await expect(page.getByTestId("student-analytics-page")).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByTestId("b12-longitudinal-mastery")).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByTestId("b12-repeated-errors")).toBeVisible();
    await expect(page.getByTestId("b12-recoverable-marks")).toBeVisible();
    await expect(page.getByTestId("b12-mistake-notebook")).toBeVisible();
    await expect(page.getByTestId("b12-recoverable-disclaimer")).toContainText(
      /analytical estimate/i,
    );
    await expect(
      page.getByRole("heading", { name: "Longitudinal mastery" }),
    ).toBeVisible();
    await expect(page.getByText(/Insufficient evidence/i).first()).toBeVisible();
  });
});
