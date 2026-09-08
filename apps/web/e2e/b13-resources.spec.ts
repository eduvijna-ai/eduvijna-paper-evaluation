import { test, expect } from "@playwright/test";

async function openAuthed(page: import("@playwright/test").Page, path: string) {
  await page.goto("/login");
  await page.getByTestId("login-email").fill("admin@demo.eduvijna.local");
  await page.getByTestId("login-password").fill("DemoAdmin!2026");
  await page.getByTestId("login-submit").click();
  await expect(page.getByTestId("app-shell")).toBeVisible({ timeout: 30_000 });
  await page.goto(path);
}

test.describe("B13 mock curriculum resources", () => {
  test("catalog page lists demo resources and create form", async ({ page }) => {
    await openAuthed(page, "/learning/resources");
    await expect(page.getByTestId("b13-resource-catalog")).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByTestId("b13-resource-create")).toBeVisible();
    await expect(page.getByTestId("b13-resource-row").first()).toBeVisible();
    await expect(page.getByText("RES-DEMO-001")).toBeVisible();
  });

  test("learning demo student shows assigned resources section", async ({
    page,
  }) => {
    await openAuthed(page, "/learning/student-demo-001");
    await expect(page.getByTestId("adaptive-learning-page")).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByTestId("b13-assigned-resources")).toBeVisible({
      timeout: 15_000,
    });
    await expect(
      page.getByTestId("b13-recommendation-vs-assignment-note"),
    ).toContainText(/Assigned catalog resources \(B13\)/i);
    await expect(page.getByTestId("b13-assignment-row").first()).toBeVisible();
    await expect(page.getByTestId("b13-assign-resource")).toBeVisible();
    await expect(page.getByTestId("b13-resources-catalog-link")).toBeVisible();
  });
});
