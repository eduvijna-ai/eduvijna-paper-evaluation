import { test, expect, type APIRequestContext, type Page } from "@playwright/test";
import { randomUUID } from "node:crypto";
import { PDFDocument, StandardFonts } from "pdf-lib";

const ADMIN_EMAIL = "admin@demo.eduvijna.local";
const ADMIN_PASSWORD = "DemoAdmin!2026";
const DEMO_USER_PASSWORD = "DemoUser!2026";

const EVALUATOR_A_EMAIL = "evaluator-a@demo.eduvijna.local";
const EVALUATOR_B_EMAIL = "evaluator-b@demo.eduvijna.local";
const MODERATOR_EMAIL = "moderator@demo.eduvijna.local";
const HOD_EMAIL = "hod@demo.eduvijna.local";

type AuthSession = {
  token: string;
  userId: string;
  headers: { Authorization: string };
};

type WorkItem = {
  id: string;
  assigned_evaluator_id: string;
  question_evaluation_id: string;
  status: string;
};

type QuestionEvaluationRow = {
  id: string;
  proposed_ai_score: number | string | null;
  max_mark: number | string;
  workflow_state: string;
  final_human_approved_score?: number | string | null;
  reviewed_by?: string | null;
};

function runId(): string {
  return `${Date.now().toString(36)}${randomUUID().replace(/-/g, "").slice(0, 8)}`;
}

function detailCode(body: unknown): string | undefined {
  const b = body as {
    detail?: { code?: string } | string;
    error?: { code?: string };
  };
  if (typeof b.detail === "object" && b.detail?.code) return b.detail.code;
  return b.error?.code;
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
  email: string,
  password: string,
): Promise<AuthSession> {
  const login = await request.post(`${apiBase}/api/v1/auth/login`, {
    data: { email, password, tenant_slug: "demo" },
  });
  expect(login.ok(), `login failed for ${email}: ${login.status()}`).toBeTruthy();
  const body = (await login.json()) as {
    access_token: string;
    user: { id: string };
  };
  return {
    token: body.access_token,
    userId: body.user.id,
    headers: { Authorization: `Bearer ${body.access_token}` },
  };
}

async function createCurriculumAssessment(
  request: APIRequestContext,
  apiBase: string,
  admin: AuthSession,
): Promise<{
  assessmentId: string;
  versionId: string;
  studentId: string;
}> {
  const headers = admin.headers;
  const suffix = runId();

  const curriculum = await request.post(`${apiBase}/api/v1/curricula`, {
    headers,
    data: {
      code: `B16-CUR-${suffix}`,
      name: `B16 Curriculum ${suffix}`,
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

  const assessment = await request.post(`${apiBase}/api/v1/assessments`, {
    headers,
    data: {
      curriculum_id: curriculumId,
      code: `B16-ASM-${suffix}`,
      title: `B16 Enterprise Ops ${suffix}`,
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
      (
        await request.post(`${apiBase}/api/v1/rubric-versions/${rvId}/approve`, {
          headers,
        })
      ).ok(),
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
      student_code: `B16S-${suffix}`,
      full_name: `B16 Student ${suffix}`,
      class_section_id: section!.id,
      academic_year_id: section!.academic_year_id,
      status: "active",
    },
  });
  expect(student.status()).toBe(201);
  const studentId = ((await student.json()) as { id: string }).id;

  return { assessmentId, versionId, studentId };
}

async function pollSubmissionState(
  request: APIRequestContext,
  apiBase: string,
  headers: { Authorization: string },
  submissionId: string,
  matcher: RegExp | string,
  timeout = 120_000,
): Promise<string> {
  let last = "";
  await expect
    .poll(
      async () => {
        const res = await request.get(
          `${apiBase}/api/v1/submissions/${submissionId}`,
          { headers },
        );
        if (!res.ok()) return `err:${res.status()}`;
        last = ((await res.json()) as { workflow_state?: string }).workflow_state ?? "";
        return last;
      },
      { timeout },
    )
    .toMatch(matcher);
  return last;
}

/**
 * Drive upload → identity → mapping → transcription → READY_FOR_EVALUATION via API.
 * Endpoints mirror apps/api/tests/test_b6_evaluation_ledger._to_ready_for_evaluation.
 */
async function driveToReadyForEvaluation(
  request: APIRequestContext,
  apiBase: string,
  admin: AuthSession,
  assessmentId: string,
  studentId: string,
  pdf: Buffer,
): Promise<string> {
  const headers = admin.headers;
  const upload = await request.post(`${apiBase}/api/v1/submissions`, {
    headers,
    multipart: {
      assessment_id: assessmentId,
      file: {
        name: "b16-enterprise.pdf",
        mimeType: "application/pdf",
        buffer: pdf,
      },
    },
  });
  if (!upload.ok()) {
    throw new Error(
      `B16 upload failed status=${upload.status()} body=${await upload.text()}`,
    );
  }
  const submissionId = ((await upload.json()) as { id: string }).id;

  await pollSubmissionState(
    request,
    apiBase,
    headers,
    submissionId,
    /IDENTITY_REVIEW/,
  );

  const confirm = await request.post(
    `${apiBase}/api/v1/submissions/${submissionId}/identity/confirm`,
    { headers, data: { student_id: studentId } },
  );
  expect(confirm.ok(), await confirm.text()).toBeTruthy();

  await pollSubmissionState(
    request,
    apiBase,
    headers,
    submissionId,
    /MAPPING_REVIEW/,
  );

  await request.post(
    `${apiBase}/api/v1/submissions/${submissionId}/mapping/prepare`,
    { headers },
  );

  let regionId = "";
  let leaves: Array<{ question_version_id: string; is_leaf_scorable?: boolean }> = [];
  await expect
    .poll(
      async () => {
        const mapping = await request.get(
          `${apiBase}/api/v1/submissions/${submissionId}/mapping`,
          { headers },
        );
        if (!mapping.ok()) return `map:${mapping.status()}`;
        const mbody = (await mapping.json()) as {
          regions?: Array<{ id: string }>;
          questions?: Array<{
            question_version_id: string;
            is_leaf_scorable?: boolean;
          }>;
        };
        leaves = (mbody.questions ?? []).filter((n) => n.is_leaf_scorable);
        const regions = mbody.regions ?? [];
        if (regions.length < 1 || leaves.length < 2) {
          return `regions:${regions.length}:leaves:${leaves.length}`;
        }
        regionId = regions[0]!.id;
        return "ready";
      },
      { timeout: 120_000 },
    )
    .toBe("ready");

  const first = leaves[0]!;
  const second = leaves[1]!;

  expect(
    (
      await request.put(
        `${apiBase}/api/v1/submissions/${submissionId}/question-mappings/${first.question_version_id}`,
        {
          headers,
          data: { disposition: "ANSWERED", region_ids: [regionId] },
        },
      )
    ).status(),
  ).toBe(200);
  expect(
    (
      await request.post(
        `${apiBase}/api/v1/submissions/${submissionId}/question-mappings/${first.question_version_id}/confirm`,
        { headers },
      )
    ).status(),
  ).toBe(200);

  expect(
    (
      await request.put(
        `${apiBase}/api/v1/submissions/${submissionId}/question-mappings/${second.question_version_id}`,
        {
          headers,
          data: { disposition: "BLANK", region_ids: [] },
        },
      )
    ).status(),
  ).toBe(200);
  expect(
    (
      await request.post(
        `${apiBase}/api/v1/submissions/${submissionId}/question-mappings/${second.question_version_id}/confirm`,
        { headers },
      )
    ).status(),
  ).toBe(200);

  const mapFin = await request.post(
    `${apiBase}/api/v1/submissions/${submissionId}/mapping/finalize`,
    { headers },
  );
  expect(mapFin.ok(), await mapFin.text()).toBeTruthy();

  await request.post(
    `${apiBase}/api/v1/submissions/${submissionId}/transcription/prepare`,
    { headers },
  );

  await expect
    .poll(
      async () => {
        const workspace = await request.get(
          `${apiBase}/api/v1/submissions/${submissionId}/transcription`,
          { headers },
        );
        if (!workspace.ok()) return `tx:${workspace.status()}`;
        const body = (await workspace.json()) as {
          items?: Array<{
            regions: Array<{
              id: string;
              requires_transcription?: boolean;
            }>;
          }>;
        };
        for (const item of body.items ?? []) {
          for (const region of item.regions) {
            if (!region.requires_transcription) continue;
            const put = await request.put(
              `${apiBase}/api/v1/answer-regions/${region.id}/transcription`,
              {
                headers,
                data: {
                  text: "EXERCISE:FULL answer",
                  outcome: "TRANSCRIBED",
                },
              },
            );
            if (![200, 409].includes(put.status())) {
              return `put:${put.status()}`;
            }
            const putBody = (await put.json()) as { id?: string };
            if (putBody.id) {
              const conf = await request.post(
                `${apiBase}/api/v1/answer-region-transcriptions/${putBody.id}/confirm`,
                { headers },
              );
              if (![200, 409].includes(conf.status())) {
                return `conf:${conf.status()}`;
              }
            }
          }
        }
        const finalize = await request.post(
          `${apiBase}/api/v1/submissions/${submissionId}/transcription/finalize`,
          { headers },
        );
        if (!finalize.ok()) return `fin:${finalize.status()}:${await finalize.text()}`;
        const finBody = (await finalize.json()) as { workflow_state?: string };
        return finBody.workflow_state ?? "";
      },
      { timeout: 180_000 },
    )
    .toBe("READY_FOR_EVALUATION");

  return submissionId;
}

async function prepareEvaluationRun(
  request: APIRequestContext,
  apiBase: string,
  admin: AuthSession,
  submissionId: string,
): Promise<{ runId: string; questionEvaluations: QuestionEvaluationRow[] }> {
  const headers = admin.headers;
  let runId = "";
  let questionEvaluations: QuestionEvaluationRow[] = [];
  await expect
    .poll(
      async () => {
        const prep = await request.post(
          `${apiBase}/api/v1/submissions/${submissionId}/evaluation/prepare`,
          { headers },
        );
        if (![200, 409].includes(prep.status())) {
          return `prep:${prep.status()}:${await prep.text()}`;
        }
        const ws = await request.get(
          `${apiBase}/api/v1/submissions/${submissionId}/evaluation`,
          { headers },
        );
        if (!ws.ok()) return `ws:${ws.status()}`;
        const body = (await ws.json()) as {
          evaluation_run?: { id: string };
          question_evaluations?: QuestionEvaluationRow[];
        };
        questionEvaluations = body.question_evaluations ?? [];
        runId = body.evaluation_run?.id ?? "";
        if (!runId || questionEvaluations.length < 2) {
          return `qes:${questionEvaluations.length}:run:${runId || "none"}`;
        }
        return "ready";
      },
      { timeout: 180_000 },
    )
    .toBe("ready");
  return { runId, questionEvaluations };
}

async function reviewAssignedWorkItems(
  request: APIRequestContext,
  apiBase: string,
  items: WorkItem[],
  sessionsByUserId: Map<string, AuthSession>,
): Promise<void> {
  for (const item of items) {
    const session = sessionsByUserId.get(item.assigned_evaluator_id);
    expect(session, `missing session for ${item.assigned_evaluator_id}`).toBeTruthy();
    const headers = session!.headers;

    if (item.status === "QUEUED" || item.status === "RETURNED") {
      const start = await request.post(
        `${apiBase}/api/v1/operations/grading/work-items/${item.id}/start`,
        { headers },
      );
      expect(start.ok(), await start.text()).toBeTruthy();
    }

    const qeRes = await request.get(
      `${apiBase}/api/v1/question-evaluations/${item.question_evaluation_id}`,
      { headers },
    );
    expect(qeRes.ok(), await qeRes.text()).toBeTruthy();
    const qe = (await qeRes.json()) as QuestionEvaluationRow;

    if (qe.workflow_state !== "ACCEPTED" && qe.workflow_state !== "OVERRIDDEN") {
      if (qe.proposed_ai_score !== null && qe.proposed_ai_score !== undefined) {
        const acc = await request.post(
          `${apiBase}/api/v1/question-evaluations/${item.question_evaluation_id}/accept`,
          { headers },
        );
        expect(acc.ok(), await acc.text()).toBeTruthy();
      } else {
        const over = await request.post(
          `${apiBase}/api/v1/question-evaluations/${item.question_evaluation_id}/override`,
          {
            headers,
            data: { score: 0, reason: "B16 blank leaf override" },
          },
        );
        expect(over.ok(), await over.text()).toBeTruthy();
      }
    }

    const submit = await request.post(
      `${apiBase}/api/v1/operations/grading/work-items/${item.id}/submit`,
      { headers },
    );
    expect(submit.ok(), await submit.text()).toBeTruthy();
  }
}

async function reviewAllAndFinalize(
  request: APIRequestContext,
  apiBase: string,
  admin: AuthSession,
  submissionId: string,
): Promise<string> {
  const headers = admin.headers;
  let workflow = "";
  await expect
    .poll(
      async () => {
        const ws = await request.get(
          `${apiBase}/api/v1/submissions/${submissionId}/evaluation`,
          { headers },
        );
        if (!ws.ok()) return `ws:${ws.status()}`;
        const body = (await ws.json()) as {
          question_evaluations?: QuestionEvaluationRow[];
        };
        for (const qe of body.question_evaluations ?? []) {
          if (qe.workflow_state === "ACCEPTED" || qe.workflow_state === "OVERRIDDEN") {
            continue;
          }
          if (qe.proposed_ai_score !== null && qe.proposed_ai_score !== undefined) {
            const acc = await request.post(
              `${apiBase}/api/v1/question-evaluations/${qe.id}/accept`,
              { headers },
            );
            if (![200, 409].includes(acc.status())) {
              return `accept:${acc.status()}:${await acc.text()}`;
            }
          } else {
            const over = await request.post(
              `${apiBase}/api/v1/question-evaluations/${qe.id}/override`,
              {
                headers,
                data: { score: 0, reason: "B16 re-evaluation override" },
              },
            );
            if (![200, 409].includes(over.status())) {
              return `override:${over.status()}:${await over.text()}`;
            }
          }
        }
        const fin = await request.post(
          `${apiBase}/api/v1/submissions/${submissionId}/evaluation/finalize`,
          { headers },
        );
        if (!fin.ok()) return `fin:${fin.status()}:${await fin.text()}`;
        workflow =
          ((await fin.json()) as { workflow_state?: string }).workflow_state ?? "";
        return workflow;
      },
      { timeout: 180_000 },
    )
    .toMatch(/MODERATION_REVIEW|APPROVED/);
  return workflow;
}

async function findModerationCase(
  request: APIRequestContext,
  apiBase: string,
  admin: AuthSession,
  submissionId: string,
): Promise<string> {
  let caseId = "";
  await expect
    .poll(
      async () => {
        const cases = await request.get(
          `${apiBase}/api/v1/operations/moderation-cases`,
          { headers: admin.headers },
        );
        if (!cases.ok()) return `cases:${cases.status()}`;
        const items = (
          (await cases.json()) as {
            items: Array<{ id: string; submission_id: string; status: string }>;
          }
        ).items;
        const found = items.find(
          (c) =>
            c.submission_id === submissionId &&
            ["PENDING", "IN_PROGRESS", "RETURNED"].includes(c.status),
        );
        caseId = found?.id ?? "";
        return caseId ? "found" : "missing";
      },
      { timeout: 60_000 },
    )
    .toBe("found");
  return caseId;
}

async function publishResult(
  request: APIRequestContext,
  apiBase: string,
  admin: AuthSession,
  submissionId: string,
): Promise<string> {
  const headers = admin.headers;
  const prep = await request.post(
    `${apiBase}/api/v1/submissions/${submissionId}/publication/prepare`,
    { headers },
  );
  expect(prep.ok(), await prep.text()).toBeTruthy();
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
  expect(pub.ok(), await pub.text()).toBeTruthy();
  expect(((await pub.json()) as { status: string }).status).toBe("PUBLISHED");
  return prid;
}

async function assertUiOperationsWorkspace(page: Page): Promise<void> {
  await page.goto("/login");
  await page.getByTestId("login-email").fill(ADMIN_EMAIL);
  await page.getByTestId("login-password").fill(ADMIN_PASSWORD);
  await page.getByTestId("login-submit").click();
  await expect(page.getByTestId("app-shell")).toBeVisible({ timeout: 30_000 });
  await page.goto("/operations/grading");
  await expect(page.getByTestId("b16-grading-workspace")).toBeVisible({
    timeout: 30_000,
  });
}

test.describe("B16.1 enterprise grading / moderation / grievance (real API)", () => {
  test("full lifecycle: pool ownership, moderation return, grievance V2, B12 single attempt", async ({
    page,
    request,
  }) => {
    test.setTimeout(600_000);
    const apiBase =
      process.env.API_UPSTREAM_URL?.replace(/\/$/, "") ?? "http://127.0.0.1:18000";

    const admin = await loginApi(request, apiBase, ADMIN_EMAIL, ADMIN_PASSWORD);
    const evalA = await loginApi(
      request,
      apiBase,
      EVALUATOR_A_EMAIL,
      DEMO_USER_PASSWORD,
    );
    const evalB = await loginApi(
      request,
      apiBase,
      EVALUATOR_B_EMAIL,
      DEMO_USER_PASSWORD,
    );
    const moderator = await loginApi(
      request,
      apiBase,
      MODERATOR_EMAIL,
      DEMO_USER_PASSWORD,
    );
    const hod = await loginApi(request, apiBase, HOD_EMAIL, DEMO_USER_PASSWORD);
    const sessionsByUserId = new Map<string, AuthSession>([
      [evalA.userId, evalA],
      [evalB.userId, evalB],
    ]);

    await assertUiOperationsWorkspace(page);

    const { assessmentId, versionId, studentId } = await createCurriculumAssessment(
      request,
      apiBase,
      admin,
    );

    // 1) Horizontal grading pool with evaluators A and B
    const poolRes = await request.post(`${apiBase}/api/v1/operations/grading-pools`, {
      headers: admin.headers,
      data: {
        assessment_id: assessmentId,
        assessment_version_id: versionId,
        allocation_strategy: "ROUND_ROBIN",
      },
    });
    expect(poolRes.ok(), await poolRes.text()).toBeTruthy();
    const poolId = ((await poolRes.json()) as { id: string }).id;

    for (const uid of [evalA.userId, evalB.userId]) {
      const mem = await request.post(
        `${apiBase}/api/v1/operations/grading-pools/${poolId}/members`,
        { headers: admin.headers, data: { user_id: uid } },
      );
      expect(mem.ok(), await mem.text()).toBeTruthy();
    }
    const actPool = await request.post(
      `${apiBase}/api/v1/operations/grading-pools/${poolId}/activate`,
      { headers: admin.headers },
    );
    expect(actPool.ok(), await actPool.text()).toBeTruthy();
    expect(((await actPool.json()) as { status: string }).status).toBe("ACTIVE");

    // 5) Moderation policy (MODERATOR then HOD) — activate before finalize
    const policyRes = await request.post(
      `${apiBase}/api/v1/operations/moderation-policies`,
      {
        headers: admin.headers,
        data: {
          assessment_id: assessmentId,
          assessment_version_id: versionId,
          stages: [
            { stage_order: 1, required_role: "MODERATOR", label: "Moderator" },
            { stage_order: 2, required_role: "HOD", label: "HOD" },
          ],
        },
      },
    );
    expect(policyRes.ok(), await policyRes.text()).toBeTruthy();
    const policyId = ((await policyRes.json()) as { id: string }).id;
    const actPolicy = await request.post(
      `${apiBase}/api/v1/operations/moderation-policies/${policyId}/activate`,
      { headers: admin.headers },
    );
    expect(actPolicy.ok(), await actPolicy.text()).toBeTruthy();

    const pdf = await buildUniquePdf("B16-ops");
    const submissionId = await driveToReadyForEvaluation(
      request,
      apiBase,
      admin,
      assessmentId,
      studentId,
      pdf,
    );

    const { runId } = await prepareEvaluationRun(
      request,
      apiBase,
      admin,
      submissionId,
    );

    // 2) Allocate question work
    const alloc = await request.post(
      `${apiBase}/api/v1/operations/grading-pools/${poolId}/allocate`,
      {
        headers: admin.headers,
        data: { evaluation_run_id: runId },
      },
    );
    expect(alloc.ok(), await alloc.text()).toBeTruthy();
    const items = ((await alloc.json()) as { items: WorkItem[] }).items;
    expect(items.length).toBeGreaterThanOrEqual(2);

    const aItem = items.find((i) => i.assigned_evaluator_id === evalA.userId);
    const bItem = items.find((i) => i.assigned_evaluator_id === evalB.userId);
    expect(aItem).toBeTruthy();
    expect(bItem).toBeTruthy();

    // 3) Evaluator A cannot accept QE_B
    const bypass = await request.post(
      `${apiBase}/api/v1/question-evaluations/${bItem!.question_evaluation_id}/accept`,
      { headers: evalA.headers },
    );
    expect(bypass.status()).toBe(403);
    expect(detailCode(await bypass.json())).toBe("GRADING_ASSIGNMENT_FORBIDDEN");

    // 4) Assigned evaluators start / accept|override / submit
    await reviewAssignedWorkItems(request, apiBase, items, sessionsByUserId);

    // 6) Finalize → MODERATION_REVIEW; publication blocked
    const fin1 = await request.post(
      `${apiBase}/api/v1/submissions/${submissionId}/evaluation/finalize`,
      { headers: admin.headers },
    );
    expect(fin1.ok(), await fin1.text()).toBeTruthy();
    expect(((await fin1.json()) as { workflow_state: string }).workflow_state).toBe(
      "MODERATION_REVIEW",
    );

    const blockedPub = await request.post(
      `${apiBase}/api/v1/submissions/${submissionId}/publication/prepare`,
      { headers: admin.headers },
    );
    expect(blockedPub.ok()).toBeFalsy();

    const caseId = await findModerationCase(
      request,
      apiBase,
      admin,
      submissionId,
    );

    // 7) Moderator RETURN → EVALUATION_REVIEW; re-submit work; re-finalize; APPROVE stages
    const returned = await request.post(
      `${apiBase}/api/v1/operations/moderation-cases/${caseId}/decide`,
      {
        headers: moderator.headers,
        data: { decision: "RETURN", reason: "Please recheck Q1 scoring" },
      },
    );
    expect(returned.ok(), await returned.text()).toBeTruthy();
    expect(((await returned.json()) as { status: string }).status).toBe("RETURNED");

    await pollSubmissionState(
      request,
      apiBase,
      admin.headers,
      submissionId,
      /EVALUATION_REVIEW/,
    );

    const queueA = await request.get(
      `${apiBase}/api/v1/operations/grading/my-queue`,
      { headers: evalA.headers },
    );
    const queueB = await request.get(
      `${apiBase}/api/v1/operations/grading/my-queue`,
      { headers: evalB.headers },
    );
    expect(queueA.ok()).toBeTruthy();
    expect(queueB.ok()).toBeTruthy();
    const returnedItems = [
      ...(((await queueA.json()) as { items: WorkItem[] }).items ?? []),
      ...(((await queueB.json()) as { items: WorkItem[] }).items ?? []),
    ].filter(
      (i) =>
        i.status === "RETURNED" &&
        items.some((orig) => orig.id === i.id),
    );
    if (returnedItems.length > 0) {
      // Fresh ledger ReviewAction after RETURN (feedback on assigned QE)
      const freshTarget = returnedItems[0]!;
      const freshSession = sessionsByUserId.get(freshTarget.assigned_evaluator_id);
      expect(freshSession).toBeTruthy();
      const startFresh = await request.post(
        `${apiBase}/api/v1/operations/grading/work-items/${freshTarget.id}/start`,
        { headers: freshSession!.headers },
      );
      expect(startFresh.ok(), await startFresh.text()).toBeTruthy();
      const feedback = await request.post(
        `${apiBase}/api/v1/question-evaluations/${freshTarget.question_evaluation_id}/feedback`,
        {
          headers: freshSession!.headers,
          data: { feedback: "Rechecked after moderation RETURN" },
        },
      );
      expect(feedback.ok(), await feedback.text()).toBeTruthy();

      for (const item of returnedItems) {
        const session = sessionsByUserId.get(item.assigned_evaluator_id);
        expect(session).toBeTruthy();
        if (item.id !== freshTarget.id) {
          const start = await request.post(
            `${apiBase}/api/v1/operations/grading/work-items/${item.id}/start`,
            { headers: session!.headers },
          );
          expect(start.ok(), await start.text()).toBeTruthy();
        }
        const submit = await request.post(
          `${apiBase}/api/v1/operations/grading/work-items/${item.id}/submit`,
          { headers: session!.headers },
        );
        expect(submit.ok(), await submit.text()).toBeTruthy();
      }
    }

    const afterReturn = await reviewAllAndFinalize(
      request,
      apiBase,
      admin,
      submissionId,
    );
    expect(afterReturn).toBe("MODERATION_REVIEW");

    const s1 = await request.post(
      `${apiBase}/api/v1/operations/moderation-cases/${caseId}/decide`,
      {
        headers: moderator.headers,
        data: { decision: "APPROVE" },
      },
    );
    expect(s1.ok(), await s1.text()).toBeTruthy();
    expect(((await s1.json()) as { status: string }).status).toBe("PENDING");

    const s2 = await request.post(
      `${apiBase}/api/v1/operations/moderation-cases/${caseId}/decide`,
      {
        headers: hod.headers,
        data: { decision: "APPROVE" },
      },
    );
    expect(s2.ok(), await s2.text()).toBeTruthy();
    expect(((await s2.json()) as { status: string }).status).toBe("APPROVED");

    await pollSubmissionState(
      request,
      apiBase,
      admin.headers,
      submissionId,
      /^APPROVED$/,
    );

    // 8) Publish V1
    const v1Prid = await publishResult(request, apiBase, admin, submissionId);

    // Materialize analytics for V1 context (B12 later asserts post-V2)
    await expect
      .poll(
        async () => {
          const prepA = await request.post(
            `${apiBase}/api/v1/analytics/published-results/${v1Prid}/prepare`,
            { headers: admin.headers },
          );
          if (!prepA.ok()) return `prep:${prepA.status()}`;
          return "ok";
        },
        { timeout: 120_000 },
      )
      .toBe("ok");

    // 9) Create/accept grievance → RE_EVALUATION with supersedes, fresh QEs
    const grievance = await request.post(`${apiBase}/api/v1/operations/grievances`, {
      headers: admin.headers,
      data: {
        published_result_id: v1Prid,
        requester_reference: "b16-e2e-parent",
        reason: "Request formal recheck of scoring",
      },
    });
    expect(grievance.ok(), await grievance.text()).toBeTruthy();
    const grievanceId = ((await grievance.json()) as { id: string }).id;

    const accepted = await request.post(
      `${apiBase}/api/v1/operations/grievances/${grievanceId}/accept`,
      {
        headers: admin.headers,
        data: { decision_reason: "Valid recheck" },
      },
    );
    expect(accepted.ok(), await accepted.text()).toBeTruthy();
    const acceptBody = (await accepted.json()) as {
      status: string;
      reevaluation_run_id: string;
    };
    expect(acceptBody.status).toBe("RE_EVALUATING");
    expect(acceptBody.reevaluation_run_id).toBeTruthy();
    const reRunId = acceptBody.reevaluation_run_id;

    await pollSubmissionState(
      request,
      apiBase,
      admin.headers,
      submissionId,
      /EVALUATION_REVIEW/,
    );

    const reWs = await request.get(
      `${apiBase}/api/v1/submissions/${submissionId}/evaluation`,
      { headers: admin.headers },
    );
    expect(reWs.ok()).toBeTruthy();
    const reBody = (await reWs.json()) as {
      evaluation_run?: { id: string; run_kind?: string; supersedes_run_id?: string };
      question_evaluations?: QuestionEvaluationRow[];
    };
    expect(reBody.evaluation_run?.id).toBe(reRunId);
    const freshQes = reBody.question_evaluations ?? [];
    expect(freshQes.length).toBeGreaterThanOrEqual(2);
    for (const qe of freshQes) {
      expect(qe.final_human_approved_score ?? null).toBeNull();
      expect(qe.reviewed_by ?? null).toBeNull();
    }

    // Allocate fresh work for re-evaluation run and review again
    const alloc2 = await request.post(
      `${apiBase}/api/v1/operations/grading-pools/${poolId}/allocate`,
      {
        headers: admin.headers,
        data: { evaluation_run_id: reRunId },
      },
    );
    expect(alloc2.ok(), await alloc2.text()).toBeTruthy();
    const items2 = ((await alloc2.json()) as { items: WorkItem[] }).items;
    if (items2.length >= 2) {
      await reviewAssignedWorkItems(request, apiBase, items2, sessionsByUserId);
      const finRe = await request.post(
        `${apiBase}/api/v1/submissions/${submissionId}/evaluation/finalize`,
        { headers: admin.headers },
      );
      expect(finRe.ok(), await finRe.text()).toBeTruthy();
      expect(
        ((await finRe.json()) as { workflow_state: string }).workflow_state,
      ).toBe("MODERATION_REVIEW");
    } else {
      // No new work items (e.g. allocate empty) — admin governance / legacy review
      const finRe = await reviewAllAndFinalize(
        request,
        apiBase,
        admin,
        submissionId,
      );
      expect(finRe).toBe("MODERATION_REVIEW");
    }

    // 10) Fresh moderation → APPROVED
    const caseId2 = await findModerationCase(
      request,
      apiBase,
      admin,
      submissionId,
    );
    const m1 = await request.post(
      `${apiBase}/api/v1/operations/moderation-cases/${caseId2}/decide`,
      { headers: moderator.headers, data: { decision: "APPROVE" } },
    );
    expect(m1.ok(), await m1.text()).toBeTruthy();
    const m2 = await request.post(
      `${apiBase}/api/v1/operations/moderation-cases/${caseId2}/decide`,
      { headers: hod.headers, data: { decision: "APPROVE" } },
    );
    expect(m2.ok(), await m2.text()).toBeTruthy();
    expect(((await m2.json()) as { status: string }).status).toBe("APPROVED");
    await pollSubmissionState(
      request,
      apiBase,
      admin.headers,
      submissionId,
      /^APPROVED$/,
    );

    // 11) Publish V2 → V1 SUPERSEDED
    const v2Prid = await publishResult(request, apiBase, admin, submissionId);
    const pubWs = await request.get(
      `${apiBase}/api/v1/submissions/${submissionId}/publication`,
      { headers: admin.headers },
    );
    expect(pubWs.ok()).toBeTruthy();
    const latest = ((await pubWs.json()) as {
      latest: {
        id: string;
        status: string;
        supersedes_result_id?: string | null;
      };
    }).latest;
    expect(latest.id).toBe(v2Prid);
    expect(latest.status).toBe("PUBLISHED");
    expect(latest.supersedes_result_id).toBe(v1Prid);

    // 12) Materialize B12; single published attempt; V1 excluded from current projections
    await expect
      .poll(
        async () => {
          const prepA = await request.post(
            `${apiBase}/api/v1/analytics/published-results/${v2Prid}/prepare`,
            { headers: admin.headers },
          );
          if (!prepA.ok()) return `prep:${prepA.status()}`;
          const rebuild = await request.post(
            `${apiBase}/api/v1/analytics/students/${studentId}/b12/rebuild`,
            { headers: admin.headers },
          );
          if (!rebuild.ok()) return `rebuild:${rebuild.status()}`;
          return "ok";
        },
        { timeout: 120_000 },
      )
      .toBe("ok");

    const assessmentAnalytics = await request.get(
      `${apiBase}/api/v1/analytics/assessments/${assessmentId}`,
      { headers: admin.headers },
    );
    expect(assessmentAnalytics.ok()).toBeTruthy();
    expect(
      ((await assessmentAnalytics.json()) as { published_attempt_count: number })
        .published_attempt_count,
    ).toBe(1);

    const studentAnalytics = await request.get(
      `${apiBase}/api/v1/analytics/students/${studentId}`,
      { headers: admin.headers },
    );
    expect(studentAnalytics.ok()).toBeTruthy();
    expect(
      ((await studentAnalytics.json()) as { published_attempt_count: number })
        .published_attempt_count,
    ).toBe(1);

    const trend = await request.get(
      `${apiBase}/api/v1/analytics/students/${studentId}/mastery-trend`,
      { headers: admin.headers },
    );
    expect(trend.ok()).toBeTruthy();
    const trendPoints = ((await trend.json()) as {
      points: Array<{ published_result_id: string }>;
    }).points;
    const trendIds = new Set(trendPoints.map((p) => p.published_result_id));

    const notebook = await request.get(
      `${apiBase}/api/v1/analytics/students/${studentId}/mistake-notebook`,
      { headers: admin.headers },
    );
    expect(notebook.ok()).toBeTruthy();
    const notebookItems = ((await notebook.json()) as {
      items: Array<{ published_result_id: string }>;
    }).items;

    // At least one current B12 projection must exclude superseded V1.
    const trendExcludesV1 = !trendIds.has(v1Prid);
    const notebookExcludesV1 = !notebookItems.some(
      (i) => i.published_result_id === v1Prid,
    );
    expect(trendExcludesV1 || notebookExcludesV1).toBeTruthy();
  });
});
