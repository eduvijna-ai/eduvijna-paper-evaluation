import type {
  AnswerKeyStep,
  Assessment,
  CriterionDecisionRow,
  EvaluationLedger,
  EvaluationWorkspacePayload,
  Question,
  RubricCriterion,
  Student,
  Submission,
  TranscriptionWorkspacePayload,
} from "@/lib/types/domain";
import type {
  ErrorCode,
  EvaluationWorkflowState,
  TeacherReviewAction,
} from "@/lib/types/enums";
import {
  applyTeacherReviewAction,
  canAcceptProposedScore,
  isLiveDisabledTeacherAction,
  validateEscalateReason,
  validateOverrideReason,
  type TeacherActionResult,
} from "@/lib/helpers/teacher-actions";
import { ApiError } from "./errors";
import { httpRequest } from "./client";
import { AuthoringHttpApi } from "./authoring";
import { MappingHttpApi } from "./mapping";
import { PlatformHttpApi } from "./platform";
import {
  submissionApiToView,
  type B3SubmissionDto,
} from "./submissions";
import { TranscriptionHttpApi } from "./transcription";

function asNumber(
  value: number | string | null | undefined,
): number | null {
  if (value === null || value === undefined || value === "") return null;
  const n = typeof value === "number" ? value : Number(value);
  return Number.isFinite(n) ? n : null;
}

function asNumberRequired(
  value: number | string | null | undefined,
  fallback = 0,
): number {
  return asNumber(value) ?? fallback;
}

export interface B6CriterionDecisionDto {
  id?: string;
  rubric_criterion_id: string;
  criterion_code?: string;
  criterion_label: string;
  max_marks: number | string;
  proposed_marks?: number | string | null;
  final_marks?: number | string | null;
  decision: string;
  error_code?: string | null;
  deduction_reason?: string | null;
  step_index?: number | null;
  ecf_source_criterion_id?: string | null;
}

export interface B6QuestionEvaluationDto {
  id: string;
  evaluation_run_id: string;
  submission_id: string;
  student_id?: string | null;
  assessment_id?: string;
  assessment_version_id: string;
  question_id?: string;
  question_version_id: string;
  rubric_version_id?: string;
  answer_key_version_id?: string;
  mapping_id?: string | null;
  answer_region_ids?: string[];
  transcription_refs?: Array<Record<string, unknown>>;
  max_mark: number | string;
  proposed_ai_score: number | string | null;
  final_human_approved_score?: number | string | null;
  first_divergence_step?: number | null;
  ecf_applied?: boolean;
  ecf_chain?: Record<string, unknown>;
  alternative_method_id?: string | null;
  alternative_method_label?: string | null;
  error_codes?: string[];
  deduction_reasons?: unknown[];
  criterion_snapshot?: unknown[];
  criterion_decisions?: B6CriterionDecisionDto[];
  identity_confidence?: number | string | null;
  mapping_confidence?: number | string | null;
  transcription_confidence?: number | string | null;
  evaluation_confidence?: number | string | null;
  math_verification_confidence?: number | string | null;
  workflow_state: string;
  ledger_version?: number;
  reviewed_by?: string | null;
  reviewed_at?: string | null;
  reviewer_feedback?: string | null;
  approved_snapshot_hash?: string | null;
}

export interface B6EvaluationRunDto {
  id: string;
  submission_id: string;
  assessment_id?: string;
  assessment_version_id?: string;
  run_number: number;
  status: string;
  provider: string;
  model?: string | null;
  rules_engine_version?: string | null;
  started_by?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  failure_code?: string | null;
  failure_detail?: string | null;
}

export interface B6EvaluationWorkspaceDto {
  submission_id: string;
  workflow_state: string;
  student_match_state?: string;
  transcription_state?: string;
  assessment_version_id?: string;
  evaluation_run: B6EvaluationRunDto | null;
  question_evaluations: B6QuestionEvaluationDto[];
  automated_evaluation_active: boolean;
}

export interface B6PrepareEvaluationDto {
  submission_id: string;
  workflow_state: string;
  evaluation_run_id: string;
  run_status: string;
  job_id?: string | null;
}

export interface B6FinalizeEvaluationDto {
  submission_id: string;
  workflow_state: string;
  evaluation_run_id?: string | null;
  run_status?: string | null;
}

function criterionApiToView(dto: B6CriterionDecisionDto): CriterionDecisionRow {
  return {
    rubric_criterion_id: dto.rubric_criterion_id,
    criterion_label: dto.criterion_label,
    max_marks: asNumberRequired(dto.max_marks),
    proposed_marks: asNumber(dto.proposed_marks),
    final_marks: asNumber(dto.final_marks),
    decision: dto.decision as CriterionDecisionRow["decision"],
    error_code: (dto.error_code as ErrorCode | null) ?? null,
    deduction_reason: dto.deduction_reason ?? null,
    step_index: dto.step_index ?? null,
  };
}

function joinTranscriptionText(
  dto: B6QuestionEvaluationDto,
  transcription: TranscriptionWorkspacePayload | null,
): string | null {
  if (!transcription) return null;
  const regionIds = new Set(dto.answer_region_ids ?? []);
  const qv = dto.question_version_id;
  const parts: string[] = [];
  for (const item of transcription.items) {
    if (item.question_version_id !== qv) continue;
    for (const region of item.regions) {
      if (regionIds.size > 0 && !regionIds.has(region.id)) continue;
      const active = region.active_transcription;
      if (!active) continue;
      if (active.unreadable) {
        parts.push("[unreadable]");
        continue;
      }
      if (active.visual_only) {
        parts.push("[visual only]");
        continue;
      }
      const text = active.text ?? active.latex;
      if (text) parts.push(text);
    }
  }
  return parts.length > 0 ? parts.join("\n") : null;
}

function mathSummaryFromConfidence(
  confidence: number | null,
): string | null {
  if (confidence === null) return null;
  return `Deterministic math verification confidence: ${Math.round(confidence * 100)}%.`;
}

/** Map B6 question evaluation DTO → EvaluationLedger domain shape. */
export function questionEvaluationApiToView(
  dto: B6QuestionEvaluationDto,
  options?: {
    tenantId?: string;
    transcription?: TranscriptionWorkspacePayload | null;
  },
): EvaluationLedger {
  const proposed = asNumber(dto.proposed_ai_score);
  const finalScore = asNumber(dto.final_human_approved_score);
  const mathConf = asNumber(dto.math_verification_confidence);
  const feedback = dto.reviewer_feedback ?? "";

  return {
    id: dto.id,
    tenant_id: options?.tenantId ?? "",
    evaluation_run_id: dto.evaluation_run_id,
    submission_id: dto.submission_id,
    student_id: dto.student_id ?? null,
    assessment_id: dto.assessment_id ?? "",
    assessment_version_id: dto.assessment_version_id,
    // Live question trees key on question_version_id
    question_id: dto.question_version_id,
    question_version_id: dto.question_version_id,
    rubric_version_id: dto.rubric_version_id ?? "",
    answer_key_version_id: dto.answer_key_version_id ?? "",
    answer_region_ids: (dto.answer_region_ids ?? []).map(String),
    max_mark: asNumberRequired(dto.max_mark),
    criterion_decisions: (dto.criterion_decisions ?? []).map(criterionApiToView),
    proposed_ai_score: proposed,
    final_human_approved_score: finalScore,
    error_codes: (dto.error_codes ?? []) as ErrorCode[],
    ecf_applied: Boolean(dto.ecf_applied),
    identity_confidence: asNumber(dto.identity_confidence),
    mapping_confidence: asNumber(dto.mapping_confidence),
    transcription_confidence: asNumber(dto.transcription_confidence),
    evaluation_confidence: asNumber(dto.evaluation_confidence),
    math_verification_confidence: mathConf,
    math_verification_summary: mathSummaryFromConfidence(mathConf),
    workflow_state: dto.workflow_state as EvaluationWorkflowState,
    ledger_version: dto.ledger_version ?? 1,
    feedback_draft: feedback,
    corrected_approach: dto.alternative_method_label ?? "",
    teacher_notes: feedback || null,
    transcription_text: joinTranscriptionText(
      dto,
      options?.transcription ?? null,
    ),
    alternative_method_id: dto.alternative_method_id ?? null,
    alternative_method_label: dto.alternative_method_label ?? null,
    score_sources: {
      ai_proposal: proposed !== null,
      deterministic_verification: mathConf !== null,
      human_final: finalScore !== null,
    },
  };
}

function pickSelectedQuestionId(
  ledgers: EvaluationLedger[],
  questionId?: string,
): string {
  if (questionId && ledgers.some((l) => l.question_id === questionId)) {
    return questionId;
  }
  const review = ledgers.find(
    (l) =>
      l.workflow_state === "REVIEW_REQUIRED" ||
      l.workflow_state === "PROPOSED" ||
      l.workflow_state === "PENDING",
  );
  return review?.question_id ?? ledgers[0]?.question_id ?? "";
}

/** Compose evaluation workspace DTO + related live resources → UI payload. */
export async function buildEvaluationWorkspacePayload(
  dto: B6EvaluationWorkspaceDto,
  deps: {
    submission: Submission;
    assessment: Assessment;
    student: Student | null;
    pages: EvaluationWorkspacePayload["pages"];
    regions: EvaluationWorkspacePayload["regions"];
    questions: Question[];
    rubrics: RubricCriterion[];
    answer_keys: AnswerKeyStep[];
    transcription: TranscriptionWorkspacePayload | null;
    questionId?: string;
  },
): Promise<EvaluationWorkspacePayload> {
  const ledgers = (dto.question_evaluations ?? []).map((qe) =>
    questionEvaluationApiToView(qe, {
      transcription: deps.transcription,
    }),
  );
  return {
    submission: {
      ...deps.submission,
      workflow_state: dto.workflow_state as Submission["workflow_state"],
    },
    assessment: deps.assessment,
    student: deps.student,
    pages: deps.pages,
    regions: deps.regions,
    questions: deps.questions,
    ledgers,
    rubrics: deps.rubrics,
    answer_keys: deps.answer_keys,
    selected_question_id: pickSelectedQuestionId(ledgers, deps.questionId),
  };
}

/**
 * Live B6 evaluation ledger review HTTP adapter.
 */
export const EvaluationHttpApi = {
  async prepareEvaluation(submissionId: string): Promise<Submission> {
    const row = await httpRequest<B6PrepareEvaluationDto>(
      `/api/v1/submissions/${submissionId}/evaluation/prepare`,
      { method: "POST" },
    );
    const submission = await httpRequest<B3SubmissionDto>(
      `/api/v1/submissions/${submissionId}`,
    );
    return submissionApiToView({
      ...submission,
      workflow_state: row.workflow_state,
    });
  },

  async getEvaluationWorkspace(
    submissionId: string,
    questionId?: string,
  ): Promise<EvaluationWorkspacePayload> {
    const [workspace, submission, mapping] = await Promise.all([
      httpRequest<B6EvaluationWorkspaceDto>(
        `/api/v1/submissions/${submissionId}/evaluation`,
      ),
      httpRequest<B3SubmissionDto>(`/api/v1/submissions/${submissionId}`),
      MappingHttpApi.getMappingReview(submissionId),
    ]);

    const submissionView = submissionApiToView(submission);

    const [assessment, student, rubrics, answer_keys, transcription] =
      await Promise.all([
        AuthoringHttpApi.getAssessment(submissionView.assessment_id),
        submissionView.student_id
          ? PlatformHttpApi.getStudent(submissionView.student_id).catch(
              () => null,
            )
          : Promise.resolve(null),
        AuthoringHttpApi.getAssessmentRubric(submissionView.assessment_id),
        AuthoringHttpApi.getAssessmentAnswerKey(submissionView.assessment_id),
        TranscriptionHttpApi.getTranscriptionWorkspace(submissionId).catch(
          () => null,
        ),
      ]);

    return buildEvaluationWorkspacePayload(workspace, {
      submission: submissionView,
      assessment,
      student,
      pages: mapping.pages,
      regions: mapping.regions,
      questions: mapping.questions.length
        ? mapping.questions
        : await AuthoringHttpApi.getAssessmentQuestions(
            submissionView.assessment_id,
          ),
      rubrics,
      answer_keys,
      transcription,
      questionId,
    });
  },

  async applyTeacherAction(
    submissionId: string,
    ledgerId: string,
    action: TeacherReviewAction,
    payload?: { newScore?: number; feedback?: string },
  ): Promise<TeacherActionResult> {
    if (isLiveDisabledTeacherAction(action)) {
      throw new ApiError({
        message: "Correction workflow not live yet.",
        status: 400,
        kind: "validation",
        code: "CORRECTION_NOT_LIVE",
      });
    }

    const qe = await httpRequest<B6QuestionEvaluationDto>(
      `/api/v1/question-evaluations/${ledgerId}`,
    );
    const proposed = asNumber(qe.proposed_ai_score);
    const maxMark = asNumberRequired(qe.max_mark);

    switch (action) {
      case "ACCEPT": {
        if (!canAcceptProposedScore(proposed)) {
          throw new ApiError({
            message: "Cannot accept a question evaluation with null proposed_ai_score",
            status: 409,
            kind: "conflict",
            code: "NO_PROPOSAL",
          });
        }
        const row = await httpRequest<B6QuestionEvaluationDto>(
          `/api/v1/question-evaluations/${ledgerId}/accept`,
          { method: "POST" },
        );
        return {
          workflow_state: "ACCEPTED",
          final_human_approved_score: asNumber(row.final_human_approved_score),
          feedback: row.reviewer_feedback ?? null,
          requires_followup: false,
          message: "AI proposal accepted.",
        };
      }
      case "CHANGE_SCORE": {
        const reasonError = validateOverrideReason(payload?.feedback);
        if (reasonError) {
          throw new ApiError({
            message: reasonError,
            status: 400,
            kind: "validation",
            code: "REASON_REQUIRED",
          });
        }
        if (payload?.newScore === undefined || payload.newScore === null) {
          throw new ApiError({
            message: "Override requires a new score.",
            status: 400,
            kind: "validation",
            code: "SCORE_REQUIRED",
          });
        }
        const row = await httpRequest<B6QuestionEvaluationDto>(
          `/api/v1/question-evaluations/${ledgerId}/override`,
          {
            method: "POST",
            body: {
              score: payload.newScore,
              reason: payload.feedback!.trim(),
            },
          },
        );
        return {
          workflow_state: "OVERRIDDEN",
          final_human_approved_score: asNumber(row.final_human_approved_score),
          feedback: row.reviewer_feedback ?? null,
          requires_followup: false,
          message: `Score overridden to ${row.final_human_approved_score}.`,
        };
      }
      case "VALID_ALTERNATIVE": {
        // Backend has no dedicated endpoint — map to OVERRIDE at full marks.
        const reason =
          payload?.feedback?.trim() ||
          "Valid alternative method; full credit awarded.";
        const row = await httpRequest<B6QuestionEvaluationDto>(
          `/api/v1/question-evaluations/${ledgerId}/override`,
          {
            method: "POST",
            body: { score: maxMark, reason },
          },
        );
        return {
          workflow_state: "OVERRIDDEN",
          final_human_approved_score: asNumber(row.final_human_approved_score),
          feedback: row.reviewer_feedback ?? null,
          requires_followup: false,
          message: "Valid alternative accepted with full credit.",
        };
      }
      case "EDIT_FEEDBACK": {
        if (!payload?.feedback?.trim()) {
          throw new ApiError({
            message: "Feedback text is required.",
            status: 400,
            kind: "validation",
            code: "FEEDBACK_REQUIRED",
          });
        }
        const row = await httpRequest<B6QuestionEvaluationDto>(
          `/api/v1/question-evaluations/${ledgerId}/feedback`,
          {
            method: "POST",
            body: { feedback: payload.feedback.trim() },
          },
        );
        return {
          workflow_state: row.workflow_state as TeacherActionResult["workflow_state"],
          final_human_approved_score: asNumber(row.final_human_approved_score),
          feedback: row.reviewer_feedback ?? null,
          requires_followup: false,
          message: "Feedback updated.",
        };
      }
      case "ESCALATE": {
        const reasonError = validateEscalateReason(payload?.feedback);
        if (reasonError) {
          throw new ApiError({
            message: reasonError,
            status: 400,
            kind: "validation",
            code: "REASON_REQUIRED",
          });
        }
        const row = await httpRequest<B6QuestionEvaluationDto>(
          `/api/v1/question-evaluations/${ledgerId}/escalate`,
          {
            method: "POST",
            body: { reason: payload!.feedback!.trim() },
          },
        );
        return {
          workflow_state: "ESCALATED",
          final_human_approved_score: asNumber(row.final_human_approved_score),
          feedback: row.reviewer_feedback ?? null,
          requires_followup: true,
          message: "Escalated for senior review.",
        };
      }
      default: {
        // Fallback for mock-compatible local computation (should not reach for live)
        void submissionId;
        return applyTeacherReviewAction({
          action,
          proposedScore: proposed,
          maxMark,
          newScore: payload?.newScore,
          feedback: payload?.feedback,
        });
      }
    }
  },

  async finalizeEvaluation(submissionId: string): Promise<Submission> {
    const row = await httpRequest<B6FinalizeEvaluationDto>(
      `/api/v1/submissions/${submissionId}/evaluation/finalize`,
      { method: "POST" },
    );
    const submission = await httpRequest<B3SubmissionDto>(
      `/api/v1/submissions/${submissionId}`,
    );
    return submissionApiToView({
      ...submission,
      workflow_state: row.workflow_state,
    });
  },
};
