import { test, expect } from "@playwright/test";

async function openAuthed(page: import("@playwright/test").Page, path: string) {
  await page.goto("/login");
  await page.getByTestId("login-email").fill("admin@demo.eduvijna.local");
  await page.getByTestId("login-password").fill("DemoAdmin!2026");
  await page.getByTestId("login-submit").click();
  await expect(page.getByTestId("app-shell")).toBeVisible({ timeout: 30_000 });
  await page.goto(path);
}

test.describe("B14 mock reassessment", () => {
  test("APPROVED create UI and learning workspace section", async ({
    page,
  }) => {
    await openAuthed(
      page,
      "/learning/student-demo-001/improvement-assessment",
    );
    await expect(page.getByTestId("improvement-assessment-page")).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByTestId("b14-create-reassessment")).toHaveCount(0);
    await expect(page.getByTestId("approve-blueprint")).toBeVisible();
    await page.getByTestId("approve-blueprint").click();
    await expect(page.getByTestId("b14-create-reassessment")).toBeVisible({
      timeout: 10_000,
    });
    await expect(page.getByTestId("b14-create-item-I1")).toBeVisible();
    await expect(page.getByTestId("b14-prompt-I1")).toBeVisible();
    await expect(page.getByTestId("b14-marks-I1")).toHaveValue("4.00");
    await page.getByTestId("b14-instantiate-submit").click();
    await expect(page.getByTestId("b14-create-success")).toBeVisible({
      timeout: 10_000,
    });
    await expect(page.getByTestId("b14-created-assessment-link")).toBeVisible();
    await expect(page.getByTestId("b14-create-success")).toContainText(/DRAFT/i);

    await page.goto("/learning/student-demo-001");
    await expect(page.getByTestId("adaptive-learning-page")).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByTestId("b14-reassessments-section")).toBeVisible();
    await expect(page.getByTestId("b14-reassessments-section")).toContainText(
      /Reassessment/i,
    );
    await expect(page.getByTestId("b14-reassessment-row").first()).toBeVisible();
    await expect(page.getByTestId("b14-mastery-delta").first()).toBeVisible();
    await expect(
      page.getByTestId("b14-insufficient-evidence").first(),
    ).toContainText(/Insufficient decisive evidence/i);
    await expect(page.getByTestId("b14-pre-publication-message")).toBeVisible();
    await expect(page.getByTestId("b13-assigned-resources")).toBeVisible();
  });
});
