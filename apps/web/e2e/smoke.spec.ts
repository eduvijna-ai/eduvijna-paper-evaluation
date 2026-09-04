import { test, expect, type Page } from "@playwright/test";

const DEMO_TEACHER_SESSION = {
  userId: "user-teacher-001",
  displayName: "Demo Teacher",
  email: "teacher@demo.eduvijna.local",
  role: "TEACHER",
  tenantId: "tenant-demo-001",
  institutionId: "inst-demo-001",
};

async function seedTeacherSession(page: Page) {
  await page.addInitScript((session) => {
    window.localStorage.setItem(
      "eduvijna_demo_session",
      JSON.stringify(session),
    );
    document.cookie = `eduvijna_demo_role=${session.role}; path=/; SameSite=Lax`;
  }, DEMO_TEACHER_SESSION);
}

async function loginViaUi(page: Page) {
  await page.goto("/login");
  await expect(page.getByTestId("login-page")).toBeVisible();
  await expect(page.getByTestId("login-page")).toHaveAttribute(
    "data-hydrated",
    "true",
  );
  await page.getByTestId("login-as-TEACHER").click();
  await page.waitForURL("**/dashboard", { timeout: 20_000 });
  await expect(page.getByTestId("dashboard-page")).toBeVisible({
    timeout: 20_000,
  });
}

async function openAuthed(page: Page, path: string) {
  await seedTeacherSession(page);
  await page.goto(path);
  await expect(page.getByTestId("app-shell")).toBeVisible({ timeout: 20_000 });
}

test.describe("CVB frontend smoke", () => {
  test.describe.configure({ mode: "serial" });

  test("1. login / demo entry", async ({ page }) => {
    await loginViaUi(page);
    await expect(page.getByTestId("app-shell")).toBeVisible();
  });

  test("2. dashboard loads", async ({ page }) => {
    await openAuthed(page, "/dashboard");
    await expect(page.getByTestId("dashboard-page")).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByTestId("dashboard-submissions")).toBeVisible();
  });

  test("3. assessment flow navigation", async ({ page }) => {
    await openAuthed(page, "/dashboard");
    await expect(page.getByTestId("nav-assessments")).toBeVisible();
    await page.goto("/assessments");
    await expect(page.getByTestId("assessments-page")).toBeVisible({
      timeout: 15_000,
    });
    await page.goto("/assessments/new");
    await expect(page.getByTestId("assessment-new-page")).toBeVisible({
      timeout: 15_000,
    });
    await page.goto("/assessments/assess-demo-001");
    await expect(page.getByTestId("assessment-detail-page")).toBeVisible({
      timeout: 15_000,
    });
    await page.goto("/assessments/assess-demo-001/questions");
    await expect(page.getByTestId("assessment-questions-page")).toBeVisible({
      timeout: 15_000,
    });
    await page.goto("/assessments/assess-demo-001/rubric");
    await expect(page.getByTestId("assessment-rubric-page")).toBeVisible({
      timeout: 15_000,
    });
  });

  test("4. submissions upload page loads", async ({ page }) => {
    await openAuthed(page, "/submissions/upload");
    await expect(page.getByTestId("submissions-upload-page")).toBeVisible({
      timeout: 15_000,
    });
  });

  test("5. identity review page", async ({ page }) => {
    await openAuthed(page, "/submissions/sub-demo-002/identity");
    await expect(page.getByTestId("identity-review-page")).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByTestId("student-identity-card")).toBeVisible();
  });

  test("6. question mapping page", async ({ page }) => {
    await openAuthed(page, "/submissions/sub-demo-003/mapping");
    await expect(page.getByTestId("mapping-review-page")).toBeVisible({
      timeout: 15_000,
    });
    await page.getByTestId("mapping-action-ACCEPT").click();
    await expect(page.getByTestId("mapping-action-result")).toBeVisible();
  });

  test("7. evaluation page", async ({ page }) => {
    await openAuthed(page, "/submissions/sub-demo-001/evaluation");
    await expect(page.getByTestId("evaluation-workspace-page")).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByTestId("evaluation-3col")).toBeVisible();
    await expect(page.getByTestId("evaluation-decision-panel")).toBeVisible();
  });

  test("8. student report", async ({ page }) => {
    await openAuthed(
      page,
      "/reports/student/student-demo-001/assessment/assess-demo-001",
    );
    await expect(page.getByTestId("student-report-page")).toBeVisible({
      timeout: 15_000,
    });
  });

  test("9. parent report", async ({ page }) => {
    await openAuthed(
      page,
      "/reports/parent/student-demo-001/assessment/assess-demo-001",
    );
    await expect(page.getByTestId("parent-report-page")).toBeVisible({
      timeout: 15_000,
    });
  });

  test("10. adaptive-learning page", async ({ page }) => {
    await openAuthed(page, "/learning/student-demo-001");
    await expect(page.getByTestId("adaptive-learning-page")).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByTestId("topic-priority-1")).toBeVisible();
  });
});
