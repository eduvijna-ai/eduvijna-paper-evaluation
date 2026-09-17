import { expect, test } from "@playwright/test";

test.setTimeout(600_000);

const apiBase =
  process.env.E2E_API_BASE_URL ??
  process.env.API_UPSTREAM_URL ??
  "http://127.0.0.1:18000";

async function apiLogin(
  request: import("@playwright/test").APIRequestContext,
  email = "admin@demo.eduvijna.local",
  password = "DemoAdmin!2026",
  tenantSlug = "demo",
) {
  const res = await request.post(`${apiBase}/api/v1/auth/login`, {
    data: { email, password, tenant_slug: tenantSlug },
  });
  expect(res.ok(), await res.text()).toBeTruthy();
  const body = (await res.json()) as { access_token: string };
  return { Authorization: `Bearer ${body.access_token}` };
}

test.describe("B19 real enterprise integrations", () => {
  test("OIDC, SCIM, LTI, roster, AGS, webhooks, machine API, and admin UI", async ({
    page,
    request,
  }) => {
    const health = await request.get(`${apiBase}/health`);
    expect(health.ok()).toBeTruthy();
    const headers = await apiLogin(request);

    const providers = await request.get(
      `${apiBase}/api/v1/integrations/identity-providers`,
      { headers },
    );
    expect(providers.ok(), await providers.text()).toBeTruthy();
    const oidc = (
      (await providers.json()) as { items: Array<{ id: string; protocol: string; name: string }> }
    ).items.find((item) => item.protocol === "OIDC");
    expect(oidc, "run seed_b19_e2e_enterprise").toBeTruthy();

    await page.goto("/login");
    await page.getByTestId("login-tenant-slug").fill("demo");
    await page.getByTestId("login-enterprise-discover").click();
    await expect(page.getByTestId("login-sso-oidc")).toBeVisible({ timeout: 15_000 });
    await page.getByTestId("login-sso-oidc").click();
    await expect(page.getByTestId("app-shell")).toBeVisible({ timeout: 45_000 });

    const start = await request.get(`${apiBase}/api/v1/sso/oidc/start`, {
      params: { tenant_slug: "demo", provider_id: oidc!.id },
      maxRedirects: 0,
    });
    expect([302, 307]).toContain(start.status());
    const replay = await request.get(`${apiBase}/api/v1/sso/oidc/callback`, {
      params: { code: "x", state: "missing" },
      maxRedirects: 0,
    });
    expect([302, 307]).toContain(replay.status());
    expect(replay.headers()["location"] ?? "").toContain("error=");

    const scimToken = await request.post(
      `${apiBase}/api/v1/integrations/identity-providers/${oidc!.id}/scim-token`,
      { headers },
    );
    expect(scimToken.ok(), await scimToken.text()).toBeTruthy();
    const scimSecret = ((await scimToken.json()) as { secret: string }).secret;
    const scimHeaders = { Authorization: `Bearer ${scimSecret}` };
    const created = await request.post(`${apiBase}/scim/v2/Users`, {
      headers: scimHeaders,
      data: {
        userName: "b19.scim@demo.eduvijna.local",
        displayName: "B19 SCIM",
        externalId: "b19-scim-1",
        active: true,
      },
    });
    expect(created.status()).toBe(201);
    const userId = ((await created.json()) as { id: string }).id;
    const updated = await request.patch(`${apiBase}/scim/v2/Users/${userId}`, {
      headers: scimHeaders,
      data: { Operations: [{ op: "replace", "path": "displayName", value: "B19 SCIM Updated" }] },
    });
    expect(updated.ok()).toBeTruthy();
    const deactivated = await request.patch(`${apiBase}/scim/v2/Users/${userId}`, {
      headers: scimHeaders,
      data: { Operations: [{ op: "replace", path: "active", value: false }] },
    });
    expect(deactivated.ok()).toBeTruthy();
    const denied = await request.post(`${apiBase}/api/v1/auth/login`, {
      data: {
        email: "b19.scim@demo.eduvijna.local",
        password: "anything",
        tenant_slug: "demo",
      },
    });
    expect(denied.status()).toBeGreaterThanOrEqual(400);
    const stillThere = await request.get(`${apiBase}/scim/v2/Users/${userId}`, {
      headers: scimHeaders,
    });
    expect(stillThere.ok()).toBeTruthy();
    expect(((await stillThere.json()) as { userName: string }).userName).toBe(
      "b19.scim@demo.eduvijna.local",
    );

    const ltiLogin = await request.get(`${apiBase}/lti/login`, {
      params: {
        iss: "https://b19-test.example/lti",
        client_id: "lti-client",
        target_link_uri: `${apiBase}/lti/launch`,
        login_hint: "lti-instructor-1",
        lti_deployment_id: "deploy-1",
      },
      maxRedirects: 0,
    });
    expect([302, 307]).toContain(ltiLogin.status());
    const authorizeUrl = ltiLogin.headers()["location"];
    expect(authorizeUrl).toBeTruthy();
    const authorize = await request.get(authorizeUrl!, { maxRedirects: 0 });
    expect(authorize.status()).toBeLessThan(400);

    const badLaunch = await request.post(`${apiBase}/lti/launch`, {
      form: { id_token: "not-a-jwt", state: "nope" },
    });
    expect(badLaunch.status()).toBeGreaterThanOrEqual(400);

    const platforms = await request.get(`${apiBase}/api/v1/integrations/lti-platforms`, {
      headers,
    });
    const platform = (
      (await platforms.json()) as { items: Array<{ id: string }> }
    ).items[0];
    expect(platform).toBeTruthy();
    const links = await request.get(`${apiBase}/api/v1/integrations/lti-resource-links`, {
      headers,
    });
    expect(links.ok()).toBeTruthy();

    const roster = await request.post(`${apiBase}/api/v1/integrations/roster-sync`, {
      headers,
      data: { provider_key: "sis-e2e", resource_link_id: null, members: [] },
    });
    const nrps = await request.post(`${apiBase}/api/v1/integrations/roster-sync`, {
      headers,
      data: {
        provider_key: "lti",
        resource_link_id: (
          (await links.json()) as { items: Array<{ id: string }> }
        ).items[0]?.id,
      },
    });
    expect(nrps.ok() || roster.ok()).toBeTruthy();

    const publishedList = (
      await request.get(`${apiBase}/api/v1/integrations/grade-passbacks`, { headers })
    ).ok();
    expect(publishedList).toBeTruthy();

    const seedMeta = await request.get(`${apiBase}/api/v1/b19-test/ready`);
    expect(seedMeta.ok()).toBeTruthy();

    const cred = await request.post(`${apiBase}/api/v1/integrations/credentials`, {
      headers,
      data: { name: "e2e-machine", scopes: ["results:read"] },
    });
    expect(cred.ok(), await cred.text()).toBeTruthy();
    const secret = ((await cred.json()) as { secret: string }).secret;
    const results = await request.get(`${apiBase}/api/integration/v1/results/published`, {
      headers: { Authorization: `Bearer ${secret}` },
    });
    expect(results.ok(), await results.text()).toBeTruthy();
    const items = ((await results.json()) as { items: Array<{ id: string; status: string }> })
      .items;
    expect(items.length).toBeGreaterThan(0);
    const scopeDenied = await request.post(`${apiBase}/api/integration/v1/roster/upsert`, {
      headers: { Authorization: `Bearer ${secret}` },
      data: { provider_key: "x", members: [] },
    });
    expect(scopeDenied.status()).toBe(403);

    const isoLogin = await request.post(`${apiBase}/api/v1/auth/login`, {
      data: {
        email: "admin@b19-iso.eduvijna.local",
        password: "DemoAdmin!2026",
        tenant_slug: "b19-iso",
      },
    });
    expect(isoLogin.ok(), await isoLogin.text()).toBeTruthy();
    const isoToken = ((await isoLogin.json()) as { access_token: string }).access_token;
    const isoProviders = await request.get(`${apiBase}/api/v1/integrations/identity-providers`, {
      headers: { Authorization: `Bearer ${isoToken}` },
    });
    expect(isoProviders.ok()).toBeTruthy();
    expect(
      ((await isoProviders.json()) as { items: Array<{ name: string }> }).items.find(
        (item) => item.name === "B19 Test OIDC",
      ),
    ).toBeFalsy();

    const hook = await request.post(`${apiBase}/api/v1/integrations/webhooks`, {
      headers,
      data: {
        name: "e2e-hook",
        destination_url: `${apiBase.replace("18000", "8000")}/api/v1/b19-test/webhook-receiver`,
        event_types: ["roster.sync.completed"],
      },
    });
    expect(hook.ok() || hook.status() === 400).toBeTruthy();
    if (hook.ok()) {
      await request.post(`${apiBase}/api/v1/b19-test/webhook-receiver/config`, {
        data: { fail_until_attempt: 1 },
      });
      const writeCred = await request.post(`${apiBase}/api/v1/integrations/credentials`, {
        headers,
        data: { name: "e2e-roster", scopes: ["roster:write"] },
      });
      const writeSecret = ((await writeCred.json()) as { secret: string }).secret;
      const sync = await request.post(`${apiBase}/api/integration/v1/roster/upsert`, {
        headers: { Authorization: `Bearer ${writeSecret}` },
        data: {
          provider_key: "e2e-sis",
          members: [
            {
              external_stable_id: "e2e-stu",
              full_name: "E2E Student",
              student_code: "e2e-stu",
            },
          ],
        },
      });
      expect(sync.ok(), await sync.text()).toBeTruthy();
      const deliveries = await request.get(
        `${apiBase}/api/v1/integrations/webhooks/${((await hook.json()) as { id: string }).id}/deliveries`,
        { headers },
      );
      expect(deliveries.ok()).toBeTruthy();
      const deliveryItems = (
        (await deliveries.json()) as { items: Array<{ id: string; status: string }> }
      ).items;
      if (deliveryItems[0] && deliveryItems[0].status !== "SUCCEEDED") {
        const retry = await request.post(
          `${apiBase}/api/v1/integrations/webhook-deliveries/${deliveryItems[0].id}/retry`,
          { headers },
        );
        expect(retry.ok()).toBeTruthy();
      }
    }

    const publishedId = items[0].id;
    const linkId = (
      (await links.json()) as { items: Array<{ id: string }> }
    ).items[0]?.id;
    if (linkId) {
      const pass1 = await request.post(`${apiBase}/api/v1/integrations/grade-passbacks`, {
        headers,
        data: {
          published_result_id: publishedId,
          resource_link_id: linkId,
          external_user_id: "nrps-student-1",
        },
      });
      expect(pass1.ok(), await pass1.text()).toBeTruthy();
      const pass2 = await request.post(`${apiBase}/api/v1/integrations/grade-passbacks`, {
        headers,
        data: {
          published_result_id: publishedId,
          resource_link_id: linkId,
          external_user_id: "nrps-student-1",
        },
      });
      expect(pass2.ok()).toBeTruthy();
      expect(((await pass2.json()) as { id: string }).id).toBe(
        ((await pass1.json()) as { id: string }).id,
      );
    }

    await page.goto("/login");
    await page.getByTestId("login-email").fill("admin@demo.eduvijna.local");
    await page.getByTestId("login-password").fill("DemoAdmin!2026");
    await page.getByTestId("login-submit").click();
    await expect(page.getByTestId("app-shell")).toBeVisible({ timeout: 30_000 });
    await page.goto("/admin/integrations");
    await expect(page.getByTestId("b19-integrations-workspace")).toBeVisible({
      timeout: 30_000,
    });
    await expect(
      page.getByTestId("b19-provider-oidc").filter({ hasText: "B19 Test OIDC" }),
    ).toBeVisible();
  });
});
