import { test, expect, type APIRequestContext, type Page } from "@playwright/test";
import { randomUUID } from "node:crypto";
import { PDFDocument, StandardFonts } from "pdf-lib";

const ADMIN_EMAIL = "admin@demo.eduvijna.local";
const ADMIN_PASSWORD = "DemoAdmin!2026";

function runId(): string {
  return `${Date.now().toString(36)}${randomUUID().replace(/-/g, "").slice(0, 8)}`;
}

async function buildUniquePdf(label: string): Promise<Buffer> {
  const doc = await PDFDocument.create();
  const font = await doc.embedFont(StandardFonts.Helvetica);
  for (const pageLabel of [`Page 1 — ${label}`, `Page 2 — ${label}`]) {
    const page = doc.addPage([400, 560]);
    page.drawText(pageLabel, { x: 48, y: 500, size: 16, font });
    page.drawText(runId(), { x: 48, y: 460, size: 10, font });
  }
  return Buffer.from(await doc.save());
}

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

async function browserLogin(page: Page) {
  await page.goto("/login");
  await page.getByTestId("login-email").fill(ADMIN_EMAIL);
  await page.getByTestId("login-password").fill(ADMIN_PASSWORD);
  await page.getByTestId("login-submit").click();
  await expect(page.getByTestId("app-shell")).toBeVisible({ timeout: 30_000 });
}

test.describe("B10 real authoring AI flows", () => {
  test("upload → parse → apply → AI answer/rubric → approve → READY → ACTIVE", async ({
    page,
    request,
  }) => {
    const apiBase = process.env.API_UPSTREAM_URL ?? "http://127.0.0.1:18000";
    expect((await request.get(`${apiBase}/health`)).ok()).toBeTruthy();

    const token = await loginApi(request, apiBase);
    const headers = { Authorization: `Bearer ${token}` };
    const suffix = runId();

    const curriculum = await request.post(`${apiBase}/api/v1/curricula`, {
      headers,
      data: {
        code: `B10-CUR-${suffix}`,
        name: `B10 Curriculum ${suffix}`,
        academic_framework: "CVB",
        version_label: "2026",
        status: "active",
      },
    });
    expect(curriculum.status()).toBe(201);
    const curriculumId = ((await curriculum.json()) as { id: string }).id;

    const node = await request.post(
      `${apiBase}/api/v1/curricula/${curriculumId}/nodes`,
      {
        headers,
        data: {
          node_type: "SUBJECT",
          code: `MATH-${suffix}`,
          name: `Mathematics ${suffix}`,
          sequence: 1,
          metadata: {},
          status: "active",
        },
      },
    );
    expect(node.status()).toBe(201);
    const nodeId = ((await node.json()) as { id: string }).id;

    await browserLogin(page);

    await page.goto("/curriculum");
    await expect(page.getByTestId("curriculum-list-page")).toBeVisible({
      timeout: 20_000,
    });
    await expect(page.getByText(`B10-CUR-${suffix}`, { exact: true })).toBeVisible({
      timeout: 20_000,
    });

    await page.goto("/assessments/new");
    await expect(page.getByTestId("assessment-new-page")).toBeVisible({
      timeout: 20_000,
    });
    const assessmentCode = `B10-ASM-${suffix}`;
    await page.getByTestId("assessment-field-title").fill(`B10 Assessment ${suffix}`);
    await page.getByTestId("assessment-field-code").fill(assessmentCode);
    await page.getByTestId("assessment-field-curriculumId").selectOption(curriculumId);
    await page.getByTestId("assessment-field-assessmentType").fill("EXAM");
    await page.getByTestId("assessment-field-maxMarks").fill("10");
    await page.getByTestId("assessment-create-submit").click();
    await expect(page.getByTestId("assessment-detail-page")).toBeVisible({
      timeout: 30_000,
    });

    const assessmentId = new URL(page.url()).pathname.split("/").filter(Boolean).at(-1)!;

    await page.goto(`/assessments/${assessmentId}/questions`);
    await expect(page.getByTestId("assessment-questions-page")).toBeVisible({
      timeout: 20_000,
    });
    await expect(page.getByTestId("question-paper-authoring")).toBeVisible();
    await expect(page.getByTestId("ai-proposal-truth-notice")).toContainText(
      /teacher apply/i,
    );

    const pdf = await buildUniquePdf(`B10-${suffix}`);
    await page.getByTestId("question-paper-upload").setInputFiles({
      name: `b10-paper-${suffix}.pdf`,
      mimeType: "application/pdf",
      buffer: pdf,
    });
    await expect(page.getByTestId("question-paper-artifact")).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByTestId("artifact-filename")).toContainText(
      `b10-paper-${suffix}.pdf`,
    );
    await expect(page.getByTestId("artifact-scan-status")).toBeVisible();

    await page.getByTestId("parse-question-paper").click();

    await expect
      .poll(
        async () => {
          const versionsResponse = await request.get(
            `${apiBase}/api/v1/assessments/${assessmentId}/versions`,
            { headers },
          );
          if (!versionsResponse.ok()) return `versions:${versionsResponse.status()}`;
          const versions = (await versionsResponse.json()) as Array<{
            id: string;
            version_number: number;
          }>;
          const versionId = [...versions].sort(
            (a, b) => b.version_number - a.version_number,
          )[0]!.id;
          const latest = await request.get(
            `${apiBase}/api/v1/assessment-versions/${versionId}/authoring-ai-runs/latest?operation=PARSE_QUESTION_PAPER`,
            { headers },
          );
          if (latest.status() === 404) return "no-run";
          if (!latest.ok()) return `latest:${latest.status()}`;
          const runBody = (await latest.json()) as {
            status?: string;
            failure_code?: string | null;
          };
          if (runBody.status === "REVIEW_REQUIRED") return "REVIEW_REQUIRED";
          if (runBody.status === "FAILED" || runBody.status === "UNAVAILABLE") {
            return `${runBody.status}:${runBody.failure_code ?? ""}`;
          }
          return runBody.status ?? "pending";
        },
        { timeout: 120_000 },
      )
      .toBe("REVIEW_REQUIRED");

    await page.reload();
    await expect(page.getByTestId("question-tree-proposal")).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByTestId("artifact-parse-status")).toContainText(
      "REVIEW_REQUIRED",
    );

    const leafPrompt = page.getByTestId("proposal-prompt-0-0");
    await expect(leafPrompt).toBeVisible();
    await leafPrompt.fill(`Corrected B10 leaf ${suffix}`);
    await page.getByTestId("save-question-tree-proposal").click();
    await page.getByTestId("apply-question-tree").click();
    await expect(page.getByTestId("question-tree-proposal")).toHaveCount(0, {
      timeout: 30_000,
    });
    await expect(page.getByText(`Corrected B10 leaf ${suffix}`)).toBeVisible({
      timeout: 30_000,
    });

    const versionsResponse = await request.get(
      `${apiBase}/api/v1/assessments/${assessmentId}/versions`,
      { headers },
    );
    expect(versionsResponse.ok()).toBeTruthy();
    const versions = (await versionsResponse.json()) as Array<{
      id: string;
      version_number: number;
    }>;
    const versionId = [...versions].sort(
      (a, b) => b.version_number - a.version_number,
    )[0]!.id;

    const treeResponse = await request.get(
      `${apiBase}/api/v1/assessment-versions/${versionId}/questions`,
      { headers },
    );
    expect(treeResponse.ok()).toBeTruthy();
    const tree = (await treeResponse.json()) as Array<{
      id: string;
      children?: Array<{ id: string }>;
    }>;
    const leafId = tree[0]?.children?.[0]?.id ?? tree[0]?.id;
    expect(leafId).toBeTruthy();

    const mapping = await request.post(
      `${apiBase}/api/v1/question-versions/${leafId}/curriculum-mappings`,
      {
        headers,
        data: {
          curriculum_node_id: nodeId,
          mapping_type: "PRIMARY",
          weight: "1.00",
        },
      },
    );
    expect(mapping.status()).toBe(201);

    await page.goto(`/assessments/${assessmentId}/answer-key`);
    await expect(page.getByTestId("assessment-answer-key-page")).toBeVisible({
      timeout: 20_000,
    });
    await expect(page.getByTestId("answer-key-truth-notice")).toBeVisible();
    await page.getByTestId(`generate-ai-answer-${leafId}`).click();
    await expect(page.getByTestId(`answer-key-status-${leafId}`)).toContainText(
      "REVIEW_REQUIRED",
      { timeout: 60_000 },
    );
    await expect(
      page.getByTestId(`answer-key-provenance-${leafId}`),
    ).toContainText(/AI proposal/i);
    await expect(
      page.getByTestId(`answer-key-provenance-${leafId}`),
    ).not.toContainText(/^Provenance: Teacher$/);

    const assessmentAfterAk = await request.get(
      `${apiBase}/api/v1/assessments/${assessmentId}`,
      { headers },
    );
    expect(assessmentAfterAk.ok()).toBeTruthy();
    expect(
      ((await assessmentAfterAk.json()) as { status: string }).status,
    ).toBe("RUBRIC_REVIEW");

    await page.goto(`/assessments/${assessmentId}/rubric`);
    await expect(page.getByTestId("assessment-rubric-page")).toBeVisible({
      timeout: 20_000,
    });
    await expect(page.getByTestId("rubric-truth-notice")).toBeVisible();
    await page.getByTestId(`generate-ai-rubric-${leafId}`).click();
    await expect(page.getByTestId(`rubric-status-${leafId}`)).toContainText(
      "REVIEW_REQUIRED",
      { timeout: 60_000 },
    );
    await expect(page.getByTestId(`rubric-provenance-${leafId}`)).toContainText(
      /AI proposal/i,
    );

    const readyBlocked = await request.post(
      `${apiBase}/api/v1/assessments/${assessmentId}/transition`,
      { headers, data: { to_status: "READY" } },
    );
    expect(readyBlocked.status()).toBe(409);

    await page.goto(`/assessments/${assessmentId}/answer-key`);
    await page.getByTestId(`approve-answer-key-${leafId}`).click();
    await expect(page.getByTestId(`answer-key-status-${leafId}`)).toContainText(
      "APPROVED",
      { timeout: 30_000 },
    );

    await page.goto(`/assessments/${assessmentId}/rubric`);
    await page.getByTestId(`approve-rubric-${leafId}`).click();
    await expect(page.getByTestId(`rubric-status-${leafId}`)).toContainText(
      "APPROVED",
      { timeout: 30_000 },
    );

    const readyOk = await request.post(
      `${apiBase}/api/v1/assessments/${assessmentId}/transition`,
      { headers, data: { to_status: "READY" } },
    );
    expect(readyOk.status()).toBe(200);
    expect(((await readyOk.json()) as { status: string }).status).toBe("READY");

    const active = await request.post(
      `${apiBase}/api/v1/assessments/${assessmentId}/transition`,
      { headers, data: { to_status: "ACTIVE" } },
    );
    expect(active.status()).toBe(200);
    expect(((await active.json()) as { status: string }).status).toBe("ACTIVE");
  });
});
