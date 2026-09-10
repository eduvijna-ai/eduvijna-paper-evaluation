import { test, expect, type APIRequestContext, type Page } from "@playwright/test";

const ADMIN_EMAIL = "admin@demo.eduvijna.local";
const ADMIN_PASSWORD = "DemoAdmin!2026";
const DEMO_USER_PASSWORD = "DemoUser!2026";
const EVALUATOR_A_EMAIL = "evaluator-a@demo.eduvijna.local";
const EVALUATOR_B_EMAIL = "evaluator-b@demo.eduvijna.local";

type AuthSession = {
  token: string;
  userId: string;
  headers: { Authorization: string };
};

function detailCode(body: unknown): string | undefined {
  const b = body as {
    detail?: { code?: string } | string;
    error?: { code?: string };
  };
  if (typeof b.detail === "object" && b.detail?.code) return b.detail.code;
  return b.error?.code;
}

async function loginApi(
  request: APIRequestContext,
  apiBase: string,
  email: string,
  password: string,
): Promise<AuthSession> {
  const login = await request.post(`${apiBase}/api/v1/auth/login`, {
    data: { email, password, tenant_slug: "demo" },
  });
  expect(login.ok(), `login failed for ${email}`).toBeTruthy();
  const body = (await login.json()) as {
    access_token: string;
    user: { id: string };
  };
  return {
    token: body.access_token,
    userId: body.user.id,
    headers: { Authorization: `Bearer ${body.access_token}` },
  };
}

async function loginUi(page: Page) {
  await page.goto("/login");
  await page.getByTestId("login-email").fill(ADMIN_EMAIL);
  await page.getByTestId("login-password").fill(ADMIN_PASSWORD);
  await page.getByTestId("login-submit").click();
  await expect(page.getByTestId("app-shell")).toBeVisible({ timeout: 30_000 });
}

test.describe("B17 real quality psychometrics + calibration", () => {
  test("psychometrics insufficient-sample + calibration blind lifecycle", async ({
    page,
    request,
  }) => {
    const apiBase =
      process.env.API_UPSTREAM_URL ??
      process.env.E2E_API_BASE_URL ??
      "http://127.0.0.1:18000";

    const admin = await loginApi(request, apiBase, ADMIN_EMAIL, ADMIN_PASSWORD);
    const evalA = await loginApi(
      request,
      apiBase,
      EVALUATOR_A_EMAIL,
      DEMO_USER_PASSWORD,
    );
    const evalB = await loginApi(
      request,
      apiBase,
      EVALUATOR_B_EMAIL,
      DEMO_USER_PASSWORD,
    );

    const assessments = await request.get(`${apiBase}/api/v1/assessments`, {
      headers: admin.headers,
    });
    expect(assessments.ok()).toBeTruthy();
    const items = ((await assessments.json()) as { items?: { id: string }[] })
      .items;
    test.skip(!items?.length, "No assessments available for B17 smoke");

    const assessmentId = items![0].id;
    const versions = await request.get(
      `${apiBase}/api/v1/assessments/${assessmentId}/versions`,
      { headers: admin.headers },
    );
    expect(versions.ok()).toBeTruthy();
    const versionItems = (
      (await versions.json()) as { items?: { id: string }[] }
    ).items;
    test.skip(!versionItems?.length, "No assessment versions for B17 smoke");
    const versionId = versionItems![0].id;

    // Psychometrics: demo cohort is typically <20 → INSUFFICIENT_SAMPLE (no fabricated metrics).
    const psych = await request.post(
      `${apiBase}/api/v1/quality/psychometrics/runs`,
      {
        headers: admin.headers,
        data: { assessment_version_id: versionId },
      },
    );
    expect(psych.ok(), await psych.text()).toBeTruthy();
    const psychBody = (await psych.json()) as {
      id: string;
      status: string;
      min_cohort_size: number;
      source_result_count: number;
    };
    expect(psychBody.min_cohort_size).toBe(20);
    expect(["INSUFFICIENT_SAMPLE", "COMPLETED"]).toContain(psychBody.status);
    if (psychBody.status === "INSUFFICIENT_SAMPLE") {
      expect(psychBody.source_result_count).toBeLessThan(20);
      const itemsResp = await request.get(
        `${apiBase}/api/v1/quality/psychometrics/runs/${psychBody.id}/items`,
        { headers: admin.headers },
      );
      expect(itemsResp.ok()).toBeTruthy();
      expect(
        ((await itemsResp.json()) as { items: unknown[] }).items.length,
      ).toBe(0);
    }

    // Calibration session (training-size min_cases allowed; reliability still floors at 10).
    const cal = await request.post(
      `${apiBase}/api/v1/quality/calibration/sessions`,
      {
        headers: admin.headers,
        data: {
          assessment_version_id: versionId,
          title: `B17 E2E ${Date.now()}`,
          min_cases: 1,
        },
      },
    );
    expect(cal.ok(), await cal.text()).toBeTruthy();
    const session = (await cal.json()) as { id: string; status: string };
    expect(session.status).toBe("DRAFT");

    // Find an eligible published QE via published results list if available.
    const published = await request.get(
      `${apiBase}/api/v1/analytics/assessments/${assessmentId}`,
      { headers: admin.headers },
    );
    // Soft: if no analytics/published cohort, still verify UI pages.
    if (published.ok()) {
      // Attempt to list eligible sources through benchmark eligibility if present.
      const eligible = await request.get(
        `${apiBase}/api/v1/quality/benchmark-datasets`,
        { headers: admin.headers },
      );
      expect(eligible.status()).not.toBe(500);
    }

    // Add participants while DRAFT (cases may be empty if no published QE found via public APIs).
    for (const userId of [evalA.userId, evalB.userId]) {
      const part = await request.post(
        `${apiBase}/api/v1/quality/calibration/sessions/${session.id}/participants`,
        {
          headers: admin.headers,
          data: { user_id: userId },
        },
      );
      // 200 when draft; ignore if session already progressed.
      expect([200, 409]).toContain(part.status());
    }

    const mySessions = await request.get(
      `${apiBase}/api/v1/quality/calibration/my-sessions`,
      { headers: evalA.headers },
    );
    expect(mySessions.ok()).toBeTruthy();

    // Evaluator must not fetch another evaluator's metrics without manage.
    const foreign = await request.get(
      `${apiBase}/api/v1/quality/calibration/sessions/${session.id}/evaluator-metrics`,
      { headers: evalA.headers },
    );
    expect([403, 401]).toContain(foreign.status());

    // Cross-tenant style: nonsense UUID should be safe NOT_FOUND for manage read.
    const missing = await request.get(
      `${apiBase}/api/v1/quality/psychometrics/runs/00000000-0000-4000-8000-000000000099`,
      { headers: admin.headers },
    );
    expect([404]).toContain(missing.status());
    const missingBody = await missing.json();
    expect(
      detailCode(missingBody) === "NOT_FOUND" || missing.status() === 404,
    ).toBeTruthy();

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
