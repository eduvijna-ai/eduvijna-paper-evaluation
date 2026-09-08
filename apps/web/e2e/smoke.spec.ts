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

async function openAuthed(page: Page, path: string) {
  await seedTeacherSession(page);
  await page.goto(path);
  await expect(page.getByTestId("app-shell")).toBeVisible({ timeout: 20_000 });
}

test.describe("CVB frontend smoke — 15 flows", () => {
  test.describe.configure({ mode: "serial" });

  test("1. dashboard", async ({ page }) => {
    await openAuthed(page, "/dashboard");
    await expect(page.getByTestId("dashboard-page")).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByTestId("dashboard-submissions")).toBeVisible();
  });

  test("2. assessment creation nav", async ({ page }) => {
    await openAuthed(page, "/assessments");
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
    await expect(page.getByTestId("link-answer-key")).toBeVisible();
    await expect(page.getByTestId("link-curriculum-map")).toBeVisible();
    await page.goto("/assessments/assess-demo-001/answer-key");
    await expect(page.getByTestId("assessment-answer-key-page")).toBeVisible({
      timeout: 15_000,
    });
    await page.goto("/assessments/assess-demo-001/curriculum-map");
    await expect(
      page.getByTestId("assessment-curriculum-map-page"),
    ).toBeVisible({ timeout: 15_000 });
  });

  test("3. student import", async ({ page }) => {
    await openAuthed(page, "/students/import");
    await expect(page.getByTestId("students-import-page")).toBeVisible({
      timeout: 15_000,
    });
  });

  test("4. raw upload", async ({ page }) => {
    await openAuthed(page, "/submissions/upload");
    await expect(page.getByTestId("submissions-upload-page")).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByTestId("raw-unmarked-banner")).toContainText(
      /RAW, UNMARKED HANDWRITTEN ANSWER SHEETS/i,
    );
  });

  test("5. identity", async ({ page }) => {
    await openAuthed(page, "/submissions/sub-demo-002/identity");
    await expect(page.getByTestId("identity-review-page")).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByTestId("student-identity-card")).toBeVisible();
    await expect(page.getByTestId("confirm-identity")).toBeVisible();
    await expect(page.getByTestId("choose-different-student")).toBeVisible();
    await expect(page.getByTestId("mark-unmatched")).toBeVisible();
  });

  test("6. mapping", async ({ page }) => {
    await openAuthed(page, "/submissions/sub-demo-003/mapping");
    await expect(page.getByTestId("mapping-review-page")).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByTestId("mapping-3col")).toBeVisible();
    await page.getByTestId("mapping-action-ACCEPT").click();
    await expect(page.getByTestId("mapping-action-result")).toBeVisible();
    await expect(page.getByTestId("mapping-action-MARK_CONTINUATION")).toBeVisible();
  });

  test("7. evaluation", async ({ page }) => {
    await openAuthed(page, "/submissions/sub-demo-001/evaluation");
    await expect(page.getByTestId("evaluation-workspace-page")).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByTestId("evaluation-3col")).toBeVisible();
    await expect(page.getByTestId("evaluation-decision-panel")).toBeVisible();
    await expect(page.getByTestId("confidence-dimensions")).toBeVisible();
  });

  test("8. teacher review", async ({ page }) => {
    await openAuthed(page, "/submissions/sub-demo-001/evaluation");
    await expect(page.getByTestId("teacher-review-actions")).toBeVisible({
      timeout: 15_000,
    });
    await page.getByTestId("teacher-action-ACCEPT").click();
    await expect(page.getByTestId("confirm-dialog")).toBeVisible();
    await page.getByTestId("confirm-dialog-confirm").click();
    await expect(page.getByTestId("teacher-action-result")).toBeVisible({
      timeout: 10_000,
    });
  });

  test("9. annotated paper", async ({ page }) => {
    await openAuthed(page, "/submissions/sub-demo-001/annotated-paper");
    await expect(page.getByTestId("annotated-paper-page")).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByTestId("annotation-score-chip")).toBeVisible();
    await page.getByTestId("evidence-region-reg-3").click();
    await expect(page.getByTestId("annotation-criterion-panel")).toBeVisible();
  });

  test("10. student report", async ({ page }) => {
    await openAuthed(
      page,
      "/reports/student/student-demo-001/assessment/assess-demo-001",
    );
    await expect(page.getByTestId("student-report-page")).toBeVisible({
      timeout: 15_000,
    });
  });

  test("11. parent report", async ({ page }) => {
    await openAuthed(
      page,
      "/reports/parent/student-demo-001/assessment/assess-demo-001",
    );
    await expect(page.getByTestId("parent-report-page")).toBeVisible({
      timeout: 15_000,
    });
  });

  test("12. assessment analytics", async ({ page }) => {
    await openAuthed(page, "/analytics/assessments/assess-demo-001");
    await expect(page.getByTestId("assessment-analytics-page")).toBeVisible({
      timeout: 15_000,
    });
  });

  test("13. student analytics", async ({ page }) => {
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
  });

  test("14. adaptive learning", async ({ page }) => {
    await openAuthed(page, "/learning/student-demo-001");
    await expect(page.getByTestId("adaptive-learning-page")).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByTestId("topic-priority-1")).toBeVisible();
    await expect(
      page.getByTestId("curriculum-restriction-notice"),
    ).toContainText(/Recommendations restricted to student's curriculum/i);
    await expect(page.getByTestId("b13-assigned-resources")).toBeVisible();
    await expect(page.getByTestId("b13-assignment-row").first()).toBeVisible();
    await expect(page.getByTestId("b14-reassessments-section")).toBeVisible();
    await expect(page.getByTestId("b14-reassessment-row").first()).toBeVisible();
  });

  test("15. improvement assessment", async ({ page }) => {
    await openAuthed(page, "/learning/student-demo-001/improvement-assessment");
    await expect(page.getByTestId("improvement-assessment-page")).toBeVisible({
      timeout: 15_000,
    });
    await expect(
      page.getByTestId("improvement-assessment-blueprint"),
    ).toContainText(/Second Derivatives/i);
    await expect(page.getByTestId("approve-blueprint")).toBeVisible();
    await expect(page.getByTestId("b14-create-reassessment")).toHaveCount(0);
  });
});
