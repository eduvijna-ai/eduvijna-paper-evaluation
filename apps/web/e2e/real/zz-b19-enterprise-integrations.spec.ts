import { createHmac } from "node:crypto";
import { expect, test } from "@playwright/test";

test.setTimeout(600_000);

const apiBase =
  process.env.E2E_API_BASE_URL ??
  process.env.API_UPSTREAM_URL ??
  "http://127.0.0.1:18000";

const WEBHOOK_SECRET = "b19-deterministic-webhook-secret";

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

function verifyWebhookHmac(
  secret: string,
  timestamp: string,
  rawBody: string,
  signature: string,
) {
  const digest = createHmac("sha256", secret)
    .update(`${timestamp}.${rawBody}`)
    .digest("hex");
  return signature === `v1=${digest}`;
}

function hiddenValue(html: string, name: string) {
  const match = html.match(
    new RegExp(`name="${name}"[^>]*value="([^"]+)"`, "i"),
  );
  expect(match, `missing form field ${name}`).toBeTruthy();
  return match![1];
}

async function waitForJson<T>(
  load: () => Promise<T>,
  predicate: (value: T) => boolean,
  timeoutMs = 45_000,
) {
  const started = Date.now();
  let last: T | undefined;
  while (Date.now() - started < timeoutMs) {
    last = await load();
    if (predicate(last)) {
      return last;
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error(`timed out waiting for condition: ${JSON.stringify(last)}`);
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
    const providerItems = (
      (await providers.json()) as {
        items: Array<{ id: string; protocol: string; name: string }>;
      }
    ).items;
    const oidc = providerItems.find((item) => item.name === "B19 Test OIDC");
    const saml = providerItems.find((item) => item.name === "B19 Test SAML");
    expect(oidc, "seed_b19_e2e_enterprise must create OIDC").toBeTruthy();
    expect(saml, "seed_b19_e2e_enterprise must create SAML").toBeTruthy();

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
    expect(start.status()).toBe(302);
    const authorizeUrl = start.headers()["location"];
    expect(authorizeUrl).toBeTruthy();
    const authorize = await request.get(authorizeUrl!, { maxRedirects: 0 });
    expect(authorize.status()).toBe(302);
    const callbackUrl = authorize.headers()["location"];
    expect(callbackUrl, "OIDC callback URL").toBeTruthy();
    const firstCallback = await request.get(callbackUrl!, { maxRedirects: 0 });
    expect(firstCallback.status()).toBe(302);
    expect(firstCallback.headers()["location"] ?? "").toContain("exchange_code=");
    const replayCallback = await request.get(callbackUrl!, { maxRedirects: 0 });
    expect(replayCallback.status()).toBe(302);
    expect(replayCallback.headers()["location"] ?? "").toMatch(/error=/);

    const samlStart = await request.get(`${apiBase}/api/v1/sso/saml/start`, {
      params: { tenant_slug: "demo", provider_id: saml!.id },
      maxRedirects: 0,
    });
    expect(samlStart.status()).toBe(302);
    const ssoUrl = samlStart.headers()["location"];
    expect(ssoUrl).toBeTruthy();
    const ssoPage = await request.get(ssoUrl!);
    expect(ssoPage.ok(), await ssoPage.text()).toBeTruthy();
    const ssoHtml = await ssoPage.text();
    const samlResponse = hiddenValue(ssoHtml, "SAMLResponse");
    const relayState = hiddenValue(ssoHtml, "RelayState");
    const acs = await request.post(`${apiBase}/api/v1/sso/saml/acs`, {
      multipart: { SAMLResponse: samlResponse, RelayState: relayState },
      maxRedirects: 0,
    });
    expect(acs.status()).toBe(302);
    expect(acs.headers()["location"] ?? "").toContain("exchange_code=");
    const acsReplay = await request.post(`${apiBase}/api/v1/sso/saml/acs`, {
      multipart: { SAMLResponse: samlResponse, RelayState: relayState },
      maxRedirects: 0,
    });
    expect(acsReplay.status()).toBe(302);
    expect(acsReplay.headers()["location"] ?? "").toMatch(/error=/);

    const scimToken = await request.post(
      `${apiBase}/api/v1/integrations/identity-providers/${oidc!.id}/scim-token`,
      { headers },
    );
    expect(scimToken.ok(), await scimToken.text()).toBeTruthy();
    const scimSecret = ((await scimToken.json()) as { secret: string }).secret;
    const scimHeaders = { Authorization: `Bearer ${scimSecret}` };

    const collision = await request.post(`${apiBase}/scim/v2/Users`, {
      headers: scimHeaders,
      data: {
        userName: "scim.held@demo.eduvijna.local",
        displayName: "Must Not Bind",
        externalId: "b19-scim-collision",
        active: true,
      },
    });
    expect(collision.status()).toBe(409);

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
      data: { Operations: [{ op: "replace", path: "displayName", value: "B19 SCIM Updated" }] },
    });
    expect(updated.ok()).toBeTruthy();

    const scimRevokeEmail = "b19.scim.revoke@demo.eduvijna.local";
    const scimRevokePassword = "DemoUser!2026";
    const revokeCreated = await request.post(`${apiBase}/scim/v2/Users`, {
      headers: scimHeaders,
      data: {
        userName: scimRevokeEmail,
        displayName: "SCIM Revoke User",
        externalId: "b19-scim-revoke",
        active: true,
      },
    });
    expect(revokeCreated.status()).toBe(201);
    const heldId = ((await revokeCreated.json()) as { id: string }).id;
    const setPassword = await request.post(
      `${apiBase}/api/v1/b19-test/users/${heldId}/local-password`,
      { data: { password: scimRevokePassword } },
    );
    expect(setPassword.ok(), await setPassword.text()).toBeTruthy();
    const heldLogin = await request.post(`${apiBase}/api/v1/auth/login`, {
      data: {
        email: scimRevokeEmail,
        password: scimRevokePassword,
        tenant_slug: "demo",
      },
    });
    expect(heldLogin.ok(), await heldLogin.text()).toBeTruthy();
    const heldToken = ((await heldLogin.json()) as { access_token: string }).access_token;
    const heldMe = await request.get(`${apiBase}/api/v1/auth/me`, {
      headers: { Authorization: `Bearer ${heldToken}` },
    });
    expect(heldMe.ok()).toBeTruthy();
    const deactivated = await request.patch(`${apiBase}/scim/v2/Users/${heldId}`, {
      headers: scimHeaders,
      data: { Operations: [{ op: "replace", path: "active", value: false }] },
    });
    expect(deactivated.ok()).toBeTruthy();
    const revokedMe = await request.get(`${apiBase}/api/v1/auth/me`, {
      headers: { Authorization: `Bearer ${heldToken}` },
    });
    expect(revokedMe.status()).toBe(401);
    const deniedLogin = await request.post(`${apiBase}/api/v1/auth/login`, {
      data: {
        email: scimRevokeEmail,
        password: scimRevokePassword,
        tenant_slug: "demo",
      },
    });
    expect(deniedLogin.status()).toBeGreaterThanOrEqual(400);
    const stillThere = await request.get(`${apiBase}/scim/v2/Users/${heldId}`, {
      headers: scimHeaders,
    });
    expect(stillThere.ok()).toBeTruthy();
    const stillBody = (await stillThere.json()) as { userName: string; active: boolean };
    expect(stillBody.userName).toBe(scimRevokeEmail);
    expect(stillBody.active).toBe(false);

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
    expect(ltiLogin.status()).toBe(302);
    const ltiAuthorizeUrl = ltiLogin.headers()["location"];
    expect(ltiAuthorizeUrl).toBeTruthy();
    const ltiAuthorize = await request.get(ltiAuthorizeUrl!);
    expect(ltiAuthorize.ok(), await ltiAuthorize.text()).toBeTruthy();
    const ltiHtml = await ltiAuthorize.text();
    const idToken = hiddenValue(ltiHtml, "id_token");
    const ltiState = hiddenValue(ltiHtml, "state");
    const launch = await request.post(`${apiBase}/lti/launch`, {
      multipart: { id_token: idToken, state: ltiState },
    });
    expect(launch.ok(), await launch.text()).toBeTruthy();

    const badLaunch = await request.post(`${apiBase}/lti/launch`, {
      multipart: { id_token: "not-a-jwt", state: "nope" },
    });
    expect(badLaunch.status()).toBeGreaterThanOrEqual(400);

    const mismatchLogin = await request.get(`${apiBase}/lti/login`, {
      params: {
        iss: "https://b19-test.example/lti",
        client_id: "lti-client",
        target_link_uri: `${apiBase}/lti/launch`,
        login_hint: "lti-instructor-1",
        lti_deployment_id: "deploy-1",
      },
      maxRedirects: 0,
    });
    expect(mismatchLogin.status()).toBe(302);
    const mismatchAuthorize = await request.get(
      `${mismatchLogin.headers()["location"]}&mismatch_target=true`,
    );
    const mismatchHtml = await mismatchAuthorize.text();
    const mismatchLaunch = await request.post(`${apiBase}/lti/launch`, {
      multipart: {
        id_token: hiddenValue(mismatchHtml, "id_token"),
        state: hiddenValue(mismatchHtml, "state"),
      },
    });
    expect(mismatchLaunch.status()).toBeGreaterThanOrEqual(400);

    const unboundLogin = await request.get(`${apiBase}/lti/login`, {
      params: {
        iss: "https://b19-test.example/lti",
        client_id: "lti-client",
        target_link_uri: `${apiBase}/lti/launch`,
        login_hint: "lti-instructor-1",
        lti_deployment_id: "deploy-1",
      },
      maxRedirects: 0,
    });
    expect(unboundLogin.status()).toBe(302);
    const unboundAuthorize = await request.get(
      `${unboundLogin.headers()["location"]}&unbound_assessment=true`,
    );
    const unboundHtml = await unboundAuthorize.text();
    const unboundLaunch = await request.post(`${apiBase}/lti/launch`, {
      multipart: {
        id_token: hiddenValue(unboundHtml, "id_token"),
        state: hiddenValue(unboundHtml, "state"),
      },
    });
    expect(unboundLaunch.status()).toBe(400);
    expect(((await unboundLaunch.json()) as { error: { code: string } }).error.code).toBe(
      "unbound_resource",
    );

    const links = await request.get(`${apiBase}/api/v1/integrations/lti-resource-links`, {
      headers,
    });
    expect(links.ok(), await links.text()).toBeTruthy();
    const link = (
      (await links.json()) as {
        items: Array<{ id: string; assessment_id: string | null; resource_link_id: string }>;
      }
    ).items.find((item) => item.resource_link_id === "res-1" && item.assessment_id);
    expect(link, "seeded LTI resource link bound to an assessment").toBeTruthy();
    const linkId = link!.id;

    const nrps = await request.post(`${apiBase}/api/v1/integrations/roster-sync`, {
      headers,
      data: { provider_key: "lti", resource_link_id: linkId, members: [] },
    });
    expect(nrps.ok(), await nrps.text()).toBeTruthy();
    const students = await request.get(`${apiBase}/api/v1/students`, { headers });
    expect(students.ok(), await students.text()).toBeTruthy();
    const studentItems = (await students.json()) as Array<{
      student_code: string;
      full_name: string;
    }>;
    const rosterStudent = studentItems.find((item) => item.student_code === "B19-E2E-STU");
    expect(rosterStudent, "NRPS/SIS must update existing Student").toBeTruthy();
    expect(rosterStudent!.full_name).toBe("Roster Student One");

    const results = await request.get(`${apiBase}/api/integration/v1/results/published`, {
      headers: {
        Authorization: `Bearer ${(
          await (
            await request.post(`${apiBase}/api/v1/integrations/credentials`, {
              headers,
              data: { name: `e2e-machine-${Date.now()}`, scopes: ["results:read"] },
            })
          ).json()
        ).secret}`,
      },
    });
    expect(results.ok(), await results.text()).toBeTruthy();
    const publishedItems = (
      (await results.json()) as {
        items: Array<{ id: string; status: string; assessment_id: string }>;
      }
    ).items;
    const published = publishedItems.find(
      (item) => item.status === "PUBLISHED" && item.assessment_id === link!.assessment_id,
    );
    expect(published, "current PUBLISHED result for the LTI-bound assessment").toBeTruthy();

    const pass1 = await request.post(`${apiBase}/api/v1/integrations/grade-passbacks`, {
      headers,
      data: {
        published_result_id: published!.id,
        resource_link_id: linkId,
      },
    });
    expect(pass1.ok(), await pass1.text()).toBeTruthy();
    const pass2 = await request.post(`${apiBase}/api/v1/integrations/grade-passbacks`, {
      headers,
      data: {
        published_result_id: published!.id,
        resource_link_id: linkId,
      },
    });
    expect(pass2.ok(), await pass2.text()).toBeTruthy();
    expect(((await pass2.json()) as { id: string }).id).toBe(
      ((await pass1.json()) as { id: string }).id,
    );
    const mismatchPass = await request.post(`${apiBase}/api/v1/integrations/grade-passbacks`, {
      headers,
      data: {
        published_result_id: published!.id,
        resource_link_id: linkId,
        external_user_id: "not-the-mapped-learner",
      },
    });
    expect(mismatchPass.status()).toBeGreaterThanOrEqual(400);

    const cred = await request.post(`${apiBase}/api/v1/integrations/credentials`, {
      headers,
      data: { name: `e2e-results-only-${Date.now()}`, scopes: ["results:read"] },
    });
    expect(cred.ok(), await cred.text()).toBeTruthy();
    const secret = ((await cred.json()) as { secret: string }).secret;
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
    const isoPass = await request.post(`${apiBase}/api/v1/integrations/grade-passbacks`, {
      headers: { Authorization: `Bearer ${isoToken}` },
      data: { published_result_id: published!.id, resource_link_id: linkId },
    });
    expect(isoPass.status()).toBeGreaterThanOrEqual(400);

    const hooks = await request.get(`${apiBase}/api/v1/integrations/webhooks`, { headers });
    expect(hooks.ok(), await hooks.text()).toBeTruthy();
    const hook = (
      (await hooks.json()) as { items: Array<{ id: string; name: string }> }
    ).items.find((item) => item.name === "B19 Test Webhook");
    expect(hook, "seeded webhook endpoint").toBeTruthy();
    await waitForJson(
      async () => {
        const res = await request.get(
          `${apiBase}/api/v1/integrations/webhooks/${hook!.id}/deliveries`,
          { headers },
        );
        expect(res.ok()).toBeTruthy();
        return ((await res.json()) as { items: Array<{ status: string }> }).items;
      },
      (items) => items.every((item) => item.status === "SUCCEEDED" || item.status === "FAILED"),
    );

    const malformed = await request.post(`${apiBase}/api/v1/b19-test/webhook-receiver`, {
      headers: {
        "X-EduVijna-Timestamp": "1",
        "X-EduVijna-Signature": "v1=00",
        "X-EduVijna-Event-Id": "x",
        "X-EduVijna-Event-Type": "roster.sync.completed",
      },
      data: "{}",
    });
    expect(malformed.status()).toBe(401);

    await request.post(`${apiBase}/api/v1/b19-test/webhook-receiver/config`, {
      data: { fail_until_attempt: 1, expected_secret: WEBHOOK_SECRET },
    });
    const retrySync = await request.post(`${apiBase}/api/v1/integrations/roster-sync`, {
      headers,
      data: {
        provider_key: "e2e-autonomous",
        members: [
          { external_stable_id: "e2e-retry", full_name: "Retry Student", student_code: "e2e-retry" },
        ],
      },
    });
    expect(retrySync.ok(), await retrySync.text()).toBeTruthy();
    const autonomous = await waitForJson(
      async () => {
        const res = await request.get(
          `${apiBase}/api/v1/integrations/webhooks/${hook!.id}/deliveries`,
          { headers },
        );
        expect(res.ok()).toBeTruthy();
        return ((await res.json()) as { items: Array<{ id: string; status: string; attempt_count: number }> })
          .items;
      },
      (items) => items.some((item) => item.status === "SUCCEEDED" && item.attempt_count >= 2),
    );
    const succeeded = autonomous.find(
      (item) => item.status === "SUCCEEDED" && item.attempt_count >= 2,
    )!;
    const attemptHistory = await request.get(
      `${apiBase}/api/v1/integrations/webhook-deliveries/${succeeded.id}/attempts`,
      { headers },
    );
    expect(attemptHistory.ok()).toBeTruthy();
    expect(
      ((await attemptHistory.json()) as { items: Array<{ attempt_number: number }> }).items.length,
    ).toBeGreaterThanOrEqual(2);

    const inbox = await request.get(`${apiBase}/api/v1/b19-test/webhook-inbox`);
    expect(inbox.ok()).toBeTruthy();
    const inboxItems = (
      (await inbox.json()) as {
        items: Array<{ timestamp: string; signature: string; body: string }>;
      }
    ).items;
    expect(
      inboxItems.some((item) =>
        verifyWebhookHmac(WEBHOOK_SECRET, item.timestamp, item.body, item.signature),
      ),
    ).toBeTruthy();

    await request.post(`${apiBase}/api/v1/b19-test/webhook-receiver/config`, {
      data: { fail_until_attempt: 5, expected_secret: WEBHOOK_SECRET },
    });
    const terminalSync = await request.post(`${apiBase}/api/v1/integrations/roster-sync`, {
      headers,
      data: {
        provider_key: "e2e-terminal",
        members: [
          {
            external_stable_id: "e2e-term",
            full_name: "Terminal Student",
            student_code: "e2e-term",
          },
        ],
      },
    });
    expect(terminalSync.ok(), await terminalSync.text()).toBeTruthy();
    const terminal = await waitForJson(
      async () => {
        const res = await request.get(
          `${apiBase}/api/v1/integrations/webhooks/${hook!.id}/deliveries`,
          { headers },
        );
        return ((await res.json()) as {
          items: Array<{ id: string; status: string; terminal_failure: boolean; attempt_count: number }>;
        }).items;
      },
      (items) => items.some((item) => item.terminal_failure === true && item.status === "FAILED"),
      90_000,
    );
    const failed = terminal.find((item) => item.terminal_failure)!;
    await request.post(`${apiBase}/api/v1/b19-test/webhook-receiver/config`, {
      data: { fail_until_attempt: 0, expected_secret: WEBHOOK_SECRET },
    });
    const manual = await request.post(
      `${apiBase}/api/v1/integrations/webhook-deliveries/${failed.id}/retry`,
      { headers },
    );
    expect(manual.ok(), await manual.text()).toBeTruthy();
    await waitForJson(
      async () => {
        const res = await request.get(
          `${apiBase}/api/v1/integrations/webhooks/${hook!.id}/deliveries`,
          { headers },
        );
        return ((await res.json()) as { items: Array<{ id: string; status: string }> }).items;
      },
      (items) => items.some((item) => item.id === failed.id && item.status === "SUCCEEDED"),
    );

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
