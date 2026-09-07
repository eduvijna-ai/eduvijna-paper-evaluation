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
  nodeACode: string;
  nodeBCode: string;
  assessmentsBefore: number;
}> {
  const headers = { Authorization: `Bearer ${token}` };
  const suffix = runId();
  const nodeACode = `NODE-A-${suffix}`;
  const nodeBCode = `NODE-B-${suffix}`;

  const beforeList = await request.get(`${apiBase}/api/v1/assessments`, { headers });
  expect(beforeList.ok()).toBeTruthy();
  const assessmentsBefore = (
    (await beforeList.json()) as unknown[] | { items?: unknown[] }
  );
  const beforeCount = Array.isArray(assessmentsBefore)
    ? assessmentsBefore.length
    : (assessmentsBefore.items?.length ?? 0);

  const curriculum = await request.post(`${apiBase}/api/v1/curricula`, {
    headers,
    data: {
      code: `B9-CUR-${suffix}`,
      name: `B9 Curriculum ${suffix}`,
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
      code: nodeACode,
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
      code: nodeBCode,
      name: `Quadratic Equations ${suffix}`,
      sequence: 2,
      metadata: {},
      status: "active",
    },
  });
  expect(nodeB.status()).toBe(201);
  const nodeBId = ((await nodeB.json()) as { id: string }).id;

  const prereq = await request.post(
    `${apiBase}/api/v1/curricula/${curriculumId}/prerequisites`,
    {
      headers,
      data: {
        prerequisite_node_id: nodeAId,
        dependent_node_id: nodeBId,
        relationship_type: "REQUIRED",
      },
    },
  );
  expect(prereq.status()).toBe(201);

  const assessment = await request.post(`${apiBase}/api/v1/assessments`, {
    headers,
    data: {
      curriculum_id: curriculumId,
      code: `B9-ASM-${suffix}`,
      title: `B9 Learning Assessment ${suffix}`,
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

    const mapping = await request.post(
      `${apiBase}/api/v1/question-versions/${questionId}/curriculum-mappings`,
      {
        headers,
        data: {
          curriculum_node_id: leaf.nodeId,
          mapping_type: "PRIMARY",
          weight: "1.00",
        },
      },
    );
    expect(mapping.status()).toBe(201);

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
      student_code: `B9-${suffix}`,
      full_name: `B9 Student ${suffix}`,
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
    nodeACode,
    nodeBCode,
    assessmentsBefore: beforeCount,
  };
}

async function publishWeakAttempt(
  page: Page,
  request: APIRequestContext,
  apiBase: string,
  token: string,
  assessmentId: string,
  studentId: string,
  pdf: Buffer,
): Promise<void> {
  const headers = { Authorization: `Bearer ${token}` };

  const upload = await request.post(`${apiBase}/api/v1/submissions`, {
    headers,
    multipart: {
      assessment_id: assessmentId,
      file: {
        name: "b9-sheet.pdf",
        mimeType: "application/pdf",
        buffer: pdf,
      },
    },
  });
  if (!upload.ok()) {
    throw new Error(
      `B9 upload failed status=${upload.status()} body=${await upload.text()}`,
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

  await page.getByTestId("question-tree-item-2").click();
  await page.getByTestId("add-answer-region").click();
  await page.getByTestId("assign-region").click();
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

  const textInputs = page.getByTestId("transcription-text-input");
  const count = await textInputs.count();
  for (let i = 0; i < count; i += 1) {
    // Fixed provider: EXERCISE:DEDUCT → CALCULATION (execution WEAK);
    // CONCEPT in text → CONCEPT taxonomy for concept WEAK.
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

  await expect(page.getByTestId("finalize-transcription")).toBeEnabled({
    timeout: 30_000,
  });
  await page.getByTestId("finalize-transcription").click();
  await expect(page).toHaveURL(new RegExp(`/submissions/${submissionId}$`), {
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
            max_mark: number | string;
            workflow_state: string;
          }>;
        };
        if (body.workflow_state === "EVALUATING") return "evaluating";
        const qes = body.question_evaluations ?? [];
        if (qes.length < 2) return `qes:${qes.length}`;
        for (const qe of qes) {
          if (qe.workflow_state === "ACCEPTED" || qe.workflow_state === "OVERRIDDEN") {
            continue;
          }
          const over = await request.post(
            `${apiBase}/api/v1/question-evaluations/${qe.id}/override`,
            {
              headers,
              data: {
                score: 1,
                reason: "B9 E2E weak evidence override",
              },
            },
          );
          if (![200, 409].includes(over.status())) return `override:${over.status()}`;
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
    .toBe("READY");
}

test.describe("B9 live learning + improvement blueprint (real API)", () => {
  test("prerequisite ordering, blueprint approve, no Assessment created", async ({
    page,
    request,
  }) => {
    test.setTimeout(600_000);
    const apiBase =
      process.env.API_UPSTREAM_URL?.replace(/\/$/, "") ?? "http://127.0.0.1:18000";
    const token = await loginApi(request, apiBase);
    const headers = { Authorization: `Bearer ${token}` };
    const {
      assessmentId,
      studentId,
      curriculumId,
      nodeACode,
      nodeBCode,
      assessmentsBefore,
    } = await createPrerequisiteCurriculumAssessment(request, apiBase, token);

    const pdf = await buildUniquePdf("B9-weak");
    await publishWeakAttempt(
      page,
      request,
      apiBase,
      token,
      assessmentId,
      studentId,
      pdf,
    );

    await page.goto(`/analytics/students/${studentId}`);
    await expect(page.getByTestId("student-analytics-page")).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByTestId("open-learning-plan")).toBeVisible();
    await page.getByTestId("open-learning-plan").click();

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
    await expect(generate).toBeVisible({ timeout: 30_000 });
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
          const rid = prepBody.run_id ?? prepBody.id;
          if (!rid) return "no-run";
          const run = await request.get(
            `${apiBase}/api/v1/learning/plan-runs/${rid}`,
            { headers },
          );
          if (!run.ok()) return `run:${run.status()}`;
          const body = (await run.json()) as {
            status?: string;
            path?: Array<{ node_code?: string; sequence?: number }>;
            learning_path?: Array<{ node_code?: string; sequence?: number }>;
            recommendations?: unknown[];
          };
          if (body.status !== "READY") return body.status ?? "pending";
          const path = body.path ?? body.learning_path ?? [];
          const recs = body.recommendations ?? [];
          if (recs.length === 0 || path.length === 0) {
            return `empty:recs=${recs.length}:path=${path.length}`;
          }
          return "READY";
        },
        { timeout: 180_000 },
      )
      .toBe("READY");

    await page.reload();
    await expect(page.getByTestId("live-learning-path")).toBeVisible({
      timeout: 30_000,
    });

    const pathText = (await page.getByTestId("live-learning-path").textContent()) ?? "";
    await expect(page.locator(`[data-node-code="${nodeACode}"]`).first()).toBeVisible();
    await expect(page.locator(`[data-node-code="${nodeBCode}"]`).first()).toBeVisible();
    const aPos = await page
      .locator(`[data-node-code="${nodeACode}"]`)
      .first()
      .evaluate((el) => {
        const steps = [
          ...document.querySelectorAll("[data-testid^='live-learning-path-step-']"),
        ];
        return steps.findIndex((s) => s.contains(el));
      });
    const bPos = await page
      .locator(`[data-node-code="${nodeBCode}"]`)
      .first()
      .evaluate((el) => {
        const steps = [
          ...document.querySelectorAll("[data-testid^='live-learning-path-step-']"),
        ];
        return steps.findIndex((s) => s.contains(el));
      });
    expect(aPos).toBeGreaterThanOrEqual(0);
    expect(bPos).toBeGreaterThanOrEqual(0);
    expect(aPos).toBeLessThan(bPos);
    expect(pathText).not.toMatch(/https?:\/\//i);
    expect(pathText).not.toMatch(/\bwww\./i);
    await expect(page.getByText(/% mastery/i)).toHaveCount(0);
    await expect(page.getByTestId("signal-concept").first()).toBeVisible();

    await page.getByTestId("improvement-assessment-link").click();
    await expect(page.getByTestId("improvement-assessment-page")).toBeVisible({
      timeout: 20_000,
    });

    const genBp = page.getByTestId("generate-improvement-blueprint");
    if (await genBp.count()) {
      await genBp.click();
    } else {
      const ws = await request.get(
        `${apiBase}/api/v1/learning/students/${studentId}?curriculum_id=${curriculumId}`,
        { headers },
      );
      expect(ws.ok()).toBeTruthy();
      const body = (await ws.json()) as {
        latest_run?: { id?: string };
        latest_plan?: { run_id?: string };
      };
      const rid = body.latest_plan?.run_id ?? body.latest_run?.id;
      expect(rid).toBeTruthy();
      const prepBp = await request.post(
        `${apiBase}/api/v1/learning/plan-runs/${rid}/improvement-blueprints/prepare`,
        { headers },
      );
      expect([200, 409]).toContain(prepBp.status());
      await page.reload();
    }

    await expect
      .poll(
        async () => {
          await page.reload();
          const state = page.getByTestId("blueprint-state");
          if ((await state.count()) === 0) return "missing";
          return ((await state.textContent()) ?? "").trim();
        },
        { timeout: 180_000 },
      )
      .toMatch(/PENDING APPROVAL/i);

    await expect(page.getByTestId("blueprint-live-copy")).toContainText(
      /freezes this improvement-assessment blueprint/i,
    );
    await expect(page.getByText(/Start assessment|Release assessment/i)).toHaveCount(0);

    await page.getByTestId("approve-blueprint").click();
    await expect(page.getByTestId("blueprint-state")).toContainText(/APPROVED/i, {
      timeout: 30_000,
    });
    await page.reload();
    await expect(page.getByTestId("blueprint-state")).toContainText(/APPROVED/i, {
      timeout: 20_000,
    });
    await expect(page.getByTestId("blueprint-approved-notice")).toBeVisible();

    const afterList = await request.get(`${apiBase}/api/v1/assessments`, { headers });
    expect(afterList.ok()).toBeTruthy();
    const afterBody = (await afterList.json()) as unknown[] | { items?: unknown[] };
    const afterCount = Array.isArray(afterBody)
      ? afterBody.length
      : (afterBody.items?.length ?? 0);
    // Only the assessment created for this E2E should exist beyond baseline (+1),
    // blueprint approval must not create a follow-up Assessment.
    expect(afterCount).toBe(assessmentsBefore + 1);
  });
});
