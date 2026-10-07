import { test, expect, type APIRequestContext, type Page } from "@playwright/test";

const ADMIN_EMAIL = "admin@demo.eduvijna.local";
const ADMIN_PASSWORD = "DemoAdmin!2026";

async function loginApi(request: APIRequestContext, apiBase: string): Promise<string> {
  const login = await request.post(`${apiBase}/api/v1/auth/login`, {
    data: { email: ADMIN_EMAIL, password: ADMIN_PASSWORD, tenant_slug: "demo" },
  });
  expect(login.ok()).toBeTruthy();
  return ((await login.json()) as { access_token: string }).access_token;
}

async function loginUi(page: Page) {
  await page.goto("/login");
  await page.getByTestId("login-email").fill(ADMIN_EMAIL);
  await page.getByTestId("login-password").fill(ADMIN_PASSWORD);
  await page.getByTestId("login-submit").click();
  await expect(page.getByTestId("app-shell")).toBeVisible();
}

test.describe("UAT critical path", () => {
  test("class section name A can exist in two grades", async ({ request, baseURL }) => {
    const apiBase = process.env.API_UPSTREAM ?? baseURL ?? "http://localhost:3000";
    const token = await loginApi(request, apiBase);
    const headers = { Authorization: `Bearer ${token}` };
    const years = await request.get(`${apiBase}/api/v1/academic-years`, { headers });
    expect(years.ok()).toBeTruthy();
    const year = (await years.json())[0].id as string;
    const suffix = Date.now();
    const g10 = await request.post(`${apiBase}/api/v1/class-sections`, {
      headers,
      data: {
        academic_year_id: year,
        name: `A-${suffix}`,
        grade_label: "Grade 10",
      },
    });
    expect(g10.status()).toBe(201);
    const g12 = await request.post(`${apiBase}/api/v1/class-sections`, {
      headers,
      data: {
        academic_year_id: year,
        name: `A-${suffix}`,
        grade_label: "Grade 12",
      },
    });
    expect(g12.status()).toBe(201);
  });

  test("curriculum authoring UI create controls", async ({ page }) => {
    await loginUi(page);
    await page.goto("/curriculum");
    await expect(page.getByTestId("curriculum-create-form")).toBeVisible();
    await expect(page.getByTestId("curriculum-create-submit")).toBeVisible();
  });

  test("question paper workflow guidance visible", async ({ page }) => {
    await loginUi(page);
    await page.goto("/assessments");
    await page.locator("table tbody tr").first().click();
    await page.getByTestId("link-questions").click();
    await expect(page.getByTestId("question-paper-workflow-guide")).toBeVisible();
    await expect(page.getByTestId("workflow-step-apply")).toBeVisible();
  });

  test("answer sheet upload guidance", async ({ page }) => {
    await loginUi(page);
    await page.goto("/submissions/upload");
    await expect(page.getByTestId("question-paper-vs-answer-sheet-guidance")).toBeVisible();
  });
});
