import { afterEach, describe, expect, it, vi } from "vitest";
import { getApiCapabilities } from "@/lib/api/capabilities";
import { HybridEduVijnaApi } from "@/lib/api/hybrid/adapter";
import {
  AUTHORING_AI_RUN_STATUSES,
  ASSESSMENT_ARTIFACT_SCAN_STATUSES,
} from "@/lib/types/enums";

const versionId = "11111111-1111-4111-8111-111111111111";
const runId = "22222222-2222-4222-8222-222222222222";
const assessmentId = "33333333-3333-4333-8333-333333333333";
const questionId = "44444444-4444-4444-8444-444444444444";
const answerKeyVersionId = "55555555-5555-4555-8555-555555555555";
const rubricVersionId = "66666666-6666-4666-8666-666666666666";

const proposedRoots = [
  {
    stable_code: "Q1",
    display_label: "1",
    sequence: 1,
    prompt_text: "Section 1",
    max_marks: "10.00",
    question_type: "SECTION",
    scoring_mode: "CONTAINER_DERIVED",
    children: [
      {
        stable_code: "Q1a",
        display_label: "1(a)",
        sequence: 1,
        prompt_text: "Leaf prompt",
        max_marks: "10.00",
        question_type: "STRUCTURED",
        scoring_mode: "LEAF_SCORABLE",
        children: [],
      },
    ],
  },
];

const artifactDto = {
  id: "77777777-7777-4777-8777-777777777777",
  tenant_id: "88888888-8888-4888-8888-888888888888",
  assessment_id: assessmentId,
  artifact_type: "QUESTION_PAPER",
  original_filename: "b10-paper.pdf",
  mime_type: "application/pdf",
  byte_size: 2048,
  content_sha256: "a".repeat(64),
  storage_key: "tenant/assessment/paper.pdf",
  security_scan_status: "CLEAN",
  uploaded_by: null,
  uploaded_at: "2026-09-07T00:00:00Z",
  created_at: "2026-09-07T00:00:00Z",
};

const reviewRunDto = {
  id: runId,
  tenant_id: "88888888-8888-4888-8888-888888888888",
  assessment_id: assessmentId,
  assessment_version_id: versionId,
  question_version_id: null,
  assessment_artifact_id: artifactDto.id,
  operation: "PARSE_QUESTION_PAPER",
  status: "REVIEW_REQUIRED",
  input_hash: "b".repeat(64),
  proposal_payload: { roots: proposedRoots, notes: "fixed" },
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

describe("B10 authoring capability", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("marks assessments live in hybrid", () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "hybrid");
    expect(getApiCapabilities().assessments).toBe("live");
    expect(getApiCapabilities().curriculum).toBe("live");
  });

  it("includes authoring AI and artifact scan statuses", () => {
    expect(AUTHORING_AI_RUN_STATUSES).toContain("QUEUED");
    expect(AUTHORING_AI_RUN_STATUSES).toContain("RUNNING");
    expect(AUTHORING_AI_RUN_STATUSES).toContain("REVIEW_REQUIRED");
    expect(AUTHORING_AI_RUN_STATUSES).toContain("SUCCEEDED");
    expect(ASSESSMENT_ARTIFACT_SCAN_STATUSES).toContain("CLEAN");
    expect(ASSESSMENT_ARTIFACT_SCAN_STATUSES).toContain("REJECTED");
  });
});

describe("B10 hybrid authoring routing", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("uploads question paper, parses to review, edits, and applies", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "hybrid");
    const fetchMock = vi
      .fn()
      .mockImplementation(async (input: RequestInfo, init?: RequestInit) => {
        const url = String(input);
        const method = (init?.method ?? "GET").toUpperCase();

        if (url.includes(`/assessment-versions/${versionId}/question-paper`) &&
          !url.includes("/parse") &&
          method === "POST") {
          return new Response(JSON.stringify(artifactDto), {
            status: 201,
            headers: { "Content-Type": "application/json" },
          });
        }
        if (
          url.includes(`/assessment-versions/${versionId}/question-paper/parse`) &&
          method === "POST"
        ) {
          return new Response(JSON.stringify(reviewRunDto), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }
        if (
          url.includes(`/authoring-ai-runs/${runId}/question-tree-proposal`) &&
          method === "PUT"
        ) {
          const body = JSON.parse(String(init?.body ?? "{}")) as {
            roots: typeof proposedRoots;
          };
          return new Response(
            JSON.stringify({
              ...reviewRunDto,
              proposal_payload: {
                roots: body.roots,
                notes: "teacher edit",
              },
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          );
        }
        if (
          url.includes(`/authoring-ai-runs/${runId}/apply-question-tree`) &&
          method === "POST"
        ) {
          return new Response(
            JSON.stringify({ ...reviewRunDto, status: "SUCCEEDED" }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          );
        }
        if (url.includes(`/authoring-ai-runs/${runId}`) && method === "GET") {
          return new Response(JSON.stringify(reviewRunDto), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        }
        return new Response(JSON.stringify({ detail: "unexpected" }), {
          status: 500,
        });
      });
    vi.stubGlobal("fetch", fetchMock);

    const file = new File([new Uint8Array([1, 2, 3])], "b10-paper.pdf", {
      type: "application/pdf",
    });
    const uploaded = await HybridEduVijnaApi.uploadQuestionPaper!(versionId, file);
    expect(uploaded.original_filename).toBe("b10-paper.pdf");
    expect(uploaded.security_scan_status).toBe("CLEAN");

    const prepared = await HybridEduVijnaApi.prepareQuestionPaperParse!(versionId);
    expect(prepared.status).toBe("REVIEW_REQUIRED");
    expect(prepared.proposal_payload?.roots?.[0]?.stable_code).toBe("Q1");

    const editedRoots = structuredClone(proposedRoots);
    editedRoots[0]!.children![0]!.prompt_text = "Corrected leaf prompt";
    const updated = await HybridEduVijnaApi.updateQuestionTreeProposal!(runId, {
      roots: editedRoots,
      notes: "teacher edit",
    });
    expect(
      updated.proposal_payload?.roots?.[0]?.children?.[0]?.prompt_text,
    ).toBe("Corrected leaf prompt");

    const applied = await HybridEduVijnaApi.applyQuestionTreeProposal!(runId);
    expect(applied.status).toBe("SUCCEEDED");

    const urls = fetchMock.mock.calls.map((call) => String(call[0]));
    expect(urls.some((u) => u.includes("/question-paper") && !u.includes("/parse"))).toBe(
      true,
    );
    expect(urls.some((u) => u.includes("/question-paper/parse"))).toBe(true);
    expect(urls.some((u) => u.includes("/apply-question-tree"))).toBe(true);
  });

  it("keeps AI answer-key and rubric provenance as review until approve", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "hybrid");
    const fetchMock = vi
      .fn()
      .mockImplementation(async (input: RequestInfo, init?: RequestInit) => {
        const url = String(input);
        const method = (init?.method ?? "GET").toUpperCase();

        if (url.includes("/ai/proposals/answer-key") && method === "POST") {
          return new Response(
            JSON.stringify({
              ...reviewRunDto,
              id: runId,
              operation: "PROPOSE_ANSWER_KEY",
              status: "REVIEW_REQUIRED",
              question_version_id: questionId,
              answer_key_version_id: answerKeyVersionId,
              proposal_payload: { answer_text_length: 20 },
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          );
        }
        if (url.includes("/ai/proposals/rubric") && method === "POST") {
          return new Response(
            JSON.stringify({
              ...reviewRunDto,
              id: runId,
              operation: "PROPOSE_RUBRIC",
              status: "REVIEW_REQUIRED",
              question_version_id: questionId,
              rubric_version_id: rubricVersionId,
              proposal_payload: {},
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          );
        }
        if (
          url.includes(`/answer-key-versions/${answerKeyVersionId}/approve`) &&
          method === "POST"
        ) {
          return new Response(
            JSON.stringify({
              id: answerKeyVersionId,
              source_type: "AI_PROPOSED",
              status: "APPROVED",
              question_version_id: questionId,
              answer_text: "Model answer",
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          );
        }
        if (
          url.includes(`/rubric-versions/${rubricVersionId}/approve`) &&
          method === "POST"
        ) {
          return new Response(
            JSON.stringify({
              id: rubricVersionId,
              source_type: "AI_PROPOSED",
              status: "APPROVED",
              question_version_id: questionId,
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          );
        }
        return new Response(JSON.stringify({ detail: "unexpected" }), {
          status: 500,
        });
      });
    vi.stubGlobal("fetch", fetchMock);

    const akRun = await HybridEduVijnaApi.prepareAiAnswerKeyProposal!({
      questionVersionId: questionId,
      assessmentVersionId: versionId,
    });
    expect(akRun.status).toBe("REVIEW_REQUIRED");
    expect(akRun.answer_key_version_id).toBe(answerKeyVersionId);
    expect(akRun.status).not.toBe("APPROVED");

    const rubRun = await HybridEduVijnaApi.prepareAiRubricProposal!({
      questionVersionId: questionId,
      assessmentVersionId: versionId,
    });
    expect(rubRun.status).toBe("REVIEW_REQUIRED");
    expect(rubRun.rubric_version_id).toBe(rubricVersionId);

    const approvedKey = await HybridEduVijnaApi.approveAnswerKey!(
      answerKeyVersionId,
    );
    expect(approvedKey.status).toBe("APPROVED");
    expect(approvedKey.source_type).toBe("AI_PROPOSED");

    const approvedRubric = await HybridEduVijnaApi.approveRubric!(
      rubricVersionId,
    );
    expect(approvedRubric.status).toBe("APPROVED");
  });

  it("surfaces live authoring HTTP errors without mock fallback", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "hybrid");
    const fetchMock = vi.fn().mockImplementation(async () =>
      new Response(
        JSON.stringify({
          detail: {
            code: "QUESTION_PAPER_STRUCTURE_EXISTS",
            message: "Assessment version already has questions",
          },
        }),
        { status: 409, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      HybridEduVijnaApi.prepareQuestionPaperParse!(versionId),
    ).rejects.toMatchObject({
      name: "ApiError",
      code: "QUESTION_PAPER_STRUCTURE_EXISTS",
    });
  });
});
