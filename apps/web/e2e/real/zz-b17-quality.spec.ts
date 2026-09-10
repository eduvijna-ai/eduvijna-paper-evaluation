/**
 * B17 PEV-048/049 real-stack quality acceptance (deterministic, never skip).
 *
 * Requires CI seed: `python -m app.cli.seed_b17_e2e_quality` after seed_dev.
 * Uses assessment code B17-E2E-QUALITY with >=20 published human-final results.
 */

import { test, expect, type APIRequestContext, type Page } from "@playwright/test";

const ADMIN_EMAIL = "admin@demo.eduvijna.local";
const ADMIN_PASSWORD = "DemoAdmin!2026";
const DEMO_USER_PASSWORD = "DemoUser!2026";
const EVALUATOR_A_EMAIL = "evaluator-a@demo.eduvijna.local";
const EVALUATOR_B_EMAIL = "evaluator-b@demo.eduvijna.local";
const MODERATOR_EMAIL = "moderator@demo.eduvijna.local";

const B17_ASSESSMENT_CODE = "B17-E2E-QUALITY";

type AuthSession = {
  token: string;
  userId: string;
  headers: { Authorization: string };
};

type EligibleCase = {
  published_result_id: string;
  question_evaluation_id: string;
  reference_score: number;
  submission_id: string;
  ledger_snapshot_hash: string;
  published_status: string;
  qe_score: number | string | null;
  qe_workflow_state: string;
};

function detailCode(body: unknown): string | undefined {
  const b = body as {
    detail?: { code?: string } | string;
    error?: { code?: string };
  };
  if (typeof b.detail === "object" && b.detail?.code) return b.detail.code;
  return b.error?.code;
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
  expect(login.ok(), `login failed for ${email}: ${await login.text()}`).toBeTruthy();
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

async function loginUi(page: Page) {
  await page.goto("/login");
  await page.getByTestId("login-email").fill(ADMIN_EMAIL);
  await page.getByTestId("login-password").fill(ADMIN_PASSWORD);
  await page.getByTestId("login-submit").click();
  await expect(page.getByTestId("app-shell")).toBeVisible({ timeout: 30_000 });
}

async function resolveB17Assessment(
  request: APIRequestContext,
  apiBase: string,
  headers: AuthSession["headers"],
): Promise<{ assessmentId: string; versionId: string }> {
  const assessments = await request.get(`${apiBase}/api/v1/assessments`, {
    headers,
  });
  expect(assessments.ok(), await assessments.text()).toBeTruthy();
  const list = (await assessments.json()) as { id: string; code?: string }[];
  const assessment = list.find((a) => a.code === B17_ASSESSMENT_CODE);
  expect(
    assessment,
    `Missing seeded assessment ${B17_ASSESSMENT_CODE}; run seed_b17_e2e_quality`,
  ).toBeTruthy();

  const versions = await request.get(
    `${apiBase}/api/v1/assessments/${assessment!.id}/versions`,
    { headers },
  );
  expect(versions.ok(), await versions.text()).toBeTruthy();
  const versionItems = (await versions.json()) as { id: string }[];
  expect(versionItems.length).toBeGreaterThan(0);
  return { assessmentId: assessment!.id, versionId: versionItems[0].id };
}

async function collectEligibleCases(
  request: APIRequestContext,
  apiBase: string,
  headers: AuthSession["headers"],
  assessmentId: string,
  minCases: number,
): Promise<EligibleCase[]> {
  const subs = await request.get(
    `${apiBase}/api/v1/submissions?assessment_id=${assessmentId}`,
    { headers },
  );
  expect(subs.ok(), await subs.text()).toBeTruthy();
  const submissions = (await subs.json()) as { id: string; workflow_state?: string }[];
  expect(submissions.length).toBeGreaterThanOrEqual(20);

  const cases: EligibleCase[] = [];
  for (const sub of submissions) {
    const pub = await request.get(
      `${apiBase}/api/v1/submissions/${sub.id}/published-result`,
      { headers },
    );
    if (!pub.ok()) continue;
    const published = (await pub.json()) as {
      id: string;
      status: string;
      ledger_snapshot_hash: string;
    };
    if (published.status !== "PUBLISHED") continue;

    const evalResp = await request.get(
      `${apiBase}/api/v1/submissions/${sub.id}/evaluation`,
      { headers },
    );
    if (!evalResp.ok()) continue;
    const evalBody = (await evalResp.json()) as {
      question_evaluations?: {
        id: string;
        workflow_state: string;
        final_human_approved_score: number | string | null;
      }[];
    };
    for (const qe of evalBody.question_evaluations ?? []) {
      if (
        !["ACCEPTED", "OVERRIDDEN"].includes(qe.workflow_state) ||
        qe.final_human_approved_score == null
      ) {
        continue;
      }
      cases.push({
        published_result_id: published.id,
        question_evaluation_id: qe.id,
        reference_score: Number(qe.final_human_approved_score),
        submission_id: sub.id,
        ledger_snapshot_hash: published.ledger_snapshot_hash,
        published_status: published.status,
        qe_score: qe.final_human_approved_score,
        qe_workflow_state: qe.workflow_state,
      });
    }
    if (cases.length >= Math.max(minCases, 20)) break;
  }
  expect(
    cases.length,
    `Need ≥${minCases} eligible QE pairs from seeded cohort`,
  ).toBeGreaterThanOrEqual(minCases);
  return cases;
}

test.describe("B17 real quality psychometrics + calibration", () => {
  test("deterministic ≥20 psychometrics + ≥10-case calibration (no skip)", async ({
    page,
    request,
  }) => {
    const apiBase =
      process.env.API_UPSTREAM_URL ??
      process.env.E2E_API_BASE_URL ??
      "http://127.0.0.1:18000";

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

    const { assessmentId, versionId } = await resolveB17Assessment(
      request,
      apiBase,
      admin.headers,
    );
    const eligible = await collectEligibleCases(
      request,
      apiBase,
      admin.headers,
      assessmentId,
      20,
    );

    // --- Psychometrics: must COMPLETE with ≥20 ---
    const psych = await request.post(
      `${apiBase}/api/v1/quality/psychometrics/runs`,
      {
        headers: admin.headers,
        data: { assessment_version_id: versionId },
      },
    );
    expect(psych.ok(), await psych.text()).toBeTruthy();
    const psychBody = (await psych.json()) as {
      id: string;
      status: string;
      min_cohort_size: number;
      source_result_count: number;
      algorithm_version: string;
    };
    expect(psychBody.status).toBe("COMPLETED");
    expect(psychBody.source_result_count).toBeGreaterThanOrEqual(20);
    expect(psychBody.min_cohort_size).toBe(20);
    expect(psychBody.algorithm_version).toBe("B17_PSYCHOMETRICS_V1");

    const itemsResp = await request.get(
      `${apiBase}/api/v1/quality/psychometrics/runs/${psychBody.id}/items`,
      { headers: admin.headers },
    );
    expect(itemsResp.ok(), await itemsResp.text()).toBeTruthy();
    const metrics = (
      (await itemsResp.json()) as {
        items: {
          difficulty_index: number | null;
          discrimination_index: number | null;
          discrimination_status: string;
          discrimination_method: string;
        }[];
      }
    ).items;
    expect(metrics.length).toBeGreaterThan(0);
    for (const m of metrics) {
      expect(m.difficulty_index).not.toBeNull();
      expect(m.discrimination_method).toBe("CORRECTED_ITEM_TOTAL_PEARSON_V1");
    }
    expect(
      metrics.some(
        (m) =>
          m.discrimination_status === "OK" &&
          m.discrimination_index != null &&
          Number.isFinite(Number(m.discrimination_index)),
      ),
    ).toBeTruthy();

    const psychAgain = await request.post(
      `${apiBase}/api/v1/quality/psychometrics/runs`,
      {
        headers: admin.headers,
        data: { assessment_version_id: versionId },
      },
    );
    expect(psychAgain.ok(), await psychAgain.text()).toBeTruthy();
    expect(((await psychAgain.json()) as { id: string }).id).toBe(psychBody.id);

    // --- Ledger snapshot before calibration ---
    const ledgerBefore = eligible.slice(0, 10).map((c) => ({
      submission_id: c.submission_id,
      published_result_id: c.published_result_id,
      ledger_snapshot_hash: c.ledger_snapshot_hash,
      published_status: c.published_status,
      qe_id: c.question_evaluation_id,
      qe_score: c.qe_score,
      qe_workflow_state: c.qe_workflow_state,
    }));

    // --- Calibration: DRAFT → 10 cases → 2 participants → ACTIVE ---
    const cal = await request.post(
      `${apiBase}/api/v1/quality/calibration/sessions`,
      {
        headers: admin.headers,
        data: {
          assessment_version_id: versionId,
          title: `B17.1 E2E ${Date.now()}`,
          min_cases: 10,
        },
      },
    );
    expect(cal.ok(), await cal.text()).toBeTruthy();
    const session = (await cal.json()) as { id: string; status: string };
    expect(session.status).toBe("DRAFT");

    const caseRefs: { id: string; reference_score: number }[] = [];
    for (const src of eligible.slice(0, 10)) {
      const added = await request.post(
        `${apiBase}/api/v1/quality/calibration/sessions/${session.id}/cases`,
        {
          headers: admin.headers,
          data: {
            published_result_id: src.published_result_id,
            question_evaluation_id: src.question_evaluation_id,
          },
        },
      );
      expect(added.ok(), await added.text()).toBeTruthy();
      const body = (await added.json()) as {
        id: string;
        reference_score: number | string;
      };
      caseRefs.push({
        id: body.id,
        reference_score: Number(body.reference_score),
      });
    }

    for (const userId of [evalA.userId, evalB.userId]) {
      const part = await request.post(
        `${apiBase}/api/v1/quality/calibration/sessions/${session.id}/participants`,
        {
          headers: admin.headers,
          data: { user_id: userId },
        },
      );
      expect(part.ok(), await part.text()).toBeTruthy();
    }

    const activated = await request.post(
      `${apiBase}/api/v1/quality/calibration/sessions/${session.id}/activate`,
      { headers: admin.headers },
    );
    expect(activated.ok(), await activated.text()).toBeTruthy();
    expect(((await activated.json()) as { status: string }).status).toBe("ACTIVE");

    // Post-activation freezes: case + participant adds → 409
    const extraCase = eligible[10] ?? eligible[0];
    const blockedCase = await request.post(
      `${apiBase}/api/v1/quality/calibration/sessions/${session.id}/cases`,
      {
        headers: admin.headers,
        data: {
          published_result_id: extraCase.published_result_id,
          question_evaluation_id: extraCase.question_evaluation_id,
        },
      },
    );
    expect(blockedCase.status()).toBe(409);
    expect(detailCode(await blockedCase.json())).toBe(
      "CALIBRATION_SESSION_NOT_DRAFT",
    );

    const blockedPart = await request.post(
      `${apiBase}/api/v1/quality/calibration/sessions/${session.id}/participants`,
      {
        headers: admin.headers,
        data: { user_id: moderator.userId },
      },
    );
    expect(blockedPart.status()).toBe(409);
    expect(detailCode(await blockedPart.json())).toBe(
      "CALIBRATION_SESSION_NOT_DRAFT",
    );

    // Blind fetch: no protected identity/reference fields
    const blind = await request.get(
      `${apiBase}/api/v1/quality/calibration/sessions/${session.id}/cases/${caseRefs[0].id}/blind`,
      { headers: evalA.headers },
    );
    expect(blind.ok(), await blind.text()).toBeTruthy();
    const blindBody = (await blind.json()) as Record<string, unknown>;
    expect(blindBody).not.toHaveProperty("reference_score");
    expect(blindBody).not.toHaveProperty("student_id");
    expect(blindBody).not.toHaveProperty("published_result_id");
    expect(blindBody).not.toHaveProperty("question_evaluation_id");
    expect(blindBody).not.toHaveProperty("submission_id");
    const evidence = (blindBody.evidence_snapshot ?? {}) as Record<string, unknown>;
    for (const key of [
      "student_id",
      "reviewed_by",
      "source_evaluator_id",
      "submission_id",
      "published_result_id",
      "question_evaluation_id",
      "reference_score",
    ]) {
      expect(evidence).not.toHaveProperty(key);
    }

    // Both evaluators submit reference-equivalent scores on all 10 cases
    for (const c of caseRefs) {
      for (const h of [evalA.headers, evalB.headers]) {
        const resp = await request.post(
          `${apiBase}/api/v1/quality/calibration/sessions/${session.id}/cases/${c.id}/responses`,
          {
            headers: h,
            data: { score: c.reference_score },
          },
        );
        expect(resp.ok(), await resp.text()).toBeTruthy();
      }
    }

    const closed = await request.post(
      `${apiBase}/api/v1/quality/calibration/sessions/${session.id}/close`,
      { headers: admin.headers },
    );
    expect(closed.ok(), await closed.text()).toBeTruthy();
    expect(((await closed.json()) as { status: string }).status).toBe("CLOSED");

    const metricsResp = await request.get(
      `${apiBase}/api/v1/quality/calibration/sessions/${session.id}/metrics`,
      { headers: admin.headers },
    );
    expect(metricsResp.ok(), await metricsResp.text()).toBeTruthy();
    const icc = (
      (await metricsResp.json()) as {
        items: {
          metric_name: string;
          status: string;
          evaluator_count: number;
          common_case_count: number;
          icc_value: number | null;
        }[];
      }
    ).items[0];
    expect(icc.metric_name).toBe("ICC_A1");
    expect(icc.status).toBe("COMPLETED");
    expect(icc.evaluator_count).toBeGreaterThanOrEqual(2);
    expect(icc.common_case_count).toBeGreaterThanOrEqual(10);
    expect(icc.icc_value).not.toBeNull();
    expect(Number(icc.icc_value)).toBeGreaterThan(0.99);

    const evalMetrics = await request.get(
      `${apiBase}/api/v1/quality/calibration/sessions/${session.id}/evaluator-metrics`,
      { headers: admin.headers },
    );
    expect(evalMetrics.ok(), await evalMetrics.text()).toBeTruthy();
    const evalRows = (
      (await evalMetrics.json()) as {
        items: {
          mean_signed_diff: number;
          mae: number;
          exact_match_rate: number;
        }[];
      }
    ).items;
    expect(evalRows.length).toBeGreaterThanOrEqual(2);
    for (const row of evalRows) {
      expect(Math.abs(Number(row.mean_signed_diff))).toBeLessThan(0.01);
      expect(Math.abs(Number(row.mae))).toBeLessThan(0.01);
      expect(Number(row.exact_match_rate)).toBe(1);
    }

    // Immutability after close
    const postCloseResp = await request.post(
      `${apiBase}/api/v1/quality/calibration/sessions/${session.id}/cases/${caseRefs[0].id}/responses`,
      {
        headers: evalA.headers,
        data: { score: 0 },
      },
    );
    expect(postCloseResp.status()).toBe(409);

    const postClosePart = await request.post(
      `${apiBase}/api/v1/quality/calibration/sessions/${session.id}/participants`,
      {
        headers: admin.headers,
        data: { user_id: moderator.userId },
      },
    );
    expect(postClosePart.status()).toBe(409);

    // Ledger isolation: published + QE unchanged
    for (const snap of ledgerBefore) {
      const pub = await request.get(
        `${apiBase}/api/v1/submissions/${snap.submission_id}/published-result`,
        { headers: admin.headers },
      );
      expect(pub.ok()).toBeTruthy();
      const published = (await pub.json()) as {
        id: string;
        status: string;
        ledger_snapshot_hash: string;
      };
      expect(published.id).toBe(snap.published_result_id);
      expect(published.status).toBe(snap.published_status);
      expect(published.ledger_snapshot_hash).toBe(snap.ledger_snapshot_hash);

      const evalResp = await request.get(
        `${apiBase}/api/v1/submissions/${snap.submission_id}/evaluation`,
        { headers: admin.headers },
      );
      expect(evalResp.ok()).toBeTruthy();
      const qes = (
        (await evalResp.json()) as {
          question_evaluations: {
            id: string;
            final_human_approved_score: number | string | null;
            workflow_state: string;
          }[];
        }
      ).question_evaluations;
      const qe = qes.find((q) => q.id === snap.qe_id);
      expect(qe).toBeTruthy();
      expect(String(qe!.final_human_approved_score)).toBe(String(snap.qe_score));
      expect(qe!.workflow_state).toBe(snap.qe_workflow_state);
    }

    // UI renders real workspaces with seeded data
    await loginUi(page);
    await page.goto("/quality/psychometrics");
    await expect(page.getByTestId("b17-psychometrics-workspace")).toBeVisible({
      timeout: 30_000,
    });
    await page.getByTestId("b17-psychometrics-version-input").fill(versionId);
    await expect(page.getByTestId("b17-psychometrics-run-list")).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByTestId("b17-psychometrics-run-status").first()).toHaveText(
      "COMPLETED",
      { timeout: 30_000 },
    );

    await page.goto("/quality/calibration");
    await expect(page.getByTestId("b17-calibration-workspace")).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByTestId("b17-calibration-session-status").first()).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByText(/B17\.1 E2E/).first()).toBeVisible({
      timeout: 30_000,
    });
  });
});
