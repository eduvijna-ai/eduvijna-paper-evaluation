import { test, expect, type APIRequestContext, type Page } from "@playwright/test";
import { randomUUID } from "node:crypto";
import { PDFDocument, StandardFonts } from "pdf-lib";

const ADMIN_EMAIL = "admin@demo.eduvijna.local";
const ADMIN_PASSWORD = "DemoAdmin!2026";
const FIXTURE_MARKER = "MATHS_IIB_UAT_FIXTURE";

function runId(): string {
  return `${Date.now().toString(36)}${randomUUID().replace(/-/g, "").slice(0, 8)}`;
}

function apiBaseFromEnv(baseURL?: string): string {
  return (
    process.env.API_UPSTREAM_URL?.replace(/\/$/, "") ??
    process.env.API_UPSTREAM ??
    baseURL ??
    "http://127.0.0.1:18000"
  );
}

async function loginApi(request: APIRequestContext, apiBase: string): Promise<string> {
  const login = await request.post(`${apiBase}/api/v1/auth/login`, {
    data: { email: ADMIN_EMAIL, password: ADMIN_PASSWORD, tenant_slug: "demo" },
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

async function buildFixturePdf(): Promise<Buffer> {
  const doc = await PDFDocument.create();
  const font = await doc.embedFont(StandardFonts.Helvetica);
  const page = doc.addPage([400, 560]);
  page.drawText(FIXTURE_MARKER, { x: 48, y: 520, size: 14, font });
  page.drawText("Section A: answer all. Section B/C: answer any five.", {
    x: 48,
    y: 480,
    size: 11,
    font,
  });
  return Buffer.from(await doc.save());
}

async function buildAnswerSheetPdf(label: string): Promise<Buffer> {
  const doc = await PDFDocument.create();
  const font = await doc.embedFont(StandardFonts.Helvetica);
  const page = doc.addPage([400, 560]);
  page.drawText(label, { x: 48, y: 500, size: 14, font });
  return Buffer.from(await doc.save());
}

test.describe("UAT critical path", () => {
  test("class section name A can exist in two grades", async ({ request, baseURL }) => {
    const apiBase = apiBaseFromEnv(baseURL);
    const token = await loginApi(request, apiBase);
    const headers = { Authorization: `Bearer ${token}` };
    const years = await request.get(`${apiBase}/api/v1/academic-years`, { headers });
    expect(years.ok()).toBeTruthy();
    const year = (await years.json())[0].id as string;
    const suffix = Date.now();
    const name = `A-${suffix}`;
    expect(
      (
        await request.post(`${apiBase}/api/v1/class-sections`, {
          headers,
          data: { academic_year_id: year, name, grade_label: "Grade 10" },
        })
      ).status(),
    ).toBe(201);
    expect(
      (
        await request.post(`${apiBase}/api/v1/class-sections`, {
          headers,
          data: { academic_year_id: year, name, grade_label: "Grade 12" },
        })
      ).status(),
    ).toBe(201);
  });

  test("curriculum create and node persist after reload", async ({ page }) => {
    await loginUi(page);
    const suffix = runId();
    const code = `UAT-CUR-${suffix}`;
    await page.goto("/curriculum");
    await page.getByTestId("curriculum-create-code").fill(code);
    await page.getByTestId("curriculum-create-name").fill(`UAT Curriculum ${suffix}`);
    await page.getByTestId("curriculum-create-version").fill("2026-27");
    await page.getByTestId("curriculum-create-framework").fill("CBSE");
    await page.getByTestId("curriculum-create-submit").click();
    await expect(page.getByTestId("curriculum-detail-page")).toBeVisible({
      timeout: 30_000,
    });
    const nodeCode = `UNIT-${suffix}`;
    await page.getByTestId("curriculum-node-code").fill(nodeCode);
    await page.getByTestId("curriculum-node-name").fill("Algebra unit");
    await page.getByTestId("curriculum-node-sequence").fill("3");
    await page.getByTestId("curriculum-node-submit").click();
    await expect(page.getByText("Algebra unit")).toBeVisible({ timeout: 20_000 });
    await page.reload();
    await expect(page.getByText("Algebra unit")).toBeVisible({ timeout: 20_000 });
    await page.goto("/curriculum");
    await expect(page.getByText(code)).toBeVisible({ timeout: 20_000 });
  });

  test("curriculum edit preserves inactive status and description", async ({
    page,
    request,
    baseURL,
  }) => {
    const apiBase = apiBaseFromEnv(baseURL);
    const token = await loginApi(request, apiBase);
    const headers = { Authorization: `Bearer ${token}` };
    const suffix = runId();
    const curriculum = await request.post(`${apiBase}/api/v1/curricula`, {
      headers,
      data: {
        code: `UAT-INACT-${suffix}`,
        name: `Inactive node ${suffix}`,
        version_label: "2026",
        status: "active",
      },
    });
    expect(curriculum.status()).toBe(201);
    const curriculumId = ((await curriculum.json()) as { id: string }).id;
    const node = await request.post(`${apiBase}/api/v1/curricula/${curriculumId}/nodes`, {
      headers,
      data: {
        node_type: "UNIT",
        code: `U-${suffix}`,
        name: "Original name",
        description: "Preserved description",
        sequence: 1,
        status: "inactive",
        metadata: {},
      },
    });
    expect(node.status()).toBe(201);
    const nodeId = ((await node.json()) as { id: string }).id;

    await loginUi(page);
    await page.goto(`/curriculum/${curriculumId}`);
    await page.getByTestId(`curriculum-node-edit-${nodeId}`).click();
    await page.getByTestId("curriculum-node-name").fill("Renamed unit");
    await page.getByTestId("curriculum-node-submit").click();
    await expect
      .poll(
        async () => {
          const tree = await request.get(
            `${apiBase}/api/v1/curricula/${curriculumId}/tree`,
            { headers },
          );
          if (!tree.ok()) return "pending";
          const nodes = (await tree.json()) as Array<{
            id: string;
            name: string;
            description?: string | null;
            status: string;
          }>;
          const row = nodes.find((n) => n.id === nodeId);
          if (!row) return "missing";
          return `${row.name}|${row.status}|${row.description ?? ""}`;
        },
        { timeout: 30_000 },
      )
      .toBe("Renamed unit|inactive|Preserved description");
    await page.reload();
    await expect(page.getByText("Renamed unit")).toBeVisible();
  });

  test("Maths-IIB ANY_N fixture parse, save, apply, and reconcile", async ({
    request,
    page,
    baseURL,
  }) => {
    test.setTimeout(300_000);
    const apiBase = apiBaseFromEnv(baseURL);
    const token = await loginApi(request, apiBase);
    const headers = { Authorization: `Bearer ${token}` };
    const suffix = runId();

    const curriculum = await request.post(`${apiBase}/api/v1/curricula`, {
      headers,
      data: {
        code: `UAT-MATH-${suffix}`,
        name: `UAT Maths ${suffix}`,
        version_label: "2026-27",
        status: "active",
      },
    });
    expect(curriculum.status()).toBe(201);
    const curriculumId = ((await curriculum.json()) as { id: string }).id;

    const assessment = await request.post(`${apiBase}/api/v1/assessments`, {
      headers,
      data: {
        curriculum_id: curriculumId,
        code: `UAT-ASM-${suffix}`,
        title: `UAT Maths-IIB ${suffix}`,
        assessment_type: "EXAM",
        max_marks: "75.00",
      },
    });
    expect(assessment.status()).toBe(201);
    const assessmentBody = (await assessment.json()) as {
      id: string;
      initial_version_id: string;
    };
    const versionId = assessmentBody.initial_version_id;
    const assessmentId = assessmentBody.id;

    const pdf = await buildFixturePdf();
    const artifact = await request.post(
      `${apiBase}/api/v1/assessment-versions/${versionId}/question-paper`,
      {
        headers,
        multipart: {
          file: {
            name: `maths-iib-${suffix}.pdf`,
            mimeType: "application/pdf",
            buffer: pdf,
          },
        },
      },
    );
    expect(artifact.status()).toBe(201);

    const parsePrep = await request.post(
      `${apiBase}/api/v1/assessment-versions/${versionId}/question-paper/parse`,
      { headers },
    );
    expect([200, 201]).toContain(parsePrep.status());
    const runIdFromPrep = ((await parsePrep.json()) as { id: string }).id;

    let roots: Array<{ stable_code: string; selection_mode?: string }> = [];
    await expect
      .poll(
        async () => {
          const run = await request.get(
            `${apiBase}/api/v1/authoring-ai-runs/${runIdFromPrep}`,
            { headers },
          );
          if (!run.ok()) return "pending";
          const body = (await run.json()) as {
            status: string;
            proposal_payload?: { roots?: typeof roots };
          };
          if (body.status !== "REVIEW_REQUIRED") return body.status;
          roots = body.proposal_payload?.roots ?? [];
          return roots.length > 0 ? "ready" : "empty";
        },
        { timeout: 120_000 },
      )
      .toBe("ready");

    const sectionB = roots.find((r) => r.stable_code === "SEC_B");
    expect(sectionB?.selection_mode).toBe("ANY_N");

    const proposalSave = await request.put(
      `${apiBase}/api/v1/authoring-ai-runs/${runIdFromPrep}/question-tree-proposal`,
      {
        headers,
        data: {
          roots: roots.map((root) =>
            root.stable_code === "SEC_B"
              ? { ...root, selection_mode: "ANY_N", selection_count: 5 }
              : root,
          ),
        },
      },
    );
    expect(proposalSave.status()).toBe(200);

    const apply = await request.post(
      `${apiBase}/api/v1/authoring-ai-runs/${runIdFromPrep}/apply-question-tree`,
      { headers },
    );
    expect(apply.status()).toBe(200);

    const reconcile = await request.get(
      `${apiBase}/api/v1/assessment-versions/${versionId}/marks/reconcile`,
      { headers },
    );
    expect(reconcile.ok()).toBeTruthy();
    const recBody = (await reconcile.json()) as { valid: boolean; leaf_marks_total: string };
    expect(recBody.valid).toBe(true);
    expect(Number(recBody.leaf_marks_total)).toBe(75);

    const tree = await request.get(
      `${apiBase}/api/v1/assessment-versions/${versionId}/questions`,
      { headers },
    );
    expect(tree.ok()).toBeTruthy();
    const countLeaves = (nodes: Array<{ children?: unknown[] }>): number =>
      nodes.reduce(
        (n, node) =>
          n +
          (node.children && node.children.length > 0
            ? countLeaves(node.children as Array<{ children?: unknown[] }>)
            : 1),
        0,
      );
    expect(countLeaves((await tree.json()) as Array<{ children?: unknown[] }>)).toBe(24);

    await loginUi(page);
    await page.goto(`/assessments/${assessmentId}/questions`);
    await expect(page.getByTestId("question-paper-workflow-guide")).toBeVisible();
    await expect(page.getByTestId("question-tree")).toBeVisible({ timeout: 30_000 });
    await expect(page.getByTestId("question-any-n-Section B")).toBeVisible();
  });

  test("question paper workflow guidance on draft assessment", async ({
    page,
    request,
    baseURL,
  }) => {
    const apiBase = apiBaseFromEnv(baseURL);
    const token = await loginApi(request, apiBase);
    const headers = { Authorization: `Bearer ${token}` };
    const suffix = runId();
    const curriculum = await request.post(`${apiBase}/api/v1/curricula`, {
      headers,
      data: {
        code: `UAT-DRAFT-${suffix}`,
        name: "Draft workflow",
        version_label: "2026",
        status: "active",
      },
    });
    expect(curriculum.status()).toBe(201);
    const curriculumId = ((await curriculum.json()) as { id: string }).id;
    const assessment = await request.post(`${apiBase}/api/v1/assessments`, {
      headers,
      data: {
        curriculum_id: curriculumId,
        code: `UAT-DR-${suffix}`,
        title: "Draft workflow assessment",
        assessment_type: "EXAM",
        max_marks: "10.00",
      },
    });
    expect(assessment.status()).toBe(201);
    const assessmentId = ((await assessment.json()) as { id: string }).id;

    const newerCurriculum = await request.post(`${apiBase}/api/v1/curricula`, {
      headers,
      data: {
        code: `UAT-NEWER-${suffix}`,
        name: "Newer listing",
        version_label: "2026",
        status: "active",
      },
    });
    expect(newerCurriculum.status()).toBe(201);
    const newerCurriculumId = ((await newerCurriculum.json()) as { id: string }).id;
    const newerActive = await request.post(`${apiBase}/api/v1/assessments`, {
      headers,
      data: {
        curriculum_id: newerCurriculumId,
        code: `UAT-ACT-${suffix}`,
        title: "Newer active assessment",
        assessment_type: "EXAM",
        max_marks: "5.00",
      },
    });
    expect(newerActive.status()).toBe(201);

    await loginUi(page);
    await page.goto(`/assessments/${assessmentId}/questions`);
    await expect(page.getByTestId("question-paper-workflow-guide")).toBeVisible();
    await expect(page.getByTestId("workflow-step-apply")).toBeVisible();
  });

  test("answer sheet upload guidance", async ({ page }) => {
    await loginUi(page);
    await page.goto("/submissions/upload");
    await expect(page.getByTestId("question-paper-vs-answer-sheet-guidance")).toBeVisible();
  });

  test("upload through evaluation finalize and publication prepare", async ({
    page,
    request,
    baseURL,
  }) => {
    test.setTimeout(480_000);
    const apiBase = apiBaseFromEnv(baseURL);
    const token = await loginApi(request, apiBase);
    const headers = { Authorization: `Bearer ${token}` };
    const suffix = runId();

    const curriculum = await request.post(`${apiBase}/api/v1/curricula`, {
      headers,
      data: {
        code: `UAT-PIPE-${suffix}`,
        name: `Pipeline ${suffix}`,
        version_label: "2026",
        status: "active",
      },
    });
    expect(curriculum.status()).toBe(201);
    const curriculumId = ((await curriculum.json()) as { id: string }).id;
    const assessment = await request.post(`${apiBase}/api/v1/assessments`, {
      headers,
      data: {
        curriculum_id: curriculumId,
        code: `UAT-PL-${suffix}`,
        title: `Pipeline ${suffix}`,
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

    const q = await request.post(
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
    expect(q.status()).toBe(201);
    const qvId = ((await q.json()) as { id: string }).id;

    const key = await request.post(
      `${apiBase}/api/v1/assessments/${assessmentId}/answer-key-versions`,
      {
        headers,
        data: {
          assessment_version_id: versionId,
          question_version_id: qvId,
          answer_text: "4",
          source_type: "TEACHER",
          status: "DRAFT",
        },
      },
    );
    expect(key.status()).toBe(201);
    await request.post(
      `${apiBase}/api/v1/answer-key-versions/${(await key.json()).id}/approve`,
      { headers },
    );

    const rubric = await request.post(`${apiBase}/api/v1/assessments/${assessmentId}/rubrics`, {
      headers,
      data: { question_version_id: qvId, title: "R1", provenance: "TEACHER" },
    });
    expect(rubric.status()).toBe(201);
    const rubricId = ((await rubric.json()) as { id: string }).id;
    const rv = await request.post(`${apiBase}/api/v1/rubrics/${rubricId}/versions`, {
      headers,
      data: {
        question_version_id: qvId,
        source_type: "TEACHER",
        status: "DRAFT",
      },
    });
    expect(rv.status()).toBe(201);
    const rvId = ((await rv.json()) as { id: string }).id;
    await request.post(`${apiBase}/api/v1/rubric-versions/${rvId}/criteria`, {
      headers,
      data: {
        criterion_code: "C1",
        description: "Correct",
        max_marks: "10.00",
        sequence: 1,
        scoring_mode: "ADDITIVE",
        partial_credit_allowed: true,
        ecf_policy: "NONE",
      },
    });
    await request.post(`${apiBase}/api/v1/rubric-versions/${rvId}/approve`, { headers });

    for (const to of ["READY", "ACTIVE"]) {
      const tr = await request.post(
        `${apiBase}/api/v1/assessments/${assessmentId}/transition`,
        { headers, data: { to_status: to } },
      );
      expect(tr.status()).toBe(200);
    }

    const sections = await request.get(`${apiBase}/api/v1/class-sections`, { headers });
    const section = (await sections.json())[0] as {
      id: string;
      academic_year_id: string;
    };
    const student = await request.post(`${apiBase}/api/v1/students`, {
      headers,
      data: {
        student_code: `UAT-ST-${suffix}`,
        full_name: `Student ${suffix}`,
        class_section_id: section.id,
        academic_year_id: section.academic_year_id,
        status: "active",
      },
    });
    expect(student.status()).toBe(201);
    const studentId = ((await student.json()) as { id: string }).id;

    await loginUi(page);
    await page.goto("/submissions/upload");
    await page.getByTestId("upload-assessment").selectOption(assessmentId);
    const pdf = await buildAnswerSheetPdf(`UAT sheet ${suffix}`);
    await page.getByTestId("upload-file").setInputFiles({
      name: "uat-sheet.pdf",
      mimeType: "application/pdf",
      buffer: pdf,
    });
    await page.getByTestId("upload-submit").click();
    await expect(page.getByTestId("submission-detail-page")).toBeVisible({
      timeout: 60_000,
    });
    const submissionId =
      page.url().split("/submissions/")[1]?.split(/[/?#]/)[0] ?? "";
    expect(submissionId).toBeTruthy();

    await page.getByTestId("link-identity").click();
    await page.getByTestId(`match-candidate-${studentId}`).click();
    await page.getByTestId("confirm-identity").click();

    await expect
      .poll(
        async () => {
          await page.goto(`/submissions/${submissionId}`);
          return (await page.getByTestId("submission-workflow-state").textContent()) ?? "";
        },
        { timeout: 120_000 },
      )
      .toMatch(/mapping review/i);

    await page.getByTestId("link-mapping").click();
    await expect(page.getByTestId("mapping-review-page")).toBeVisible({
      timeout: 30_000,
    });
    await page.getByTestId("question-tree-item-1").click();
    if ((await page.getByTestId("region-ai-proposal-badge").count()) === 0) {
      await page.getByTestId("add-answer-region").click();
    }
    await expect(page.getByTestId("assign-region")).toBeEnabled({ timeout: 60_000 });
    await page.getByTestId("assign-region").click();
    await page.getByTestId("confirm-mapping").click();
    await page.getByTestId("finalize-mapping").click();

    await expect
      .poll(
        async () => {
          await page.goto(`/submissions/${submissionId}`);
          return (await page.getByTestId("submission-workflow-state").textContent()) ?? "";
        },
        { timeout: 120_000 },
      )
      .toMatch(/ready for evaluation|awaiting transcription/i);

    await expect
      .poll(
        async () => {
          await page.reload();
          return (await page.getByTestId("open-current-stage").getAttribute("href")) ?? "";
        },
        { timeout: 120_000 },
      )
      .toMatch(/\/transcription$/);

    await page.getByTestId("open-current-stage").click();
    const textInput = page.getByTestId("transcription-text-input").first();
    if (await textInput.count()) {
      await textInput.fill("4");
      await page.getByTestId("save-transcription").first().click();
    }
    const confirm = page.getByTestId("confirm-transcription").first();
    if ((await confirm.count()) && (await confirm.isEnabled())) {
      await confirm.click();
    }
    await expect(page.getByTestId("finalize-transcription")).toBeEnabled({
      timeout: 60_000,
    });
    await page.getByTestId("finalize-transcription").click();

    await expect
      .poll(
        async () => {
          const prep = await request.post(
            `${apiBase}/api/v1/submissions/${submissionId}/evaluation/prepare`,
            { headers },
          );
          if (![200, 409].includes(prep.status())) return `prep:${prep.status()}`;
          const fin = await request.post(
            `${apiBase}/api/v1/submissions/${submissionId}/evaluation/finalize`,
            { headers },
          );
          if (!fin.ok()) return `fin:${fin.status()}`;
          return (await fin.json()).workflow_state ?? "unknown";
        },
        { timeout: 180_000 },
      )
      .toBe("APPROVED");

    const pubPrep = await request.post(
      `${apiBase}/api/v1/submissions/${submissionId}/publication/prepare`,
      { headers },
    );
    expect([200, 409]).toContain(pubPrep.status());
  });
});
