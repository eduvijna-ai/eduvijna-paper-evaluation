import { afterEach, describe, expect, it, vi } from "vitest";
import { getApiCapabilities } from "@/lib/api/capabilities";
import { HybridEduVijnaApi } from "@/lib/api/hybrid/adapter";
import { ApiError } from "@/lib/api/http/errors";
import {
  curriculumResourceApiToView,
  curriculumResourceListApiToView,
  studentResourceAssignmentApiToView,
  type B13CurriculumResourceDto,
  type B13StudentResourceAssignmentDto,
} from "@/lib/api/http/resources";
import { learningWorkspaceApiToView } from "@/lib/api/http/learning";
import {
  CURRICULUM_RESOURCE_KINDS,
  CURRICULUM_RESOURCE_STATUSES,
  STUDENT_RESOURCE_ASSIGNMENT_STATUSES,
} from "@/lib/types/enums";

const studentId = "33333333-3333-4333-8333-333333333333";
const curriculumId = "44444444-4444-4444-8444-444444444444";
const resourceId = "55555555-5555-4555-8555-555555555555";
const assignmentId = "66666666-6666-4666-8666-666666666666";
const nodeId = "77777777-7777-4777-8777-777777777777";
const recommendationId = "88888888-8888-4888-8888-888888888888";

const resourceDto: B13CurriculumResourceDto = {
  id: resourceId,
  curriculum_id: curriculumId,
  code: "RES-ALG-01",
  title: "Algebra practice packet",
  description: "Institution packet",
  resource_kind: "PRACTICE_SET",
  status: "ACTIVE",
  content_ref: "internal://catalog/alg-practice-1",
  curriculum_node_ids: [nodeId],
  created_by: null,
  approved_by: null,
  approved_at: "2026-09-07T00:00:00Z",
  created_at: "2026-09-07T00:00:00Z",
  updated_at: "2026-09-07T00:00:00Z",
};

const assignmentDto: B13StudentResourceAssignmentDto = {
  id: assignmentId,
  student_id: studentId,
  resource_id: resourceId,
  resource: resourceDto,
  learning_recommendation_id: recommendationId,
  status: "ASSIGNED",
  assigned_by: null,
  assigned_at: "2026-09-07T01:00:00Z",
  cancelled_at: null,
  cancelled_by: null,
};

describe("B13 enums", () => {
  it("includes resource and assignment statuses", () => {
    expect(CURRICULUM_RESOURCE_KINDS).toContain("PRACTICE_SET");
    expect(CURRICULUM_RESOURCE_STATUSES).toEqual([
      "DRAFT",
      "APPROVED",
      "ACTIVE",
      "DEACTIVATED",
    ]);
    expect(STUDENT_RESOURCE_ASSIGNMENT_STATUSES).toContain("ASSIGNED");
    expect(STUDENT_RESOURCE_ASSIGNMENT_STATUSES).toContain("CANCELLED");
  });
});

describe("B13 resource mappers", () => {
  it("maps curriculum resource fields", () => {
    const view = curriculumResourceApiToView(resourceDto);
    expect(view.code).toBe("RES-ALG-01");
    expect(view.status).toBe("ACTIVE");
    expect(view.curriculum_node_ids).toEqual([nodeId]);
    expect(view.content_ref).toBe("internal://catalog/alg-practice-1");
    expect(JSON.stringify(view)).not.toMatch(/https?:\/\//);
  });

  it("filters catalog list by status via mapper payload", () => {
    const list = curriculumResourceListApiToView({
      curriculum_id: curriculumId,
      status_filter: "ACTIVE",
      items: [resourceDto, { ...resourceDto, id: "other", status: "DRAFT" }],
    });
    expect(list.status_filter).toBe("ACTIVE");
    expect(list.items).toHaveLength(2);
    expect(list.items.filter((i) => i.status === "ACTIVE")).toHaveLength(1);
  });

  it("maps assignment and keeps recommendation linkage distinct", () => {
    const assignment = studentResourceAssignmentApiToView(assignmentDto);
    expect(assignment.status).toBe("ASSIGNED");
    expect(assignment.resource.title).toBe("Algebra practice packet");
    expect(assignment.learning_recommendation_id).toBe(recommendationId);
    // Assignment is not a B9 recommendation row
    expect(assignment).not.toHaveProperty("recommendation_kind");
    expect(assignment).not.toHaveProperty("concept_signal");
  });

  it("maps workspace resource_assignments separately from recommendations", () => {
    const workspace = learningWorkspaceApiToView({
      student: {
        id: studentId,
        display_name: "Ada Lovelace",
      },
      available_curricula: [
        { id: curriculumId, code: "CUR-A", name: "Algebra" },
      ],
      selected_curriculum: { id: curriculumId, code: "CUR-A", name: "Algebra" },
      materialization_status: "READY",
      evidence_coverage: { curriculum_node_count: 1, evidence_row_count: 1 },
      latest_plan: {
        run_id: "run-1",
        version_number: 1,
        status: "READY",
        algorithm_version: "B9_V1",
        source_evidence_hash: "a".repeat(64),
        curriculum_graph_hash: "b".repeat(64),
        input_hash: "c".repeat(64),
        is_stale: false,
        recommendations: [
          {
            id: recommendationId,
            curriculum_node_id: nodeId,
            code: "NODE-A",
            title: "Linear Equations",
            node_type: "TOPIC",
            recommendation_kind: "TARGET_CONCEPT",
            priority: 1,
            rationale: "Weak concept",
            concept_signal: "WEAK",
            execution_signal: "INCONCLUSIVE",
            procedure_signal: "INCONCLUSIVE",
            evidence_count: 1,
            mean_evidence_score_ratio: 0.2,
            status: "ACTIVE",
          },
        ],
        path: [],
      },
      is_stale: false,
      resource_assignments: [assignmentDto],
    });

    expect(workspace.latest_plan?.recommendations).toHaveLength(1);
    expect(workspace.resource_assignments).toHaveLength(1);
    expect(workspace.resource_assignments?.[0]?.resource.code).toBe("RES-ALG-01");
    expect(workspace.resource_assignments?.[0]?.id).not.toBe(
      workspace.latest_plan?.recommendations[0]?.id,
    );
  });

  it("maps empty resource_assignments when omitted", () => {
    const workspace = learningWorkspaceApiToView({
      student: { id: studentId, display_name: "Ada" },
      materialization_status: "NONE",
      evidence_coverage: {},
    });
    expect(workspace.resource_assignments).toEqual([]);
  });
});

describe("B13 hybrid routing", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("routes catalog list to live HTTP", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "hybrid");
    expect(getApiCapabilities().learning).toBe("live");

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          curriculum_id: curriculumId,
          status_filter: "ACTIVE",
          items: [resourceDto],
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await HybridEduVijnaApi.listCurriculumResources!({
      curriculumId,
      status: "ACTIVE",
    });
    expect(result.items[0]?.code).toBe("RES-ALG-01");
    const url = String(fetchMock.mock.calls[0]?.[0]);
    expect(url).toContain("/api/v1/learning/resources");
    expect(url).toContain(`curriculum_id=${curriculumId}`);
    expect(url).toContain("status=ACTIVE");
  });

  it("routes assign to live HTTP", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "hybrid");
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(assignmentDto), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await HybridEduVijnaApi.assignStudentResource!(studentId, {
      resource_id: resourceId,
    });
    expect(result.id).toBe(assignmentId);
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain(
      `/api/v1/learning/students/${studentId}/resource-assignments`,
    );
  });

  it("serves demo catalog fixtures in mock mode", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "mock");
    const list = await HybridEduVijnaApi.listCurriculumResources!();
    expect(list.items.some((i) => i.code === "RES-DEMO-001")).toBe(true);

    const active = await HybridEduVijnaApi.listCurriculumResources!({
      status: "ACTIVE",
    });
    expect(active.items.every((i) => i.status === "ACTIVE")).toBe(true);

    const assignments =
      await HybridEduVijnaApi.listStudentResourceAssignments!(
        "student-demo-001",
      );
    expect(assignments.items.length).toBeGreaterThan(0);
    expect(assignments.items[0]?.resource.code).toBe("RES-DEMO-001");
  });

  it("rejects live UUIDs for B13 when learning is mock", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "mock");
    expect(getApiCapabilities().learning).toBe("mock");

    await expect(
      HybridEduVijnaApi.getCurriculumResource!(resourceId),
    ).rejects.toMatchObject({ code: "B13_MOCK_DEMO_ONLY" });

    await expect(
      HybridEduVijnaApi.listStudentResourceAssignments!(studentId),
    ).rejects.toMatchObject({ code: "B13_MOCK_DEMO_ONLY" });

    await expect(
      HybridEduVijnaApi.assignStudentResource!(studentId, {
        resource_id: resourceId,
      }),
    ).rejects.toMatchObject({ code: "B13_MOCK_DEMO_ONLY" });
  });

  it("propagates live HTTP errors without mock fallback", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "hybrid");
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          error: { code: "NOT_FOUND", message: "Curriculum resource not found" },
        }),
        { status: 404, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      HybridEduVijnaApi.getCurriculumResource!(resourceId),
    ).rejects.toBeInstanceOf(ApiError);
  });
});
