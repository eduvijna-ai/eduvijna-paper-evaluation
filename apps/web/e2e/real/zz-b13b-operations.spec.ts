import { test, expect, type APIRequestContext } from "@playwright/test";

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

test.describe("B16 real operations (as far as practical)", () => {
  test("operations APIs are reachable with fixed providers", async ({
    request,
    page,
  }) => {
    const apiBase =
      process.env.API_UPSTREAM_URL?.replace(/\/$/, "") ?? "http://127.0.0.1:18000";

    expect((await request.get(`${apiBase}/health`)).ok()).toBeTruthy();

    const token = await loginApi(request, apiBase);
    const headers = { Authorization: `Bearer ${token}` };

    const pools = await request.get(`${apiBase}/api/v1/operations/grading-pools`, {
      headers,
    });
    expect(pools.status()).toBe(200);
    expect(await pools.json()).toHaveProperty("items");

    const policies = await request.get(
      `${apiBase}/api/v1/operations/moderation-policies`,
      { headers },
    );
    expect(policies.status()).toBe(200);

    const cases = await request.get(
      `${apiBase}/api/v1/operations/moderation-cases`,
      { headers },
    );
    expect(cases.status()).toBe(200);

    const grievances = await request.get(
      `${apiBase}/api/v1/operations/grievances`,
      { headers },
    );
    expect(grievances.status()).toBe(200);

    await page.goto("/login");
    await page.getByTestId("login-email").fill(ADMIN_EMAIL);
    await page.getByTestId("login-password").fill(ADMIN_PASSWORD);
    await page.getByTestId("login-submit").click();
    await expect(page.getByTestId("app-shell")).toBeVisible({ timeout: 30_000 });
    await page.goto("/operations/grading");
    await expect(page.getByTestId("b16-grading-workspace")).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByTestId("nav-operations")).toBeVisible();
  });
});
