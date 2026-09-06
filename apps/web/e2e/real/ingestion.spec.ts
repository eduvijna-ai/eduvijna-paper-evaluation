import { test, expect, type APIRequestContext } from "@playwright/test";
import { randomUUID } from "node:crypto";
import { PDFDocument, StandardFonts } from "pdf-lib";

const ADMIN_EMAIL = "admin@demo.eduvijna.local";
const ADMIN_PASSWORD = "DemoAdmin!2026";

function runId(): string {
  return `${Date.now().toString(36)}${randomUUID().replace(/-/g, "").slice(0, 8)}`;
}

async function buildMultiPagePdf(): Promise<Buffer> {
  const doc = await PDFDocument.create();
  const font = await doc.embedFont(StandardFonts.Helvetica);
  for (const label of ["Page 1 — B3", "Page 2 — B3"]) {
    const page = doc.addPage([400, 560]);
    page.drawText(label, { x: 48, y: 500, size: 18, font });
  }
  return Buffer.from(await doc.save());
}

async function loginApi(request: APIRequestContext, apiBase: string): Promise<string> {
  const login = await request.post(`${apiBase}/api/v1/auth/login`, {
    data: { email: ADMIN_EMAIL, password: ADMIN_PASSWORD, tenant_slug: "demo" },
  });
  expect(login.ok()).toBeTruthy();
  return ((await login.json()) as { access_token: string }).access_token;
}

async function createActiveAssessment(
  request: APIRequestContext,
  apiBase: string,
  token: string,
): Promise<{ assessmentId: string; studentId: string }> {
  const headers = { Authorization: `Bearer ${token}` };
  const suffix = runId();

  const curriculum = await request.post(`${apiBase}/api/v1/curricula`, {
    headers,
    data: {
      code: `B3-CUR-${suffix}`,
      name: `B3 Curriculum ${suffix}`,
      version_label: "2026",
      status: "active",
    },
  });
  expect(curriculum.status()).toBe(201);
  const curriculumId = ((await curriculum.json()) as { id: string }).id;

  const node = await request.post(`${apiBase}/api/v1/curricula/${curriculumId}/nodes`, {
    headers,
    data: {
      node_type: "SUBJECT",
      code: `SUB-${suffix}`,
      name: `Subject ${suffix}`,
      sequence: 1,
      metadata: {},
      status: "active",
    },
  });
  expect(node.status()).toBe(201);

  const assessment = await request.post(`${apiBase}/api/v1/assessments`, {
    headers,
    data: {
      curriculum_id: curriculumId,
      code: `B3-ASM-${suffix}`,
      title: `B3 Active Assessment ${suffix}`,
      assessment_type: "EXAM",
      max_marks: "10.00",
    },
  });
  expect(assessment.status()).toBe(201);
  const assessmentBody = (await assessment.json()) as {
    id: string;
    initial_version_id: string;
  };
  const versionId = assessmentBody.initial_version_id;
  const assessmentId = assessmentBody.id;

  const question = await request.post(
    `${apiBase}/api/v1/assessment-versions/${versionId}/questions`,
    {
      headers,
      data: {
        stable_code: "Q1",
        display_label: "1",
        sequence: 1,
        prompt_text: "2+2?",
        max_marks: "10.00",
        question_type: "SHORT",
        scoring_mode: "LEAF_SCORABLE",
      },
    },
  );
  expect(question.status()).toBe(201);
  const questionId = ((await question.json()) as { id: string }).id;

  const key = await request.post(
    `${apiBase}/api/v1/assessments/${assessmentId}/answer-key-versions`,
    {
      headers,
      data: {
        assessment_version_id: versionId,
        question_version_id: questionId,
        answer_text: "4",
        source_type: "TEACHER",
        status: "DRAFT",
      },
    },
  );
  expect(key.status()).toBe(201);
  expect(
    (
      await request.post(
        `${apiBase}/api/v1/answer-key-versions/${(await key.json()).id}/approve`,
        { headers },
      )
    ).ok(),
  ).toBeTruthy();

  const rubric = await request.post(`${apiBase}/api/v1/assessments/${assessmentId}/rubrics`, {
    headers,
    data: {
      question_version_id: questionId,
      title: "Q1",
      provenance: "TEACHER",
    },
  });
  expect(rubric.status()).toBe(201);
  const rubricId = ((await rubric.json()) as { id: string }).id;
  const rv = await request.post(`${apiBase}/api/v1/rubrics/${rubricId}/versions`, {
    headers,
    data: {
      question_version_id: questionId,
      source_type: "TEACHER",
      status: "DRAFT",
    },
  });
  expect(rv.status()).toBe(201);
  const rvId = ((await rv.json()) as { id: string }).id;
  expect(
    (
      await request.post(`${apiBase}/api/v1/rubric-versions/${rvId}/criteria`, {
        headers,
        data: {
          criterion_code: "C1",
          description: "correct",
          max_marks: "10.00",
          sequence: 1,
          scoring_mode: "ADDITIVE",
          partial_credit_allowed: true,
          ecf_policy: "NONE",
        },
      })
    ).status(),
  ).toBe(201);
  expect(
    (await request.post(`${apiBase}/api/v1/rubric-versions/${rvId}/approve`, { headers })).ok(),
  ).toBeTruthy();

  expect(
    (
      await request.post(`${apiBase}/api/v1/assessments/${assessmentId}/transition`, {
        headers,
        data: { to_status: "READY" },
      })
    ).ok(),
  ).toBeTruthy();
  expect(
    (
      await request.post(`${apiBase}/api/v1/assessments/${assessmentId}/transition`, {
        headers,
        data: { to_status: "ACTIVE" },
      })
    ).ok(),
  ).toBeTruthy();

  const years = await request.get(`${apiBase}/api/v1/academic-years`, { headers });
  const sections = await request.get(`${apiBase}/api/v1/class-sections`, { headers });
  expect(years.ok()).toBeTruthy();
  expect(sections.ok()).toBeTruthy();
  const yearRows = (await years.json()) as Array<{ id: string }>;
  const sectionRows = (await sections.json()) as Array<{
    id: string;
    academic_year_id: string;
  }>;
  const section = sectionRows.find((s) =>
    yearRows.some((y) => y.id === s.academic_year_id),
  );
  expect(section).toBeTruthy();
  const student = await request.post(`${apiBase}/api/v1/students`, {
    headers,
    data: {
      student_code: `B3S-${suffix}`,
      full_name: `B3 Student ${suffix}`,
      class_section_id: section!.id,
      academic_year_id: section!.academic_year_id,
      status: "active",
    },
  });
  expect(student.status()).toBe(201);
  return { assessmentId, studentId: ((await student.json()) as { id: string }).id };
}

test.describe("B3 real submission ingestion + identity", () => {
  test("upload → normalize → identity confirm with live boundary", async ({
    page,
    request,
  }) => {
    const apiBase = process.env.API_UPSTREAM_URL ?? "http://127.0.0.1:18000";
    expect((await request.get(`${apiBase}/health`)).ok()).toBeTruthy();
    const token = await loginApi(request, apiBase);
    const { assessmentId, studentId } = await createActiveAssessment(
      request,
      apiBase,
      token,
    );
    const pdf = await buildMultiPagePdf();

    await page.goto("/login");
    await page.getByTestId("login-email").fill(ADMIN_EMAIL);
    await page.getByTestId("login-password").fill(ADMIN_PASSWORD);
    await page.getByTestId("login-submit").click();
    await expect(page.getByTestId("app-shell")).toBeVisible({ timeout: 30_000 });

    await page.goto("/submissions/upload");
    await expect(page.getByTestId("submissions-upload-page")).toBeVisible({
      timeout: 20_000,
    });
    await expect(page.getByTestId("raw-unmarked-banner")).toBeVisible();
    await page.getByTestId("upload-assessment").selectOption(assessmentId);
    await page
      .getByTestId("upload-file")
      .setInputFiles({
        name: "b3-sheet.pdf",
        mimeType: "application/pdf",
        buffer: pdf,
      });
    await page.getByTestId("upload-submit").click();
    await expect(page.getByTestId("submission-detail-page")).toBeVisible({
      timeout: 60_000,
    });

    await expect
      .poll(
        async () => {
          const text = await page.getByTestId("submission-workflow-state").textContent();
          return text?.trim() ?? "";
        },
        { timeout: 90_000 },
      )
      .toMatch(/identity review/i);

    await expect(page.getByTestId("submission-page-count")).toHaveText("2");
    await expect(page.getByTestId("submission-downstream-boundary")).toBeVisible();
    await expect(page.getByTestId("link-mapping")).toHaveCount(0);
    await expect(page.getByTestId("link-evaluation")).toHaveCount(0);

    await page.getByTestId("link-identity").click();
    await expect(page.getByTestId("identity-review-page")).toBeVisible({
      timeout: 20_000,
    });
    await expect(page.getByTestId("paper-viewer-shell")).toBeVisible();
    await expect(page.getByTestId("live-page-image")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("identity-live-notice")).toBeVisible();
    await expect(page.getByText(/manual|roster/i).first()).toBeVisible();

    await expect(page.getByTestId(`match-candidate-${studentId}`)).toBeVisible();
    await page.getByTestId(`match-candidate-${studentId}`).click();
    await page.getByTestId("confirm-identity").click();
    await expect(page.getByTestId("submission-detail-page")).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByTestId("submission-identity-state")).toContainText(
      /confirmed/i,
    );
    await expect(page.getByTestId("submission-workflow-state")).toContainText(
      /processing/i,
    );
    await expect(page.getByTestId("submission-downstream-boundary")).toBeVisible();
    await expect(page.getByTestId("link-mapping")).toHaveCount(0);
    await expect(page.getByTestId("link-evaluation")).toHaveCount(0);
  });
});
