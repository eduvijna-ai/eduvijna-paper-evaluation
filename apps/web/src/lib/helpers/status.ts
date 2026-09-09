import type {
  AssessmentState,
  EvaluationWorkflowState,
  IdentityMatchState,
  SubmissionState,
} from "@/lib/types/enums";

export type StatusTone = "neutral" | "info" | "success" | "warning" | "danger";

export interface StatusVisual {
  label: string;
  tone: StatusTone;
}

const assessmentLabels: Record<AssessmentState, StatusVisual> = {
  DRAFT: { label: "Draft", tone: "neutral" },
  RUBRIC_REVIEW: { label: "Rubric review", tone: "warning" },
  READY: { label: "Ready", tone: "info" },
  ACTIVE: { label: "Active", tone: "success" },
  CLOSED: { label: "Closed", tone: "neutral" },
  ARCHIVED: { label: "Archived", tone: "neutral" },
};

const submissionLabels: Record<SubmissionState, StatusVisual> = {
  UPLOADED: { label: "Uploaded", tone: "info" },
  PROCESSING: { label: "Processing", tone: "info" },
  IDENTITY_REVIEW: { label: "Identity review", tone: "warning" },
  MAPPING_REVIEW: { label: "Mapping review", tone: "warning" },
  READY_FOR_EVALUATION: { label: "Ready for evaluation", tone: "info" },
  EVALUATING: { label: "Evaluating", tone: "info" },
  EVALUATION_REVIEW: { label: "Evaluation review", tone: "warning" },
  MODERATION_REVIEW: { label: "Moderation review", tone: "warning" },
  APPROVED: { label: "Approved", tone: "success" },
  PUBLISHED: { label: "Published", tone: "success" },
  FAILED: { label: "Failed", tone: "danger" },
};

const identityLabels: Record<IdentityMatchState, StatusVisual> = {
  UNMATCHED: { label: "Unmatched", tone: "danger" },
  REVIEW_REQUIRED: { label: "Review required", tone: "warning" },
  AUTO_MATCHED: { label: "Auto-matched", tone: "info" },
  CONFIRMED: { label: "Confirmed", tone: "success" },
};

const evaluationLabels: Record<EvaluationWorkflowState, StatusVisual> = {
  PENDING: { label: "Pending", tone: "neutral" },
  PROPOSED: { label: "Proposed", tone: "info" },
  REVIEW_REQUIRED: { label: "Review required", tone: "warning" },
  ACCEPTED: { label: "Accepted", tone: "success" },
  OVERRIDDEN: { label: "Overridden", tone: "warning" },
  ESCALATED: { label: "Escalated", tone: "danger" },
};

export function getAssessmentStatus(state: AssessmentState): StatusVisual {
  return assessmentLabels[state];
}

export function getSubmissionStatus(state: SubmissionState): StatusVisual {
  return submissionLabels[state];
}

export function getIdentityStatus(state: IdentityMatchState): StatusVisual {
  return identityLabels[state];
}

export function getEvaluationStatus(
  state: EvaluationWorkflowState,
): StatusVisual {
  return evaluationLabels[state];
}

export type DomainStatusKind =
  | "assessment"
  | "submission"
  | "identity"
  | "evaluation";

export function resolveStatusVisual(
  kind: DomainStatusKind,
  state: string,
): StatusVisual {
  switch (kind) {
    case "assessment":
      return getAssessmentStatus(state as AssessmentState);
    case "submission":
      return getSubmissionStatus(state as SubmissionState);
    case "identity":
      return getIdentityStatus(state as IdentityMatchState);
    case "evaluation":
      return getEvaluationStatus(state as EvaluationWorkflowState);
    default:
      return { label: state, tone: "neutral" };
  }
}
