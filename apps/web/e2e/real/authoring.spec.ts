import { test, expect } from "@playwright/test";
import { randomUUID } from "node:crypto";

const ADMIN_EMAIL = "admin@demo.eduvijna.local";
const ADMIN_PASSWORD = "DemoAdmin!2026";

function runId(): string {
  return `${Date.now().toString(36)}${randomUUID().replace(/-/g, "").slice(0, 8)}`;
}

test.describe("B2 real A2 authoring flows", () => {
  test("curriculum → assessment → question/answer/rubric/mapping", async ({
    page,
    request,
  }) => {
    const apiBase = process.env.API_UPSTREAM_URL ?? "http://127.0.0.1:18000";
    expect((await request.get(`${apiBase}/health`)).ok()).toBeTruthy();

    const login = await request.post(`${apiBase}/api/v1/auth/login`, {
      data: { email: ADMIN_EMAIL, password: ADMIN_PASSWORD, tenant_slug: "demo" },
    });
    expect(login.ok()).toBeTruthy();
    const token = (await login.json()).access_token as string;
    const headers = { Authorization: `Bearer ${token}` };
    const suffix = runId();

    const curriculumResponse = await request.post(`${apiBase}/api/v1/curricula`, {
      headers,
      data: {
        code: `B2-CUR-${suffix}`,
        name: `B2 Mathematics ${suffix}`,
        academic_framework: "CVB",
        version_label: "2026",
        status: "active",
      },
    });
    expect(curriculumResponse.status()).toBe(201);
    const curriculum = await curriculumResponse.json();

    const nodeResponse = await request.post(
      `${apiBase}/api/v1/curricula/${curriculum.id}/nodes`,
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
    expect(nodeResponse.status()).toBe(201);
    const node = await nodeResponse.json();

    // Browser auth proves the same-origin Next rewrite is used by live pages.
    await page.goto("/login");
    await page.getByTestId("login-email").fill(ADMIN_EMAIL);
    await page.getByTestId("login-password").fill(ADMIN_PASSWORD);
    await page.getByTestId("login-submit").click();
    await expect(page.getByTestId("app-shell")).toBeVisible({ timeout: 30_000 });

    await page.goto("/curriculum");
    await expect(page.getByTestId("curriculum-list-page")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByText(curriculum.code, { exact: true })).toBeVisible({
      timeout: 20_000,
    });
    await page.getByText(curriculum.code, { exact: true }).click();
    await expect(page.getByTestId("curriculum-detail-page")).toBeVisible({ timeout: 20_000 });
    // exact:true avoids matching the page heading when it contains the node name as a substring
    await expect(page.getByText(node.name, { exact: true })).toBeVisible();

    await page.goto("/assessments/new");
    await expect(page.getByTestId("assessment-new-page")).toBeVisible({ timeout: 20_000 });
    const assessmentCode = `B2-ASM-${suffix}`;
    await page.getByTestId("assessment-field-title").fill(`B2 Assessment ${suffix}`);
    await page.getByTestId("assessment-field-code").fill(assessmentCode);
    await page
      .getByTestId("assessment-field-curriculumId")
      .selectOption(curriculum.id);
    await page.getByTestId("assessment-field-assessmentType").fill("EXAM");
    await page.getByTestId("assessment-field-maxMarks").fill("10");
    await page.getByTestId("assessment-create-submit").click();
    await expect(page.getByTestId("assessment-detail-page")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByText(assessmentCode, { exact: true })).toBeVisible();
    await expect(page.getByTestId("assessment-downstream-boundary")).toBeVisible();
    // B8: analytics is live — link is available even with zero published attempts.
    await expect(page.getByTestId("link-analytics")).toBeVisible();

    const assessmentId = new URL(page.url()).pathname.split("/").filter(Boolean).at(-1)!;
    const versionsResponse = await request.get(
      `${apiBase}/api/v1/assessments/${assessmentId}/versions`,
      { headers },
    );
    expect(versionsResponse.ok()).toBeTruthy();
    const versions = (await versionsResponse.json()) as Array<{ id: string; version_number: number }>;
    const versionId = [...versions].sort((a, b) => b.version_number - a.version_number)[0]!.id;

    const questionResponse = await request.post(
      `${apiBase}/api/v1/assessment-versions/${versionId}/questions`,
      {
        headers,
        data: {
          stable_code: "Q1",
          display_label: "1",
          sequence: 1,
          prompt_text: `What is 2 + 2? ${suffix}`,
          max_marks: "10.00",
          question_type: "SHORT",
          scoring_mode: "LEAF_SCORABLE",
        },
      },
    );
    expect(questionResponse.status()).toBe(201);
    const question = await questionResponse.json();

    const mappingResponse = await request.post(
      `${apiBase}/api/v1/question-versions/${question.id}/curriculum-mappings`,
      {
        headers,
        data: {
          curriculum_node_id: node.id,
          mapping_type: "PRIMARY",
          weight: "1.00",
        },
      },
    );
    expect(mappingResponse.status()).toBe(201);

    const answerResponse = await request.post(
      `${apiBase}/api/v1/assessments/${assessmentId}/answer-key-versions`,
      {
        headers,
        data: {
          assessment_version_id: versionId,
          question_version_id: question.id,
          answer_text: `4 — B2 answer ${suffix}`,
          source_type: "TEACHER",
          status: "DRAFT",
        },
      },
    );
    expect(answerResponse.status()).toBe(201);

    const rubricResponse = await request.post(
      `${apiBase}/api/v1/assessments/${assessmentId}/rubrics`,
      {
        headers,
        data: {
          question_version_id: question.id,
          title: `Q1 rubric ${suffix}`,
          provenance: "TEACHER",
        },
      },
    );
    expect(rubricResponse.status()).toBe(201);
    const rubric = await rubricResponse.json();

    const rubricVersionResponse = await request.post(
      `${apiBase}/api/v1/rubrics/${rubric.id}/versions`,
      {
        headers,
        data: {
          question_version_id: question.id,
          source_type: "TEACHER",
          status: "DRAFT",
        },
      },
    );
    expect(rubricVersionResponse.status()).toBe(201);
    const rubricVersion = await rubricVersionResponse.json();

    const criterionResponse = await request.post(
      `${apiBase}/api/v1/rubric-versions/${rubricVersion.id}/criteria`,
      {
        headers,
        data: {
          criterion_code: "C1",
          description: `Correct answer criterion ${suffix}`,
          max_marks: "10.00",
          sequence: 1,
          scoring_mode: "ADDITIVE",
          partial_credit_allowed: true,
          ecf_policy: "NONE",
          accepted_equivalents: ["4", "four"],
        },
      },
    );
    expect(criterionResponse.status()).toBe(201);

    await page.goto(`/assessments/${assessmentId}/questions`);
    await expect(page.getByTestId("assessment-questions-page")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByText(`What is 2 + 2? ${suffix}`, { exact: true })).toBeVisible();

    await page.goto(`/assessments/${assessmentId}/answer-key`);
    await expect(page.getByTestId("assessment-answer-key-page")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByText(`4 — B2 answer ${suffix}`, { exact: true })).toBeVisible();

    await page.goto(`/assessments/${assessmentId}/rubric`);
    await expect(page.getByTestId("assessment-rubric-page")).toBeVisible({ timeout: 20_000 });
    await expect(
      page.getByText(`Correct answer criterion ${suffix}`, { exact: true }),
    ).toBeVisible();

    await page.goto(`/assessments/${assessmentId}/curriculum-map`);
    await expect(page.getByTestId("assessment-curriculum-map-page")).toBeVisible({ timeout: 20_000 });
    await expect(page.getByTestId("curriculum-map-table")).toContainText(node.name);
  });
});
