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

async function createPrerequisiteCurriculumAssessment(
  request: APIRequestContext,
  apiBase: string,
  token: string,
): Promise<{
  assessmentId: string;
  studentId: string;
  curriculumId: string;
}> {
  const headers = { Authorization: `Bearer ${token}` };
  const suffix = runId();

  const curriculum = await request.post(`${apiBase}/api/v1/curricula`, {
    headers,
    data: {
      code: `B14-CUR-${suffix}`,
      name: `B14 Curriculum ${suffix}`,
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

  const nodeA = await request.post(`${apiBase}/api/v1/curricula/${curriculumId}/nodes`, {
    headers,
    data: {
      parent_id: subjectId,
      node_type: "TOPIC",
      code: `NODE-A-${suffix}`,
      name: `Linear Equations ${suffix}`,
      sequence: 1,
      metadata: {},
      status: "active",
    },
  });
  expect(nodeA.status()).toBe(201);
  const nodeAId = ((await nodeA.json()) as { id: string }).id;

  const nodeB = await request.post(`${apiBase}/api/v1/curricula/${curriculumId}/nodes`, {
    headers,
    data: {
      parent_id: subjectId,
      node_type: "TOPIC",
      code: `NODE-B-${suffix}`,
      name: `Quadratic Equations ${suffix}`,
      sequence: 2,
      metadata: {},
      status: "active",
    },
  });
  expect(nodeB.status()).toBe(201);
  const nodeBId = ((await nodeB.json()) as { id: string }).id;

  expect(
    (
      await request.post(`${apiBase}/api/v1/curricula/${curriculumId}/prerequisites`, {
        headers,
        data: {
          prerequisite_node_id: nodeAId,
          dependent_node_id: nodeBId,
          relationship_type: "REQUIRED",
        },
      })
    ).status(),
  ).toBe(201);

  const assessment = await request.post(`${apiBase}/api/v1/assessments`, {
    headers,
    data: {
      curriculum_id: curriculumId,
      code: `B14-ASM-${suffix}`,
      title: `B14 Source Assessment ${suffix}`,
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
    {
      code: "Q1",
      label: "1",
      prompt: "Solve linear: 2x=4",
      marks: "5.00",
      answer: "2",
      nodeId: nodeAId,
    },
    {
      code: "Q2",
      label: "2",
      prompt: "Solve quadratic: x^2=9",
      marks: "5.00",
      answer: "3",
      nodeId: nodeBId,
    },
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
              curriculum_node_id: leaf.nodeId,
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
      student_code: `B14-${suffix}`,
      full_name: `B14 Student ${suffix}`,
      class_section_id: section!.id,
      academic_year_id: section!.academic_year_id,
      status: "active",
    },
  });
  expect(student.status()).toBe(201);

  return {
    assessmentId,
    studentId: ((await student.json()) as { id: string }).id,
    curriculumId,
  };
}

async function authorAkRubricForVersion(
  request: APIRequestContext,
  apiBase: string,
  headers: Record<string, string>,
  assessmentId: string,
  versionId: string,
): Promise<string[]> {
  const qs = await request.get(
    `${apiBase}/api/v1/assessment-versions/${versionId}/questions`,
    { headers },
  );
  expect(qs.ok()).toBeTruthy();
  const body = (await qs.json()) as
    | Array<{ id: string; max_marks?: string; display_label?: string }>
    | {
        items?: Array<{ id: string; max_marks?: string; display_label?: string }>;
      };
  const questions = Array.isArray(body) ? body : (body.items ?? []);
  expect(questions.length).toBeGreaterThan(0);

  for (const [index, q] of questions.entries()) {
    const marks = q.max_marks ?? "5.00";
    const key = await request.post(
      `${apiBase}/api/v1/assessments/${assessmentId}/answer-key-versions`,
      {
        headers,
        data: {
          assessment_version_id: versionId,
          question_version_id: q.id,
          answer_text: `answer-${index + 1}`,
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
          question_version_id: q.id,
          title: `RA-${index + 1}`,
          provenance: "TEACHER",
        },
      },
    );
    expect(rubric.status()).toBe(201);
    const rubricId = ((await rubric.json()) as { id: string }).id;
    const rv = await request.post(`${apiBase}/api/v1/rubrics/${rubricId}/versions`, {
      headers,
      data: {
        question_version_id: q.id,
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
            max_marks: marks,
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
  // Mapping UI testids use display_label (QuestionTree → question.code).
  return questions.map((q, index) => q.display_label || String(index + 1));
}

async function publishAttempt(
  page: Page,
  request: APIRequestContext,
  apiBase: string,
  token: string,
  assessmentId: string,
  studentId: string,
  pdf: Buffer,
  questionCodes: string[],
  score = 4,
): Promise<string> {
  const questionCount = questionCodes.length;
  const headers = { Authorization: `Bearer ${token}` };

  const upload = await request.post(`${apiBase}/api/v1/submissions`, {
    headers,
    multipart: {
      assessment_id: assessmentId,
      file: {
        name: "b14-sheet.pdf",
        mimeType: "application/pdf",
        buffer: pdf,
      },
    },
  });
  if (!upload.ok()) {
    throw new Error(
      `B14 upload failed status=${upload.status()} body=${await upload.text()}`,
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

  for (let i = 0; i < questionCodes.length; i += 1) {
    if (i > 0) {
      await page.getByTestId(`question-tree-item-${questionCodes[i]}`).click();
    }
    const aiBadge = page.getByTestId("region-ai-proposal-badge");
    if ((await aiBadge.count()) === 0) {
      await page.getByTestId("add-answer-region").click();
    }
    await page.getByTestId("assign-region").click();
    await page.getByTestId("confirm-mapping").click();
  }
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

  const textInputs = page.getByTestId("transcription-text-input");
  const count = await textInputs.count();
  for (let i = 0; i < count; i += 1) {
    await textInputs
      .nth(i)
      .fill(
        i === 0
          ? "EXERCISE:DEDUCT CONCEPT gap on linear equations"
          : "EXERCISE:DEDUCT CONCEPT gap on quadratics",
      );
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

  // APP-013.1: success must be UI-driven only — no API finalize rescue / forced goto.
  const finalizeBtn = page.getByTestId("finalize-transcription");
  await expect(finalizeBtn).toBeEnabled({ timeout: 30_000 });
  await Promise.all([
    page
      .waitForURL(
        (url) => {
          try {
            return new URL(url).pathname === `/submissions/${submissionId}`;
          } catch {
            return false;
          }
        },
        { timeout: 90_000 },
      )
      .catch(() => undefined),
    finalizeBtn.click(),
  ]);
  await expect
    .poll(
      async () => {
        const path = new URL(page.url()).pathname;
        if (path === `/submissions/${submissionId}`) return "done";
        if (path.endsWith("/transcription")) {
          const btn = page.getByTestId("finalize-transcription");
          // Retry the same UI control only while it remains legitimately enabled.
          if (await btn.isEnabled().catch(() => false)) {
            await Promise.all([
              page
                .waitForURL(
                  (url) => {
                    try {
                      return new URL(url).pathname === `/submissions/${submissionId}`;
                    } catch {
                      return false;
                    }
                  },
                  { timeout: 20_000 },
                )
                .catch(() => undefined),
              btn.click().catch(() => undefined),
            ]);
          }
        }
        return new URL(page.url()).pathname === `/submissions/${submissionId}`
          ? "done"
          : path;
      },
      { timeout: 120_000 },
    )
    .toBe("done");
  await expect(page.getByTestId("submission-detail-page")).toBeVisible({
    timeout: 30_000,
  });

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
        if (qes.length < questionCount) return `qes:${qes.length}`;
        for (const qe of qes) {
          if (qe.workflow_state === "ACCEPTED" || qe.workflow_state === "OVERRIDDEN") {
            continue;
          }
          const maxMark = Number(qe.max_mark ?? score);
          const clamped =
            Number.isFinite(maxMark) && maxMark >= 0
              ? Math.min(Math.max(0, score), maxMark)
              : Math.max(0, score);
          const over = await request.post(
            `${apiBase}/api/v1/question-evaluations/${qe.id}/override`,
            {
              headers,
              data: {
                score: clamped,
                reason: "B14 E2E override",
              },
            },
          );
          if (![200, 409].includes(over.status())) {
            return `override:${over.status()}:${await over.text()}`;
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
  const prid = ((await prep.json()) as { published_result_id: string }).published_result_id;

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

async function approveBlueprint(
  page: Page,
  request: APIRequestContext,
  apiBase: string,
  headers: Record<string, string>,
  studentId: string,
  curriculumId: string,
): Promise<{ id: string; items: Array<{ id: string; item_code: string }> }> {
  await page.goto(`/learning/${studentId}?curriculum_id=${curriculumId}`);
  await expect(page.getByTestId("adaptive-learning-page")).toBeVisible({
    timeout: 30_000,
  });
  await expect(page.getByTestId("adaptive-learning-page")).toHaveAttribute(
    "data-learning-mode",
    "live",
  );

  await expect
    .poll(
      async () => {
        const text =
          (await page.getByTestId("learning-materialization-status").textContent()) ??
          "";
        const match = text.match(/\b(READY|PARTIAL|QUEUED|RUNNING|FAILED|NOT_STARTED)\b/);
        return match?.[1] ?? text;
      },
      { timeout: 120_000 },
    )
    .toBe("READY");

  const generate = page.getByTestId("generate-learning-plan");
  await expect(generate).toBeEnabled({ timeout: 30_000 });
  await generate.click();

  await expect
    .poll(
      async () => {
        const prep = await request.post(
          `${apiBase}/api/v1/learning/students/${studentId}/prepare`,
          { headers, data: { curriculum_id: curriculumId } },
        );
        if (![200, 409].includes(prep.status())) {
          return `prep:${prep.status()}:${await prep.text()}`;
        }
        const prepBody = (await prep.json()) as {
          run_id?: string;
          id?: string;
          status?: string;
        };
        const runId = prepBody.run_id ?? prepBody.id;
        if (!runId) return "no-run";
        const run = await request.get(
          `${apiBase}/api/v1/learning/plan-runs/${runId}`,
          { headers },
        );
        if (!run.ok()) return `run:${run.status()}`;
        const body = (await run.json()) as { status?: string };
        if (body.status !== "READY") return body.status ?? "pending";
        return "READY";
      },
      { timeout: 180_000 },
    )
    .toBe("READY");

  await page.reload();
  await page.getByTestId("improvement-assessment-link").click();
  await expect(page.getByTestId("improvement-assessment-page")).toBeVisible({
    timeout: 20_000,
  });

  const genBp = page.getByTestId("generate-improvement-blueprint");
  if (await genBp.count()) {
    await genBp.click();
  }

  await expect
    .poll(
      async () => {
        const ws = await request.get(
          `${apiBase}/api/v1/learning/students/${studentId}?curriculum_id=${curriculumId}`,
          { headers },
        );
        if (!ws.ok()) return `ws:${ws.status()}`;
        const body = (await ws.json()) as {
          latest_run?: { id?: string };
          latest_plan?: { run_id?: string; id?: string };
          latest_improvement_blueprint?: {
            id?: string;
            status?: string;
            failure_code?: string | null;
          } | null;
        };
        const existing = body.latest_improvement_blueprint;
        if (existing?.status === "PENDING_APPROVAL") return "PENDING_APPROVAL";
        if (existing?.status === "FAILED") {
          return `FAILED:${existing.failure_code ?? "?"}`;
        }
        if (existing?.status === "GENERATING" || existing?.status === "DRAFT") {
          return existing.status;
        }
        const rid =
          body.latest_plan?.run_id ?? body.latest_plan?.id ?? body.latest_run?.id;
        if (!rid) return "no-run";
        const prepBp = await request.post(
          `${apiBase}/api/v1/learning/plan-runs/${rid}/improvement-blueprints/prepare`,
          { headers },
        );
        if (![200, 409].includes(prepBp.status())) {
          return `prepBp:${prepBp.status()}:${await prepBp.text()}`;
        }
        const prepBody = (await prepBp.json()) as { status?: string };
        return prepBody.status ?? "prepared";
      },
      { timeout: 180_000 },
    )
    .toBe("PENDING_APPROVAL");

  await page.reload();
  await expect(page.getByTestId("blueprint-state")).toContainText(/PENDING APPROVAL/i, {
    timeout: 30_000,
  });
  await page.getByTestId("approve-blueprint").click();
  await expect(page.getByTestId("blueprint-state")).toContainText(/APPROVED/i, {
    timeout: 30_000,
  });
  await expect(page.getByTestId("b14-create-reassessment")).toBeVisible({
    timeout: 20_000,
  });

  const bp = await request.get(
    `${apiBase}/api/v1/learning/students/${studentId}?curriculum_id=${curriculumId}`,
    { headers },
  );
  expect(bp.ok()).toBeTruthy();
  const wsBody = (await bp.json()) as {
    latest_improvement_blueprint: {
      id: string;
      items: Array<{ id: string; item_code: string }>;
    };
  };
  return wsBody.latest_improvement_blueprint;
}

test.describe("B14 live reassessment mastery (real API)", () => {
  test("instantiate → author → publish → learning deltas + isolation", async ({
    page,
    request,
  }) => {
    test.setTimeout(900_000);
    const apiBase =
      process.env.API_UPSTREAM_URL?.replace(/\/$/, "") ?? "http://127.0.0.1:18000";
    const token = await loginApi(request, apiBase);
    const headers = { Authorization: `Bearer ${token}` };

    const { assessmentId, studentId, curriculumId } =
      await createPrerequisiteCurriculumAssessment(request, apiBase, token);

    const sourcePdf = await buildUniquePdf("B14-source-weak");
    await publishAttempt(
      page,
      request,
      apiBase,
      token,
      assessmentId,
      studentId,
      sourcePdf,
      ["1", "2"],
      1,
    );

    const blueprint = await approveBlueprint(
      page,
      request,
      apiBase,
      headers,
      studentId,
      curriculumId,
    );
    expect(blueprint.items.length).toBeGreaterThan(0);

    // Isolation: foreign/unknown reassessment id → 404
    const missing = await request.get(
      `${apiBase}/api/v1/reassessments/${randomUUID()}`,
      { headers },
    );
    expect(missing.status()).toBe(404);

    await page.getByTestId("b14-instantiate-submit").click();
    await expect(page.getByTestId("b14-create-success")).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByTestId("b14-create-success")).toContainText(/DRAFT/i);

    const detailFromUi = page.getByTestId("b14-created-assessment-link");
    const reassessmentAssessmentHref = await detailFromUi.getAttribute("href");
    expect(reassessmentAssessmentHref).toMatch(/\/assessments\//);

    const raList = await request.get(
      `${apiBase}/api/v1/learning/students/${studentId}?curriculum_id=${curriculumId}`,
      { headers },
    );
    expect(raList.ok()).toBeTruthy();
    const workspace = (await raList.json()) as {
      reassessments?: Array<{
        id: string;
        assessment_id: string;
        assessment_version_id: string;
        status: string;
      }>;
    };
    expect(workspace.reassessments?.length).toBeGreaterThan(0);
    const reassessment = workspace.reassessments![0]!;
    expect(reassessment.status).toBe("CREATED");

    // Wrong-student isolation on intended learner reassessment detail stays tenant-scoped
    const otherStudent = await request.post(`${apiBase}/api/v1/students`, {
      headers,
      data: {
        student_code: `B14-OTHER-${runId()}`,
        full_name: "B14 Other Student",
        status: "active",
      },
    });
    expect(otherStudent.status()).toBe(201);
    const otherId = ((await otherStudent.json()) as { id: string }).id;
    const otherWs = await request.get(
      `${apiBase}/api/v1/learning/students/${otherId}?curriculum_id=${curriculumId}`,
      { headers },
    );
    if (otherWs.ok()) {
      const otherBody = (await otherWs.json()) as {
        reassessments?: Array<{ id: string }>;
      };
      expect(
        (otherBody.reassessments ?? []).some((r) => r.id === reassessment.id),
      ).toBe(false);
    }

    const questionCodes = await authorAkRubricForVersion(
      request,
      apiBase,
      headers,
      reassessment.assessment_id,
      reassessment.assessment_version_id,
    );

    expect(
      (
        await request.post(
          `${apiBase}/api/v1/assessments/${reassessment.assessment_id}/transition`,
          { headers, data: { to_status: "READY" } },
        )
      ).status(),
    ).toBe(200);
    expect(
      (
        await request.post(
          `${apiBase}/api/v1/assessments/${reassessment.assessment_id}/transition`,
          { headers, data: { to_status: "ACTIVE" } },
        )
      ).status(),
    ).toBe(200);

    const rePdf = await buildUniquePdf("B14-reassess-strong");
    await publishAttempt(
      page,
      request,
      apiBase,
      token,
      reassessment.assessment_id,
      studentId,
      rePdf,
      questionCodes,
      5,
    );

    // Ensure B14 deltas materialize (publish hook or explicit rebuild)
    const rebuild = await request.post(
      `${apiBase}/api/v1/reassessments/${reassessment.id}/b14/rebuild`,
      { headers },
    );
    expect([200, 409]).toContain(rebuild.status());
    if (rebuild.status() === 409) {
      // May already be materialized by publish analytics; detail should still expose deltas.
    }

    await expect
      .poll(
        async () => {
          const detail = await request.get(
            `${apiBase}/api/v1/reassessments/${reassessment.id}`,
            { headers },
          );
          if (!detail.ok()) return `detail:${detail.status()}`;
          const body = (await detail.json()) as {
            status?: string;
            mastery_deltas?: Array<{
              materialized_at?: string | null;
              concept_delta?: number | null;
              execution_delta?: number | null;
            }>;
          };
          if (body.status !== "PUBLISHED") return body.status ?? "pending";
          const ready = (body.mastery_deltas ?? []).some(
            (d) => d.materialized_at != null,
          );
          return ready ? "READY" : "waiting-deltas";
        },
        { timeout: 180_000 },
      )
      .toBe("READY");

    await page.goto(`/learning/${studentId}?curriculum_id=${curriculumId}`);
    await expect(page.getByTestId("adaptive-learning-page")).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByTestId("b14-reassessments-section")).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByTestId("b14-reassessment-row").first()).toBeVisible();
    await expect(page.getByTestId("b14-mastery-delta").first()).toBeVisible();
    // Null mastery must never render as bare 0 in insufficient spots when present
    const insufficient = page.getByTestId("b14-insufficient-evidence");
    if ((await insufficient.count()) > 0) {
      await expect(insufficient.first()).toContainText(
        /Insufficient decisive evidence/i,
      );
    }
  });
});
