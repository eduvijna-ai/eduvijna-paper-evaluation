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

async function loginApi(request: APIRequestContext, apiBase: string): Promise<string> {
  const login = await request.post(`${apiBase}/api/v1/auth/login`, {
    data: { email: ADMIN_EMAIL, password: ADMIN_PASSWORD, tenant_slug: "demo" },
  });
  expect(login.ok()).toBeTruthy();
  return ((await login.json()) as { access_token: string }).access_token;
}

async function createB12Fixture(
  request: APIRequestContext,
  apiBase: string,
  token: string,
): Promise<{
  assessmentA: string;
  assessmentB: string;
  studentId: string;
  curriculumId: string;
  nodeId: string;
}> {
  const headers = { Authorization: `Bearer ${token}` };
  const suffix = runId();

  const curriculum = await request.post(`${apiBase}/api/v1/curricula`, {
    headers,
    data: {
      code: `B12-CUR-${suffix}`,
      name: `B12 Curriculum ${suffix}`,
      version_label: "2026",
      status: "active",
    },
  });
  expect(curriculum.status()).toBe(201);
  const curriculumId = ((await curriculum.json()) as { id: string }).id;

  const subjectNode = await request.post(
    `${apiBase}/api/v1/curricula/${curriculumId}/nodes`,
    {
      headers,
      data: {
        node_type: "SUBJECT",
        code: `SUB-${suffix}`,
        name: `Subject ${suffix}`,
        sequence: 1,
        metadata: {},
        status: "active",
      },
    },
  );
  expect(subjectNode.status()).toBe(201);
  const nodeId = ((await subjectNode.json()) as { id: string }).id;

  async function createAssessment(tag: string): Promise<string> {
    const assessment = await request.post(`${apiBase}/api/v1/assessments`, {
      headers,
      data: {
        curriculum_id: curriculumId,
        code: `B12-${tag}-${suffix}`,
        title: `B12 Assessment ${tag} ${suffix}`,
        assessment_type: "EXAM",
        max_marks: "10.00",
      },
    });
    expect(assessment.status()).toBe(201);
    const body = (await assessment.json()) as {
      id: string;
      initial_version_id: string;
    };
    const versionId = body.initial_version_id;
    const assessmentId = body.id;

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

      expect(
        (
          await request.post(
            `${apiBase}/api/v1/question-versions/${questionId}/curriculum-mappings`,
            {
              headers,
              data: {
                curriculum_node_id: nodeId,
                mapping_type: "PRIMARY",
                weight: "1.00",
              },
            },
          )
        ).status(),
      ).toBe(201);

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
      const rv = await request.post(
        `${apiBase}/api/v1/rubrics/${rubricId}/versions`,
        {
          headers,
          data: {
            question_version_id: questionId,
            source_type: "TEACHER",
            status: "DRAFT",
          },
        },
      );
      expect(rv.status()).toBe(201);
      const rvId = ((await rv.json()) as { id: string }).id;
      expect(
        (
          await request.post(
            `${apiBase}/api/v1/rubric-versions/${rvId}/criteria`,
            {
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
            },
          )
        ).status(),
      ).toBe(201);
      expect(
        (
          await request.post(
            `${apiBase}/api/v1/rubric-versions/${rvId}/approve`,
            { headers },
          )
        ).ok(),
      ).toBeTruthy();
    }

    expect(
      (
        await request.post(
          `${apiBase}/api/v1/assessments/${assessmentId}/transition`,
          { headers, data: { to_status: "READY" } },
        )
      ).status(),
    ).toBe(200);
    expect(
      (
        await request.post(
          `${apiBase}/api/v1/assessments/${assessmentId}/transition`,
          { headers, data: { to_status: "ACTIVE" } },
        )
      ).status(),
    ).toBe(200);

    return assessmentId;
  }

  const assessmentA = await createAssessment("A");
  const assessmentB = await createAssessment("B");

  const years = await request.get(`${apiBase}/api/v1/academic-years`, { headers });
  const sections = await request.get(`${apiBase}/api/v1/class-sections`, {
    headers,
  });
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
      student_code: `B12S-${suffix}`,
      full_name: `B12 Student ${suffix}`,
      class_section_id: section!.id,
      academic_year_id: section!.academic_year_id,
      status: "active",
    },
  });
  expect(student.status()).toBe(201);
  const studentId = ((await student.json()) as { id: string }).id;

  return { assessmentA, assessmentB, studentId, curriculumId, nodeId };
}

/**
 * Publish one attempt with EXERCISE:DEDUCT (CALCULATION) on Q1 and accept AI.
 * Q2 gets a review-style UNREADABLE-ish path via blank mapping so review codes
 * exist but must NOT appear in B12 academic recurrence.
 */
async function publishDeductAttempt(
  page: Page,
  request: APIRequestContext,
  apiBase: string,
  token: string,
  assessmentId: string,
  studentId: string,
  pdf: Buffer,
  label: string,
): Promise<string> {
  const headers = { Authorization: `Bearer ${token}` };

  const upload = await request.post(`${apiBase}/api/v1/submissions`, {
    headers: { Authorization: `Bearer ${token}` },
    multipart: {
      assessment_id: assessmentId,
      file: {
        name: `b12-${label}.pdf`,
        mimeType: "application/pdf",
        buffer: pdf,
      },
    },
  });
  if (!upload.ok()) {
    throw new Error(
      `B12 upload failed status=${upload.status()} body=${await upload.text()}`,
    );
  }
  const submissionId = ((await upload.json()) as { id: string }).id;

  await page.goto("/login");
  await page.getByTestId("login-email").fill(ADMIN_EMAIL);
  await page.getByTestId("login-password").fill(ADMIN_PASSWORD);
  await page.getByTestId("login-submit").click();
  await expect(page.getByTestId("app-shell")).toBeVisible({ timeout: 30_000 });

  await page.goto(`/submissions/${submissionId}`);
  await expect(page.getByTestId("submission-detail-page")).toBeVisible({
    timeout: 30_000,
  });

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

  // Leave Q2 blank → review/system style evidence, not academic recurrence.
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

  await expect(
    page
      .getByTestId("transcription-ai-copy")
      .or(page.getByTestId("transcription-text-input"))
      .first(),
  ).toBeVisible({ timeout: 90_000 });

  const textInput = page.getByTestId("transcription-text-input").first();
  if (await textInput.count()) {
    // Fixed provider: EXERCISE:DEDUCT → CALCULATION on criterion.
    await textInput.fill("EXERCISE:DEDUCT arithmetic slip");
    await page.getByTestId("save-transcription").first().click();
    await page.waitForTimeout(500);
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

  // Accept AI proposals so criterion error_code=CALCULATION is preserved.
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
            error_codes?: string[];
          }>;
        };
        if (body.workflow_state === "EVALUATING") return "evaluating";
        const qes = body.question_evaluations ?? [];
        if (qes.length < 1) return `qes:${qes.length}`;
        for (const qe of qes) {
          if (qe.workflow_state === "ACCEPTED" || qe.workflow_state === "OVERRIDDEN") {
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
                  score: 0,
                  reason: "B12 blank/review leaf override",
                },
              },
            );
            if (![200, 409].includes(over.status())) return `override:${over.status()}`;
          }
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

  const prep = await request.post(
    `${apiBase}/api/v1/submissions/${submissionId}/publication/prepare`,
    { headers },
  );
  expect(prep.ok()).toBeTruthy();
  const prid = ((await prep.json()) as { published_result_id: string })
    .published_result_id;

  await expect
    .poll(
      async () => {
        const ws = await request.get(
          `${apiBase}/api/v1/submissions/${submissionId}/publication`,
          { headers },
        );
        if (!ws.ok()) return "err";
        const latest = (await ws.json()) as { latest?: { status?: string } };
        return latest.latest?.status ?? "";
      },
      { timeout: 120_000 },
    )
    .toBe("GENERATED");

  const pub = await request.post(
    `${apiBase}/api/v1/publication-results/${prid}/publish`,
    { headers },
  );
  expect(pub.ok()).toBeTruthy();

  await expect
    .poll(
      async () => {
        const prepA = await request.post(
          `${apiBase}/api/v1/analytics/published-results/${prid}/prepare`,
          { headers },
        );
        if (!prepA.ok()) return `prep:${prepA.status()}`;
        const st = await request.get(
          `${apiBase}/api/v1/analytics/students/${studentId}`,
          { headers },
        );
        if (!st.ok()) return `st:${st.status()}`;
        const body = (await st.json()) as { materialization_status?: string };
        return body.materialization_status ?? "";
      },
      { timeout: 120_000 },
    )
    .toMatch(/READY|PARTIAL/);

  return prid;
}

test.describe("B12 longitudinal mastery + mistake intelligence (real API)", () => {
  test("two published attempts drive B12 sections with academic recurrence", async ({
    page,
    request,
  }) => {
    test.setTimeout(600_000);
    const apiBase =
      process.env.API_UPSTREAM_URL?.replace(/\/$/, "") ?? "http://127.0.0.1:18000";
    const token = await loginApi(request, apiBase);
    const headers = { Authorization: `Bearer ${token}` };
    const { assessmentA, assessmentB, studentId } = await createB12Fixture(
      request,
      apiBase,
      token,
    );

    const pdfA = await buildUniquePdf("B12-A");
    const pdfB = await buildUniquePdf("B12-B");

    await publishDeductAttempt(
      page,
      request,
      apiBase,
      token,
      assessmentA,
      studentId,
      pdfA,
      "a",
    );
    await publishDeductAttempt(
      page,
      request,
      apiBase,
      token,
      assessmentB,
      studentId,
      pdfB,
      "b",
    );

    await expect
      .poll(
        async () => {
          const rebuild = await request.post(
            `${apiBase}/api/v1/analytics/students/${studentId}/b12/rebuild`,
            { headers },
          );
          if (!rebuild.ok()) return `rebuild:${rebuild.status()}`;
          const state = await request.get(
            `${apiBase}/api/v1/analytics/students/${studentId}/mastery-state`,
            { headers },
          );
          if (!state.ok()) return `state:${state.status()}`;
          const body = (await state.json()) as { items?: unknown[] };
          return (body.items?.length ?? 0) > 0 ? "ready" : "empty";
        },
        { timeout: 120_000 },
      )
      .toBe("ready");

    const repeated = await request.get(
      `${apiBase}/api/v1/analytics/students/${studentId}/repeated-errors`,
      { headers },
    );
    expect(repeated.ok()).toBeTruthy();
    const repeatedBody = (await repeated.json()) as {
      items: Array<{ error_code: string }>;
    };
    const codes = new Set(repeatedBody.items.map((i) => i.error_code));
    expect(codes.has("CALCULATION")).toBeTruthy();
    expect(codes.has("UNREADABLE")).toBeFalsy();

    const recoverable = await request.get(
      `${apiBase}/api/v1/analytics/students/${studentId}/recoverable-marks`,
      { headers },
    );
    expect(recoverable.ok()).toBeTruthy();
    const recoverableBody = (await recoverable.json()) as {
      attributed_potentially_recoverable_marks: string;
      disclaimer: string;
    };
    expect(Number(recoverableBody.attributed_potentially_recoverable_marks)).toBeGreaterThan(
      0,
    );
    expect(recoverableBody.disclaimer).toMatch(/analytical estimate/i);

    await page.goto(`/analytics/students/${studentId}`);
    await expect(page.getByTestId("student-analytics-page")).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByTestId("concept-signals-section")).toBeVisible();
    await expect(page.getByText(/Current evidence signals/i)).toBeVisible();

    await expect(page.getByTestId("b12-longitudinal-mastery")).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByTestId("b12-repeated-errors")).toBeVisible();
    await expect(page.getByTestId("b12-recoverable-marks")).toBeVisible();
    await expect(page.getByTestId("b12-mistake-notebook")).toBeVisible();

    await expect
      .poll(
        async () =>
          (await page.getByTestId("b12-repeated-errors").textContent()) ?? "",
        { timeout: 30_000 },
      )
      .toMatch(/CALCULATION/i);

    await expect(page.getByTestId("b12-recoverable-disclaimer")).toContainText(
      /analytical estimate/i,
    );

    await expect
      .poll(
        async () =>
          (await page.getByTestId("b12-mistake-notebook").textContent()) ?? "",
        { timeout: 30_000 },
      )
      .toMatch(/CALCULATION/i);

    await expect(page.getByTestId("b12-repeated-errors")).not.toContainText(
      /UNREADABLE/i,
    );
  });
});
