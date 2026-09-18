import { afterEach, describe, expect, it, vi } from "vitest";
import { assessmentApiToView, assessmentFormToApi } from "@/lib/api/mappers/authoring";
import {
  submissionApiToView,
  type B3SubmissionDto,
} from "@/lib/api/http/submissions";
import {
  transcriptionWorkspaceApiToView,
  type B5TranscriptionWorkspaceDto,
} from "@/lib/api/http/transcription";
import { HybridEduVijnaApi } from "@/lib/api/hybrid/adapter";
import { ApiError } from "@/lib/api/http/errors";
import {
  B20_ERROR_CODES,
  isAutomationBlocked,
  isMathVerificationEligible,
  languageStateLabel,
  subjectProfileLabel,
} from "@/lib/b20/context";

describe("B20 subject profile mappers", () => {
  it("maps assessment subject_node_id as the canonical subject anchor", () => {
    const view = assessmentApiToView({
      id: "a1",
      tenant_id: "t1",
      curriculum_id: "c1",
      subject_node_id: "node-physics",
      subject_profile: "PHYSICS",
      subject_node_code: "PHY",
      subject_node_name: "Physics",
      math_verification_eligible: false,
      code: "PHY-1",
      title: "Forces",
      assessment_type: "EXAM",
      max_marks: "20.00",
      status: "ACTIVE",
    });
    expect(view.subject_node_id).toBe("node-physics");
    expect(view.subject_profile).toBe("PHYSICS");
    expect(view.subject).toBe("Physics");
    expect(view.math_verification_eligible).toBe(false);
    expect(isMathVerificationEligible(view.subject_profile)).toBe(false);
  });

  it("does not invent Mathematics for an unspecified legacy assessment", () => {
    const view = assessmentApiToView({
      id: "a2",
      tenant_id: "t1",
      curriculum_id: "c1",
      code: "LEGACY",
      title: "Legacy",
      assessment_type: "EXAM",
      max_marks: "10.00",
      status: "DRAFT",
    });
    expect(view.subject_profile).toBeUndefined();
    expect(subjectProfileLabel(view.subject_profile)).toBe("Unspecified");
  });

  it("treats a present unknown subject profile as unsupported, not Math-eligible", () => {
    const view = assessmentApiToView({
      id: "a3",
      tenant_id: "t1",
      curriculum_id: "c1",
      subject_node_id: "node-astronomy",
      subject_profile: "UNSUPPORTED",
      subject_node_code: "ASTRONOMY",
      subject_node_name: "Astronomy",
      math_verification_eligible: false,
      code: "ASTRO-1",
      title: "Astronomy",
      assessment_type: "EXAM",
      max_marks: "10.00",
      status: "ACTIVE",
    });
    expect(view.subject_node_id).toBe("node-astronomy");
    expect(view.subject_profile).toBe("UNSUPPORTED");
    expect(view.math_verification_eligible).toBe(false);
    expect(isMathVerificationEligible(view.subject_profile)).toBe(false);
    expect(B20_ERROR_CODES.LANGUAGE_CONTEXT_LOCKED).toBe("LANGUAGE_CONTEXT_LOCKED");
  });

  it("sends subject_node_id on create and never a disconnected subject store id", () => {
    expect(
      assessmentFormToApi({
        curriculumId: "c1",
        subjectNodeId: "node-math",
        code: "M1",
        title: "Math",
        assessmentType: "EXAM",
        maxMarks: 40,
      }),
    ).toMatchObject({
      curriculum_id: "c1",
      subject_node_id: "node-math",
    });
  });
});

describe("B20 language/script API models", () => {
  const dto: B3SubmissionDto = {
    id: "11111111-1111-4111-8111-111111111111",
    tenant_id: "22222222-2222-4222-8222-222222222222",
    assessment_id: "33333333-3333-4333-8333-333333333333",
    workflow_state: "READY_FOR_EVALUATION",
    student_match_state: "CONFIRMED",
    language_code: "hi",
    script_code: "Deva",
    language_source: "PROVIDED",
    language_confidence: null,
    language_state: "CONFIRMED",
    subject_context: {
      subject_profile: "MATHEMATICS",
      subject_node_id: "node-math",
      math_verification_eligible: true,
    },
    language_context: {
      language_code: "hi",
      script_code: "Deva",
      language_source: "PROVIDED",
      language_confidence: null,
      language_state: "CONFIRMED",
    },
  };

  it("round-trips language, script, provenance, and keeps language confidence separate", () => {
    const view = submissionApiToView(dto);
    expect(view.language_code).toBe("hi");
    expect(view.script_code).toBe("Deva");
    expect(view.language_source).toBe("PROVIDED");
    expect(view.language_confidence).toBeNull();
    expect(view.language_state).toBe("CONFIRMED");
    expect(view.subject_context?.subject_profile).toBe("MATHEMATICS");
  });

  it("maps unsupported/review-required states without treating them as confirmed", () => {
    const unsupported = submissionApiToView({
      ...dto,
      language_code: "ja",
      script_code: "Jpan",
      language_state: "UNSUPPORTED",
      automation_block_code: B20_ERROR_CODES.LANGUAGE_UNSUPPORTED,
      language_context: {
        language_code: "ja",
        script_code: "Jpan",
        language_source: "PROVIDED",
        language_confidence: 0.2,
        language_state: "UNSUPPORTED",
      },
    });
    expect(unsupported.language_state).toBe("UNSUPPORTED");
    expect(unsupported.automation_block_code).toBe("LANGUAGE_UNSUPPORTED");
    expect(isAutomationBlocked(unsupported.automation_block_code)).toBe(true);
    expect(languageStateLabel(unsupported.language_state)).toBe("Unsupported");
  });
});

describe("B20 transcription workspace original vs derived", () => {
  const workspace: B5TranscriptionWorkspaceDto = {
    submission_id: "11111111-1111-4111-8111-111111111111",
    workflow_state: "READY_FOR_EVALUATION",
    transcription_state: "REVIEW_REQUIRED",
    automated_transcription_active: true,
    subject_context: {
      subject_profile: "MATHEMATICS",
      math_verification_eligible: true,
    },
    language_context: {
      language_code: "hi",
      script_code: "Deva",
      language_source: "PROVIDED",
      language_confidence: null,
      language_state: "CONFIRMED",
    },
    progress: { reviewed: 0, required: 1, label: "0 of 1" },
    items: [
      {
        question_version_id: "q1",
        question_label: "Q1",
        disposition: "ANSWERED",
        mapping_state: "CONFIRMED",
        requires_transcription: true,
        regions: [
          {
            id: "r1",
            label: "Answer",
            detection_confidence: 0.8,
            bbox: { x: 0, y: 0, width: 1, height: 1 },
            latest_ai_proposal: {
              id: "tx1",
              answer_region_id: "r1",
              version_number: 1,
              source_type: "AI",
              text: "हिंदी में हल: क्षेत्रफल = लंबाई × चौड़ाई",
              unreadable: false,
              visual_only: false,
              status: "PROPOSED",
              transcription_confidence: 0.81,
              derived_texts: [
                {
                  id: "d1",
                  source_transcription_id: "tx1",
                  kind: "TRANSLATION",
                  text: "Solution in Hindi: area = length × width",
                  source_language_code: "hi",
                  target_language_code: "en",
                  status: "PROPOSED",
                },
              ],
            },
            active_transcription: {
              id: "tx1",
              answer_region_id: "r1",
              version_number: 1,
              source_type: "AI",
              text: "हिंदी में हल: क्षेत्रफल = लंबाई × चौड़ाई",
              unreadable: false,
              visual_only: false,
              status: "PROPOSED",
              derived_texts: [
                {
                  id: "d1",
                  source_transcription_id: "tx1",
                  kind: "TRANSLATION",
                  text: "Solution in Hindi: area = length × width",
                  source_language_code: "hi",
                  target_language_code: "en",
                  status: "PROPOSED",
                },
              ],
            },
            requires_transcription: true,
          },
        ],
      },
    ],
  };

  it("keeps original text distinct from linked translation", () => {
    const view = transcriptionWorkspaceApiToView(workspace);
    const active = view.items[0]?.regions[0]?.active_transcription;
    expect(active?.text).toBe("हिंदी में हल: क्षेत्रफल = लंबाई × चौड़ाई");
    expect(active?.derived_texts?.[0]?.kind).toBe("TRANSLATION");
    expect(active?.derived_texts?.[0]?.source_transcription_id).toBe("tx1");
    expect(active?.derived_texts?.[0]?.text).not.toBe(active?.text);
    expect(view.language_context?.language_code).toBe("hi");
    expect(view.subject_context?.subject_profile).toBe("MATHEMATICS");
  });
});

describe("B20 hybrid live UUID failure", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("does not silently fall back to mock for a live UUID", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "hybrid");
    const fetchMock = vi.fn().mockImplementation(
      async () =>
        new Response(
          JSON.stringify({ detail: { code: "NOT_FOUND", message: "not found" } }),
          { status: 404, headers: { "Content-Type": "application/json" } },
        ),
    );
    vi.stubGlobal("fetch", fetchMock);
    await expect(
      HybridEduVijnaApi.getTranscriptionWorkspace(
        "11111111-1111-4111-8111-111111111111",
      ),
    ).rejects.toBeInstanceOf(ApiError);
    expect(fetchMock).toHaveBeenCalled();
    await expect(
      HybridEduVijnaApi.getSubmission("11111111-1111-4111-8111-111111111111"),
    ).rejects.toBeInstanceOf(ApiError);
  });
});
