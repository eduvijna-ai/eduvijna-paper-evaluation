import { afterEach, describe, expect, it, vi } from "vitest";
import { getApiCapabilities } from "@/lib/api/capabilities";
import { HybridEduVijnaApi } from "@/lib/api/hybrid/adapter";
import { ApiError } from "@/lib/api/http/errors";
import { learningWorkspaceApiToView } from "@/lib/api/http/learning";
import {
  reassessmentApiToView,
  reassessmentMasteryDeltaApiToView,
  type B14ReassessmentDto,
} from "@/lib/api/http/reassessment";
import {
  B14_INSUFFICIENT_EVIDENCE_LABEL,
  buildInstantiateRequestFromBlueprintItems,
  canCreateReassessmentFromBlueprint,
  deltaTone,
  formatMasteryValue,
  formatSignedDelta,
  reassessmentHasMaterializedDeltas,
  suggestedMarksPrefill,
} from "@/lib/helpers/b14-reassessment";
import { REASSESSMENT_STATUSES } from "@/lib/types/enums";

const studentId = "33333333-3333-4333-8333-333333333333";
const blueprintId = "11111111-1111-4111-8111-111111111111";
const reassessmentId = "22222222-2222-4222-8222-222222222222";
const assessmentId = "44444444-4444-4444-8444-444444444444";
const nodeId = "55555555-5555-4555-8555-555555555555";
const itemId = "66666666-6666-4666-8666-666666666666";

const reassessmentDto: B14ReassessmentDto = {
  id: reassessmentId,
  improvement_assessment_id: blueprintId,
  blueprint_title: "Improvement Check",
  blueprint_version_number: 1,
  student_id: studentId,
  curriculum_id: "77777777-7777-4777-8777-777777777777",
  assessment_id: assessmentId,
  assessment_status: "DRAFT",
  assessment_version_id: "88888888-8888-4888-8888-888888888888",
  submission_id: null,
  published_result_id: null,
  status: "CREATED",
  algorithm_version: "B14_V1",
  instantiation_hash: "a".repeat(64),
  baseline_captured_at: "2026-09-08T00:00:00Z",
  created_at: "2026-09-08T00:00:00Z",
  updated_at: "2026-09-08T00:00:00Z",
  items: [
    {
      id: "99999999-9999-4999-8999-999999999999",
      improvement_assessment_item_id: itemId,
      question_version_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
      curriculum_node_id: nodeId,
      item_code_snapshot: "I1",
      template_kind_snapshot: "CONCEPT_CHECK",
      question_template_ref_snapshot: "tmpl://x",
    },
  ],
  mastery_deltas: [
    {
      curriculum_node_id: nodeId,
      baseline_concept_mastery: 0.2,
      baseline_execution_accuracy: null,
      baseline_concept_decisive_count: 1,
      baseline_execution_decisive_count: 0,
      baseline_concept_inconclusive_count: 0,
      baseline_execution_inconclusive_count: 1,
      baseline_evidence_count: 1,
      baseline_source_evidence_hash: "b".repeat(64),
      post_snapshot_id: null,
      post_published_result_id: null,
      post_concept_mastery: null,
      post_execution_accuracy: null,
      post_concept_decisive_count: null,
      post_execution_decisive_count: null,
      post_concept_inconclusive_count: null,
      post_execution_inconclusive_count: null,
      post_evidence_count: null,
      post_source_evidence_hash: null,
      concept_delta: null,
      execution_delta: null,
      materialized_at: null,
      algorithm_version: "B14_V1",
    },
  ],
};

describe("B14 enums", () => {
  it("includes reassessment statuses", () => {
    expect(REASSESSMENT_STATUSES).toEqual([
      "CREATED",
      "SUBMITTED",
      "PUBLISHED",
    ]);
  });
});

describe("B14 mappers", () => {
  it("maps reassessment and preserves null mastery semantics", () => {
    const view = reassessmentApiToView(reassessmentDto);
    expect(view.status).toBe("CREATED");
    expect(view.assessment_status).toBe("DRAFT");
    expect(view.items).toHaveLength(1);
    expect(view.mastery_deltas[0]?.baseline_execution_accuracy).toBeNull();
    expect(view.mastery_deltas[0]?.concept_delta).toBeNull();
    expect(view.mastery_deltas[0]?.baseline_concept_mastery).toBe(0.2);
  });

  it("maps string numeric deltas without coercing null to 0", () => {
    const delta = reassessmentMasteryDeltaApiToView({
      curriculum_node_id: nodeId,
      baseline_concept_mastery: null,
      baseline_execution_accuracy: "0.50",
      concept_delta: null,
      execution_delta: "0.10",
      baseline_concept_decisive_count: 0,
      baseline_execution_decisive_count: 1,
      baseline_concept_inconclusive_count: 1,
      baseline_execution_inconclusive_count: 0,
      baseline_evidence_count: 1,
      baseline_source_evidence_hash: "c".repeat(64),
      algorithm_version: "B14_V1",
      materialized_at: "2026-09-08T01:00:00Z",
      post_snapshot_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
      post_concept_mastery: null,
      post_execution_accuracy: "0.60",
    });
    expect(delta.baseline_concept_mastery).toBeNull();
    expect(delta.concept_delta).toBeNull();
    expect(delta.baseline_execution_accuracy).toBe(0.5);
    expect(delta.execution_delta).toBe(0.1);
  });

  it("maps workspace reassessments separately from recommendations and B13", () => {
    const workspace = learningWorkspaceApiToView({
      student: { id: studentId, display_name: "Ada" },
      materialization_status: "READY",
      evidence_coverage: {},
      resource_assignments: [],
      reassessments: [reassessmentDto],
    });
    expect(workspace.reassessments).toHaveLength(1);
    expect(workspace.reassessments?.[0]?.id).toBe(reassessmentId);
    expect(workspace.resource_assignments).toEqual([]);
  });

  it("maps empty reassessments when omitted", () => {
    const workspace = learningWorkspaceApiToView({
      student: { id: studentId, display_name: "Ada" },
      materialization_status: "NONE",
      evidence_coverage: {},
    });
    expect(workspace.reassessments).toEqual([]);
  });
});

describe("B14 display helpers", () => {
  it("gates create form to APPROVED only", () => {
    expect(
      canCreateReassessmentFromBlueprint({ status: "APPROVED" }),
    ).toBe(true);
    expect(
      canCreateReassessmentFromBlueprint({ status: "PENDING_APPROVAL" }),
    ).toBe(false);
    expect(canCreateReassessmentFromBlueprint(null)).toBe(false);
  });

  it("builds instantiate payload covering all items", () => {
    const items = [
      {
        id: itemId,
        learning_recommendation_id: null,
        curriculum_node_id: nodeId,
        node_code: "N1",
        node_title: "Node",
        item_code: "I1",
        template_kind: "CONCEPT_CHECK",
        question_template_ref: "tmpl",
        focus: "Focus",
        difficulty: "MEDIUM",
        suggested_marks: 4,
        sort_order: 1,
      },
    ];
    const request = buildInstantiateRequestFromBlueprintItems(items, {
      [itemId]: { prompt_text: "Custom prompt", max_marks: "5.00" },
    });
    expect(request.items).toHaveLength(1);
    expect(request.items[0]?.improvement_assessment_item_id).toBe(itemId);
    expect(request.items[0]?.prompt_text).toBe("Custom prompt");
    expect(request.items[0]?.max_marks).toBe("5.00");
    expect(suggestedMarksPrefill({ suggested_marks: 4 })).toBe("4.00");
  });

  it("never renders null mastery as 0", () => {
    expect(formatMasteryValue(null)).toBe(B14_INSUFFICIENT_EVIDENCE_LABEL);
    expect(formatMasteryValue(undefined)).toBe(B14_INSUFFICIENT_EVIDENCE_LABEL);
    expect(formatMasteryValue(0)).toBe("0.000");
    expect(formatSignedDelta(0.3)).toBe("+0.300");
    expect(formatSignedDelta(-0.05)).toBe("-0.050");
    expect(formatSignedDelta(null)).toBe(B14_INSUFFICIENT_EVIDENCE_LABEL);
    expect(deltaTone(0.1)).toBe("improvement");
    expect(deltaTone(-0.1)).toBe("regression");
    expect(deltaTone(null)).toBe("insufficient");
  });

  it("detects pre vs post materialization", () => {
    const view = reassessmentApiToView(reassessmentDto);
    expect(reassessmentHasMaterializedDeltas(view.mastery_deltas)).toBe(false);
    expect(
      reassessmentHasMaterializedDeltas([
        {
          ...view.mastery_deltas[0]!,
          materialized_at: "2026-09-08T02:00:00Z",
          post_snapshot_id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
        },
      ]),
    ).toBe(true);
  });
});

describe("B14 hybrid routing", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("routes instantiate to live HTTP", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "hybrid");
    expect(getApiCapabilities().learning).toBe("live");

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(reassessmentDto), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await HybridEduVijnaApi.instantiateReassessment(blueprintId, [
      {
        improvement_assessment_item_id: itemId,
        prompt_text: "Solve for x",
        max_marks: "4.00",
      },
    ]);
    expect(result.id).toBe(reassessmentId);
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain(
      `/api/v1/improvement-assessments/${blueprintId}/reassessment`,
    );
  });

  it("routes getReassessment to live HTTP", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "hybrid");
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(reassessmentDto), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await HybridEduVijnaApi.getReassessment(reassessmentId);
    expect(result.assessment_id).toBe(assessmentId);
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain(
      `/api/v1/reassessments/${reassessmentId}`,
    );
  });

  it("serves demo reassessment fixtures in mock mode", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "mock");
    const published = await HybridEduVijnaApi.getReassessment(
      "reassessment-demo-001",
    );
    expect(published.status).toBe("PUBLISHED");
    expect(published.mastery_deltas.some((d) => d.concept_delta === null)).toBe(
      true,
    );

    const created = await HybridEduVijnaApi.instantiateReassessment(
      "imp-demo-001",
      [
        {
          improvement_assessment_item_id: "imp-item-demo-001",
          prompt_text: "Demo prompt",
          max_marks: "4.00",
        },
      ],
    );
    expect(created.status).toBe("CREATED");
    expect(created.assessment_status).toBe("DRAFT");
  });

  it("rejects live UUIDs for B14 when learning is mock", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "mock");
    expect(getApiCapabilities().learning).toBe("mock");

    await expect(
      HybridEduVijnaApi.getReassessment(reassessmentId),
    ).rejects.toMatchObject({ code: "B14_MOCK_DEMO_ONLY" });

    await expect(
      HybridEduVijnaApi.instantiateReassessment(blueprintId, [
        {
          improvement_assessment_item_id: itemId,
          prompt_text: "x",
          max_marks: "1.00",
        },
      ]),
    ).rejects.toMatchObject({ code: "B14_MOCK_DEMO_ONLY" });

    await expect(
      HybridEduVijnaApi.rebuildReassessmentB14!(reassessmentId),
    ).rejects.toMatchObject({ code: "B14_MOCK_DEMO_ONLY" });
  });

  it("propagates live HTTP errors without mock fallback", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "hybrid");
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          error: { code: "NOT_FOUND", message: "Reassessment not found" },
        }),
        { status: 404, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      HybridEduVijnaApi.getReassessment(reassessmentId),
    ).rejects.toBeInstanceOf(ApiError);
  });
});
