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
  for (const label of ["Page 1 — B7", "Page 2 — B7"]) {
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
      code: `B7-CUR-${suffix}`,
      name: `B7 Curriculum ${suffix}`,
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
      code: `B7-ASM-${suffix}`,
      title: `B7 Publication Assessment ${suffix}`,
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
      student_code: `B7S-${suffix}`,
      full_name: `B7 Student ${suffix}`,
      class_section_id: section!.id,
      academic_year_id: section!.academic_year_id,
      status: "active",
    },
  });
  expect(student.status()).toBe(201);
  return { assessmentId, studentId: ((await student.json()) as { id: string }).id };
}

async function reachApproved(
  page: Page,
  request: APIRequestContext,
  apiBase: string,
  token: string,
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
    name: "b7-sheet.pdf",
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

  await page.getByTestId("question-tree-item-2").click();
  await page.getByTestId("mark-blank").click();
  await page.getByTestId("confirm-mapping").click();
  await page.getByTestId("finalize-mapping").click();
  await expect(page.getByTestId("submission-detail-page")).toBeVisible({
    timeout: 30_000,
  });

  await expect
    .poll(
      async () => {
        await page.goto(`/submissions/${submissionId}`);
        return (await page.getByTestId("submission-workflow-state").textContent()) ?? "";
      },
      { timeout: 60_000 },
    )
    .toMatch(/ready for evaluation/i);

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

  await expect(page.getByTestId("transcription-ai-copy").or(page.getByTestId("transcription-text-input")).first()).toBeVisible({
    timeout: 90_000,
  });

  const textInput = page.getByTestId("transcription-text-input").first();
  if (await textInput.count()) {
    await textInput.fill("4");
    await page.getByTestId("save-transcription").first().click();
    await page.waitForTimeout(500);
  }
  const confirmFirst = page.getByTestId("confirm-transcription").first();
  if ((await confirmFirst.count()) && (await confirmFirst.isEnabled())) {
    await confirmFirst.click();
    await page.waitForTimeout(400);
  }
  for (let i = 0; i < 12; i += 1) {
    const enabled = page.locator(
      '[data-testid="confirm-transcription"]:not([disabled])',
    );
    if ((await enabled.count()) === 0) break;
    await enabled.first().click();
    await page.waitForTimeout(500);
  }

  await expect(page.getByTestId("finalize-transcription")).toBeEnabled({
    timeout: 30_000,
  });
  await page.getByTestId("finalize-transcription").click();
  await expect(page).toHaveURL(new RegExp(`/submissions/${submissionId}$`), {
    timeout: 30_000,
  });
  await expect(page.getByTestId("submission-detail-page")).toBeVisible({
    timeout: 30_000,
  });
  await expect(page.getByTestId("link-evaluation")).toBeVisible();

  // Drive evaluation to APPROVED via API for reliability; UI publication is covered below.
  const headers = { Authorization: `Bearer ${token}` };
  await expect
    .poll(
      async () => {
        const prep = await request.post(
          `${apiBase}/api/v1/submissions/${submissionId}/evaluation/prepare`,
          { headers },
        );
        if (![200, 409].includes(prep.status())) return `prep:${prep.status()}`;
        const ws = await request.get(
          `${apiBase}/api/v1/submissions/${submissionId}/evaluation`,
          { headers },
        );
        if (!ws.ok()) return `ws:${ws.status()}`;
        const body = (await ws.json()) as {
          workflow_state?: string;
          question_evaluations?: Array<{
            id: string;
            proposed_ai_score: number | string | null;
            max_mark: number | string;
            workflow_state: string;
          }>;
        };
        if (body.workflow_state === "EVALUATING") return "evaluating";
        const qes = body.question_evaluations ?? [];
        if (qes.length < 2) return `qes:${qes.length}`;
        let idx = 0;
        for (const qe of qes) {
          if (qe.workflow_state === "ACCEPTED" || qe.workflow_state === "OVERRIDDEN") {
            idx += 1;
            continue;
          }
          if (qe.proposed_ai_score !== null && qe.proposed_ai_score !== undefined) {
            const acc = await request.post(
              `${apiBase}/api/v1/question-evaluations/${qe.id}/accept`,
              { headers },
            );
            if (![200, 409].includes(acc.status())) return `accept:${acc.status()}`;
          } else {
            const over = await request.post(
              `${apiBase}/api/v1/question-evaluations/${qe.id}/override`,
              {
                headers,
                data: {
                  score: Number(qe.max_mark) > 0 ? Math.min(3.5, Number(qe.max_mark)) : 0,
                  reason: `B7 E2E override Q${idx}`,
                },
              },
            );
            if (![200, 409].includes(over.status())) return `override:${over.status()}`;
          }
          idx += 1;
        }
        const fin = await request.post(
          `${apiBase}/api/v1/submissions/${submissionId}/evaluation/finalize`,
          { headers },
        );
        if (!fin.ok()) return `fin:${fin.status()}:${await fin.text()}`;
        const finBody = (await fin.json()) as { workflow_state?: string };
        return finBody.workflow_state ?? "unknown";
      },
      { timeout: 180_000 },
    )
    .toBe("APPROVED");

  await page.goto(`/submissions/${submissionId}`);
  await expect(page.getByTestId("submission-workflow-state")).toContainText(
    /approved/i,
    { timeout: 30_000 },
  );
  return submissionId;
}

test.describe("B7 publication + reports (real API)", () => {
  test("generate package, consumer 404 before publish, success after; analytics/learning refuse live UUID", async ({
    page,
    request,
  }) => {
    test.setTimeout(420_000);
    const apiBase =
      process.env.API_UPSTREAM_URL?.replace(/\/$/, "") ?? "http://127.0.0.1:18000";
    const token = await loginApi(request, apiBase);
    const { assessmentId, studentId } = await createTwoLeafAssessment(
      request,
      apiBase,
      token,
    );
    const pdf = await buildMultiPagePdf();
    const submissionId = await reachApproved(
      page,
      request,
      apiBase,
      token,
      assessmentId,
      studentId,
      pdf,
    );

    // Consumer 404 before publish (API + UI).
    const before = await request.get(
      `${apiBase}/api/v1/submissions/${submissionId}/published-result`,
      { headers: { Authorization: `Bearer ${token}` } },
    );
    expect(before.status()).toBe(404);

    await page.goto(`/reports/student/${studentId}/assessment/${assessmentId}`);
    await expect(
      page.getByTestId("error-state").or(page.getByText(/not found|failed|unavailable/i)),
    ).toBeVisible({ timeout: 20_000 });

    await page.goto(`/submissions/${submissionId}`);
    await expect(page.getByTestId("link-publication")).toBeVisible();
    await page.getByTestId("link-publication").click();
    await expect(page.getByTestId("publication-workspace-page")).toBeVisible({
      timeout: 30_000,
    });

    await page.getByTestId("generate-publication-package").click();
    await expect
      .poll(
        async () => {
          const status =
            (await page.getByTestId("publication-result-status").textContent()) ??
            "";
          return status.trim();
        },
        { timeout: 120_000 },
      )
      .toMatch(/GENERATED/i);

    await expect(page.getByTestId("publication-snapshot-hash")).toBeVisible();
    await expect(page.getByTestId("preview-annotated-paper")).toBeVisible();
    await expect(page.getByTestId("publish-results")).toBeVisible();

    // Still not published — consumer 404.
    await page.goto(`/reports/parent/${studentId}/assessment/${assessmentId}`);
    await expect(page.getByTestId("error-state")).toBeVisible({ timeout: 20_000 });

    await page.goto(`/submissions/${submissionId}/publication`);
    await expect(page.getByTestId("publish-results")).toBeVisible({
      timeout: 30_000,
    });
    page.once("dialog", (dialog) => dialog.accept());
    await page.getByTestId("publish-results").click();

    await expect
      .poll(
        async () => {
          await page.goto(`/submissions/${submissionId}`);
          return (
            (await page.getByTestId("submission-workflow-state").textContent()) ??
            ""
          );
        },
        { timeout: 60_000 },
      )
      .toMatch(/published/i);

    await expect(page.getByTestId("submission-published-immutable")).toBeVisible();
    await expect(page.getByTestId("link-student-report")).toBeVisible();

    await page.getByTestId("link-student-report").click();
    await expect(page.getByTestId("student-report-page")).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByText(/Topics/i)).toHaveCount(0);

    await page.goto(`/reports/parent/${studentId}/assessment/${assessmentId}`);
    await expect(page.getByTestId("parent-report-page")).toBeVisible({
      timeout: 20_000,
    });

    await page.goto(`/reports/teacher/${studentId}/assessment/${assessmentId}`);
    await expect(page.getByTestId("teacher-report-page")).toBeVisible({
      timeout: 20_000,
    });

    await page.goto(`/submissions/${submissionId}/annotated-paper`);
    await expect(page.getByTestId("annotated-paper-page")).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByTestId("download-evaluated-pdf")).toBeVisible();
    await expect(page.getByTestId("annotation-score-chip")).toBeVisible();

    // Analytics / learning unavailable for live UUID.
    await page.goto(`/analytics/assessments/${assessmentId}`);
    await expect(
      page.getByTestId("error-state").or(page.getByText(/not live|unavailable|failed/i)),
    ).toBeVisible({ timeout: 20_000 });

    await page.goto(`/learning/${studentId}`);
    await expect(
      page.getByTestId("error-state").or(page.getByText(/not live|unavailable|failed/i)),
    ).toBeVisible({ timeout: 20_000 });
  });
});
