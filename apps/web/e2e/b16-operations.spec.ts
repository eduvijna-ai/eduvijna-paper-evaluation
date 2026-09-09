import { test, expect } from "@playwright/test";

async function openAuthed(page: import("@playwright/test").Page, path: string) {
  await page.goto("/login");
  await page.getByTestId("login-email").fill("admin@demo.eduvijna.local");
  await page.getByTestId("login-password").fill("DemoAdmin!2026");
  await page.getByTestId("login-submit").click();
  await expect(page.getByTestId("app-shell")).toBeVisible({ timeout: 30_000 });
  await page.goto(path);
}

test.describe("B16 mock operations", () => {
  test("grading, queue, moderation, and grievances workspaces", async ({
    page,
  }) => {
    await openAuthed(page, "/operations/grading");
    await expect(page.getByTestId("b16-grading-workspace")).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByTestId("nav-operations")).toBeVisible();
    await expect(page.getByTestId("b16-pool-list")).toBeVisible();
    await expect(page.getByTestId("b16-pool-row").first()).toBeVisible();
    await expect(page.getByTestId("b16-pool-status").first()).toContainText(
      /ACTIVE|DRAFT|CLOSED/,
    );

    await page.getByTestId("b16-link-my-queue").click();
    await expect(page.getByTestId("b16-my-queue-workspace")).toBeVisible();
    await expect(page.getByTestId("b16-queue-item").first()).toBeVisible();

    await page.goto("/operations/moderation");
    await expect(page.getByTestId("b16-moderation-workspace")).toBeVisible();
    await expect(page.getByTestId("b16-moderation-row").first()).toBeVisible();
    await expect(page.getByTestId("b16-moderation-approve")).toBeVisible();

    await page.goto("/operations/grievances");
    await expect(page.getByTestId("b16-grievances-workspace")).toBeVisible();
    await expect(page.getByTestId("b16-grievance-row").first()).toBeVisible();
    await expect(page.getByTestId("b16-grievance-original")).toBeVisible();
  });
});
