import type { EvaluationWorkflowState, TeacherReviewAction } from "@/lib/types/enums";
import { clampScore } from "./score";

export interface TeacherActionInput {
  action: TeacherReviewAction;
  proposedScore: number | null;
  maxMark: number;
  newScore?: number;
  feedback?: string;
}

export interface TeacherActionResult {
  workflow_state:
    | "ACCEPTED"
    | "OVERRIDDEN"
    | "REVIEW_REQUIRED"
    | "ESCALATED";
  final_human_approved_score: number | null;
  feedback: string | null;
  requires_followup: boolean;
  message: string;
}

/** Actions that require a correction workflow not yet live on B6. */
export const LIVE_DISABLED_TEACHER_ACTIONS: TeacherReviewAction[] = [
  "OCR_TRANSCRIPTION_ERROR",
  "MAPPING_ERROR",
];

export function isLiveDisabledTeacherAction(
  action: TeacherReviewAction,
): boolean {
  return LIVE_DISABLED_TEACHER_ACTIONS.includes(action);
}

export function canAcceptProposedScore(proposed: number | null): boolean {
  return proposed !== null && proposed !== undefined;
}

export function validateOverrideReason(reason: string | undefined | null): string | null {
  if (!reason || !reason.trim()) {
    return "Override requires a mandatory reason.";
  }
  return null;
}

export function validateEscalateReason(reason: string | undefined | null): string | null {
  if (!reason || !reason.trim()) {
    return "Escalation requires a reason.";
  }
  return null;
}

/** Approval gate: every question ledger must be ACCEPTED or OVERRIDDEN. */
export function canApproveEvaluation(
  states: EvaluationWorkflowState[],
): boolean {
  if (states.length === 0) return false;
  return states.every((s) => s === "ACCEPTED" || s === "OVERRIDDEN");
}

export function countFinalizedQuestions(
  states: EvaluationWorkflowState[],
): { finalized: number; total: number } {
  const finalized = states.filter(
    (s) => s === "ACCEPTED" || s === "OVERRIDDEN",
  ).length;
  return { finalized, total: states.length };
}

export function applyTeacherReviewAction(
  input: TeacherActionInput,
): TeacherActionResult {
  switch (input.action) {
    case "ACCEPT": {
      if (!canAcceptProposedScore(input.proposedScore)) {
        return {
          workflow_state: "REVIEW_REQUIRED",
          final_human_approved_score: null,
          feedback: input.feedback ?? null,
          requires_followup: true,
          message: "Cannot accept: no automatic score proposed.",
        };
      }
      return {
        workflow_state: "ACCEPTED",
        final_human_approved_score: input.proposedScore,
        feedback: input.feedback ?? null,
        requires_followup: false,
        message: "AI proposal accepted.",
      };
    }
    case "CHANGE_SCORE": {
      const reasonError = validateOverrideReason(input.feedback);
      if (reasonError) {
        return {
          workflow_state: "REVIEW_REQUIRED",
          final_human_approved_score: null,
          feedback: null,
          requires_followup: true,
          message: reasonError,
        };
      }
      const score = clampScore(
        input.newScore ?? input.proposedScore ?? 0,
        input.maxMark,
      );
      return {
        workflow_state: "OVERRIDDEN",
        final_human_approved_score: score,
        feedback: input.feedback ?? null,
        requires_followup: false,
        message: `Score changed to ${score}.`,
      };
    }
    case "EDIT_FEEDBACK":
      return {
        workflow_state: "OVERRIDDEN",
        final_human_approved_score: input.proposedScore,
        feedback: input.feedback ?? "",
        requires_followup: false,
        message: "Feedback updated.",
      };
    case "VALID_ALTERNATIVE": {
      const reason =
        input.feedback?.trim() ||
        "Marked as valid alternative method; full credit awarded.";
      return {
        workflow_state: "OVERRIDDEN",
        final_human_approved_score: input.maxMark,
        feedback: reason,
        requires_followup: false,
        message: "Valid alternative accepted with full credit.",
      };
    }
    case "OCR_TRANSCRIPTION_ERROR":
      return {
        workflow_state: "REVIEW_REQUIRED",
        final_human_approved_score: null,
        feedback: input.feedback ?? "Flagged for OCR/transcription correction.",
        requires_followup: true,
        message: "Queued for transcription correction.",
      };
    case "MAPPING_ERROR":
      return {
        workflow_state: "REVIEW_REQUIRED",
        final_human_approved_score: null,
        feedback: input.feedback ?? "Flagged for question mapping correction.",
        requires_followup: true,
        message: "Queued for mapping correction.",
      };
    case "ESCALATE": {
      const reasonError = validateEscalateReason(input.feedback);
      if (reasonError) {
        return {
          workflow_state: "REVIEW_REQUIRED",
          final_human_approved_score: null,
          feedback: null,
          requires_followup: true,
          message: reasonError,
        };
      }
      return {
        workflow_state: "ESCALATED",
        final_human_approved_score: null,
        feedback: input.feedback ?? "Escalated to senior reviewer.",
        requires_followup: true,
        message: "Escalated for senior review.",
      };
    }
    default: {
      const _exhaustive: never = input.action;
      return _exhaustive;
    }
  }
}
