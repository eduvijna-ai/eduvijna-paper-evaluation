import { afterEach, describe, expect, it, vi } from "vitest";
import {
  answerRegionApiToView,
  mappingWorkspaceApiToView,
  MappingHttpApi,
  questionMappingApiToView,
  questionTreeApiToView,
  type B4MappingWorkspaceDto,
} from "@/lib/api/http/mapping";
import { getApiCapabilities } from "@/lib/api/capabilities";

describe("B4 mapping mappers", () => {
  const workspace: B4MappingWorkspaceDto = {
    submission: {
      id: "11111111-1111-4111-8111-111111111111",
      tenant_id: "22222222-2222-4222-8222-222222222222",
      assessment_id: "33333333-3333-4333-8333-333333333333",
      assessment_version_id: "44444444-4444-4444-8444-444444444444",
      assessment_title: "Mid-Term Math",
      student_id: "55555555-5555-4555-8555-555555555555",
      student_display_name: "Ada",
      workflow_state: "MAPPING_REVIEW",
      student_match_state: "CONFIRMED",
      roll_number_detected: null,
      name_detected: null,
      identity_confidence: "1.0000",
      mapping_confidence: 0,
      page_count: 1,
      uploaded_at: "2026-09-06T10:00:00Z",
      updated_at: "2026-09-06T10:05:00Z",
    },
    pages: [
      {
        id: "p1",
        page_number: 1,
        label: "Page 1",
        width: 800,
        height: 1100,
        is_continuation: false,
      },
    ],
    regions: [
      {
        id: "r1",
        page_id: "p1",
        page_number: 1,
        label: "Ans",
        bbox: { x: 0.1, y: 0.2, width: 0.3, height: 0.15 },
        x: 0.1,
        y: 0.2,
        width: 0.3,
        height: 0.15,
        region_type: "ANSWER",
        source_type: "HUMAN",
        detection_confidence: 0,
        confidence: 0,
        crossed_out: false,
        ignored: false,
        is_continuation: false,
        question_id: null,
      },
    ],
    questions: [
      {
        id: "qv1",
        question_version_id: "qv1",
        question_id: "q1",
        assessment_id: "a1",
        parent_id: null,
        code: "1",
        prompt: "2+2?",
        max_mark: "5.00",
        sort_order: 1,
        scoring_mode: "LEAF_SCORABLE",
        is_leaf_scorable: true,
        curriculum_node_ids: [],
        children: [],
      },
    ],
    mapping: [
      {
        question_id: "qv1",
        question_code: "1",
        region_ids: ["r1"],
        confidence: 0,
        status: "PROPOSED",
      },
    ],
    mappings: [
      {
        id: "m1",
        question_id: "q1",
        question_version_id: "qv1",
        question_code: "1",
        disposition: "ANSWERED",
        mapping_state: "PROPOSED",
        mapped_by: "HUMAN",
        mapping_confidence: 0,
        region_ids: ["r1"],
        confirmed_by: null,
        confirmed_at: null,
      },
    ],
    completion: {
      leaf_total: 1,
      confirmed_count: 0,
      unresolved_question_codes: ["1"],
    },
    assessment_version_id: "44444444-4444-4444-8444-444444444444",
    automated_region_detection_active: false,
    automated_mapping_active: false,
  };

  it("maps workspace including legacy mapping array and region bbox fields", () => {
    const view = mappingWorkspaceApiToView(workspace);
    expect(view.submission.workflow_state).toBe("MAPPING_REVIEW");
    expect(view.pages[0]).toMatchObject({ id: "p1", is_continuation: false });
    expect(view.regions[0]).toMatchObject({
      id: "r1",
      x: 0.1,
      y: 0.2,
      width: 0.3,
      height: 0.15,
      region_type: "ANSWER",
      source_type: "HUMAN",
    });
    expect(view.mapping[0]).toMatchObject({
      question_id: "qv1",
      status: "PROPOSED",
      region_ids: ["r1"],
    });
    expect(view.mappings?.[0]).toMatchObject({
      question_version_id: "qv1",
      disposition: "ANSWERED",
    });
    expect(view.completion).toMatchObject({
      leaf_total: 1,
      confirmed_count: 0,
    });
    expect(view.automated_mapping_active).toBe(false);
  });

  it("maps region from nested bbox when flat fields are absent", () => {
    expect(
      answerRegionApiToView({
        id: "r2",
        page_id: "p1",
        label: "Box",
        bbox: { x: 0.2, y: 0.3, width: 0.4, height: 0.1 },
      }),
    ).toMatchObject({ x: 0.2, y: 0.3, width: 0.4, height: 0.1 });
  });

  it("maps question tree leaf metadata", () => {
    expect(questionTreeApiToView(workspace.questions![0]!)).toMatchObject({
      id: "qv1",
      question_version_id: "qv1",
      scoring_mode: "LEAF_SCORABLE",
      is_leaf_scorable: true,
      max_mark: 5,
    });
  });

  it("maps question answer mapping view", () => {
    expect(questionMappingApiToView(workspace.mappings![0]!)).toMatchObject({
      id: "m1",
      mapping_state: "PROPOSED",
      mapped_by: "HUMAN",
      region_ids: ["r1"],
    });
  });
});

describe("B4 MappingHttpApi request shapes", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("posts prepare / create / upsert / confirm / finalize with expected paths and bodies", async () => {
    const calls: Array<{ url: string; init?: RequestInit }> = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        calls.push({ url: String(url), init });
        const path = String(url);
        if (path.includes("/answer-regions") && init?.method === "POST") {
          return new Response(
            JSON.stringify({
              id: "r-new",
              page_id: "p1",
              page_number: 1,
              label: "Answer region",
              x: 0.1,
              y: 0.1,
              width: 0.3,
              height: 0.2,
              region_type: "ANSWER",
              source_type: "HUMAN",
              confidence: 0,
              crossed_out: false,
            }),
            { status: 201, headers: { "Content-Type": "application/json" } },
          );
        }
        if (path.includes("/question-mappings/") && init?.method === "PUT") {
          return new Response(
            JSON.stringify({
              id: "m1",
              question_id: "q1",
              question_version_id: "qv1",
              question_code: "1",
              disposition: "ANSWERED",
              mapping_state: "PROPOSED",
              mapped_by: "HUMAN",
              mapping_confidence: 0,
              region_ids: ["r-new"],
              confirmed_by: null,
              confirmed_at: null,
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          );
        }
        if (path.includes("/confirm") && init?.method === "POST") {
          return new Response(
            JSON.stringify({
              id: "m1",
              question_id: "q1",
              question_version_id: "qv1",
              question_code: "1",
              disposition: "ANSWERED",
              mapping_state: "CONFIRMED",
              mapped_by: "HUMAN",
              mapping_confidence: 0,
              region_ids: ["r-new"],
              confirmed_by: "u1",
              confirmed_at: "2026-09-06T12:00:00Z",
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          );
        }
        if (path.includes("/mapping/finalize")) {
          return new Response(
            JSON.stringify({
              id: "11111111-1111-4111-8111-111111111111",
              tenant_id: "22222222-2222-4222-8222-222222222222",
              assessment_id: "33333333-3333-4333-8333-333333333333",
              workflow_state: "READY_FOR_EVALUATION",
              student_match_state: "CONFIRMED",
              identity_confidence: 1,
              mapping_confidence: 0,
              page_count: 1,
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          );
        }
        if (path.includes("/mapping/prepare")) {
          return new Response(
            JSON.stringify({
              id: "11111111-1111-4111-8111-111111111111",
              tenant_id: "22222222-2222-4222-8222-222222222222",
              assessment_id: "33333333-3333-4333-8333-333333333333",
              workflow_state: "PROCESSING",
              student_match_state: "CONFIRMED",
              identity_confidence: 1,
              mapping_confidence: 0,
              page_count: 1,
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          );
        }
        if (path.endsWith("/mapping") && (!init?.method || init.method === "GET")) {
          return new Response(
            JSON.stringify({
              submission: {
                id: "11111111-1111-4111-8111-111111111111",
                tenant_id: "22222222-2222-4222-8222-222222222222",
                assessment_id: "33333333-3333-4333-8333-333333333333",
                workflow_state: "MAPPING_REVIEW",
                student_match_state: "CONFIRMED",
                identity_confidence: 1,
                mapping_confidence: 0,
                page_count: 1,
              },
              pages: [],
              regions: [],
              questions: [],
              mapping: [],
              mappings: [],
              completion: {
                leaf_total: 0,
                confirmed_count: 0,
                unresolved_question_codes: [],
              },
              automated_mapping_active: false,
              automated_region_detection_active: false,
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          );
        }
        return new Response("{}", {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }),
    );

    const sid = "11111111-1111-4111-8111-111111111111";
    await MappingHttpApi.prepareMappingReview(sid);
    await MappingHttpApi.getMappingReview(sid);
    await MappingHttpApi.createAnswerRegion("p1", {
      label: "Answer region",
      region_type: "ANSWER",
      bbox: { x: 0.1, y: 0.1, width: 0.3, height: 0.2 },
    });
    await MappingHttpApi.upsertQuestionMapping(sid, "qv1", {
      disposition: "ANSWERED",
      region_ids: ["r-new"],
    });
    await MappingHttpApi.confirmQuestionMapping(sid, "qv1");
    const finalized = await MappingHttpApi.finalizeMappingReview(sid);

    expect(calls.map((c) => c.url)).toEqual(
      expect.arrayContaining([
        expect.stringContaining(`/api/v1/submissions/${sid}/mapping/prepare`),
        expect.stringContaining(`/api/v1/submissions/${sid}/mapping`),
        expect.stringContaining("/api/v1/submission-pages/p1/answer-regions"),
        expect.stringContaining(
          `/api/v1/submissions/${sid}/question-mappings/qv1`,
        ),
        expect.stringContaining(
          `/api/v1/submissions/${sid}/question-mappings/qv1/confirm`,
        ),
        expect.stringContaining(`/api/v1/submissions/${sid}/mapping/finalize`),
      ]),
    );

    const createCall = calls.find((c) =>
      c.url.includes("/answer-regions"),
    );
    expect(JSON.parse(String(createCall?.init?.body))).toMatchObject({
      label: "Answer region",
      region_type: "ANSWER",
      bbox: { x: 0.1, y: 0.1, width: 0.3, height: 0.2 },
    });

    const upsertCall = calls.find(
      (c) =>
        c.url.includes("/question-mappings/qv1") &&
        !c.url.includes("/confirm") &&
        c.init?.method === "PUT",
    );
    expect(JSON.parse(String(upsertCall?.init?.body))).toMatchObject({
      disposition: "ANSWERED",
      region_ids: ["r-new"],
    });

    expect(finalized.workflow_state).toBe("READY_FOR_EVALUATION");
  });
});

describe("B4 API capabilities", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("marks mapping live in hybrid while evaluation stays mock", () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "hybrid");
    const caps = getApiCapabilities();
    expect(caps.submissions).toBe("live");
    expect(caps.identityReview).toBe("live");
    expect(caps.mapping).toBe("live");
    expect(caps.evaluation).toBe("mock");
    expect(caps.reports).toBe("mock");
    expect(caps.analytics).toBe("mock");
    expect(caps.learning).toBe("mock");
  });
});
