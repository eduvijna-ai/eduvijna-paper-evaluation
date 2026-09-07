import { afterEach, describe, expect, it, vi } from "vitest";
import { HybridEduVijnaApi } from "@/lib/api/hybrid/adapter";

const runId = "22222222-2222-4222-8222-222222222222";
const assessmentId = "33333333-3333-4333-8333-333333333333";
const versionId = "11111111-1111-4111-8111-111111111111";
const questionId = "44444444-4444-4444-8444-444444444444";
const curriculumId = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const nodeId = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";

const proposalMappings = [
  {
    curriculum_node_id: nodeId,
    mapping_type: "PRIMARY",
    weight: "1.00",
    rationale: "Primary topic match",
  },
];

const reviewRunDto = {
  id: runId,
  tenant_id: "88888888-8888-4888-8888-888888888888",
  assessment_id: assessmentId,
  assessment_version_id: versionId,
  question_version_id: questionId,
  assessment_artifact_id: null,
  operation: "SUGGEST_CURRICULUM_MAPPING",
  status: "REVIEW_REQUIRED",
  input_hash: "b".repeat(64),
  proposal_payload: {
    curriculum_id: curriculumId,
    mappings: proposalMappings,
    candidate_node_ids: [nodeId],
  },
  requested_by: "99999999-9999-4999-8999-999999999999",
  requested_at: "2026-09-07T00:00:00Z",
  started_at: "2026-09-07T00:00:01Z",
  finished_at: "2026-09-07T00:00:02Z",
  celery_task_id: "task-1",
  answer_key_version_id: null,
  rubric_version_id: null,
  correlation_id: null,
  failure_code: null,
  failure_detail: null,
  enqueue_error: null,
};

describe("B11 curriculum mapping human-gate", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("calls apply-curriculum-mappings HTTP endpoint", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "hybrid");
    const fetchMock = vi
      .fn()
      .mockImplementation(async (input: RequestInfo, init?: RequestInit) => {
        const url = String(input);
        const method = (init?.method ?? "GET").toUpperCase();

        if (
          url.includes("/ai/proposals/curriculum-mapping") &&
          method === "POST"
        ) {
          return new Response(JSON.stringify(reviewRunDto), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }
        if (
          url.includes(
            `/authoring-ai-runs/${runId}/curriculum-mapping-proposal`,
          ) &&
          method === "PUT"
        ) {
          const body = JSON.parse(String(init?.body ?? "{}")) as {
            mappings: typeof proposalMappings;
          };
          return new Response(
            JSON.stringify({
              ...reviewRunDto,
              proposal_payload: {
                ...reviewRunDto.proposal_payload,
                mappings: body.mappings,
              },
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          );
        }
        if (
          url.includes(
            `/authoring-ai-runs/${runId}/apply-curriculum-mappings`,
          ) &&
          method === "POST"
        ) {
          return new Response(
            JSON.stringify({ ...reviewRunDto, status: "SUCCEEDED" }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          );
        }
        return new Response(JSON.stringify({ detail: "unexpected" }), {
          status: 500,
        });
      });
    vi.stubGlobal("fetch", fetchMock);

    const prepared = await HybridEduVijnaApi.prepareAiCurriculumMappingProposal!({
      questionVersionId: questionId,
      curriculumId,
      instructions: "map",
    });
    expect(prepared.status).toBe("REVIEW_REQUIRED");
    expect(prepared.proposal_payload?.mappings).toHaveLength(1);
    expect(prepared.status).not.toBe("SUCCEEDED");

    const updated = await HybridEduVijnaApi.updateCurriculumMappingProposal!(
      runId,
      proposalMappings,
    );
    expect(updated.status).toBe("REVIEW_REQUIRED");

    const applied = await HybridEduVijnaApi.applyCurriculumMappings!(runId, [
      0,
    ]);
    expect(applied.status).toBe("SUCCEEDED");

    const urls = fetchMock.mock.calls.map((call) => String(call[0]));
    expect(urls.some((u) => u.includes("/ai/proposals/curriculum-mapping"))).toBe(
      true,
    );
    expect(
      urls.some((u) => u.includes("/apply-curriculum-mappings")),
    ).toBe(true);

    const applyCall = fetchMock.mock.calls.find((call) =>
      String(call[0]).includes("/apply-curriculum-mappings"),
    );
    expect(applyCall?.[1]?.method?.toUpperCase()).toBe("POST");
    expect(JSON.parse(String(applyCall?.[1]?.body ?? "{}"))).toEqual({
      selected_indices: [0],
    });
  });

  it("does not treat proposal as applied until apply", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "hybrid");
    const fetchMock = vi.fn().mockImplementation(async () =>
      new Response(JSON.stringify(reviewRunDto), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const prepared = await HybridEduVijnaApi.prepareAiCurriculumMappingProposal!({
      questionVersionId: questionId,
      curriculumId,
    });

    expect(prepared.status).toBe("REVIEW_REQUIRED");
    expect(prepared.proposal_payload?.mappings?.[0]?.curriculum_node_id).toBe(
      nodeId,
    );
    expect(prepared.status).not.toBe("SUCCEEDED");
    expect(
      fetchMock.mock.calls.some((call) =>
        String(call[0]).includes("/apply-curriculum-mappings"),
      ),
    ).toBe(false);
  });

  it("surfaces curriculum-mapping HTTP errors without mock fallback", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "hybrid");
    const fetchMock = vi.fn().mockImplementation(async () =>
      new Response(
        JSON.stringify({
          detail: {
            code: "AUTHORING_PROVIDER_INVALID_CURRICULUM_NODE",
            message: "Invalid curriculum node",
          },
        }),
        { status: 422, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      HybridEduVijnaApi.prepareAiCurriculumMappingProposal!({
        questionVersionId: questionId,
        curriculumId,
      }),
    ).rejects.toMatchObject({
      name: "ApiError",
      code: "AUTHORING_PROVIDER_INVALID_CURRICULUM_NODE",
    });

    await expect(
      HybridEduVijnaApi.applyCurriculumMappings!(runId, [0]),
    ).rejects.toMatchObject({
      name: "ApiError",
      code: "AUTHORING_PROVIDER_INVALID_CURRICULUM_NODE",
    });
  });
});
