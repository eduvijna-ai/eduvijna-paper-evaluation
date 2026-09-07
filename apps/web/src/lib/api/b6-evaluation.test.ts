import { afterEach, describe, expect, it, vi } from "vitest";
import {
  questionEvaluationApiToView,
  type B6QuestionEvaluationDto,
} from "@/lib/api/http/evaluation";
import { getApiCapabilities } from "@/lib/api/capabilities";
import { HybridEduVijnaApi } from "@/lib/api/hybrid/adapter";
import { ApiError } from "@/lib/api/http/errors";
import {
  formatCriterionMarks,
  formatProposedScoreLabel,
  formatScorePair,
  NO_PROPOSAL_SCORE_MESSAGE,
  resolveDisplayScore,
} from "@/lib/helpers/score";
import {
  canAcceptProposedScore,
  canApproveEvaluation,
  countFinalizedQuestions,
  isLiveDisabledTeacherAction,
  validateOverrideReason,
  applyTeacherReviewAction,
} from "@/lib/helpers/teacher-actions";
import { EVALUATION_WORKFLOW_STATES } from "@/lib/types/enums";

const sampleQe: B6QuestionEvaluationDto = {
  id: "qe-1",
  evaluation_run_id: "run-1",
  submission_id: "11111111-1111-4111-8111-111111111111",
  assessment_id: "asm-1",
  assessment_version_id: "av-1",
  question_id: "q-logical",
  question_version_id: "qv-1",
  rubric_version_id: "rv-1",
  answer_key_version_id: "ak-1",
  answer_region_ids: ["r1"],
  max_mark: "5.00",
  proposed_ai_score: "3.50",
  final_human_approved_score: null,
  ecf_applied: false,
  error_codes: ["CALCULATION"],
  criterion_decisions: [
    {
      rubric_criterion_id: "c1",
      criterion_label: "Setup",
      max_marks: 5,
      proposed_marks: "3.50",
      final_marks: null,
      decision: "PARTIAL",
      error_code: "CALCULATION",
      deduction_reason: "Arithmetic slip",
      step_index: 1,
    },
  ],
  identity_confidence: "0.91",
  mapping_confidence: "0.80",
  transcription_confidence: "0.70",
  evaluation_confidence: "0.60",
  math_verification_confidence: "0.85",
  workflow_state: "REVIEW_REQUIRED",
  ledger_version: 1,
};

describe("B6 evaluation capability", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("marks evaluation, publication, reports, analytics, and learning live in hybrid", () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "hybrid");
    const caps = getApiCapabilities();
    expect(caps.evaluation).toBe("live");
    expect(caps.transcription).toBe("live");
    expect(caps.publication).toBe("live");
    expect(caps.reports).toBe("live");
    expect(caps.analytics).toBe("live");
    expect(caps.learning).toBe("live");
  });

  it("keeps evaluation mock in default mock mode", () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "mock");
    expect(getApiCapabilities().evaluation).toBe("mock");
  });

  it("includes ESCALATED in evaluation workflow states", () => {
    expect(EVALUATION_WORKFLOW_STATES).toContain("ESCALATED");
  });
});

describe("B6 question evaluation mapper", () => {
  it("maps DTO to ledger with confidence dimensions and math summary", () => {
    const ledger = questionEvaluationApiToView(sampleQe);
    expect(ledger.question_id).toBe("qv-1");
    expect(ledger.proposed_ai_score).toBe(3.5);
    expect(ledger.identity_confidence).toBe(0.91);
    expect(ledger.mapping_confidence).toBe(0.8);
    expect(ledger.math_verification_summary).toMatch(/85%/);
    expect(ledger.score_sources).toEqual({
      ai_proposal: true,
      deterministic_verification: true,
      human_final: false,
    });
    expect(ledger.criterion_decisions[0]?.proposed_marks).toBe(3.5);
  });

  it("preserves null proposed score (unreadable) without coercing to zero", () => {
    const ledger = questionEvaluationApiToView({
      ...sampleQe,
      proposed_ai_score: null,
      evaluation_confidence: null,
      math_verification_confidence: null,
      error_codes: ["UNREADABLE"],
      criterion_decisions: [
        {
          rubric_criterion_id: "c1",
          criterion_label: "Setup",
          max_marks: 5,
          proposed_marks: null,
          final_marks: null,
          decision: "UNREADABLE",
          error_code: "UNREADABLE",
          deduction_reason: null,
          step_index: 0,
        },
      ],
    });
    expect(ledger.proposed_ai_score).toBeNull();
    expect(ledger.proposed_ai_score).not.toBe(0);
    expect(ledger.criterion_decisions[0]?.proposed_marks).toBeNull();
    expect(ledger.score_sources?.ai_proposal).toBe(false);
    expect(formatProposedScoreLabel(ledger.proposed_ai_score, 5)).toBe(
      NO_PROPOSAL_SCORE_MESSAGE,
    );
    expect(formatScorePair(ledger.proposed_ai_score, 5)).toBe("— / 5");
    expect(formatCriterionMarks(null)).toBe("—");
  });
});

describe("B6 score display helpers", () => {
  it("does not display null proposed as zero", () => {
    expect(resolveDisplayScore(null, null)).toBeNull();
    expect(formatScorePair(null, 4)).toBe("— / 4");
    expect(formatProposedScoreLabel(null, 4)).toBe(NO_PROPOSAL_SCORE_MESSAGE);
    expect(formatProposedScoreLabel(0, 4)).toBe("0 / 4");
  });

  it("prefers human final over proposed", () => {
    expect(resolveDisplayScore(2, 3)).toBe(3);
  });
});

describe("B6 accept / override validation", () => {
  it("disables accept when proposed score is null", () => {
    expect(canAcceptProposedScore(null)).toBe(false);
    expect(canAcceptProposedScore(2)).toBe(true);
    const denied = applyTeacherReviewAction({
      action: "ACCEPT",
      proposedScore: null,
      maxMark: 4,
    });
    expect(denied.workflow_state).toBe("REVIEW_REQUIRED");
    expect(denied.message).toMatch(/no automatic score/i);
  });

  it("requires override reason", () => {
    expect(validateOverrideReason("")).toMatch(/mandatory reason/i);
    expect(validateOverrideReason("  ok  ")).toBeNull();
    const missing = applyTeacherReviewAction({
      action: "CHANGE_SCORE",
      proposedScore: 1,
      maxMark: 4,
      newScore: 2,
    });
    expect(missing.message).toMatch(/mandatory reason/i);
  });

  it("maps CHANGE_SCORE to OVERRIDDEN when reason present", () => {
    const result = applyTeacherReviewAction({
      action: "CHANGE_SCORE",
      proposedScore: 1,
      maxMark: 4,
      newScore: 3,
      feedback: "Teacher correction",
    });
    expect(result.workflow_state).toBe("OVERRIDDEN");
    expect(result.final_human_approved_score).toBe(3);
  });

  it("supports escalate to ESCALATED", () => {
    const result = applyTeacherReviewAction({
      action: "ESCALATE",
      proposedScore: 2,
      maxMark: 4,
      feedback: "Needs senior review",
    });
    expect(result.workflow_state).toBe("ESCALATED");
  });

  it("flags OCR/mapping correction actions as not live", () => {
    expect(isLiveDisabledTeacherAction("OCR_TRANSCRIPTION_ERROR")).toBe(true);
    expect(isLiveDisabledTeacherAction("MAPPING_ERROR")).toBe(true);
    expect(isLiveDisabledTeacherAction("ACCEPT")).toBe(false);
  });
});

describe("B6 approval gate", () => {
  it("requires all ACCEPTED or OVERRIDDEN", () => {
    expect(canApproveEvaluation(["ACCEPTED", "OVERRIDDEN"])).toBe(true);
    expect(canApproveEvaluation(["ACCEPTED", "REVIEW_REQUIRED"])).toBe(false);
    expect(canApproveEvaluation(["ESCALATED"])).toBe(false);
    expect(canApproveEvaluation([])).toBe(false);
    expect(countFinalizedQuestions(["ACCEPTED", "PROPOSED"])).toEqual({
      finalized: 1,
      total: 2,
    });
  });
});

describe("B6 hybrid adapter live routing", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("routes live evaluation methods without mock fallback on HTTP errors", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "hybrid");
    const fetchMock = vi.fn().mockImplementation(
      async () =>
        new Response(
          JSON.stringify({
            detail: { code: "PROVIDER_DOWN", message: "Evaluation unavailable" },
          }),
          { status: 503, headers: { "Content-Type": "application/json" } },
        ),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      HybridEduVijnaApi.getEvaluationWorkspace(
        "11111111-1111-4111-8111-111111111111",
      ),
    ).rejects.toBeInstanceOf(ApiError);

    expect(fetchMock).toHaveBeenCalled();
    const urls = fetchMock.mock.calls.map((c) => String(c[0]));
    expect(urls.some((u) => u.includes("/evaluation"))).toBe(true);
  });

  it("routes live reports and analytics to HTTP and learning to live workspace", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "hybrid");
    const liveId = "22222222-2222-4222-8222-222222222222";
    const fetchMock = vi.fn().mockImplementation(async (input: RequestInfo) => {
      const url = String(input);
      if (url.includes("/learning/")) {
        return new Response(
          JSON.stringify({
            student: {
              id: liveId,
              display_name: "Live Student",
            },
            available_curricula: [],
            selected_curriculum: null,
            materialization_status: "READY",
            evidence_coverage: {
              curriculum_node_count: 0,
              evidence_row_count: 0,
            },
            latest_run: null,
            latest_plan: null,
            is_stale: false,
            latest_improvement_blueprint: null,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      if (url.includes("/analytics/")) {
        return new Response(
          JSON.stringify({
            detail: { code: "NOT_FOUND", message: "No analytics" },
          }),
          { status: 404, headers: { "Content-Type": "application/json" } },
        );
      }
      return new Response(
        JSON.stringify({
          detail: { code: "NOT_FOUND", message: "No published report" },
        }),
        { status: 404, headers: { "Content-Type": "application/json" } },
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      HybridEduVijnaApi.getStudentReport(liveId, liveId),
    ).rejects.toBeInstanceOf(ApiError);
    expect(fetchMock).toHaveBeenCalled();
    const urls = fetchMock.mock.calls.map((c) => String(c[0]));
    expect(urls.some((u) => u.includes("/reports/student/"))).toBe(true);

    await expect(
      HybridEduVijnaApi.getAssessmentAnalytics(liveId),
    ).rejects.toBeInstanceOf(ApiError);
    const analyticsUrls = fetchMock.mock.calls.map((c) => String(c[0]));
    expect(
      analyticsUrls.some((u) => u.includes("/analytics/assessments/")),
    ).toBe(true);

    const workspace = await HybridEduVijnaApi.getLearningWorkspace!(liveId);
    expect(workspace.student.id).toBe(liveId);
    expect(workspace.materialization_status).toBe("READY");
  });

  it("exposes prepareEvaluation and finalizeEvaluation on hybrid client", () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "hybrid");
    expect(typeof HybridEduVijnaApi.prepareEvaluation).toBe("function");
    expect(typeof HybridEduVijnaApi.finalizeEvaluation).toBe("function");
  });
});
