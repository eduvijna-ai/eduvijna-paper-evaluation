import { test, expect, type APIRequestContext, type Page } from "@playwright/test";
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
  for (const label of ["Page 1 — B6", "Page 2 — B6"]) {
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

async function createTwoLeafAssessment(
  request: APIRequestContext,
  apiBase: string,
  token: string,
): Promise<{ assessmentId: string; studentId: string }> {
  const headers = { Authorization: `Bearer ${token}` };
  const suffix = runId();

  const curriculum = await request.post(`${apiBase}/api/v1/curricula`, {
    headers,
    data: {
      code: `B6-CUR-${suffix}`,
      name: `B6 Curriculum ${suffix}`,
      version_label: "2026",
      status: "active",
    },
  });
  expect(curriculum.status()).toBe(201);
  const curriculumId = ((await curriculum.json()) as { id: string }).id;

  await request.post(`${apiBase}/api/v1/curricula/${curriculumId}/nodes`, {
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

  const assessment = await request.post(`${apiBase}/api/v1/assessments`, {
    headers,
    data: {
      curriculum_id: curriculumId,
      code: `B6-ASM-${suffix}`,
      title: `B6 Evaluation Assessment ${suffix}`,
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

  const leafSpecs = [
    { code: "Q1", label: "1", prompt: "2+2?", marks: "5.00", answer: "4" },
    { code: "Q2", label: "2", prompt: "3+3?", marks: "5.00", answer: "6" },
  ];

  for (const [index, leaf] of leafSpecs.entries()) {
    const question = await request.post(
      `${apiBase}/api/v1/assessment-versions/${versionId}/questions`,
      {
        headers,
        data: {
          stable_code: leaf.code,
          display_label: leaf.label,
          sequence: index + 1,
          prompt_text: leaf.prompt,
          max_marks: leaf.marks,
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
          answer_text: leaf.answer,
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

    const rubric = await request.post(
      `${apiBase}/api/v1/assessments/${assessmentId}/rubrics`,
      {
        headers,
        data: {
          question_version_id: questionId,
          title: leaf.code,
          provenance: "TEACHER",
        },
      },
    );
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
            max_marks: leaf.marks,
            sequence: 1,
            scoring_mode: "ADDITIVE",
            partial_credit_allowed: true,
            ecf_policy: "NONE",
          },
        })
      ).status(),
    ).toBe(201);
    expect(
      (await request.post(`${apiBase}/api/v1/rubric-versions/${rvId}/approve`, { headers }))
        .ok(),
    ).toBeTruthy();
  }

  expect(
    (
      await request.post(`${apiBase}/api/v1/assessments/${assessmentId}/transition`, {
        headers,
        data: { to_status: "READY" },
      })
    ).status(),
  ).toBe(200);
  expect(
    (
      await request.post(`${apiBase}/api/v1/assessments/${assessmentId}/transition`, {
        headers,
        data: { to_status: "ACTIVE" },
      })
    ).status(),
  ).toBe(200);

  const years = await request.get(`${apiBase}/api/v1/academic-years`, { headers });
  const sections = await request.get(`${apiBase}/api/v1/class-sections`, { headers });
  const yearRows = (await years.json()) as { id: string }[];
  const sectionRows = (await sections.json()) as {
    id: string;
    academic_year_id: string;
  }[];
  const section = sectionRows.find((s) =>
    yearRows.some((y) => y.id === s.academic_year_id),
  );
  expect(section).toBeTruthy();
  const student = await request.post(`${apiBase}/api/v1/students`, {
    headers,
    data: {
      student_code: `B6S-${suffix}`,
      full_name: `B6 Student ${suffix}`,
      class_section_id: section!.id,
      academic_year_id: section!.academic_year_id,
      status: "active",
    },
  });
  expect(student.status()).toBe(201);
  return { assessmentId, studentId: ((await student.json()) as { id: string }).id };
}

async function reachTranscriptionReady(
  page: Page,
  assessmentId: string,
  studentId: string,
  pdf: Buffer,
): Promise<string> {
  await page.goto("/login");
  await page.getByTestId("login-email").fill(ADMIN_EMAIL);
  await page.getByTestId("login-password").fill(ADMIN_PASSWORD);
  await page.getByTestId("login-submit").click();
  await expect(page.getByTestId("app-shell")).toBeVisible({ timeout: 30_000 });

  await page.goto("/submissions/upload");
  await page.getByTestId("upload-assessment").selectOption(assessmentId);
  await page.getByTestId("upload-file").setInputFiles({
    name: "b6-sheet.pdf",
    mimeType: "application/pdf",
    buffer: pdf,
  });
  await page.getByTestId("upload-submit").click();
  await expect(page.getByTestId("submission-detail-page")).toBeVisible({
    timeout: 60_000,
  });
  const submissionUrl = page.url();
  const submissionId = submissionUrl.split("/submissions/")[1]?.split(/[/?#]/)[0] ?? "";
  expect(submissionId).toBeTruthy();

  await expect
    .poll(
      async () => {
        const text = await page.getByTestId("submission-workflow-state").textContent();
        return text?.trim() ?? "";
      },
      { timeout: 120_000 },
    )
    .toMatch(/identity review/i);

  await page.getByTestId("link-identity").click();
  await expect(page.getByTestId("identity-review-page")).toBeVisible({
    timeout: 20_000,
  });
  await page.getByTestId(`match-candidate-${studentId}`).click();
  await page.getByTestId("confirm-identity").click();

  await expect
    .poll(
      async () => {
        await page.goto(`/submissions/${submissionId}`);
        const text = await page.getByTestId("submission-workflow-state").textContent();
        return text?.trim() ?? "";
      },
      { timeout: 120_000 },
    )
    .toMatch(/mapping review/i);

  await page.getByTestId("link-mapping").click();
  await expect(page.getByTestId("mapping-review-page")).toBeVisible({
    timeout: 30_000,
  });

  const aiBadge = page.getByTestId("region-ai-proposal-badge");
  if ((await aiBadge.count()) === 0) {
    await page.getByTestId("add-answer-region").click();
  }
  await page.getByTestId("assign-region").click();
  await page.getByTestId("confirm-mapping").click();
  await expect(page.getByTestId("mapping-completion")).toContainText(
    /1 of 2 scorable questions confirmed/i,
    { timeout: 20_000 },
  );

  await page.getByTestId("question-tree-item-2").click();
  await page.getByTestId("mark-blank").click();
  await page.getByTestId("confirm-mapping").click();
  await expect(page.getByTestId("mapping-completion")).toContainText(
    /2 of 2 scorable questions confirmed/i,
    { timeout: 20_000 },
  );

  await page.getByTestId("finalize-mapping").click();
  await expect(page.getByTestId("submission-detail-page")).toBeVisible({
    timeout: 30_000,
  });

  await expect
    .poll(
      async () => {
        await page.reload();
        const href = await page.getByTestId("open-current-stage").getAttribute("href");
        return href ?? "";
      },
      { timeout: 120_000 },
    )
    .toMatch(/\/transcription$/);

  await page.getByTestId("open-current-stage").click();
  await expect(page.getByTestId("transcription-review-page")).toBeVisible({
    timeout: 30_000,
  });

  const textInput = page.getByTestId("transcription-text-input").first();
  if (await textInput.count()) {
    await textInput.fill("4");
    await page.getByTestId("save-transcription").first().click();
  }
  for (let i = 0; i < 10; i += 1) {
    const enabled = page.locator(
      '[data-testid="confirm-transcription"]:not([disabled])',
    );
    if ((await enabled.count()) === 0) break;
    await enabled.first().click();
    await page.waitForTimeout(400);
  }

  await page.getByTestId("finalize-transcription").click();
  await expect(page).toHaveURL(new RegExp(`/submissions/${submissionId}$`), {
    timeout: 30_000,
  });
  await expect(page.getByTestId("submission-detail-page")).toBeVisible({
    timeout: 30_000,
  });
  await expect(page.getByTestId("link-evaluation")).toBeVisible();
  return submissionId;
}

test.describe("B6 real evaluation ledger review", () => {
  test("accept + override + finalize → APPROVED (not published)", async ({
    page,
    request,
  }) => {
    const apiBase = process.env.API_UPSTREAM_URL ?? "http://127.0.0.1:18000";
    expect((await request.get(`${apiBase}/health`)).ok()).toBeTruthy();
    const token = await loginApi(request, apiBase);
    const { assessmentId, studentId } = await createTwoLeafAssessment(
      request,
      apiBase,
      token,
    );
    const pdf = await buildMultiPagePdf();
    const submissionId = await reachTranscriptionReady(
      page,
      assessmentId,
      studentId,
      pdf,
    );

    await page.getByTestId("link-evaluation").click();
    await expect(page.getByTestId("evaluation-workspace-page")).toBeVisible({
      timeout: 60_000,
    });
    await expect(page.getByTestId("evaluation-workspace-page")).toHaveAttribute(
      "data-evaluation-mode",
      "live",
    );

    await expect
      .poll(
        async () => {
          await page.reload();
          const text = await page.getByTestId("evaluation-progress").textContent();
          const panel = await page.getByTestId("evaluation-decision-panel").count();
          return `${text ?? ""}|${panel}`;
        },
        { timeout: 180_000 },
      )
      .toMatch(/of \d+ questions finalized\|1/);

    await expect(page.getByTestId("confidence-dimensions")).toBeVisible();
    await expect(page.getByTestId("evaluation-transcription")).toBeVisible();

    // ACCEPT first question when a proposal exists.
    const acceptBtn = page.getByTestId("teacher-action-ACCEPT");
    if (await acceptBtn.isEnabled()) {
      await acceptBtn.click();
      await page.getByRole("button", { name: "Apply" }).click();
      await expect(page.getByTestId("teacher-action-result")).toContainText(
        /accepted/i,
        { timeout: 20_000 },
      );
    }

    // Move to second question and OVERRIDE with reason.
    await page.getByTestId("question-tree-item-2").click();
    await page.waitForTimeout(500);
    await page.getByTestId("teacher-action-CHANGE_SCORE").click();
    await page.getByTestId("teacher-new-score").fill("4");
    await page.getByTestId("teacher-feedback").fill("Teacher override for B6 E2E");
    await page.getByRole("button", { name: "Apply" }).click();
    await expect(page.getByTestId("teacher-action-result")).toContainText(
      /overrid/i,
      { timeout: 20_000 },
    );

    // Persistence across reload.
    await page.reload();
    await expect(page.getByTestId("evaluation-workspace-page")).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByTestId("evaluation-progress")).toContainText(
      /of \d+ questions finalized/i,
    );

    // Finish any remaining questions via tree codes 1/2.
    for (const code of ["1", "2"]) {
      const approve = page.getByTestId("approve-evaluation");
      if (await approve.count()) break;
      const item = page.getByTestId(`question-tree-item-${code}`);
      if (await item.count()) await item.click();
      await page.waitForTimeout(400);
      const accept = page.getByTestId("teacher-action-ACCEPT");
      if ((await accept.count()) && (await accept.isEnabled())) {
        await accept.click();
        await page.getByRole("button", { name: "Apply" }).click();
        await page.waitForTimeout(500);
        continue;
      }
      const change = page.getByTestId("teacher-action-CHANGE_SCORE");
      if (await change.count()) {
        await change.click();
        await page.getByTestId("teacher-new-score").fill("3");
        await page.getByTestId("teacher-feedback").fill(`Finalize remaining Q ${code}`);
        await page.getByRole("button", { name: "Apply" }).click();
        await page.waitForTimeout(500);
      }
    }

    await expect(page.getByTestId("approve-evaluation")).toBeVisible({
      timeout: 60_000,
    });
    await page.getByTestId("approve-evaluation").click();
    await expect(page.getByTestId("evaluation-approved-boundary")).toContainText(
      /Evaluation approved\./i,
      { timeout: 30_000 },
    );
    await expect(page.getByTestId("link-publication-from-evaluation").or(page.getByTestId("evaluation-downstream-mock-boundary"))).toBeVisible();

    await page.goto(`/submissions/${submissionId}`);
    await expect(page.getByTestId("submission-workflow-state")).toContainText(
      /approved/i,
      { timeout: 30_000 },
    );
    await expect(page.getByTestId("submission-workflow-state")).not.toContainText(
      /published/i,
    );
    await expect(page.getByTestId("submission-downstream-boundary")).toContainText(
      /publication|analytics|learning/i,
    );

    // Live UUID must not open mock analytics/learning.
    await expect(page.getByTestId("link-evaluation")).toBeVisible();
    await page.goto(`/analytics/assessments/${assessmentId}`);
    await expect(page.getByTestId("error-state").or(page.getByText(/not live|unavailable|failed/i))).toBeVisible({
      timeout: 20_000,
    });
  });
});
