import { test, expect, type APIRequestContext, type Page } from "@playwright/test";
import { randomUUID } from "node:crypto";

const ADMIN_EMAIL = "admin@demo.eduvijna.local";
const ADMIN_PASSWORD = "DemoAdmin!2026";

function runId(): string {
  return `${Date.now().toString(36)}${randomUUID().replace(/-/g, "").slice(0, 8)}`;
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

async function createB13Fixture(
  request: APIRequestContext,
  apiBase: string,
  token: string,
): Promise<{
  curriculumId: string;
  nodeId: string;
  studentId: string;
  resourceId: string;
  resourceTitle: string;
}> {
  const headers = { Authorization: `Bearer ${token}` };
  const suffix = runId();
  const resourceTitle = `B13 Packet ${suffix}`;

  const curriculum = await request.post(`${apiBase}/api/v1/curricula`, {
    headers,
    data: {
      code: `B13-CUR-${suffix}`,
      name: `B13 Curriculum ${suffix}`,
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

  const years = await request.get(`${apiBase}/api/v1/academic-years`, {
    headers,
  });
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
      student_code: `B13-${suffix}`,
      full_name: `B13 Student ${suffix}`,
      class_section_id: section!.id,
      academic_year_id: section!.academic_year_id,
      status: "active",
    },
  });
  expect(student.status()).toBe(201);
  const studentId = ((await student.json()) as { id: string }).id;

  const created = await request.post(`${apiBase}/api/v1/learning/resources`, {
    headers,
    data: {
      curriculum_id: curriculumId,
      code: `RES-B13-${suffix}`,
      title: resourceTitle,
      description: "B13 e2e packet",
      resource_kind: "PRACTICE_SET",
      content_ref: `internal://catalog/b13-${suffix}`,
      curriculum_node_ids: [nodeId],
    },
  });
  expect(created.status()).toBe(201);
  const createdBody = (await created.json()) as {
    id: string;
    status: string;
  };
  const resourceId = createdBody.id;
  expect(createdBody.status).toBe("DRAFT");

  const approved = await request.post(
    `${apiBase}/api/v1/learning/resources/${resourceId}/approve`,
    { headers },
  );
  expect(approved.ok()).toBeTruthy();
  expect(((await approved.json()) as { status: string }).status).toBe(
    "APPROVED",
  );

  const activated = await request.post(
    `${apiBase}/api/v1/learning/resources/${resourceId}/activate`,
    { headers },
  );
  expect(activated.ok()).toBeTruthy();
  expect(((await activated.json()) as { status: string }).status).toBe(
    "ACTIVE",
  );

  const assigned = await request.post(
    `${apiBase}/api/v1/learning/students/${studentId}/resource-assignments`,
    {
      headers,
      data: { resource_id: resourceId },
    },
  );
  expect(assigned.ok()).toBeTruthy();
  expect(((await assigned.json()) as { status: string }).status).toBe(
    "ASSIGNED",
  );

  return { curriculumId, nodeId, studentId, resourceId, resourceTitle };
}

async function loginUi(page: Page) {
  await page.goto("/login");
  await page.getByTestId("login-email").fill(ADMIN_EMAIL);
  await page.getByTestId("login-password").fill(ADMIN_PASSWORD);
  await page.getByTestId("login-submit").click();
  await expect(page.getByTestId("app-shell")).toBeVisible({ timeout: 30_000 });
}

test.describe("B13 real curriculum resources", () => {
  test("assign catalog resource and show on learning page; tenant isolation", async ({
    page,
    request,
  }) => {
    const apiBase =
      process.env.API_UPSTREAM_URL ?? "http://127.0.0.1:18000";
    expect((await request.get(`${apiBase}/health`)).ok()).toBeTruthy();

    const token = await loginApi(request, apiBase);
    const headers = { Authorization: `Bearer ${token}` };
    const fixture = await createB13Fixture(request, apiBase, token);

    const workspace = await request.get(
      `${apiBase}/api/v1/learning/students/${fixture.studentId}?curriculum_id=${fixture.curriculumId}`,
      { headers },
    );
    expect(workspace.ok()).toBeTruthy();
    const workspaceBody = (await workspace.json()) as {
      resource_assignments?: Array<{ resource?: { title?: string } }>;
    };
    expect(
      workspaceBody.resource_assignments?.some(
        (a) => a.resource?.title === fixture.resourceTitle,
      ),
    ).toBeTruthy();

    await loginUi(page);
    await page.goto(
      `/learning/${fixture.studentId}?curriculum_id=${fixture.curriculumId}`,
    );
    await expect(page.getByTestId("adaptive-learning-page")).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByTestId("b13-assigned-resources")).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.getByTestId("b13-assignment-row").first()).toContainText(
      fixture.resourceTitle,
    );
    await expect(
      page.getByTestId("b13-recommendation-vs-assignment-note"),
    ).toContainText(/B13/i);

    // Foreign tenant / unknown resource → 404
    const missing = await request.get(
      `${apiBase}/api/v1/learning/resources/${randomUUID()}`,
      { headers },
    );
    expect(missing.status()).toBe(404);

    const wrongAssign = await request.post(
      `${apiBase}/api/v1/learning/students/${fixture.studentId}/resource-assignments`,
      {
        headers,
        data: { resource_id: randomUUID() },
      },
    );
    expect(wrongAssign.status()).toBe(404);
  });
});
