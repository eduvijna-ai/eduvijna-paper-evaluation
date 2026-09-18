import { test, expect, type APIRequestContext } from "@playwright/test";
import { randomUUID } from "node:crypto";
import { PDFDocument, StandardFonts } from "pdf-lib";

test.setTimeout(600_000);

const ADMIN_EMAIL = "admin@demo.eduvijna.local";
const ADMIN_PASSWORD = "DemoAdmin!2026";
const ISO_EMAIL = "admin@b19-iso.eduvijna.local";
const ISO_TENANT = "b19-iso";

function runId(): string {
  return `${Date.now().toString(36)}${randomUUID().replace(/-/g, "").slice(0, 8)}`;
}

function detailCode(body: unknown): string | undefined {
  const b = body as {
    detail?: { code?: string } | string;
    error?: { code?: string; details?: { code?: string } };
  };
  if (typeof b.detail === "object" && b.detail?.code) return b.detail.code;
  if (b.error?.code) return b.error.code;
  return b.error?.details?.code;
}

function apiBaseUrl(): string {
  return (
    process.env.E2E_API_BASE_URL ??
    process.env.API_UPSTREAM_URL ??
    "http://127.0.0.1:18000"
  );
}

async function buildPdf(label: string): Promise<Buffer> {
  const doc = await PDFDocument.create();
  const font = await doc.embedFont(StandardFonts.Helvetica);
  for (const pageLabel of [`Page 1 — ${label}`, `Page 2 — ${label}`]) {
    const page = doc.addPage([400, 560]);
    page.drawText(pageLabel, { x: 48, y: 500, size: 16, font });
  }
  return Buffer.from(await doc.save());
}

async function loginApi(
  request: APIRequestContext,
  apiBase: string,
  email = ADMIN_EMAIL,
  password = ADMIN_PASSWORD,
  tenantSlug = "demo",
): Promise<string> {
  const login = await request.post(`${apiBase}/api/v1/auth/login`, {
    data: { email, password, tenant_slug: tenantSlug },
  });
  expect(login.ok(), await login.text()).toBeTruthy();
  return ((await login.json()) as { access_token: string }).access_token;
}

async function waitUntil<T>(
  load: () => Promise<T>,
  predicate: (value: T) => boolean,
  timeoutMs: number,
  label: string,
): Promise<T> {
  const started = Date.now();
  let last: T | undefined;
  while (Date.now() - started < timeoutMs) {
    last = await load();
    if (predicate(last)) return last;
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error(`timed out waiting for ${label}: ${JSON.stringify(last)}`);
}

type SubjectSpec = {
  code: string;
  name: string;
  metadata?: Record<string, string>;
};

async function createLeafAssessment(
  request: APIRequestContext,
  apiBase: string,
  token: string,
  opts: {
    prefix: string;
    subject: SubjectSpec;
    prompt: string;
    answer: string;
  },
): Promise<{ assessmentId: string; studentId: string; subjectNodeId: string }> {
  const headers = { Authorization: `Bearer ${token}` };
  const suffix = runId();

  const curriculum = await request.post(`${apiBase}/api/v1/curricula`, {
    headers,
    data: {
      code: `${opts.prefix}-CUR-${suffix}`,
      name: `${opts.prefix} Curriculum ${suffix}`,
      version_label: "2026",
      status: "active",
    },
  });
  expect(curriculum.status()).toBe(201);
  const curriculumId = ((await curriculum.json()) as { id: string }).id;

  const node = await request.post(
    `${apiBase}/api/v1/curricula/${curriculumId}/nodes`,
    {
      headers,
      data: {
        node_type: "SUBJECT",
        code: `${opts.subject.code}-${suffix}`,
        name: opts.subject.name,
        sequence: 1,
        metadata: opts.subject.metadata ?? {},
        status: "active",
      },
    },
  );
  expect(node.status()).toBe(201);
  const subjectNodeId = ((await node.json()) as { id: string }).id;

  const assessment = await request.post(`${apiBase}/api/v1/assessments`, {
    headers,
    data: {
      curriculum_id: curriculumId,
      subject_node_id: subjectNodeId,
      code: `${opts.prefix}-ASM-${suffix}`,
      title: `${opts.prefix} Assessment ${suffix}`,
      assessment_type: "EXAM",
      max_marks: "5.00",
    },
  });
  expect(assessment.status()).toBe(201);
  const assessmentBody = (await assessment.json()) as {
    id: string;
    initial_version_id: string;
    subject_profile?: string;
    subject_node_id?: string;
  };
  expect(assessmentBody.subject_node_id).toBe(subjectNodeId);
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
        prompt_text: opts.prompt,
        max_marks: "5.00",
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
        answer_text: opts.answer,
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
  const section = sectionRows.find((row) =>
    yearRows.some((year) => year.id === row.academic_year_id),
  );
  expect(section).toBeTruthy();
  const student = await request.post(`${apiBase}/api/v1/students`, {
    headers,
    data: {
      student_code: `${opts.prefix}-${suffix}`,
      full_name: `${opts.prefix} Student ${suffix}`,
      class_section_id: section!.id,
      academic_year_id: section!.academic_year_id,
      status: "active",
    },
  });
  expect(student.status()).toBe(201);
  return {
    assessmentId,
    studentId: ((await student.json()) as { id: string }).id,
    subjectNodeId,
  };
}

async function uiLogin(page: import("@playwright/test").Page) {
  await page.goto("/login");
  await page.getByTestId("login-email").fill(ADMIN_EMAIL);
  await page.getByTestId("login-password").fill(ADMIN_PASSWORD);
  await page.getByTestId("login-submit").click();
  await expect(page.getByTestId("app-shell")).toBeVisible({ timeout: 30_000 });
}

async function uploadViaUi(
  page: import("@playwright/test").Page,
  assessmentId: string,
  pdf: Buffer,
  language?: { language: string; script: string },
) {
  await page.goto("/submissions/upload");
  await page.getByTestId("upload-assessment").selectOption(assessmentId);
  if (language) {
    await page.getByTestId("upload-language-code").selectOption(language.language);
    await page.getByTestId("upload-script-code").selectOption(language.script);
  }
  await page.getByTestId("upload-file").setInputFiles({
    name: "b20-sheet.pdf",
    mimeType: "application/pdf",
    buffer: pdf,
  });
  await page.getByTestId("upload-submit").click();
  await expect(page.getByTestId("submission-detail-page")).toBeVisible({
    timeout: 60_000,
  });
}

async function confirmIdentityAndMap(
  page: import("@playwright/test").Page,
  studentId: string,
) {
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
        await page.goto(page.url().replace(/\/identity.*/, ""));
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
    /1 of 1 scorable questions confirmed/i,
    { timeout: 20_000 },
  );
  await page.getByTestId("finalize-mapping").click();
  await expect(page.getByTestId("submission-detail-page")).toBeVisible({
    timeout: 30_000,
  });
}

async function openTranscriptionWorkspace(page: import("@playwright/test").Page) {
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
}

async function confirmAndFinalizeTranscription(page: import("@playwright/test").Page) {
  await expect(page.getByTestId("transcription-original-text").first()).toBeVisible({
    timeout: 60_000,
  });
  await page.getByTestId("transcription-original-text").first().click();
  const buttons = page.getByTestId("confirm-transcription");
  const total = await buttons.count();
  expect(total).toBeGreaterThan(0);
  for (let i = 0; i < total; i += 1) {
    const btn = buttons.nth(i);
    if (await btn.isDisabled()) continue;
    await btn.scrollIntoViewIfNeeded();
    await expect(btn).toBeEnabled({ timeout: 30_000 });
    await btn.click({ timeout: 30_000 });
    await expect(btn).toBeDisabled({ timeout: 30_000 });
  }
  await expect(page.locator('[data-testid="confirm-transcription"]:not([disabled])')).toHaveCount(
    0,
    { timeout: 30_000 },
  );
  await expect(page.getByTestId("finalize-transcription")).toBeEnabled({
    timeout: 30_000,
  });
  await page.getByTestId("finalize-transcription").click();
  await expect(page.getByTestId("submission-detail-page")).toBeVisible({
    timeout: 30_000,
  });
  await expect(page.getByTestId("link-evaluation")).toBeVisible({ timeout: 30_000 });
}

async function enterEvaluationWorkspace(page: import("@playwright/test").Page) {
  await page.getByTestId("link-evaluation").click();
  await expect(page.getByTestId("evaluation-workspace-page")).toBeVisible({
    timeout: 60_000,
  });
  await expect(page.getByTestId("evaluation-workspace-page")).toHaveAttribute(
    "data-evaluation-mode",
    "live",
  );
}

function submissionIdFromUrl(url: string): string {
  const id = url.split("/submissions/")[1]?.split("/")[0];
  expect(id).toBeTruthy();
  return id as string;
}

async function waitForEvaluationEvidence(
  request: APIRequestContext,
  apiBase: string,
  token: string,
  submissionId: string,
  expectedProfile: string,
) {
  return waitUntil(
    async () => {
      const res = await request.get(
        `${apiBase}/api/v1/submissions/${submissionId}/evaluation`,
        { headers: { Authorization: `Bearer ${token}` } },
      );
      expect(res.status()).toBe(200);
      return (await res.json()) as {
        workflow_state?: string;
        question_evaluations?: Array<{
          subject_profile?: string;
          math_verification_invoked?: boolean;
          workflow_state?: string;
        }>;
      };
    },
    (body) => {
      if (body.workflow_state !== "EVALUATION_REVIEW") return false;
      const qes = body.question_evaluations ?? [];
      if (qes.length === 0) return false;
      return qes.every(
        (qe) =>
          qe.subject_profile === expectedProfile &&
          qe.math_verification_invoked === false &&
          qe.workflow_state !== "PENDING",
      );
    },
    180_000,
    `${expectedProfile} evaluation evidence without Math verification`,
  );
}

test.describe("B20 real multi-subject and multilingual", () => {
  test("Path A — Mathematics regression through the real pipeline", async ({
    page,
    request,
  }) => {
    const apiBase = apiBaseUrl();
    expect((await request.get(`${apiBase}/health`)).ok()).toBeTruthy();
    const token = await loginApi(request, apiBase);
    const created = await createLeafAssessment(request, apiBase, token, {
      prefix: "B20A",
      subject: { code: "MATH", name: "Mathematics", metadata: { subject_profile: "MATHEMATICS" } },
      prompt: "2+2?",
      answer: "4",
    });
    const assessment = await request.get(
      `${apiBase}/api/v1/assessments/${created.assessmentId}`,
      { headers: { Authorization: `Bearer ${token}` } },
    );
    expect(assessment.ok()).toBeTruthy();
    const assessmentBody = (await assessment.json()) as {
      subject_profile: string;
      math_verification_eligible: boolean;
    };
    expect(assessmentBody.subject_profile).toBe("MATHEMATICS");
    expect(assessmentBody.math_verification_eligible).toBe(true);

    await uiLogin(page);
    await page.goto(`/assessments/${created.assessmentId}`);
    await expect(page.getByTestId("assessment-subject-profile")).toContainText(/Mathematics/i);

    await uploadViaUi(page, created.assessmentId, await buildPdf("B20A"));
    await confirmIdentityAndMap(page, created.studentId);
    await openTranscriptionWorkspace(page);
    await expect(page.getByTestId("transcription-subject-profile")).toContainText(
      /Mathematics/i,
    );
    await expect(page.getByTestId("transcription-review-page")).toHaveAttribute(
      "data-transcription-mode",
      "live",
    );
    const textInput = page.getByTestId("transcription-text-input").first();
    await textInput.fill("4");
    await page.getByTestId("save-transcription").first().click();
    await page.getByTestId("confirm-transcription").first().click();
    await page.getByTestId("finalize-transcription").click();
    await expect(page.getByTestId("submission-detail-page")).toBeVisible({
      timeout: 30_000,
    });
  });

  test("Path B — Physics structured non-Math does not use Math verification", async ({
    page,
    request,
  }) => {
    const apiBase = apiBaseUrl();
    const token = await loginApi(request, apiBase);
    const created = await createLeafAssessment(request, apiBase, token, {
      prefix: "B20B",
      subject: { code: "PHY", name: "Physics", metadata: { subject_profile: "PHYSICS" } },
      prompt: "State Newton second law.",
      answer: "F = ma",
    });
    const assessment = await request.get(
      `${apiBase}/api/v1/assessments/${created.assessmentId}`,
      { headers: { Authorization: `Bearer ${token}` } },
    );
    const assessmentBody = (await assessment.json()) as {
      subject_profile: string;
      math_verification_eligible: boolean;
      subject_node_id: string;
    };
    expect(assessmentBody.subject_profile).toBe("PHYSICS");
    expect(assessmentBody.math_verification_eligible).toBe(false);
    expect(assessmentBody.subject_node_id).toBe(created.subjectNodeId);

    await uiLogin(page);
    await page.goto(`/assessments/${created.assessmentId}`);
    await expect(page.getByTestId("assessment-subject-profile")).toContainText(/Physics/i);
    await expect(page.getByTestId("assessment-math-verification")).toContainText(/Not eligible/i);

    await uploadViaUi(page, created.assessmentId, await buildPdf("B20B"), {
      language: "en",
      script: "Latn",
    });
    await confirmIdentityAndMap(page, created.studentId);
    await openTranscriptionWorkspace(page);
    await expect(page.getByTestId("transcription-subject-profile")).toContainText(/Physics/i);
    await expect(page.getByTestId("transcription-original-text").first()).toBeVisible({
      timeout: 60_000,
    });
    await expect(page.getByTestId("transcription-original-text").first()).toContainText(
      /Newton|force|mass/i,
    );
    await confirmAndFinalizeTranscription(page);
    await enterEvaluationWorkspace(page);
    const submissionId = submissionIdFromUrl(page.url());
    const evidence = await waitForEvaluationEvidence(
      request,
      apiBase,
      token,
      submissionId,
      "PHYSICS",
    );
    expect(evidence.workflow_state).toBe("EVALUATION_REVIEW");
    const qes = evidence.question_evaluations ?? [];
    expect(qes.length).toBeGreaterThan(0);
    for (const qe of qes) {
      expect(qe.subject_profile).toBe("PHYSICS");
      expect(qe.math_verification_invoked).toBe(false);
    }
  });

  test("Path C — structured descriptive subject travels the governed path", async ({
    page,
    request,
  }) => {
    const apiBase = apiBaseUrl();
    const token = await loginApi(request, apiBase);
    const created = await createLeafAssessment(request, apiBase, token, {
      prefix: "B20C",
      subject: {
        code: "HIST",
        name: "History",
        metadata: { subject_profile: "STRUCTURED_DESCRIPTIVE" },
      },
      prompt: "Explain urban labour relations.",
      answer: "Labour relations changed during industrial expansion.",
    });
    const assessment = await request.get(
      `${apiBase}/api/v1/assessments/${created.assessmentId}`,
      { headers: { Authorization: `Bearer ${token}` } },
    );
    expect(((await assessment.json()) as { subject_profile: string }).subject_profile).toBe(
      "STRUCTURED_DESCRIPTIVE",
    );

    await uiLogin(page);
    await page.goto(`/assessments/${created.assessmentId}`);
    await expect(page.getByTestId("assessment-subject-profile")).toContainText(
      /Structured descriptive/i,
    );
    await uploadViaUi(page, created.assessmentId, await buildPdf("B20C"), {
      language: "en",
      script: "Latn",
    });
    await confirmIdentityAndMap(page, created.studentId);
    await openTranscriptionWorkspace(page);
    await expect(page.getByTestId("transcription-subject-profile")).toContainText(
      /Structured descriptive/i,
    );
    await expect(page.getByTestId("transcription-original-text").first()).toBeVisible({
      timeout: 60_000,
    });
    await confirmAndFinalizeTranscription(page);
    await enterEvaluationWorkspace(page);
    const submissionId = submissionIdFromUrl(page.url());
    const evidence = await waitForEvaluationEvidence(
      request,
      apiBase,
      token,
      submissionId,
      "STRUCTURED_DESCRIPTIVE",
    );
    expect(evidence.workflow_state).toBe("EVALUATION_REVIEW");
    const qes = evidence.question_evaluations ?? [];
    expect(qes.length).toBeGreaterThan(0);
    for (const qe of qes) {
      expect(qe.subject_profile).toBe("STRUCTURED_DESCRIPTIVE");
      expect(qe.math_verification_invoked).toBe(false);
    }
  });

  test("Path D — Hindi Devanagari original transcription remains authoritative", async ({
    page,
    request,
  }) => {
    const apiBase = apiBaseUrl();
    const token = await loginApi(request, apiBase);
    const created = await createLeafAssessment(request, apiBase, token, {
      prefix: "B20D",
      subject: { code: "MATH", name: "Mathematics", metadata: { subject_profile: "MATHEMATICS" } },
      prompt: "Find the area.",
      answer: "length times width",
    });

    await uiLogin(page);
    await uploadViaUi(page, created.assessmentId, await buildPdf("B20D"), {
      language: "hi",
      script: "Deva",
    });
    await expect(page.getByTestId("submission-language-code")).toHaveText("hi");
    await expect(page.getByTestId("submission-script-code")).toHaveText("Deva");
    const submissionUrl = page.url();

    await confirmIdentityAndMap(page, created.studentId);
    await openTranscriptionWorkspace(page);
    await expect(page.getByTestId("transcription-language-code")).toHaveText("hi");
    await expect(page.getByTestId("transcription-script-code")).toHaveText("Deva");
    await expect(page.getByTestId("transcription-language-source")).toContainText(/PROVIDED/i);
    await expect(page.getByTestId("transcription-original-text").first()).toContainText(
      "हिंदी में हल",
      { timeout: 60_000 },
    );
    await expect(page.getByTestId("transcription-translation")).toBeVisible();
    await expect(page.getByTestId("transcription-translation")).toContainText("Solution in Hindi");
    await expect(page.getByTestId("transcription-transliteration")).toBeVisible();
    const derivedSource = page.getByTestId("transcription-derived-source-id").first();
    await expect(derivedSource).not.toHaveText("");
    const originalBeforeConfirm = await page
      .getByTestId("transcription-original-text")
      .first()
      .textContent();
    expect(originalBeforeConfirm).toContain("हिंदी में हल");
    const submissionId = submissionIdFromUrl(page.url());
    await confirmAndFinalizeTranscription(page);

    const confirmed = await request.get(
      `${apiBase}/api/v1/submissions/${submissionId}/transcription`,
      { headers: { Authorization: `Bearer ${token}` } },
    );
    expect(confirmed.status()).toBe(200);
    const confirmedBody = (await confirmed.json()) as {
      language_context?: { language_code?: string; script_code?: string };
      items?: Array<{
        regions?: Array<{
          active_transcription?: {
            id?: string;
            status?: string;
            text?: string;
            language_code?: string;
            script_code?: string;
            derived_texts?: Array<{
              kind?: string;
              text?: string;
              source_transcription_id?: string;
            }>;
          };
        }>;
      }>;
    };
    expect(confirmedBody.language_context?.language_code).toBe("hi");
    expect(confirmedBody.language_context?.script_code).toBe("Deva");
    const actives = (confirmedBody.items ?? []).flatMap((item) =>
      (item.regions ?? []).map((region) => region.active_transcription),
    );
    const active = actives.find(
      (row) => row?.status === "CONFIRMED" && (row.text ?? "").includes("हिंदी में हल"),
    );
    expect(active).toBeTruthy();
    expect(active?.language_code).toBe("hi");
    expect(active?.script_code).toBe("Deva");
    const derived = active?.derived_texts ?? [];
    const translation = derived.find((row) => row.kind === "TRANSLATION");
    const transliteration = derived.find((row) => row.kind === "TRANSLITERATION");
    expect(translation).toBeTruthy();
    expect(transliteration).toBeTruthy();
    expect(translation?.text).toContain("Solution in Hindi");
    expect(translation?.text).not.toBe(active?.text);
    expect(translation?.source_transcription_id).toBe(active?.id);
    expect(transliteration?.source_transcription_id).toBe(active?.id);

    await page.goto(submissionUrl);
    await expect(page.getByTestId("submission-language-code")).toHaveText("hi");
    await expect(page.getByTestId("submission-script-code")).toHaveText("Deva");
  });

  test("Path E — unsupported language cannot silently auto-progress", async ({
    page,
    request,
  }) => {
    const apiBase = apiBaseUrl();
    const token = await loginApi(request, apiBase);
    const created = await createLeafAssessment(request, apiBase, token, {
      prefix: "B20E",
      subject: { code: "MATH", name: "Mathematics", metadata: { subject_profile: "MATHEMATICS" } },
      prompt: "2+2?",
      answer: "4",
    });

    await uiLogin(page);
    await uploadViaUi(page, created.assessmentId, await buildPdf("B20E"), {
      language: "ja",
      script: "Jpan",
    });
    await expect(page.getByTestId("submission-language-state")).toContainText(/Unsupported/i);
    const submissionId = page.url().split("/submissions/")[1]?.split("/")[0];
    expect(submissionId).toBeTruthy();

    await confirmIdentityAndMap(page, created.studentId);
    await openTranscriptionWorkspace(page);
    await expect(page.getByTestId("transcription-language-state")).toContainText(/Unsupported/i);
    await expect(page.getByTestId("transcription-automation-block")).toContainText(
      "LANGUAGE_UNSUPPORTED",
    );
    await page.getByTestId("finalize-transcription").click();
    await expect(page.getByTestId("transcription-action-error")).toContainText(
      "LANGUAGE_UNSUPPORTED",
    );

    const prepare = await request.post(
      `${apiBase}/api/v1/submissions/${submissionId}/transcription/prepare`,
      { headers: { Authorization: `Bearer ${token}` } },
    );
    expect(prepare.status()).toBe(409);
    expect(detailCode(await prepare.json())).toBe("LANGUAGE_UNSUPPORTED");
  });

  test("Path G — UI confirms detected hi/Deva without changing the pair", async ({
    page,
    request,
  }) => {
    const apiBase = apiBaseUrl();
    const token = await loginApi(request, apiBase);
    const created = await createLeafAssessment(request, apiBase, token, {
      prefix: "B20G",
      subject: { code: "MATH", name: "Mathematics", metadata: { subject_profile: "MATHEMATICS" } },
      prompt: "Find the area.",
      answer: "length times width",
    });

    await uiLogin(page);
    await uploadViaUi(page, created.assessmentId, await buildPdf("B20G"));
    const submissionId = submissionIdFromUrl(page.url());

    const detected = await request.put(
      `${apiBase}/api/v1/submissions/${submissionId}/language`,
      {
        headers: { Authorization: `Bearer ${token}` },
        data: {
          language_code: "hi",
          script_code: "Deva",
          source: "DETECTED",
          confidence: 0.4,
          ambiguous: true,
        },
      },
    );
    expect(detected.ok(), await detected.text()).toBeTruthy();
    const detectedBody = (await detected.json()) as {
      language_code: string;
      script_code: string;
      language_source: string;
      language_state: string;
      automation_block_code: string | null;
    };
    expect(detectedBody.language_code).toBe("hi");
    expect(detectedBody.script_code).toBe("Deva");
    expect(detectedBody.language_source).toBe("DETECTED");
    expect(detectedBody.language_state).toBe("REVIEW_REQUIRED");
    expect(detectedBody.automation_block_code).toBe("LANGUAGE_REVIEW_REQUIRED");

    await page.reload();
    await expect(page.getByTestId("submission-detail-page")).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByTestId("submission-language-code")).toHaveText("hi");
    await expect(page.getByTestId("submission-script-code")).toHaveText("Deva");
    await expect(page.getByTestId("submission-language-source")).toHaveText("DETECTED");
    await expect(page.getByTestId("submission-language-state")).toContainText(
      /Review required/i,
    );
    await expect(page.getByTestId("language-review-panel")).toBeVisible();
    await expect(page.getByTestId("language-review-language")).toHaveValue("hi");
    await expect(page.getByTestId("language-review-script")).toHaveValue("Deva");
    await page.getByTestId("confirm-language").click();
    await expect(page.getByTestId("submission-language-source")).toHaveText("PROVIDED", {
      timeout: 30_000,
    });
    await expect(page.getByTestId("submission-language-state")).toContainText(/Confirmed/i);
    await expect(page.getByTestId("language-review-panel")).toHaveCount(0);

    const afterUi = await request.get(`${apiBase}/api/v1/submissions/${submissionId}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(afterUi.ok(), await afterUi.text()).toBeTruthy();
    const confirmedBody = (await afterUi.json()) as {
      language_code: string;
      script_code: string;
      language_source: string;
      language_state: string;
      automation_block_code: string | null;
    };
    expect(confirmedBody.language_code).toBe("hi");
    expect(confirmedBody.script_code).toBe("Deva");
    expect(confirmedBody.language_source).toBe("PROVIDED");
    expect(confirmedBody.language_state).toBe("CONFIRMED");
    expect(confirmedBody.automation_block_code).toBeNull();

    await confirmIdentityAndMap(page, created.studentId);
    await openTranscriptionWorkspace(page);
    await expect(page.getByTestId("transcription-language-code")).toHaveText("hi");
    await expect(page.getByTestId("transcription-script-code")).toHaveText("Deva");
    await expect(page.getByTestId("transcription-language-source")).toContainText(/PROVIDED/i);
    await expect(page.getByTestId("transcription-language-state")).toContainText(/Confirmed/i);
    await expect(page.getByTestId("transcription-automation-block")).toHaveCount(0);
    await expect(page.getByTestId("language-review-panel")).toHaveCount(0);
    await expect(page.getByTestId("transcription-original-text").first()).toBeVisible({
      timeout: 60_000,
    });
  });

  test("Path F — another tenant cannot access subject/language metadata", async ({
    request,
  }) => {
    const apiBase = apiBaseUrl();
    const token = await loginApi(request, apiBase);
    const created = await createLeafAssessment(request, apiBase, token, {
      prefix: "B20F",
      subject: { code: "PHY", name: "Physics", metadata: { subject_profile: "PHYSICS" } },
      prompt: "Force?",
      answer: "mass times acceleration",
    });
    const pdf = await buildPdf("B20F");
    const upload = await request.post(`${apiBase}/api/v1/submissions`, {
      headers: { Authorization: `Bearer ${token}` },
      multipart: {
        assessment_id: created.assessmentId,
        language_code: "hi",
        script_code: "Deva",
        file: {
          name: "iso.pdf",
          mimeType: "application/pdf",
          buffer: pdf,
        },
      },
    });
    expect(upload.status()).toBe(201);
    const submissionId = ((await upload.json()) as { id: string }).id;
    await waitUntil(
      async () =>
        (
          await (
            await request.get(`${apiBase}/api/v1/submissions/${submissionId}`, {
              headers: { Authorization: `Bearer ${token}` },
            })
          ).json()
        ).id,
      (id) => Boolean(id),
      15_000,
      "submission readable",
    );

    const isoToken = await loginApi(request, apiBase, ISO_EMAIL, ADMIN_PASSWORD, ISO_TENANT);
    const isoHeaders = { Authorization: `Bearer ${isoToken}` };
    expect(
      (
        await request.get(`${apiBase}/api/v1/submissions/${submissionId}`, {
          headers: isoHeaders,
        })
      ).status(),
    ).toBe(404);
    expect(
      (
        await request.put(`${apiBase}/api/v1/submissions/${submissionId}/language`, {
          headers: isoHeaders,
          data: { language_code: "en", script_code: "Latn" },
        })
      ).status(),
    ).toBe(404);
    expect(
      (
        await request.get(`${apiBase}/api/v1/submissions/${submissionId}/transcription`, {
          headers: isoHeaders,
        })
      ).status(),
    ).toBe(404);
    expect(
      (
        await request.get(`${apiBase}/api/v1/assessments/${created.assessmentId}`, {
          headers: isoHeaders,
        })
      ).status(),
    ).toBe(404);
  });
});
