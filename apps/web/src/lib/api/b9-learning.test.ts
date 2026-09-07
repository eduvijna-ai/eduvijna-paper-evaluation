import { afterEach, describe, expect, it, vi } from "vitest";
import { getApiCapabilities } from "@/lib/api/capabilities";
import { HybridEduVijnaApi } from "@/lib/api/hybrid/adapter";
import { ApiError } from "@/lib/api/http/errors";
import {
  improvementAssessmentApiToView,
  learningPlanApiToView,
  learningWorkspaceApiToView,
  type B9ImprovementAssessmentDto,
  type B9LearningPlanDto,
  type B9LearningWorkspaceDto,
} from "@/lib/api/http/learning";
import {
  IMPROVEMENT_BLUEPRINT_STATES,
  LEARNING_PLAN_RUN_STATUSES,
  LEARNING_RECOMMENDATION_KINDS,
} from "@/lib/types/enums";

const studentId = "33333333-3333-4333-8333-333333333333";
const curriculumId = "44444444-4444-4444-8444-444444444444";
const runId = "55555555-5555-4555-8555-555555555555";
const blueprintId = "66666666-6666-4666-8666-666666666666";
const nodeA = "77777777-7777-4777-8777-777777777777";
const nodeB = "88888888-8888-4888-8888-888888888888";

const workspaceDto: B9LearningWorkspaceDto = {
  student: {
    id: studentId,
    display_name: "Ada Lovelace",
    student_code: "ADA-1",
    external_ref: "EXT-ADA",
  },
  available_curricula: [
    { id: curriculumId, code: "CUR-A", name: "Algebra" },
    { id: "99999999-9999-4999-8999-999999999999", code: "CUR-B", name: "Geometry" },
  ],
  selected_curriculum: { id: curriculumId, code: "CUR-A", name: "Algebra" },
  materialization_status: "READY",
  evidence_coverage: { curriculum_node_count: 2, evidence_row_count: 4 },
  latest_run: {
    id: runId,
    version_number: 1,
    status: "READY",
    generation_source: "FIXED",
    algorithm_version: "B9_V1",
    source_evidence_hash: "a".repeat(64),
    curriculum_graph_hash: "b".repeat(64),
    input_hash: "c".repeat(64),
  },
  latest_plan: {
    run_id: runId,
    version_number: 1,
    status: "READY",
    generation_source: "FIXED",
    algorithm_version: "B9_V1",
    source_evidence_hash: "a".repeat(64),
    curriculum_graph_hash: "b".repeat(64),
    input_hash: "c".repeat(64),
    is_stale: false,
    recommendations: [
      {
        id: "rec-a",
        curriculum_node_id: nodeA,
        code: "NODE-A",
        title: "Linear Equations",
        node_type: "TOPIC",
        recommendation_kind: "PREREQUISITE_REPAIR",
        priority: 1,
        rationale: "Required prerequisite is weak",
        concept_signal: "WEAK",
        execution_signal: "INCONCLUSIVE",
        procedure_signal: "INCONCLUSIVE",
        evidence_count: 2,
        mean_evidence_score_ratio: "0.25",
        status: "ACTIVE",
      },
      {
        id: "rec-b",
        curriculum_node_id: nodeB,
        code: "NODE-B",
        title: "Quadratic Equations",
        node_type: "TOPIC",
        recommendation_kind: "TARGET_CONCEPT",
        priority: 1,
        rationale: "Target concept is weak",
        concept_signal: "WEAK",
        execution_signal: "STRONG",
        procedure_signal: "INCONCLUSIVE",
        evidence_count: 2,
        mean_evidence_score_ratio: 0.3,
        status: "ACTIVE",
      },
    ],
    path: [
      {
        id: "step-1",
        kind: "PREREQUISITE",
        sequence: 1,
        title: "Required prerequisite repair — Linear Equations",
        description: "Repair NODE-A before NODE-B",
        curriculum_node_id: nodeA,
        node_code: "NODE-A",
        node_title: "Linear Equations",
        evidence_basis: "CONCEPT",
        relationship_type: "REQUIRED",
        estimated_minutes: null,
      },
      {
        id: "step-2",
        kind: "LEARN",
        sequence: 2,
        title: "Target concept — Quadratic Equations",
        description: "Focus on NODE-B",
        curriculum_node_id: nodeB,
        node_code: "NODE-B",
        node_title: "Quadratic Equations",
        evidence_basis: "CONCEPT",
        relationship_type: null,
      },
    ],
    materialization_status: "READY",
    evidence_coverage: { curriculum_node_count: 2, evidence_row_count: 4 },
  },
  is_stale: false,
  latest_improvement_blueprint: null,
};

const planDto: B9LearningPlanDto = workspaceDto.latest_plan!;

const blueprintDto: B9ImprovementAssessmentDto = {
  id: blueprintId,
  student_id: studentId,
  curriculum_id: curriculumId,
  learning_plan_run_id: runId,
  version_number: 1,
  title: "Improvement blueprint",
  status: "PENDING_APPROVAL",
  generation_source: "FIXED",
  algorithm_version: "B9_V1",
  is_stale: false,
  items: [
    {
      id: "item-1",
      learning_recommendation_id: "rec-b",
      curriculum_node_id: nodeB,
      node_code: "NODE-B",
      node_title: "Quadratic Equations",
      item_code: "I1",
      template_kind: "CONCEPT_CHECK",
      question_template_ref: "CVB:CONCEPT_CHECK:v1",
      focus: "Quadratic concept",
      difficulty: "MEDIUM",
      suggested_marks: "4.00",
      sort_order: 1,
    },
  ],
  created_at: "2026-09-07T00:00:00Z",
};

describe("B9 learning capability", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("marks learning live in hybrid", () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "hybrid");
    expect(getApiCapabilities().learning).toBe("live");
    expect(getApiCapabilities().analytics).toBe("live");
  });

  it("keeps learning mock in mock mode", () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "mock");
    expect(getApiCapabilities().learning).toBe("mock");
  });

  it("includes B9 improvement and plan run statuses", () => {
    expect(IMPROVEMENT_BLUEPRINT_STATES).toContain("GENERATING");
    expect(IMPROVEMENT_BLUEPRINT_STATES).toContain("FAILED");
    expect(LEARNING_PLAN_RUN_STATUSES).toContain("SUPERSEDED");
    expect(LEARNING_RECOMMENDATION_KINDS).toContain("EXECUTION_PRACTICE");
  });
});

describe("B9 learning mappers", () => {
  it("maps workspace without mastery percent fields", () => {
    const view = learningWorkspaceApiToView(workspaceDto);
    expect(view.selected_curriculum?.code).toBe("CUR-A");
    expect(view.latest_plan?.recommendations).toHaveLength(2);
    expect(view.latest_plan?.path[0]?.node_code).toBe("NODE-A");
    expect(view.latest_plan?.path[1]?.node_code).toBe("NODE-B");
    expect(view.latest_plan?.path[0]?.estimated_minutes).toBeNull();
    expect(JSON.stringify(view)).not.toMatch(/mastery/);
    expect(JSON.stringify(view.latest_plan?.recommendations)).toContain(
      "concept_signal",
    );
  });

  it("maps plan with prerequisite ordering and signals", () => {
    const plan = learningPlanApiToView(planDto);
    expect(plan.recommendations[0]?.recommendation_kind).toBe(
      "PREREQUISITE_REPAIR",
    );
    expect(plan.recommendations[0]?.concept_signal).toBe("WEAK");
    expect(plan.path.map((s) => s.node_code)).toEqual(["NODE-A", "NODE-B"]);
  });

  it("maps improvement blueprint items without reassessment actions", () => {
    const view = improvementAssessmentApiToView(blueprintDto);
    expect(view.status).toBe("PENDING_APPROVAL");
    expect(view.items[0]?.template_kind).toBe("CONCEPT_CHECK");
    expect(view.items[0]?.suggested_marks).toBe(4);
    expect(JSON.stringify(view)).not.toMatch(/Start assessment|Release assessment/i);
  });
});

describe("B9 hybrid learning routing", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("routes getLearningWorkspace to live HTTP", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "hybrid");
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(workspaceDto), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await HybridEduVijnaApi.getLearningWorkspace!(
      studentId,
      curriculumId,
    );
    expect(result.latest_plan?.run_id).toBe(runId);
    const url = String(fetchMock.mock.calls[0]?.[0]);
    expect(url).toContain(`/api/v1/learning/students/${studentId}`);
    expect(url).toContain(`curriculum_id=${curriculumId}`);
  });

  it("prepares plan, polls run, prepares and approves blueprint", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "hybrid");
    const fetchMock = vi.fn().mockImplementation(async (input: RequestInfo, init?: RequestInit) => {
      const url = String(input);
      const method = (init?.method ?? "GET").toUpperCase();
      if (url.includes("/prepare") && url.includes("/students/") && method === "POST") {
        return new Response(
          JSON.stringify({
            run_id: runId,
            student_id: studentId,
            curriculum_id: curriculumId,
            version_number: 1,
            status: "QUEUED",
            celery_task_id: "task-1",
            algorithm_version: "B9_V1",
            is_idempotent_reuse: false,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (url.includes(`/learning/plan-runs/${runId}`) && method === "GET") {
        return new Response(
          JSON.stringify({
            id: runId,
            version_number: 1,
            status: "READY",
            generation_source: "FIXED",
            algorithm_version: "B9_V1",
            source_evidence_hash: "a".repeat(64),
            curriculum_graph_hash: "b".repeat(64),
            input_hash: "c".repeat(64),
            is_stale: false,
            recommendations: planDto.recommendations,
            path: planDto.path,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (url.includes("/improvement-blueprints/prepare") && method === "POST") {
        return new Response(
          JSON.stringify({
            improvement_assessment_id: blueprintId,
            learning_plan_run_id: runId,
            version_number: 1,
            status: "GENERATING",
            celery_task_id: "task-2",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (url.includes(`/improvement-assessments/${blueprintId}/approve`)) {
        return new Response(
          JSON.stringify({ ...blueprintDto, status: "APPROVED" }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (url.includes(`/improvement-assessments/${blueprintId}/reject`)) {
        return new Response(
          JSON.stringify({
            ...blueprintDto,
            status: "REJECTED",
            rejection_reason: "Needs clearer focus",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (url.includes(`/improvement-assessments/${blueprintId}`)) {
        return new Response(JSON.stringify(blueprintDto), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      return new Response(JSON.stringify({ detail: "unexpected" }), {
        status: 500,
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    const prepared = await HybridEduVijnaApi.prepareLearningPlan!(
      studentId,
      curriculumId,
    );
    expect(prepared.run_id).toBe(runId);
    expect(prepared.status).toBe("QUEUED");

    const run = await HybridEduVijnaApi.getLearningPlanRun!(runId);
    expect(run.status).toBe("READY");
    expect(run.path[0]?.node_code).toBe("NODE-A");
    expect(run.path[1]?.node_code).toBe("NODE-B");

    const bpPrep = await HybridEduVijnaApi.prepareImprovementBlueprint!(runId);
    expect(bpPrep.improvement_assessment_id).toBe(blueprintId);

    const approved = await HybridEduVijnaApi.approveImprovementBlueprint(
      blueprintId,
    );
    expect("status" in approved && approved.status).toBe("APPROVED");

    const rejected = await HybridEduVijnaApi.rejectImprovementBlueprint!(
      blueprintId,
      "Needs clearer focus",
    );
    expect(rejected.status).toBe("REJECTED");
    expect(rejected.rejection_reason).toBe("Needs clearer focus");
  });

  it("surfaces live learning HTTP errors without mock fallback", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "hybrid");
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          detail: {
            code: "LEARNING_EVIDENCE_NOT_READY",
            message: "Evidence not ready",
          },
        }),
        { status: 409, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      HybridEduVijnaApi.prepareLearningPlan!(studentId, curriculumId),
    ).rejects.toBeInstanceOf(ApiError);
  });

  it("does not silently fall back mock adaptive learning when live", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "hybrid");
    await expect(
      HybridEduVijnaApi.getAdaptiveLearning(studentId),
    ).rejects.toMatchObject({ code: "LEARNING_USE_LIVE_WORKSPACE" });
  });
});
