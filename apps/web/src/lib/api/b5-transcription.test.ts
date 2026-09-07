import { afterEach, describe, expect, it, vi } from "vitest";
import {
  regionTranscriptionApiToView,
  transcriptionRegionApiToView,
  transcriptionWorkspaceApiToView,
  TranscriptionHttpApi,
  type B5TranscriptionWorkspaceDto,
} from "@/lib/api/http/transcription";
import { getApiCapabilities } from "@/lib/api/capabilities";
import { HybridEduVijnaApi } from "@/lib/api/hybrid/adapter";
import { ApiError } from "@/lib/api/http/errors";

describe("B5 transcription mappers", () => {
  const workspace: B5TranscriptionWorkspaceDto = {
    submission_id: "11111111-1111-4111-8111-111111111111",
    workflow_state: "READY_FOR_EVALUATION",
    transcription_state: "REVIEW_REQUIRED",
    automated_transcription_active: true,
    progress: {
      reviewed: 1,
      required: 2,
      label: "1 of 2 evidence regions reviewed",
    },
    items: [
      {
        question_version_id: "qv1",
        question_label: "Q1",
        disposition: "ANSWERED",
        mapping_state: "CONFIRMED",
        requires_transcription: true,
        regions: [
          {
            id: "r1",
            label: "Answer",
            region_type: "ANSWER",
            source_type: "AI",
            detection_confidence: 0.88,
            bbox: { x: 0.1, y: 0.2, width: 0.3, height: 0.15 },
            crop_url: "/api/v1/answer-regions/r1/crop",
            page_index: 0,
            latest_ai_proposal: {
              id: "tx1",
              answer_region_id: "r1",
              version_number: 1,
              source_type: "AI",
              text: "x = 4",
              latex: null,
              transcription_confidence: 0.76,
              unreadable: false,
              visual_only: false,
              status: "PROPOSED",
            },
            active_transcription: {
              id: "tx1",
              answer_region_id: "r1",
              version_number: 1,
              source_type: "AI",
              text: "x = 4",
              latex: null,
              transcription_confidence: 0.76,
              unreadable: false,
              visual_only: false,
              status: "PROPOSED",
            },
            requires_transcription: true,
          },
        ],
      },
    ],
  };

  it("maps transcription workspace with progress and AI proposals", () => {
    const view = transcriptionWorkspaceApiToView(workspace);
    expect(view.transcription_state).toBe("REVIEW_REQUIRED");
    expect(view.progress).toMatchObject({
      reviewed: 1,
      required: 2,
      label: "1 of 2 evidence regions reviewed",
    });
    expect(view.items[0]?.regions[0]).toMatchObject({
      id: "r1",
      crop_url: "/api/v1/answer-regions/r1/crop",
      detection_confidence: 0.88,
      source_type: "AI",
    });
    expect(view.items[0]?.regions[0]?.latest_ai_proposal?.text).toBe("x = 4");
  });

  it("maps region transcription confidence from string decimals", () => {
    expect(
      regionTranscriptionApiToView({
        id: "tx1",
        answer_region_id: "r1",
        version_number: 1,
        source_type: "AI",
        text: "a",
        unreadable: false,
        visual_only: false,
        status: "PROPOSED",
        transcription_confidence: "0.8200",
      }),
    ).toMatchObject({ transcription_confidence: 0.82 });
  });

  it("maps region bbox and crop path", () => {
    expect(
      transcriptionRegionApiToView({
        id: "r1",
        label: "Ans",
        bbox: { x: 0.2, y: 0.3, width: 0.4, height: 0.1 },
        crop_url: "/api/v1/answer-regions/r1/crop",
      }),
    ).toMatchObject({
      bbox: { x: 0.2, y: 0.3, width: 0.4, height: 0.1 },
      crop_url: "/api/v1/answer-regions/r1/crop",
    });
  });
});

describe("B5 TranscriptionHttpApi request shapes", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("posts prepare / put / confirm / finalize with expected paths", async () => {
    const calls: Array<{ url: string; init?: RequestInit }> = [];
    const sid = "11111111-1111-4111-8111-111111111111";

    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        calls.push({ url: String(url), init });
        const path = String(url);

        if (path.includes("/transcription/prepare")) {
          return new Response(
            JSON.stringify({
              submission_id: sid,
              workflow_state: "READY_FOR_EVALUATION",
              transcription_state: "QUEUED",
              job_id: "job-1",
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          );
        }
        if (path.endsWith(`/submissions/${sid}`) && (!init?.method || init.method === "GET")) {
          return new Response(
            JSON.stringify({
              id: sid,
              tenant_id: "t1",
              assessment_id: "a1",
              workflow_state: "READY_FOR_EVALUATION",
              student_match_state: "CONFIRMED",
              identity_confidence: 1,
              mapping_confidence: 0,
              transcription_state: "QUEUED",
              page_count: 1,
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          );
        }
        if (path.endsWith("/transcription") && (!init?.method || init.method === "GET")) {
          return new Response(
            JSON.stringify({
              submission_id: sid,
              workflow_state: "READY_FOR_EVALUATION",
              transcription_state: "REVIEW_REQUIRED",
              automated_transcription_active: true,
              progress: { reviewed: 0, required: 1 },
              items: [],
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          );
        }
        if (path.includes("/answer-regions/r1/transcription") && init?.method === "PUT") {
          return new Response(
            JSON.stringify({
              id: "tx-human",
              answer_region_id: "r1",
              version_number: 2,
              source_type: "HUMAN",
              text: "corrected",
              unreadable: false,
              visual_only: false,
              status: "REVIEW_REQUIRED",
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          );
        }
        if (path.includes("/answer-region-transcriptions/tx1/confirm")) {
          return new Response(
            JSON.stringify({
              id: "tx1",
              answer_region_id: "r1",
              version_number: 1,
              source_type: "HUMAN",
              text: "confirmed",
              transcription_confidence: 0.9,
              unreadable: false,
              visual_only: false,
              status: "CONFIRMED",
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          );
        }
        if (path.includes("/transcription/finalize")) {
          return new Response(
            JSON.stringify({
              submission_id: sid,
              workflow_state: "READY_FOR_EVALUATION",
              transcription_state: "READY",
              evaluation_enqueued: false,
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

    await TranscriptionHttpApi.prepareTranscription(sid);
    await TranscriptionHttpApi.getTranscriptionWorkspace(sid);
    await TranscriptionHttpApi.putRegionTranscription("r1", { text: "corrected" });
    await TranscriptionHttpApi.confirmTranscription("tx1");
    const finalized = await TranscriptionHttpApi.finalizeTranscription(sid);

    expect(calls.map((c) => c.url)).toEqual(
      expect.arrayContaining([
        expect.stringContaining(`/api/v1/submissions/${sid}/transcription/prepare`),
        expect.stringContaining(`/api/v1/submissions/${sid}/transcription`),
        expect.stringContaining("/api/v1/answer-regions/r1/transcription"),
        expect.stringContaining("/api/v1/answer-region-transcriptions/tx1/confirm"),
        expect.stringContaining(`/api/v1/submissions/${sid}/transcription/finalize`),
      ]),
    );

    const putCall = calls.find((c) => c.url.includes("/answer-regions/r1/transcription"));
    expect(JSON.parse(String(putCall?.init?.body))).toMatchObject({
      text: "corrected",
    });
    expect(finalized.transcription_state).toBe("READY");
  });
});

describe("B5 hybrid adapter guards", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("routes live evaluation for live submission UUIDs in hybrid", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "hybrid");
    const fetchMock = vi.fn().mockImplementation(
      async () =>
        new Response(
          JSON.stringify({
            detail: { code: "NOT_FOUND", message: "not found" },
          }),
          { status: 404, headers: { "Content-Type": "application/json" } },
        ),
    );
    vi.stubGlobal("fetch", fetchMock);
    await expect(
      HybridEduVijnaApi.getEvaluationWorkspace(
        "11111111-1111-4111-8111-111111111111",
      ),
    ).rejects.toBeInstanceOf(ApiError);
    expect(fetchMock).toHaveBeenCalled();
  });
});

describe("B5 API capabilities", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("marks transcription and evaluation live in hybrid", () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "hybrid");
    const caps = getApiCapabilities();
    expect(caps.transcription).toBe("live");
    expect(caps.evaluation).toBe("live");
    expect(caps.mapping).toBe("live");
  });

  it("keeps transcription mock in default mock mode", () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "mock");
    const caps = getApiCapabilities();
    expect(caps.transcription).toBe("mock");
  });
});
