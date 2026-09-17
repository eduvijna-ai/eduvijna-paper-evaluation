import { test, expect } from "@playwright/test";

async function openAuthed(page: import("@playwright/test").Page, path: string) {
  await page.goto("/login");
  await page.getByTestId("login-email").fill("admin@demo.eduvijna.local");
  await page.getByTestId("login-password").fill("DemoAdmin!2026");
  await page.getByTestId("login-submit").click();
  await expect(page.getByTestId("app-shell")).toBeVisible({ timeout: 30_000 });
  await page.goto(path);
}

test.describe("B19 mock enterprise integrations", () => {
  test("integrations workspace renders identity and LTI sections", async ({
    page,
  }) => {
    await openAuthed(page, "/admin/integrations");
    await expect(page.getByTestId("b19-integrations-workspace")).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByTestId("b19-provider-oidc")).toBeVisible();
    await page.getByTestId("b19-tab-lti").click();
    await expect(page.getByTestId("b19-lti-platform")).toBeVisible();
    await page.getByTestId("b19-tab-credentials").click();
    await expect(page.getByTestId("b19-create-credential")).toBeVisible();
  });

  test("login exposes enterprise SSO discovery", async ({ page }) => {
    await page.goto("/login");
    await page.getByTestId("login-enterprise-discover").click();
    await expect(page.getByTestId("login-sso-oidc")).toBeVisible();
  });
});
