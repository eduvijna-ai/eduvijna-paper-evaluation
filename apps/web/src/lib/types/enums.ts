/** Domain enums aligned with architecture contracts (WORKFLOW_STATES, ERROR_TAXONOMY, curriculum ontology). */

export const ASSESSMENT_STATES = [
  "DRAFT",
  "RUBRIC_REVIEW",
  "READY",
  "ACTIVE",
  "CLOSED",
  "ARCHIVED",
] as const;
export type AssessmentState = (typeof ASSESSMENT_STATES)[number];

export const SUBMISSION_STATES = [
  "UPLOADED",
  "PROCESSING",
  "IDENTITY_REVIEW",
  "MAPPING_REVIEW",
  "READY_FOR_EVALUATION",
  "EVALUATING",
  "EVALUATION_REVIEW",
  "APPROVED",
  "PUBLISHED",
  "FAILED",
] as const;
export type SubmissionState = (typeof SUBMISSION_STATES)[number];

export const IDENTITY_MATCH_STATES = [
  "UNMATCHED",
  "REVIEW_REQUIRED",
  "AUTO_MATCHED",
  "CONFIRMED",
] as const;
export type IdentityMatchState = (typeof IDENTITY_MATCH_STATES)[number];

export const EVALUATION_WORKFLOW_STATES = [
  "PENDING",
  "PROPOSED",
  "REVIEW_REQUIRED",
  "ACCEPTED",
  "OVERRIDDEN",
] as const;
export type EvaluationWorkflowState = (typeof EVALUATION_WORKFLOW_STATES)[number];

export const CRITERION_DECISIONS = [
  "AWARDED",
  "PARTIAL",
  "DEDUCTED",
  "NOT_APPLICABLE",
  "UNREADABLE",
] as const;
export type CriterionDecision = (typeof CRITERION_DECISIONS)[number];

export const CURRICULUM_NODE_TYPES = [
  "GRADE",
  "SEMESTER",
  "SUBJECT",
  "UNIT",
  "CHAPTER",
  "TOPIC",
  "SUBTOPIC",
  "CONCEPT",
  "SKILL",
  "LEARNING_OUTCOME",
] as const;
export type CurriculumNodeType = (typeof CURRICULUM_NODE_TYPES)[number];

export const ACADEMIC_ERROR_CODES = [
  "CONCEPT",
  "FORMULA",
  "METHOD",
  "CALCULATION",
  "ALGEBRA",
  "SIGN",
  "SUBSTITUTION",
  "NOTATION",
  "UNIT",
  "DIAGRAM",
  "INTERPRETATION",
  "INCOMPLETE",
  "LOGIC_REASONING",
  "PRESENTATION",
  "FINAL_ANSWER",
] as const;
export type AcademicErrorCode = (typeof ACADEMIC_ERROR_CODES)[number];

export const SYSTEM_ERROR_CODES = [
  "UNREADABLE",
  "OCR_TRANSCRIPTION",
  "QUESTION_MAPPING",
  "IDENTITY_MAPPING",
  "VALID_ALTERNATIVE",
  "RUBRIC_AMBIGUITY",
  "OTHER_REVIEW_REQUIRED",
] as const;
export type SystemErrorCode = (typeof SYSTEM_ERROR_CODES)[number];

export type ErrorCode = AcademicErrorCode | SystemErrorCode;

export const USER_ROLES = [
  "PLATFORM_ADMIN",
  "TEACHER",
  "STUDENT",
  "PARENT",
] as const;
export type UserRole = (typeof USER_ROLES)[number];

export const MAPPING_ACTIONS = [
  "ACCEPT",
  "MOVE",
  "MERGE",
  "SPLIT",
  "IGNORE",
  "MARK_CROSSED_OUT",
] as const;
export type MappingAction = (typeof MAPPING_ACTIONS)[number];

export const TEACHER_REVIEW_ACTIONS = [
  "ACCEPT",
  "CHANGE_SCORE",
  "EDIT_FEEDBACK",
  "VALID_ALTERNATIVE",
  "OCR_TRANSCRIPTION_ERROR",
  "MAPPING_ERROR",
  "ESCALATE",
] as const;
export type TeacherReviewAction = (typeof TEACHER_REVIEW_ACTIONS)[number];

export const LEARNING_PATH_STEPS = [
  "PREREQUISITE",
  "LEARN",
  "WORKED_EXAMPLE",
  "GUIDED",
  "INDEPENDENT",
  "EXAM_STYLE",
  "MASTERY_CHECK",
] as const;
export type LearningPathStepKind = (typeof LEARNING_PATH_STEPS)[number];

export const IMPROVEMENT_BLUEPRINT_STATES = [
  "DRAFT",
  "PENDING_APPROVAL",
  "APPROVED",
  "REJECTED",
] as const;
export type ImprovementBlueprintState =
  (typeof IMPROVEMENT_BLUEPRINT_STATES)[number];
