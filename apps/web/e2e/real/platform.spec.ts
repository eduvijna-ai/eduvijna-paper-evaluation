import { test, expect } from "@playwright/test";
import { randomUUID } from "node:crypto";

const ADMIN_EMAIL = "admin@demo.eduvijna.local";
const ADMIN_PASSWORD = "DemoAdmin!2026";

function uniqueRunId(): string {
  const ts = Date.now().toString(36);
  const frag = randomUUID().replace(/-/g, "").slice(0, 10);
  return `${ts}${frag}`;
}

test.describe("B1 real A1 platform flows", () => {
  test.describe.configure({ mode: "serial" });

  test("login → CRUD → import → guardian → logout", async ({
    page,
    request,
  }) => {
    const healthBase =
      process.env.API_UPSTREAM_URL ?? "http://127.0.0.1:18000";
    const health = await request.get(`${healthBase}/health`);
    test.skip(!health.ok(), `API not reachable at ${healthBase}`);

    const runId = uniqueRunId();

    // Prove Next same-origin rewrite → backend (login via browser, not direct API).
    await page.goto("/login");
    await expect(page.getByTestId("login-page")).toBeVisible();
    const meViaRewrite = page.waitForResponse(
      (res) =>
        res.url().includes("/api/v1/auth/") &&
        (res.request().method() === "POST" || res.url().includes("/me")),
      { timeout: 30_000 },
    );
    await page.getByTestId("login-email").fill(ADMIN_EMAIL);
    await page.getByTestId("login-password").fill(ADMIN_PASSWORD);
    await page.getByTestId("login-submit").click();
    const authResponse = await meViaRewrite;
    expect(authResponse.ok()).toBeTruthy();
    await expect(page.getByTestId("app-shell")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("dashboard-page")).toBeVisible({
      timeout: 20_000,
    });

    await page.goto("/students");
    await expect(page.getByTestId("students-page")).toBeVisible({
      timeout: 20_000,
    });
    await page.getByTestId("student-create-toggle").click();
    const code = `STU-E2E-${runId}`;
    await page.locator('input[name="studentCode"]').fill(code);
    await page.locator('input[name="fullName"]').fill("E2E Student");
    const login = await request.post(`${healthBase}/api/v1/auth/login`, {
      data: { email: ADMIN_EMAIL, password: ADMIN_PASSWORD },
    });
    const token = (await login.json()).access_token as string;
    const years = (await (
      await request.get(`${healthBase}/api/v1/academic-years`, {
        headers: { Authorization: `Bearer ${token}` },
      })
    ).json()) as Array<{ id: string; name: string }>;
    const sections = (await (
      await request.get(`${healthBase}/api/v1/class-sections`, {
        headers: { Authorization: `Bearer ${token}` },
      })
    ).json()) as Array<{
      id: string;
      name: string;
      academic_year_id: string;
    }>;
    const year = years.find((y) => y.name === "2026-27") ?? years[0];
    const section = sections.find((s) => s.academic_year_id === year?.id);
    expect(year).toBeTruthy();
    expect(section).toBeTruthy();
    await page.locator('select[name="academicYearId"]').selectOption(year!.id);
    await page
      .locator('select[name="classSectionId"]')
      .selectOption(section!.id);
    await page.getByTestId("student-create-submit").click();
    await expect(page.getByTestId("student-detail-page")).toBeVisible({
      timeout: 30_000,
    });
    const assignedStudentUrl = page.url();

    await page.getByTestId("student-edit-toggle").click();
    await page.locator('input[name="fullName"]').fill("E2E Student Edited");
    await page.getByTestId("student-edit-submit").click();
    await expect(page.getByText("Student updated.")).toBeVisible({
      timeout: 15_000,
    });

    // Create without year/section, edit, then reload. Both-null is a supported state.
    await page.goto("/students");
    await expect(page.getByTestId("students-page")).toBeVisible({
      timeout: 20_000,
    });
    await page.getByTestId("student-create-toggle").click();
    const unassignedCode = `STU-UNASSIGNED-${runId}`;
    await page.locator('input[name="studentCode"]').fill(unassignedCode);
    await page.locator('input[name="fullName"]').fill("E2E Unassigned");
    await page.getByTestId("student-create-submit").click();
    await expect(page.getByTestId("student-detail-page")).toBeVisible({
      timeout: 30_000,
    });
    await page.getByTestId("student-edit-toggle").click();
    await page.locator('input[name="fullName"]').fill("E2E Unassigned Edited");
    await page.getByTestId("student-edit-submit").click();
    await expect(page.getByText("Student updated.")).toBeVisible({
      timeout: 15_000,
    });
    await page.reload();
    await expect(page.getByTestId("student-detail-page")).toBeVisible({
      timeout: 20_000,
    });
    await expect(page.getByText("E2E Unassigned Edited")).toBeVisible({
      timeout: 15_000,
    });

    await page.goto(assignedStudentUrl);
    await expect(page.getByTestId("student-detail-page")).toBeVisible({
      timeout: 20_000,
    });

    // Guardian create + link
    const guardianName = `E2E Guardian ${runId}`;
    await page.locator('input[placeholder="Display name"]').fill(guardianName);
    await page
      .locator('input[placeholder="Relationship (e.g. PARENT)"]')
      .fill("PARENT");
    await page.getByTestId("guardian-create-submit").click();
    await expect(page.getByText(/Guardian created/i)).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByTestId("guardians-linked-list")).toContainText(
      guardianName,
      { timeout: 15_000 },
    );

    // Reload — guardian link must persist
    await page.reload();
    await expect(page.getByTestId("student-detail-page")).toBeVisible({
      timeout: 20_000,
    });
    await expect(page.getByTestId("guardians-linked-list")).toContainText(
      guardianName,
      { timeout: 15_000 },
    );

    // Unlink + reload — link must remain absent
    const unlinkButton = page.locator('[data-testid^="guardian-unlink-"]').first();
    await unlinkButton.click();
    await expect(page.getByTestId("guardians-empty")).toBeVisible({
      timeout: 15_000,
    });
    await page.reload();
    await expect(page.getByTestId("student-detail-page")).toBeVisible({
      timeout: 20_000,
    });
    await expect(page.getByTestId("guardians-empty")).toBeVisible({
      timeout: 15_000,
    });

    // CSV import validate + commit
    await page.goto("/students/import");
    await expect(page.getByTestId("students-import-page")).toBeVisible();

    const yearName = year!.name;
    const sectionName = section!.name;
    const importCode = `STU-IMP-${runId}`;
    const importRoll = `R${runId.slice(0, 12)}`;
    const importAdmission = `ADM-${runId.slice(0, 12)}`;
    const csv = [
      "student_code,admission_number,roll_number,full_name,academic_year,class_section",
      `${importCode},${importAdmission},${importRoll},Import Student,${yearName},${sectionName}`,
    ].join("\n");

    await page.getByTestId("import-file").setInputFiles({
      name: "roster.csv",
      mimeType: "text/csv",
      buffer: Buffer.from(csv),
    });
    await page.getByTestId("import-validate").click();
    await expect(page.getByTestId("import-validation-panel")).toBeVisible({
      timeout: 20_000,
    });
    await expect(page.getByTestId("import-outcome-0")).toContainText("VALID");
    await expect(page.getByTestId("import-validation-panel")).toContainText(
      importCode,
    );
    await page.getByTestId("import-commit").click();
    await expect(page.getByTestId("import-success")).toBeVisible({
      timeout: 20_000,
    });
    await expect(page.getByTestId("import-success")).toContainText(
      "Imported 1 student",
    );

    // Imported student must exist (authenticated backend GET)
    const studentsAfter = (await (
      await request.get(`${healthBase}/api/v1/students`, {
        headers: { Authorization: `Bearer ${token}` },
      })
    ).json()) as Array<{ student_code: string; full_name: string }>;
    expect(
      studentsAfter.some((s) => s.student_code === importCode),
    ).toBeTruthy();

    // Also visible in frontend list
    await page.goto("/students");
    await expect(page.getByTestId("students-page")).toBeVisible({
      timeout: 20_000,
    });
    await expect(page.getByText(importCode)).toBeVisible({ timeout: 20_000 });

    // Second unique CSV import against same DB
    const runId2 = uniqueRunId();
    const importCode2 = `STU-IMP2-${runId2}`;
    const csv2 = [
      "student_code,admission_number,roll_number,full_name,academic_year,class_section",
      `${importCode2},ADM2-${runId2.slice(0, 10)},R2${runId2.slice(0, 10)},Import Student Two,${yearName},${sectionName}`,
    ].join("\n");
    await page.goto("/students/import");
    await page.getByTestId("import-file").setInputFiles({
      name: "roster2.csv",
      mimeType: "text/csv",
      buffer: Buffer.from(csv2),
    });
    await page.getByTestId("import-validate").click();
    await expect(page.getByTestId("import-outcome-0")).toContainText("VALID", {
      timeout: 20_000,
    });
    await page.getByTestId("import-commit").click();
    await expect(page.getByTestId("import-success")).toContainText(
      "Imported 1 student",
      { timeout: 20_000 },
    );

    await page.getByTestId("logout-button").click();
    await expect(page.getByTestId("login-page")).toBeVisible({
      timeout: 15_000,
    });
  });

  test("unauthorized redirect", async ({ page }) => {
    await page.goto("/students");
    await expect(page.getByTestId("login-page")).toBeVisible({
      timeout: 20_000,
    });
  });
});
