import type { TeacherReviewAction } from "@/lib/types/enums";
import { clampScore } from "./score";

export interface TeacherActionInput {
  action: TeacherReviewAction;
  proposedScore: number;
  maxMark: number;
  newScore?: number;
  feedback?: string;
}

export interface TeacherActionResult {
  workflow_state: "ACCEPTED" | "OVERRIDDEN" | "REVIEW_REQUIRED";
  final_human_approved_score: number | null;
  feedback: string | null;
  requires_followup: boolean;
  message: string;
}

export function applyTeacherReviewAction(
  input: TeacherActionInput,
): TeacherActionResult {
  switch (input.action) {
    case "ACCEPT":
      return {
        workflow_state: "ACCEPTED",
        final_human_approved_score: input.proposedScore,
        feedback: input.feedback ?? null,
        requires_followup: false,
        message: "AI proposal accepted.",
      };
    case "CHANGE_SCORE": {
      const score = clampScore(input.newScore ?? input.proposedScore, input.maxMark);
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
    case "VALID_ALTERNATIVE":
      return {
        workflow_state: "OVERRIDDEN",
        final_human_approved_score: input.maxMark,
        feedback:
          input.feedback ??
          "Marked as valid alternative method; full credit awarded.",
        requires_followup: false,
        message: "Valid alternative accepted with full credit.",
      };
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
    case "ESCALATE":
      return {
        workflow_state: "REVIEW_REQUIRED",
        final_human_approved_score: null,
        feedback: input.feedback ?? "Escalated to senior reviewer.",
        requires_followup: true,
        message: "Escalated for senior review.",
      };
    default: {
      const _exhaustive: never = input.action;
      return _exhaustive;
    }
  }
}
