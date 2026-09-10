import { test, expect, type APIRequestContext, type Page } from "@playwright/test";

const ADMIN_EMAIL = "admin@demo.eduvijna.local";
const ADMIN_PASSWORD = "DemoAdmin!2026";

async function loginApi(
  request: APIRequestContext,
  apiBase: string,
): Promise<string> {
  const login = await request.post(`${apiBase}/api/v1/auth/login`, {
    data: {
      email: ADMIN_EMAIL,
      password: ADMIN_PASSWORD,
      tenant_slug: "demo",
    },
  });
  expect(login.ok()).toBeTruthy();
  return ((await login.json()) as { access_token: string }).access_token;
}

async function loginUi(page: Page) {
  await page.goto("/login");
  await page.getByTestId("login-email").fill(ADMIN_EMAIL);
  await page.getByTestId("login-password").fill(ADMIN_PASSWORD);
  await page.getByTestId("login-submit").click();
  await expect(page.getByTestId("app-shell")).toBeVisible({ timeout: 30_000 });
}

test.describe("B17 real quality psychometrics + calibration smoke", () => {
  test("API smoke + UI pages reachable", async ({ page, request }) => {
    const apiBase = process.env.E2E_API_BASE_URL ?? "http://127.0.0.1:8000";
    const token = await loginApi(request, apiBase);
    const headers = { Authorization: `Bearer ${token}` };

    const assessments = await request.get(`${apiBase}/api/v1/assessments`, {
      headers,
    });
    expect(assessments.ok()).toBeTruthy();
    const items = ((await assessments.json()) as { items?: { id: string }[] })
      .items;
    test.skip(!items?.length, "No assessments available for B17 smoke");

    // Prefer an assessment that has a version; fall back to list versions.
    const assessmentId = items![0].id;
    const versions = await request.get(
      `${apiBase}/api/v1/assessments/${assessmentId}/versions`,
      { headers },
    );
    expect(versions.ok()).toBeTruthy();
    const versionItems = (
      (await versions.json()) as { items?: { id: string }[] }
    ).items;
    test.skip(!versionItems?.length, "No assessment versions for B17 smoke");
    const versionId = versionItems![0].id;

    const psych = await request.post(
      `${apiBase}/api/v1/quality/psychometrics/runs`,
      {
        headers,
        data: { assessment_version_id: versionId },
      },
    );
    expect(psych.ok()).toBeTruthy();
    const psychBody = (await psych.json()) as {
      id: string;
      status: string;
    };
    expect(["INSUFFICIENT_SAMPLE", "COMPLETED", "PENDING"]).toContain(
      psychBody.status,
    );

    const cal = await request.post(
      `${apiBase}/api/v1/quality/calibration/sessions`,
      {
        headers,
        data: {
          assessment_version_id: versionId,
          title: `B17 E2E ${Date.now()}`,
          min_cases: 2,
        },
      },
    );
    expect(cal.ok()).toBeTruthy();
    expect(((await cal.json()) as { status: string }).status).toBe("DRAFT");

    await loginUi(page);
    await page.goto("/quality/psychometrics");
    await expect(page.getByTestId("b17-psychometrics-workspace")).toBeVisible({
      timeout: 30_000,
    });
    await page.goto("/quality/calibration");
    await expect(page.getByTestId("b17-calibration-workspace")).toBeVisible({
      timeout: 30_000,
    });
  });
});
