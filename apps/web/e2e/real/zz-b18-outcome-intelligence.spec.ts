/**
 * B18.1 real-stack acceptance — clustering reproducibility + CO/PO mapping invariants.
 *
 * Requires CI seed: `python -m app.cli.seed_b18_e2e_outcome_intelligence` after seed_dev.
 * Assessment code B18-E2E-OUTCOME with >=20 current PUBLISHED human-final results.
 * Isolation tenant: b18-iso / admin@b18-iso.eduvijna.local
 *
 * Never skip. Never conditionally bypass.
 */

import { test, expect, type APIRequestContext, type Page } from "@playwright/test";

const ADMIN_EMAIL = "admin@demo.eduvijna.local";
const ADMIN_PASSWORD = "DemoAdmin!2026";
const ISO_ADMIN_EMAIL = "admin@b18-iso.eduvijna.local";
const ISO_TENANT_SLUG = "b18-iso";

const B18_ASSESSMENT_CODE = "B18-E2E-OUTCOME";

/** Seed: PATTERN_A ×10 + PATTERN_B ×10 → exactly two clusters of 10 under COSINE_GRAPH_V1 @ 0.75. */
const EXPECTED_CLUSTER_COUNT = 2;
const EXPECTED_MEMBER_COUNTS = [10, 10];

type AuthSession = {
  token: string;
  userId: string;
  headers: { Authorization: string };
};

type Metric = {
  outcome_definition_id: string;
  outcome_code?: string;
  weighted_earned: number;
  weighted_max: number;
  attainment_pct: number | null;
  denom_status: string;
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
  tenantSlug = "demo",
): Promise<AuthSession> {
  const login = await request.post(`${apiBase}/api/v1/auth/login`, {
    data: { email, password, tenant_slug: tenantSlug },
  });
  expect(
    login.ok(),
    `login failed for ${email}@${tenantSlug}: ${await login.text()}`,
  ).toBeTruthy();
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

async function resolveB18Assessment(
  request: APIRequestContext,
  apiBase: string,
  headers: AuthSession["headers"],
): Promise<{
  assessmentId: string;
  versionId: string;
  questionIdQ1: string;
  questionIdQ2: string;
}> {
  const assessments = await request.get(`${apiBase}/api/v1/assessments`, {
    headers,
  });
  expect(assessments.ok()).toBeTruthy();
  const items = (await assessments.json()) as {
    items?: Array<{ id: string; code: string }>;
  } & Array<{ id: string; code: string }>;
  const list = Array.isArray(items) ? items : (items.items ?? []);
  const assessment = list.find((a) => a.code === B18_ASSESSMENT_CODE);
  expect(
    assessment,
    "B18-E2E-OUTCOME assessment missing — run seed_b18",
  ).toBeTruthy();
  const versions = await request.get(
    `${apiBase}/api/v1/assessments/${assessment!.id}/versions`,
    { headers },
  );
  expect(versions.ok()).toBeTruthy();
  const vBody = (await versions.json()) as {
    items?: Array<{ id: string; version_number: number }>;
  } & Array<{ id: string; version_number: number }>;
  const vList = Array.isArray(vBody) ? vBody : (vBody.items ?? []);
  const version = vList.sort((a, b) => a.version_number - b.version_number)[0];
  expect(version).toBeTruthy();

  const questions = await request.get(
    `${apiBase}/api/v1/assessment-versions/${version!.id}/questions`,
    { headers },
  );
  expect(questions.ok(), await questions.text()).toBeTruthy();
  const qBody = (await questions.json()) as {
    items?: Array<{ id: string; question_id: string; display_label?: string }>;
  } & Array<{ id: string; question_id: string; display_label?: string }>;
  const qList = Array.isArray(qBody) ? qBody : (qBody.items ?? []);
  const q1 = qList.find((q) => q.display_label === "1") ?? qList[0];
  const q2 = qList.find((q) => q.display_label === "2") ?? qList[1];
  expect(q1).toBeTruthy();
  expect(q2).toBeTruthy();

  return {
    assessmentId: assessment!.id,
    versionId: version!.id,
    questionIdQ1: q1!.question_id,
    questionIdQ2: q2!.question_id,
  };
}

async function reviewAndFinalize(
  request: APIRequestContext,
  apiBase: string,
  admin: AuthSession,
  submissionId: string,
  scoresByQuestionId: Record<string, number>,
): Promise<string> {
  let workflow = "";
  await expect
    .poll(
      async () => {
        const ws = await request.get(
          `${apiBase}/api/v1/submissions/${submissionId}/evaluation`,
          { headers: admin.headers },
        );
        if (!ws.ok()) return `ws:${ws.status()}`;
        const body = (await ws.json()) as {
          question_evaluations?: Array<{
            id: string;
            question_id: string;
            workflow_state: string;
            proposed_ai_score: number | null;
          }>;
        };
        for (const qe of body.question_evaluations ?? []) {
          if (
            qe.workflow_state === "ACCEPTED" ||
            qe.workflow_state === "OVERRIDDEN"
          ) {
            continue;
          }
          const score = scoresByQuestionId[qe.question_id] ?? 0;
          const over = await request.post(
            `${apiBase}/api/v1/question-evaluations/${qe.id}/override`,
            {
              headers: admin.headers,
              data: {
                score,
                reason: "B18.1 grievance re-evaluation override",
              },
            },
          );
          if (![200, 409].includes(over.status())) {
            return `override:${over.status()}:${await over.text()}`;
          }
        }
        const fin = await request.post(
          `${apiBase}/api/v1/submissions/${submissionId}/evaluation/finalize`,
          { headers: admin.headers },
        );
        if (!fin.ok()) return `fin:${fin.status()}:${await fin.text()}`;
        workflow =
          ((await fin.json()) as { workflow_state?: string }).workflow_state ??
          "";
        return workflow;
      },
      { timeout: 180_000 },
    )
    .toMatch(/APPROVED|MODERATION_REVIEW/);
  return workflow;
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

function assertMetric(
  metrics: Metric[],
  outcomeId: string,
  expected: {
    earned: number;
    max: number;
    pct: number;
    denom?: string;
  },
) {
  const m = metrics.find((x) => x.outcome_definition_id === outcomeId);
  expect(m, `metric missing for outcome ${outcomeId}`).toBeTruthy();
  expect(Number(m!.weighted_earned)).toBe(expected.earned);
  expect(Number(m!.weighted_max)).toBe(expected.max);
  expect(Number(m!.attainment_pct)).toBe(expected.pct);
  expect(m!.denom_status).toBe(expected.denom ?? "OK");
}

test.describe("B18.1 outcome intelligence acceptance (real)", () => {
  test("full lifecycle: clusters, mapping invariants, grievance V2, isolation", async ({
    page,
    request,
  }) => {
    test.setTimeout(600_000);
    const apiBase =
      process.env.E2E_API_BASE_URL?.replace(/\/$/, "") ||
      "http://127.0.0.1:18000";

    const admin = await loginApi(request, apiBase, ADMIN_EMAIL, ADMIN_PASSWORD);
    const isoAdmin = await loginApi(
      request,
      apiBase,
      ISO_ADMIN_EMAIL,
      ADMIN_PASSWORD,
      ISO_TENANT_SLUG,
    );
    const { versionId, questionIdQ1, questionIdQ2 } = await resolveB18Assessment(
      request,
      apiBase,
      admin.headers,
    );

    // ========== C1: Deterministic clustering ==========
    const clusterBody = {
      assessment_version_id: versionId,
      question_id: questionIdQ1,
      similarity_threshold: 0.75,
    };
    const clusterRun = await request.post(
      `${apiBase}/api/v1/quality/answer-clusters/runs`,
      { headers: admin.headers, data: clusterBody },
    );
    expect(clusterRun.ok(), await clusterRun.text()).toBeTruthy();
    const runV1 = (await clusterRun.json()) as {
      id: string;
      status: string;
      algorithm_version: string;
      cluster_count: number;
      source_result_count: number;
      source_set_hash: string;
      source_published_result_ids: string[];
      embedding_provider: string;
      embedding_model: string;
      embedding_model_version: string;
      similarity_threshold: number;
    };
    expect(runV1.status).toBe("COMPLETED");
    expect(runV1.algorithm_version).toBe("COSINE_GRAPH_V1");
    expect(runV1.source_result_count).toBe(20);
    expect(runV1.source_published_result_ids.length).toBe(20);
    expect(runV1.embedding_provider).toBe("fixed");
    expect(runV1.cluster_count).toBe(EXPECTED_CLUSTER_COUNT);
    expect(Number(runV1.similarity_threshold)).toBe(0.75);

    const clusterRun2 = await request.post(
      `${apiBase}/api/v1/quality/answer-clusters/runs`,
      { headers: admin.headers, data: clusterBody },
    );
    expect(clusterRun2.ok()).toBeTruthy();
    const runV1Again = (await clusterRun2.json()) as {
      id: string;
      source_set_hash: string;
      source_published_result_ids: string[];
    };
    expect(runV1Again.id).toBe(runV1.id);
    expect(runV1Again.source_set_hash).toBe(runV1.source_set_hash);

    const clustersResp = await request.get(
      `${apiBase}/api/v1/quality/answer-clusters/runs/${runV1.id}/clusters`,
      { headers: admin.headers },
    );
    expect(clustersResp.ok()).toBeTruthy();
    const clusterItems = (
      (await clustersResp.json()) as {
        items: Array<{ id: string; member_count: number; cluster_index: number }>;
      }
    ).items;
    expect(clusterItems.length).toBe(EXPECTED_CLUSTER_COUNT);
    const memberCounts = clusterItems
      .map((c) => c.member_count)
      .sort((a, b) => a - b);
    expect(memberCounts).toEqual(EXPECTED_MEMBER_COUNTS);

    const memberships: string[][] = [];
    for (const c of clusterItems) {
      const detail = await request.get(
        `${apiBase}/api/v1/quality/answer-clusters/clusters/${c.id}`,
        { headers: admin.headers },
      );
      expect(detail.ok()).toBeTruthy();
      const members = (
        (await detail.json()) as {
          members: Array<{
            question_evaluation_id: string;
            published_result_id: string;
            submission_id: string;
            final_human_approved_score: number | null;
          }>;
        }
      ).members;
      expect(members.length).toBe(c.member_count);
      memberships.push(
        members.map((m) => m.question_evaluation_id).sort(),
      );
    }
    // Idempotent re-fetch same membership
    const clustersResp2 = await request.get(
      `${apiBase}/api/v1/quality/answer-clusters/runs/${runV1Again.id}/clusters`,
      { headers: admin.headers },
    );
    const clusterItems2 = (
      (await clustersResp2.json()) as {
        items: Array<{ id: string; member_count: number }>;
      }
    ).items;
    const memberships2: string[][] = [];
    for (const c of clusterItems2) {
      const detail = await request.get(
        `${apiBase}/api/v1/quality/answer-clusters/clusters/${c.id}`,
        { headers: admin.headers },
      );
      const members = (
        (await detail.json()) as {
          members: Array<{ question_evaluation_id: string }>;
        }
      ).members;
      memberships2.push(
        members.map((m) => m.question_evaluation_id).sort(),
      );
    }
    expect(memberships2.map((m) => m.join(",")).sort()).toEqual(
      memberships.map((m) => m.join(",")).sort(),
    );

    // ========== C2: Advisory review non-mutation ==========
    const targetCluster = clusterItems[0];
    const detailBefore = await request.get(
      `${apiBase}/api/v1/quality/answer-clusters/clusters/${targetCluster.id}`,
      { headers: admin.headers },
    );
    const membersBefore = (
      (await detailBefore.json()) as {
        members: Array<{
          question_evaluation_id: string;
          published_result_id: string;
          submission_id: string;
          final_human_approved_score: number | null;
        }>;
      }
    ).members;
    const targetMember = membersBefore[0];
    const qeId = targetMember.question_evaluation_id;
    const submissionId = targetMember.submission_id;
    const v1PublishedResultId = targetMember.published_result_id;

    const qeBefore = await request.get(
      `${apiBase}/api/v1/question-evaluations/${qeId}`,
      { headers: admin.headers },
    );
    expect(qeBefore.ok(), await qeBefore.text()).toBeTruthy();
    const qeSnap = (await qeBefore.json()) as {
      final_human_approved_score: number | null;
      workflow_state: string;
      ledger_version: number;
      approved_snapshot_hash: string | null;
      rubric_version_id: string;
      reviewed_by: string | null;
    };

    const pubBefore = await request.get(
      `${apiBase}/api/v1/submissions/${submissionId}/publication`,
      { headers: admin.headers },
    );
    expect(pubBefore.ok(), await pubBefore.text()).toBeTruthy();
    const pubSnap = (
      (await pubBefore.json()) as {
        latest: {
          id: string;
          status: string;
          version_number: number;
          ledger_snapshot_hash: string | null;
        };
      }
    ).latest;
    expect(pubSnap.id).toBe(v1PublishedResultId);

    const rubBefore = await request.get(
      `${apiBase}/api/v1/rubric-versions/${qeSnap.rubric_version_id}/criteria`,
      { headers: admin.headers },
    );
    expect(rubBefore.ok(), await rubBefore.text()).toBeTruthy();
    const rubSnap = JSON.stringify(await rubBefore.json());

    const evalWsBefore = await request.get(
      `${apiBase}/api/v1/submissions/${submissionId}/evaluation`,
      { headers: admin.headers },
    );
    expect(evalWsBefore.ok()).toBeTruthy();
    const evalBefore = (await evalWsBefore.json()) as {
      evaluation_run?: { id: string; status: string };
      question_evaluations?: Array<{ id: string; workflow_state: string }>;
    };
    const reviewActionFingerprintBefore = JSON.stringify(
      (evalBefore.question_evaluations ?? [])
        .map((q) => `${q.id}:${q.workflow_state}`)
        .sort(),
    );

    const review = await request.post(
      `${apiBase}/api/v1/quality/answer-clusters/clusters/${targetCluster.id}/reviews`,
      {
        headers: admin.headers,
        data: {
          observation: "B18.1 advisory observation — must not mutate ledger",
          suggested_rubric_refinement: "Clarify photosynthesis vs respiration",
        },
      },
    );
    expect(review.ok(), await review.text()).toBeTruthy();
    expect(((await review.json()) as { id: string }).id).toBeTruthy();

    const qeAfter = await request.get(
      `${apiBase}/api/v1/question-evaluations/${qeId}`,
      { headers: admin.headers },
    );
    expect(qeAfter.ok()).toBeTruthy();
    const qeAfterBody = (await qeAfter.json()) as typeof qeSnap;
    expect(qeAfterBody.final_human_approved_score).toBe(
      qeSnap.final_human_approved_score,
    );
    expect(qeAfterBody.workflow_state).toBe(qeSnap.workflow_state);
    expect(qeAfterBody.ledger_version).toBe(qeSnap.ledger_version);
    expect(qeAfterBody.approved_snapshot_hash).toBe(qeSnap.approved_snapshot_hash);
    expect(qeAfterBody.rubric_version_id).toBe(qeSnap.rubric_version_id);
    expect(qeAfterBody.reviewed_by).toBe(qeSnap.reviewed_by);

    const pubAfter = await request.get(
      `${apiBase}/api/v1/submissions/${submissionId}/publication`,
      { headers: admin.headers },
    );
    const pubAfterBody = (
      (await pubAfter.json()) as {
        latest: {
          id: string;
          status: string;
          version_number: number;
          ledger_snapshot_hash: string | null;
        };
      }
    ).latest;
    expect(pubAfterBody.id).toBe(pubSnap.id);
    expect(pubAfterBody.status).toBe(pubSnap.status);
    expect(pubAfterBody.version_number).toBe(pubSnap.version_number);
    expect(pubAfterBody.ledger_snapshot_hash).toBe(pubSnap.ledger_snapshot_hash);

    const rubAfter = await request.get(
      `${apiBase}/api/v1/rubric-versions/${qeSnap.rubric_version_id}/criteria`,
      { headers: admin.headers },
    );
    expect(JSON.stringify(await rubAfter.json())).toBe(rubSnap);

    const evalWsAfter = await request.get(
      `${apiBase}/api/v1/submissions/${submissionId}/evaluation`,
      { headers: admin.headers },
    );
    const evalAfter = (await evalWsAfter.json()) as typeof evalBefore;
    expect(evalAfter.evaluation_run?.id).toBe(evalBefore.evaluation_run?.id);
    expect(evalAfter.evaluation_run?.status).toBe(
      evalBefore.evaluation_run?.status,
    );
    const reviewActionFingerprintAfter = JSON.stringify(
      (evalAfter.question_evaluations ?? [])
        .map((q) => `${q.id}:${q.workflow_state}`)
        .sort(),
    );
    expect(reviewActionFingerprintAfter).toBe(reviewActionFingerprintBefore);

    // ========== C3: Two COs + two POs with exact marks-weighted math ==========
    // Seed scores: Q1 = 4×10 + 2×10; Q2 = 3×20; max_mark = 5 each.
    // Mappings:
    //   CO1 → Q1 w=1.0  → earned 60, max 100, pct 60
    //   CO2 → Q2 w=0.5  → earned 30, max 50,  pct 60
    //   PO1 → Q1 w=0.25 → earned 15, max 25,  pct 60
    //   PO2 → Q2 w=1.0  → earned 60, max 100, pct 60
    const stamp = Date.now().toString(36);
    const defIds: Record<string, string> = {};
    for (const [type, code, title] of [
      ["CO", `CO1-${stamp}`, "B18.1 Course Outcome 1"],
      ["CO", `CO2-${stamp}`, "B18.1 Course Outcome 2"],
      ["PO", `PO1-${stamp}`, "B18.1 Program Outcome 1"],
      ["PO", `PO2-${stamp}`, "B18.1 Program Outcome 2"],
    ] as const) {
      const created = await request.post(
        `${apiBase}/api/v1/outcomes/definitions`,
        {
          headers: admin.headers,
          data: { outcome_type: type, code, title },
        },
      );
      expect(created.ok(), await created.text()).toBeTruthy();
      defIds[code.split("-")[0]] = ((await created.json()) as { id: string }).id;
    }
    const co1Id = defIds.CO1;
    const co2Id = defIds.CO2;
    const po1Id = defIds.PO1;
    const po2Id = defIds.PO2;

    // ========== C4: Invalid mapping behavior ==========
    const retiredDef = await request.post(
      `${apiBase}/api/v1/outcomes/definitions`,
      {
        headers: admin.headers,
        data: {
          outcome_type: "CO",
          code: `CO-RET-${stamp}`,
          title: "Retired outcome",
        },
      },
    );
    expect(retiredDef.ok()).toBeTruthy();
    const retiredId = ((await retiredDef.json()) as { id: string }).id;
    const retireAttempt = await request.patch(
      `${apiBase}/api/v1/outcomes/definitions/${retiredId}`,
      { headers: admin.headers, data: { status: "RETIRED" } },
    );
    expect(retireAttempt.ok(), await retireAttempt.text()).toBeTruthy();

    const set1 = await request.post(`${apiBase}/api/v1/outcomes/mapping-sets`, {
      headers: admin.headers,
      data: { assessment_version_id: versionId, title: "B18.1 mapping v1" },
    });
    expect(set1.ok(), await set1.text()).toBeTruthy();
    const set1Body = (await set1.json()) as {
      id: string;
      status: string;
      version_number: number;
      activation_hash: string | null;
    };
    expect(set1Body.status).toBe("DRAFT");
    expect(set1Body.activation_hash).toBeNull();

    const badWeight = await request.post(
      `${apiBase}/api/v1/outcomes/mapping-sets/${set1Body.id}/mappings`,
      {
        headers: admin.headers,
        data: {
          question_id: questionIdQ1,
          outcome_definition_id: co1Id,
          weight: 1.5,
        },
      },
    );
    expect([400, 422]).toContain(badWeight.status());
    if (badWeight.status() === 400) {
      expect(detailCode(await badWeight.json())).toBe("INVALID_WEIGHT");
    }

    const retiredMap = await request.post(
      `${apiBase}/api/v1/outcomes/mapping-sets/${set1Body.id}/mappings`,
      {
        headers: admin.headers,
        data: {
          question_id: questionIdQ1,
          outcome_definition_id: retiredId,
          weight: 0.5,
        },
      },
    );
    expect(retiredMap.status()).toBe(409);
    expect(detailCode(await retiredMap.json())).toBe("OUTCOME_NOT_ACTIVE");

    const mappingsToAdd: Array<{
      question_id: string;
      outcome_definition_id: string;
      weight: number;
    }> = [
      { question_id: questionIdQ1, outcome_definition_id: co1Id, weight: 1 },
      { question_id: questionIdQ2, outcome_definition_id: co2Id, weight: 0.5 },
      { question_id: questionIdQ1, outcome_definition_id: po1Id, weight: 0.25 },
      { question_id: questionIdQ2, outcome_definition_id: po2Id, weight: 1 },
    ];
    for (const m of mappingsToAdd) {
      const added = await request.post(
        `${apiBase}/api/v1/outcomes/mapping-sets/${set1Body.id}/mappings`,
        { headers: admin.headers, data: m },
      );
      expect(added.ok(), await added.text()).toBeTruthy();
    }

    const activate = await request.post(
      `${apiBase}/api/v1/outcomes/mapping-sets/${set1Body.id}/activate`,
      { headers: admin.headers },
    );
    expect(activate.ok(), await activate.text()).toBeTruthy();
    const activatedV1 = (await activate.json()) as {
      status: string;
      activation_hash: string;
      version_number: number;
    };
    expect(activatedV1.status).toBe("ACTIVE");
    expect(activatedV1.activation_hash).toBeTruthy();
    expect(activatedV1.activation_hash.length).toBe(64);
    const hashV1 = activatedV1.activation_hash;

    const blocked = await request.post(
      `${apiBase}/api/v1/outcomes/mapping-sets/${set1Body.id}/mappings`,
      {
        headers: admin.headers,
        data: {
          question_id: questionIdQ1,
          outcome_definition_id: co1Id,
          weight: 0.1,
        },
      },
    );
    expect(blocked.status()).toBe(409);
    expect(detailCode(await blocked.json())).toBe("MAPPING_SET_NOT_DRAFT");

    const set2 = await request.post(`${apiBase}/api/v1/outcomes/mapping-sets`, {
      headers: admin.headers,
      data: { assessment_version_id: versionId, title: "B18.1 mapping v2" },
    });
    expect(set2.ok()).toBeTruthy();
    const set2Body = (await set2.json()) as {
      id: string;
      version_number: number;
    };
    expect(set2Body.version_number).toBe(set1Body.version_number + 1);

    await request.post(
      `${apiBase}/api/v1/outcomes/mapping-sets/${set2Body.id}/mappings`,
      {
        headers: admin.headers,
        data: {
          question_id: questionIdQ1,
          outcome_definition_id: co1Id,
          weight: 1,
        },
      },
    );
    const activateV2 = await request.post(
      `${apiBase}/api/v1/outcomes/mapping-sets/${set2Body.id}/activate`,
      { headers: admin.headers },
    );
    expect(activateV2.ok(), await activateV2.text()).toBeTruthy();
    const activatedV2 = (await activateV2.json()) as {
      status: string;
      activation_hash: string;
    };
    expect(activatedV2.activation_hash).toBeTruthy();
    expect(activatedV2.activation_hash).not.toBe(hashV1);

    const v1After = await request.get(
      `${apiBase}/api/v1/outcomes/mapping-sets/${set1Body.id}`,
      { headers: admin.headers },
    );
    expect(v1After.ok()).toBeTruthy();
    const v1AfterBody = (await v1After.json()) as {
      status: string;
      activation_hash: string;
    };
    expect(v1AfterBody.status).toBe("RETIRED");
    expect(v1AfterBody.activation_hash).toBe(hashV1);

    const retiredEdit = await request.post(
      `${apiBase}/api/v1/outcomes/mapping-sets/${set1Body.id}/mappings`,
      {
        headers: admin.headers,
        data: {
          question_id: questionIdQ2,
          outcome_definition_id: po2Id,
          weight: 0.2,
        },
      },
    );
    expect(retiredEdit.status()).toBe(409);

    // Re-activate mapping v1 identity for attainment via recreating ACTIVE set that
    // matches the original math — v2 is ACTIVE with only CO1. Create v3 with full maps.
    const set3 = await request.post(`${apiBase}/api/v1/outcomes/mapping-sets`, {
      headers: admin.headers,
      data: {
        assessment_version_id: versionId,
        title: "B18.1 mapping v3 full math",
      },
    });
    expect(set3.ok()).toBeTruthy();
    const set3Body = (await set3.json()) as { id: string; version_number: number };
    for (const m of mappingsToAdd) {
      const added = await request.post(
        `${apiBase}/api/v1/outcomes/mapping-sets/${set3Body.id}/mappings`,
        { headers: admin.headers, data: m },
      );
      expect(added.ok(), await added.text()).toBeTruthy();
    }
    const activateV3 = await request.post(
      `${apiBase}/api/v1/outcomes/mapping-sets/${set3Body.id}/activate`,
      { headers: admin.headers },
    );
    expect(activateV3.ok(), await activateV3.text()).toBeTruthy();
    const activatedV3 = (await activateV3.json()) as {
      activation_hash: string;
      version_number: number;
    };
    const hashV3 = activatedV3.activation_hash;
    // Historical v1 hash still unchanged
    const v1Still = await request.get(
      `${apiBase}/api/v1/outcomes/mapping-sets/${set1Body.id}`,
      { headers: admin.headers },
    );
    expect(((await v1Still.json()) as { activation_hash: string }).activation_hash).toBe(
      hashV1,
    );

    const report = await request.post(
      `${apiBase}/api/v1/outcomes/attainment-reports`,
      {
        headers: admin.headers,
        data: {
          assessment_version_id: versionId,
          mapping_set_id: set3Body.id,
        },
      },
    );
    expect(report.ok(), await report.text()).toBeTruthy();
    const reportV1 = (await report.json()) as {
      id: string;
      status: string;
      algorithm_version: string;
      source_result_count: number;
      source_set_hash: string;
      source_published_result_ids: string[];
      mapping_set_id: string;
      mapping_set_version_number: number;
      mapping_activation_hash: string;
      metrics: Metric[];
    };
    expect(reportV1.status).toBe("COMPLETED");
    expect(reportV1.algorithm_version).toBe("MARKS_WEIGHTED_V1");
    expect(reportV1.source_result_count).toBe(20);
    expect(reportV1.mapping_set_id).toBe(set3Body.id);
    expect(reportV1.mapping_activation_hash).toBe(hashV3);
    expect(reportV1.metrics.length).toBe(4);
    assertMetric(reportV1.metrics, co1Id, { earned: 60, max: 100, pct: 60 });
    assertMetric(reportV1.metrics, co2Id, { earned: 30, max: 50, pct: 60 });
    assertMetric(reportV1.metrics, po1Id, { earned: 15, max: 25, pct: 60 });
    assertMetric(reportV1.metrics, po2Id, { earned: 60, max: 100, pct: 60 });

    // ========== C5: CSV ==========
    const csv = await request.get(
      `${apiBase}/api/v1/outcomes/attainment-reports/${reportV1.id}/export.csv`,
      { headers: admin.headers },
    );
    expect(csv.ok()).toBeTruthy();
    expect(csv.headers()["content-type"] || "").toContain("text/csv");
    const csvText = await csv.text();
    for (const col of [
      "report_id",
      "mapping_set_id",
      "mapping_set_version_number",
      "mapping_activation_hash",
      "outcome_code",
      "outcome_type",
      "weighted_earned",
      "weighted_max",
      "attainment_pct",
      "denom_status",
    ]) {
      expect(csvText, `csv missing column ${col}`).toContain(col);
    }
    expect(csvText).toContain(hashV3);
    expect(csvText).toContain(`CO1-${stamp}`);
    expect(csvText).toContain(`PO2-${stamp}`);
    expect(csvText).toContain("60");

    // ========== C6: Genuine cross-tenant isolation ==========
    const iso404 = async (method: "get" | "post", path: string, data?: object) => {
      const resp =
        method === "get"
          ? await request.get(`${apiBase}${path}`, { headers: isoAdmin.headers })
          : await request.post(`${apiBase}${path}`, {
              headers: isoAdmin.headers,
              data,
            });
      expect(resp.status(), `${method.toUpperCase()} ${path}`).toBe(404);
    };
    await iso404("get", `/api/v1/quality/answer-clusters/runs/${runV1.id}`);
    await iso404(
      "get",
      `/api/v1/quality/answer-clusters/clusters/${targetCluster.id}`,
    );
    await iso404(
      "post",
      `/api/v1/quality/answer-clusters/clusters/${targetCluster.id}/reviews`,
      { observation: "iso attempt" },
    );
    await iso404("get", `/api/v1/outcomes/definitions/${co1Id}`);
    await iso404("get", `/api/v1/outcomes/mapping-sets/${set3Body.id}`);
    await iso404("get", `/api/v1/outcomes/attainment-reports/${reportV1.id}`);
    await iso404(
      "get",
      `/api/v1/outcomes/attainment-reports/${reportV1.id}/export.csv`,
    );
    const isoDefs = await request.get(`${apiBase}/api/v1/outcomes/definitions`, {
      headers: isoAdmin.headers,
    });
    expect(isoDefs.ok()).toBeTruthy();
    const isoDefItems = (
      (await isoDefs.json()) as { items: Array<{ id: string }> }
    ).items;
    expect(isoDefItems.every((d) => d.id !== co1Id)).toBeTruthy();

    // ========== C7: Grievance V1 → RE_EVALUATION → V2 ==========
    const grievance = await request.post(
      `${apiBase}/api/v1/operations/grievances`,
      {
        headers: admin.headers,
        data: {
          published_result_id: v1PublishedResultId,
          requester_reference: "b18-1-e2e-parent",
          reason: "B18.1 formal recheck for superseded publication",
        },
      },
    );
    expect(grievance.ok(), await grievance.text()).toBeTruthy();
    const grievanceId = ((await grievance.json()) as { id: string }).id;

    const accepted = await request.post(
      `${apiBase}/api/v1/operations/grievances/${grievanceId}/accept`,
      {
        headers: admin.headers,
        data: { decision_reason: "Valid B18.1 recheck" },
      },
    );
    expect(accepted.ok(), await accepted.text()).toBeTruthy();
    const acceptBody = (await accepted.json()) as {
      status: string;
      reevaluation_run_id: string;
    };
    expect(acceptBody.status).toBe("RE_EVALUATING");
    expect(acceptBody.reevaluation_run_id).toBeTruthy();

    await expect
      .poll(
        async () => {
          const sub = await request.get(
            `${apiBase}/api/v1/submissions/${submissionId}`,
            { headers: admin.headers },
          );
          if (!sub.ok()) return `sub:${sub.status()}`;
          return ((await sub.json()) as { workflow_state: string }).workflow_state;
        },
        { timeout: 60_000 },
      )
      .toMatch(/EVALUATION_REVIEW/);

    const reWs = await request.get(
      `${apiBase}/api/v1/submissions/${submissionId}/evaluation`,
      { headers: admin.headers },
    );
    expect(reWs.ok()).toBeTruthy();
    const reBody = (await reWs.json()) as {
      evaluation_run?: {
        id: string;
        run_kind?: string;
        supersedes_run_id?: string;
      };
      question_evaluations?: Array<{
        id: string;
        question_id: string;
        final_human_approved_score: number | null;
        reviewed_by: string | null;
        approved_snapshot_hash: string | null;
      }>;
    };
    expect(reBody.evaluation_run?.id).toBe(acceptBody.reevaluation_run_id);
    expect(reBody.evaluation_run?.run_kind).toBe("RE_EVALUATION");
    const freshQes = reBody.question_evaluations ?? [];
    expect(freshQes.length).toBeGreaterThanOrEqual(2);
    for (const qe of freshQes) {
      expect(qe.final_human_approved_score ?? null).toBeNull();
      expect(qe.reviewed_by ?? null).toBeNull();
      expect(qe.approved_snapshot_hash ?? null).toBeNull();
    }

    // V2 scores: bump Q1 to 5 (from pattern-group dependent original), keep Q2=3
    // → CO1 earned becomes 61 (was 60) if this member was score-4, or 63 if was score-2.
    const originalQ1Score = Number(qeSnap.final_human_approved_score);
    const v2Q1Score = 5;
    const workflow = await reviewAndFinalize(
      request,
      apiBase,
      admin,
      submissionId,
      {
        [questionIdQ1]: v2Q1Score,
        [questionIdQ2]: 3,
      },
    );
    if (workflow === "MODERATION_REVIEW") {
      // No moderation policy on B18 seed — should not happen; fail loudly if it does.
      throw new Error(
        "Unexpected MODERATION_REVIEW for B18 seed assessment without policy",
      );
    }
    expect(workflow).toBe("APPROVED");

    const v2PublishedResultId = await publishResult(
      request,
      apiBase,
      admin,
      submissionId,
    );

    const pubWs = await request.get(
      `${apiBase}/api/v1/submissions/${submissionId}/publication`,
      { headers: admin.headers },
    );
    expect(pubWs.ok()).toBeTruthy();
    const latest = (
      (await pubWs.json()) as {
        latest: {
          id: string;
          status: string;
          supersedes_result_id?: string | null;
        };
      }
    ).latest;
    expect(latest.id).toBe(v2PublishedResultId);
    expect(latest.status).toBe("PUBLISHED");
    expect(latest.supersedes_result_id).toBe(v1PublishedResultId);

    const v1Pub = await request.get(
      `${apiBase}/api/v1/submissions/${submissionId}/publication`,
      { headers: admin.headers },
    );
    expect(v1Pub.ok()).toBeTruthy();
    const pubHistory = (await v1Pub.json()) as {
      latest: { id: string; status: string; supersedes_result_id?: string | null };
      versions: Array<{ id: string; status: string }>;
    };
    const v1Row = pubHistory.versions.find((r) => r.id === v1PublishedResultId);
    expect(v1Row?.status).toBe("SUPERSEDED");

    // ========== C8: Re-cluster after V2 ==========
    const histBefore = await request.get(
      `${apiBase}/api/v1/quality/answer-clusters/runs/${runV1.id}`,
      { headers: admin.headers },
    );
    const histSnap = (await histBefore.json()) as {
      id: string;
      source_set_hash: string;
      source_result_count: number;
      source_published_result_ids: string[];
      cluster_count: number;
    };

    const clusterRunNew = await request.post(
      `${apiBase}/api/v1/quality/answer-clusters/runs`,
      { headers: admin.headers, data: clusterBody },
    );
    expect(clusterRunNew.ok(), await clusterRunNew.text()).toBeTruthy();
    const runNew = (await clusterRunNew.json()) as {
      id: string;
      source_set_hash: string;
      source_result_count: number;
      source_published_result_ids: string[];
      cluster_count: number;
    };
    expect(runNew.id).not.toBe(runV1.id);
    expect(runNew.source_set_hash).not.toBe(runV1.source_set_hash);
    expect(runNew.source_result_count).toBe(20);
    expect(runNew.source_published_result_ids).toContain(v2PublishedResultId);
    expect(runNew.source_published_result_ids).not.toContain(v1PublishedResultId);
    // No double-count of V1+V2
    expect(
      new Set(runNew.source_published_result_ids).size,
    ).toBe(runNew.source_result_count);

    const histAfter = await request.get(
      `${apiBase}/api/v1/quality/answer-clusters/runs/${runV1.id}`,
      { headers: admin.headers },
    );
    const histAfterBody = (await histAfter.json()) as typeof histSnap;
    expect(histAfterBody.source_set_hash).toBe(histSnap.source_set_hash);
    expect(histAfterBody.source_result_count).toBe(histSnap.source_result_count);
    expect(histAfterBody.source_published_result_ids).toEqual(
      histSnap.source_published_result_ids,
    );
    expect(histAfterBody.source_published_result_ids).toContain(
      v1PublishedResultId,
    );
    expect(histAfterBody.cluster_count).toBe(histSnap.cluster_count);

    const clusterRunNew2 = await request.post(
      `${apiBase}/api/v1/quality/answer-clusters/runs`,
      { headers: admin.headers, data: clusterBody },
    );
    expect(((await clusterRunNew2.json()) as { id: string }).id).toBe(runNew.id);

    // ========== C9: Re-run attainment after V2 ==========
    // Expected CO1 after V2: original 60 + (v2Q1Score - originalQ1Score) * weight 1
    const expectedCo1Earned = 60 + (v2Q1Score - originalQ1Score);
    const expectedCo1Pct = Math.round((expectedCo1Earned / 100) * 10000) / 100;
    // PO1 weight 0.25 on Q1
    const expectedPo1Earned = 15 + (v2Q1Score - originalQ1Score) * 0.25;

    const reportNew = await request.post(
      `${apiBase}/api/v1/outcomes/attainment-reports`,
      {
        headers: admin.headers,
        data: {
          assessment_version_id: versionId,
          mapping_set_id: set3Body.id,
        },
      },
    );
    expect(reportNew.ok(), await reportNew.text()).toBeTruthy();
    const reportV2 = (await reportNew.json()) as typeof reportV1;
    expect(reportV2.id).not.toBe(reportV1.id);
    expect(reportV2.source_set_hash).not.toBe(reportV1.source_set_hash);
    expect(reportV2.source_result_count).toBe(20);
    expect(reportV2.source_published_result_ids).toContain(v2PublishedResultId);
    expect(reportV2.source_published_result_ids).not.toContain(
      v1PublishedResultId,
    );
    expect(reportV2.mapping_activation_hash).toBe(hashV3);
    expect(reportV2.mapping_set_id).toBe(set3Body.id);
    assertMetric(reportV2.metrics, co1Id, {
      earned: expectedCo1Earned,
      max: 100,
      pct: expectedCo1Pct,
    });
    assertMetric(reportV2.metrics, po1Id, {
      earned: expectedPo1Earned,
      max: 25,
      pct: Math.round((expectedPo1Earned / 25) * 10000) / 100,
    });
    // Q2 unchanged
    assertMetric(reportV2.metrics, co2Id, { earned: 30, max: 50, pct: 60 });
    assertMetric(reportV2.metrics, po2Id, { earned: 60, max: 100, pct: 60 });

    const oldReport = await request.get(
      `${apiBase}/api/v1/outcomes/attainment-reports/${reportV1.id}`,
      { headers: admin.headers },
    );
    expect(oldReport.ok()).toBeTruthy();
    const oldReportBody = (await oldReport.json()) as typeof reportV1;
    expect(oldReportBody.source_set_hash).toBe(reportV1.source_set_hash);
    expect(oldReportBody.source_published_result_ids).toEqual(
      reportV1.source_published_result_ids,
    );
    expect(oldReportBody.mapping_activation_hash).toBe(hashV3);
    assertMetric(oldReportBody.metrics, co1Id, {
      earned: 60,
      max: 100,
      pct: 60,
    });

    // ========== C10: UI smoke ==========
    await loginUi(page);
    await page.goto("/quality/clustering");
    await expect(page.getByTestId("b18-clustering-workspace")).toBeVisible({
      timeout: 30_000,
    });
    await page.goto("/outcomes/reporting");
    await expect(page.getByTestId("b18-outcomes-workspace")).toBeVisible({
      timeout: 30_000,
    });
  });
});
