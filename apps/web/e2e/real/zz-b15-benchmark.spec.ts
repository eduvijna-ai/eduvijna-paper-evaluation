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

async function loginUi(page: Page) {
  await page.goto("/login");
  await page.getByTestId("login-email").fill(ADMIN_EMAIL);
  await page.getByTestId("login-password").fill(ADMIN_PASSWORD);
  await page.getByTestId("login-submit").click();
  await expect(page.getByTestId("app-shell")).toBeVisible({ timeout: 30_000 });
}

async function createSourceAssessment(
  request: APIRequestContext,
  apiBase: string,
  token: string,
): Promise<{ assessmentId: string; studentId: string; questionCodes: string[] }> {
  const headers = { Authorization: `Bearer ${token}` };
  const suffix = runId();

  const curriculum = await request.post(`${apiBase}/api/v1/curricula`, {
    headers,
    data: {
      code: `B15-CUR-${suffix}`,
      name: `B15 Curriculum ${suffix}`,
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
  const subjectId = ((await subjectNode.json()) as { id: string }).id;

  const topicNode = await request.post(
    `${apiBase}/api/v1/curricula/${curriculumId}/nodes`,
    {
      headers,
      data: {
        parent_id: subjectId,
        node_type: "TOPIC",
        code: `TOP-${suffix}`,
        name: `Topic ${suffix}`,
        sequence: 1,
        metadata: {},
        status: "active",
      },
    },
  );
  expect(topicNode.status()).toBe(201);
  const nodeId = ((await topicNode.json()) as { id: string }).id;

  const assessment = await request.post(`${apiBase}/api/v1/assessments`, {
    headers,
    data: {
      curriculum_id: curriculumId,
      code: `B15-ASM-${suffix}`,
      title: `B15 Source Assessment ${suffix}`,
      assessment_type: "EXAM",
      max_marks: "5.00",
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
        prompt_text: "Solve 2x=4",
        max_marks: "5.00",
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
        answer_text: "2",
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
        title: "Q1",
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
          max_marks: "5.00",
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
      student_code: `B15-${suffix}`,
      full_name: `B15 Student ${suffix}`,
      class_section_id: section!.id,
      academic_year_id: section!.academic_year_id,
      status: "active",
    },
  });
  expect(student.status()).toBe(201);

  return {
    assessmentId,
    studentId: ((await student.json()) as { id: string }).id,
    questionCodes: ["1"],
  };
}

async function publishApprovedResult(
  page: Page,
  request: APIRequestContext,
  apiBase: string,
  token: string,
  assessmentId: string,
  studentId: string,
  pdf: Buffer,
): Promise<{ publishedResultId: string; questionEvaluationId: string }> {
  const headers = { Authorization: `Bearer ${token}` };

  const upload = await request.post(`${apiBase}/api/v1/submissions`, {
    headers,
    multipart: {
      assessment_id: assessmentId,
      file: {
        name: "b15-sheet.pdf",
        mimeType: "application/pdf",
        buffer: pdf,
      },
    },
  });
  expect(upload.ok()).toBeTruthy();
  const submissionId = ((await upload.json()) as { id: string }).id;

  await loginUi(page);
  await page.goto(`/submissions/${submissionId}`);
  await expect(page.getByTestId("submission-detail-page")).toBeVisible({
    timeout: 30_000,
  });

  await expect
    .poll(
      async () =>
        (await page.getByTestId("submission-workflow-state").textContent())?.trim() ??
        "",
      { timeout: 120_000 },
    )
    .toMatch(/identity review/i);

  await page.getByTestId("link-identity").click();
  await page.getByTestId(`match-candidate-${studentId}`).click();
  await page.getByTestId("confirm-identity").click();

  await expect
    .poll(
      async () => {
        await page.goto(`/submissions/${submissionId}`);
        return (
          (await page.getByTestId("submission-workflow-state").textContent())?.trim() ??
          ""
        );
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
  await page.getByTestId("finalize-mapping").click();

  await expect
    .poll(
      async () => {
        await page.reload();
        return (
          (await page.getByTestId("open-current-stage").getAttribute("href")) ?? ""
        );
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

  const textInputs = page.getByTestId("transcription-text-input");
  const count = await textInputs.count();
  for (let i = 0; i < count; i += 1) {
    await textInputs.nth(i).fill("EXERCISE:PARTIAL anonymized answer text");
    await page.getByTestId("save-transcription").nth(i).click();
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
  await expect
    .poll(
      async () => {
        const path = new URL(page.url()).pathname;
        if (path === `/submissions/${submissionId}`) return "done";
        if (path.endsWith("/transcription")) {
          const btn = page.getByTestId("finalize-transcription");
          if (await btn.isEnabled().catch(() => false)) {
            await btn.click().catch(() => undefined);
          }
        }
        return path;
      },
      { timeout: 90_000 },
    )
    .toBe("done");

  let questionEvaluationId = "";
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
            workflow_state: string;
            max_mark?: number | string;
          }>;
        };
        if (body.workflow_state === "EVALUATING") return "evaluating";
        const qes = body.question_evaluations ?? [];
        if (qes.length < 1) return "qes:0";
        for (const qe of qes) {
          if (qe.workflow_state === "ACCEPTED" || qe.workflow_state === "OVERRIDDEN") {
            questionEvaluationId = qe.id;
            continue;
          }
          const maxMark = Number(qe.max_mark ?? 5);
          const over = await request.post(
            `${apiBase}/api/v1/question-evaluations/${qe.id}/override`,
            {
              headers,
              data: { score: Math.min(3.5, maxMark), reason: "B15 E2E gold" },
            },
          );
          if (![200, 409].includes(over.status())) {
            return `override:${over.status()}`;
          }
          questionEvaluationId = qe.id;
        }
        const fin = await request.post(
          `${apiBase}/api/v1/submissions/${submissionId}/evaluation/finalize`,
          { headers },
        );
        if (!fin.ok()) return `fin:${fin.status()}`;
        return ((await fin.json()) as { workflow_state?: string }).workflow_state ?? "";
      },
      { timeout: 180_000 },
    )
    .toBe("APPROVED");

  const prep = await request.post(
    `${apiBase}/api/v1/submissions/${submissionId}/publication/prepare`,
    { headers },
  );
  expect(prep.ok()).toBeTruthy();
  const publishedResultId = ((await prep.json()) as { published_result_id: string })
    .published_result_id;

  await expect
    .poll(
      async () => {
        const ws = await request.get(
          `${apiBase}/api/v1/submissions/${submissionId}/publication`,
          { headers },
        );
        if (!ws.ok()) return "err";
        return ((await ws.json()) as { latest?: { status?: string } }).latest
          ?.status ?? "";
      },
      { timeout: 120_000 },
    )
    .toBe("GENERATED");

  expect(
    (
      await request.post(
        `${apiBase}/api/v1/publication-results/${publishedResultId}/publish`,
        { headers },
      )
    ).ok(),
  ).toBeTruthy();

  expect(questionEvaluationId).toBeTruthy();
  return { publishedResultId, questionEvaluationId };
}

test.describe("B15 live gold benchmark quality (real API)", () => {
  test("dataset → case → lock → pass gate (+ regress fail) + auth boundary", async ({
    page,
    request,
  }) => {
    test.setTimeout(900_000);
    const apiBase =
      process.env.API_UPSTREAM_URL?.replace(/\/$/, "") ?? "http://127.0.0.1:18000";
    expect((await request.get(`${apiBase}/health`)).ok()).toBeTruthy();

    const token = await loginApi(request, apiBase);
    const headers = { Authorization: `Bearer ${token}` };
    const suffix = runId();

    const datasetRes = await request.post(
      `${apiBase}/api/v1/quality/benchmark-datasets`,
      {
        headers,
        data: {
          code: `GOLD-E2E-${suffix}`,
          title: `B15 Gold ${suffix}`,
          description: "Real E2E dataset",
        },
      },
    );
    expect(datasetRes.ok()).toBeTruthy();
    const dataset = (await datasetRes.json()) as { id: string; code: string };

    const versionRes = await request.post(
      `${apiBase}/api/v1/quality/benchmark-datasets/${dataset.id}/versions`,
      { headers, data: {} },
    );
    expect(versionRes.ok()).toBeTruthy();
    const version = (await versionRes.json()) as {
      id: string;
      status: string;
    };
    expect(version.status).toBe("DRAFT");

    let publishedResultId = "";
    let questionEvaluationId = "";

    const eligible = await request.get(
      `${apiBase}/api/v1/quality/benchmark-versions/${version.id}/eligible-sources`,
      { headers },
    );
    expect(eligible.ok()).toBeTruthy();
    const eligibleBody = (await eligible.json()) as {
      items?: Array<{
        published_result_id: string;
        question_evaluations: Array<{ question_evaluation_id: string }>;
      }>;
    };
    const firstSource = eligibleBody.items?.[0];
    const firstQe = firstSource?.question_evaluations?.[0];
    if (firstSource && firstQe) {
      publishedResultId = firstSource.published_result_id;
      questionEvaluationId = firstQe.question_evaluation_id;
    } else {
      const source = await createSourceAssessment(request, apiBase, token);
      const pdf = await buildUniquePdf("B15-gold");
      const published = await publishApprovedResult(
        page,
        request,
        apiBase,
        token,
        source.assessmentId,
        source.studentId,
        pdf,
      );
      publishedResultId = published.publishedResultId;
      questionEvaluationId = published.questionEvaluationId;
    }

    const caseRes = await request.post(
      `${apiBase}/api/v1/quality/benchmark-versions/${version.id}/cases`,
      {
        headers,
        data: {
          published_result_id: publishedResultId,
          question_evaluation_id: questionEvaluationId,
        },
      },
    );
    expect(caseRes.ok()).toBeTruthy();
    const goldCase = (await caseRes.json()) as {
      id: string;
      expected_final_marks: number;
    };
    expect(JSON.stringify(goldCase).toLowerCase()).not.toContain("student");

    const lockRes = await request.post(
      `${apiBase}/api/v1/quality/benchmark-versions/${version.id}/lock`,
      { headers },
    );
    expect(lockRes.ok()).toBeTruthy();
    expect(((await lockRes.json()) as { status: string }).status).toBe("LOCKED");

    const passRun = await request.post(
      `${apiBase}/api/v1/quality/benchmark-versions/${version.id}/regression-runs`,
      {
        headers,
        data: {
          candidate_provider: "fixed",
          candidate_model: "fixed-benchmark-pass",
          candidate_model_version: "B15_V1",
          candidate_prompt_template_version: "fixed-benchmark-v1",
          idempotency_key: `pass-${suffix}`,
        },
      },
    );
    expect(passRun.ok()).toBeTruthy();
    const passBody = (await passRun.json()) as {
      id: string;
      verdict: string;
      status: string;
    };
    expect(passBody.verdict).toBe("PASS");
    expect(passBody.status).toBe("PASSED");

    const passGate = await request.get(
      `${apiBase}/api/v1/quality/regression-runs/${passBody.id}/gate`,
      { headers },
    );
    expect(passGate.ok()).toBeTruthy();
    const passGateBody = (await passGate.json()) as {
      verdict: string;
      passed: boolean;
    };
    expect(passGateBody.verdict).toBe("PASS");
    expect(passGateBody.passed).toBe(true);

    const failRun = await request.post(
      `${apiBase}/api/v1/quality/benchmark-versions/${version.id}/regression-runs`,
      {
        headers,
        data: {
          candidate_provider: "fixed",
          candidate_model: "fixed-benchmark-regress",
          candidate_model_version: "B15_V1",
          candidate_prompt_template_version: "fixed-benchmark-v1",
          idempotency_key: `fail-${suffix}`,
        },
      },
    );
    expect(failRun.ok()).toBeTruthy();
    const failBody = (await failRun.json()) as {
      id: string;
      verdict: string;
      status: string;
    };
    expect(failBody.verdict).toBe("FAIL");
    expect(failBody.status).toBe("FAILED");

    const failGate = await request.get(
      `${apiBase}/api/v1/quality/regression-runs/${failBody.id}/gate`,
      { headers },
    );
    expect(failGate.ok()).toBeTruthy();
    expect(((await failGate.json()) as { passed: boolean }).passed).toBe(false);

    await loginUi(page);
    await page.goto("/quality/benchmarks");
    await expect(page.getByTestId("b15-benchmark-workspace")).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByTestId("b15-dataset-row").filter({ hasText: dataset.code })).toBeVisible({
      timeout: 30_000,
    });
    await page
      .getByTestId("b15-dataset-row")
      .filter({ hasText: dataset.code })
      .click();
    await expect(
      page.getByTestId("b15-version-status").filter({ hasText: "LOCKED" }).first(),
    ).toBeVisible({ timeout: 15_000 });
    await page
      .getByTestId("b15-version-row")
      .filter({ has: page.getByTestId("b15-version-status").filter({ hasText: "LOCKED" }) })
      .first()
      .click();
    await expect(page.getByTestId("b15-run-list")).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId("b15-gate-verdict")).toBeVisible();
    await expect(page.getByTestId("b15-gold-label").first()).toContainText(
      /Human gold result/i,
    );
    await expect(page.getByTestId("b15-candidate-label").first()).toContainText(
      /Candidate AI output/i,
    );

    // Auth / tenant boundary
    const missing = await request.get(
      `${apiBase}/api/v1/quality/benchmark-datasets/${randomUUID()}`,
      { headers },
    );
    expect(missing.status()).toBe(404);

    const unauth = await request.get(
      `${apiBase}/api/v1/quality/benchmark-datasets`,
    );
    expect([401, 403]).toContain(unauth.status());
  });
});
