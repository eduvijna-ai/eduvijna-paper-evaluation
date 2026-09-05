import { test, expect } from "@playwright/test";

const ADMIN_EMAIL = "admin@demo.eduvijna.local";
const ADMIN_PASSWORD = "DemoAdmin!2026";

test.describe("B1 real A1 platform flows", () => {
  test.describe.configure({ mode: "serial" });

  test("login → dashboard → students → create → import → guardian → logout", async ({
    page,
    request,
  }) => {
    const healthBase =
      process.env.API_UPSTREAM_URL ?? "http://127.0.0.1:18000";
    const health = await request.get(`${healthBase}/health`);
    test.skip(!health.ok(), `API not reachable at ${healthBase}`);

    await page.goto("/login");
    await expect(page.getByTestId("login-page")).toBeVisible();
    await page.getByTestId("login-email").fill(ADMIN_EMAIL);
    await page.getByTestId("login-password").fill(ADMIN_PASSWORD);
    await page.getByTestId("login-submit").click();
    await expect(page.getByTestId("app-shell")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("dashboard-page")).toBeVisible({
      timeout: 20_000,
    });

    await page.goto("/students");
    await expect(page.getByTestId("students-page")).toBeVisible({
      timeout: 20_000,
    });
    await page.getByTestId("student-create-toggle").click();
    const code = `STU-E2E-${Date.now().toString().slice(-6)}`;
    await page.locator('input[name="studentCode"]').fill(code);
    await page.locator('input[name="fullName"]').fill("E2E Student");
    // Resolve a matching year/section pair from the API (Playwright request, no CORS).
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

    await page.getByTestId("student-edit-toggle").click();
    await page.locator('input[name="fullName"]').fill("E2E Student Edited");
    await page.getByTestId("student-edit-submit").click();
    await expect(page.getByText("Student updated.")).toBeVisible({
      timeout: 15_000,
    });

    // Guardian create + link
    await page.locator('input[placeholder="Display name"]').fill("E2E Guardian");
    await page
      .locator('input[placeholder="Relationship (e.g. PARENT)"]')
      .fill("PARENT");
    await page.getByTestId("guardian-create-submit").click();
    await expect(page.getByText(/Guardian created/i)).toBeVisible({
      timeout: 15_000,
    });

    // CSV import validate + commit
    await page.goto("/students/import");
    await expect(page.getByTestId("students-import-page")).toBeVisible();

    const yearName = year!.name;
    const sectionName = section!.name;
    const importCode = `STU-IMP-${Date.now().toString().slice(-6)}`;
    const csv = [
      "student_code,admission_number,roll_number,full_name,academic_year,class_section",
      `${importCode},ADM-X,99,Import Student,${yearName},${sectionName}`,
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
    await page.getByTestId("import-commit").click();
    await expect(page.getByTestId("import-success")).toBeVisible({
      timeout: 20_000,
    });

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
