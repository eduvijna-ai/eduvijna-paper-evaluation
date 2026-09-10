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
  "MODERATION_REVIEW",
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
  "ESCALATED",
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
  "MARK_CONTINUATION",
] as const;
export type MappingAction = (typeof MAPPING_ACTIONS)[number];

export const MAPPING_NODE_STATES = [
  "PROPOSED",
  "REVIEW_REQUIRED",
  "CONFIRMED",
  "CROSSED_OUT",
] as const;
export type MappingNodeState = (typeof MAPPING_NODE_STATES)[number];

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

export const LEARNING_PLAN_RUN_STATUSES = [
  "QUEUED",
  "RUNNING",
  "READY",
  "FAILED",
  "SUPERSEDED",
] as const;
export type LearningPlanRunStatus = (typeof LEARNING_PLAN_RUN_STATUSES)[number];

export const LEARNING_RECOMMENDATION_KINDS = [
  "PREREQUISITE_REPAIR",
  "TARGET_CONCEPT",
  "PROCEDURE_PRACTICE",
  "EXECUTION_PRACTICE",
] as const;
export type LearningRecommendationKind =
  (typeof LEARNING_RECOMMENDATION_KINDS)[number];

export const LEARNING_RECOMMENDATION_STATUSES = [
  "ACTIVE",
  "DISMISSED",
  "COMPLETED",
] as const;
export type LearningRecommendationStatus =
  (typeof LEARNING_RECOMMENDATION_STATUSES)[number];

export const IMPROVEMENT_BLUEPRINT_STATES = [
  "DRAFT",
  "GENERATING",
  "PENDING_APPROVAL",
  "APPROVED",
  "REJECTED",
  "FAILED",
] as const;
export type ImprovementBlueprintState =
  (typeof IMPROVEMENT_BLUEPRINT_STATES)[number];

export const IMPROVEMENT_TEMPLATE_KINDS = [
  "CONCEPT_CHECK",
  "PREREQUISITE_CHECK",
  "PROCEDURE_PRACTICE",
  "EXECUTION_PRACTICE",
  "TRANSFER_CHECK",
] as const;
export type ImprovementTemplateKind =
  (typeof IMPROVEMENT_TEMPLATE_KINDS)[number];

export const TRANSCRIPTION_STATES = [
  "NOT_STARTED",
  "QUEUED",
  "RUNNING",
  "REVIEW_REQUIRED",
  "READY",
  "FAILED",
  "UNAVAILABLE",
] as const;
export type TranscriptionState = (typeof TRANSCRIPTION_STATES)[number];

/** B10 authoring AI durable run statuses. */
export const AUTHORING_AI_RUN_STATUSES = [
  "QUEUED",
  "RUNNING",
  "REVIEW_REQUIRED",
  "SUCCEEDED",
  "FAILED",
  "UNAVAILABLE",
] as const;
export type AuthoringAiRunStatus = (typeof AUTHORING_AI_RUN_STATUSES)[number];

export const AUTHORING_AI_OPERATIONS = [
  "PARSE_QUESTION_PAPER",
  "PROPOSE_ANSWER_KEY",
  "PROPOSE_RUBRIC",
  "SUGGEST_CURRICULUM_MAPPING",
] as const;
export type AuthoringAiOperation = (typeof AUTHORING_AI_OPERATIONS)[number];

/** B10 assessment artifact security scan statuses. */
export const ASSESSMENT_ARTIFACT_SCAN_STATUSES = [
  "NOT_CONFIGURED",
  "CLEAN",
  "REJECTED",
  "ERROR",
] as const;
export type AssessmentArtifactScanStatus =
  (typeof ASSESSMENT_ARTIFACT_SCAN_STATUSES)[number];

export const AUTHORING_SOURCE_TYPES = [
  "TEACHER",
  "AI_PROPOSED",
  "IMPORTED",
] as const;
export type AuthoringSourceType = (typeof AUTHORING_SOURCE_TYPES)[number];

export const AUTHORING_MATERIAL_STATUSES = [
  "DRAFT",
  "REVIEW_REQUIRED",
  "APPROVED",
  "SUPERSEDED",
] as const;
export type AuthoringMaterialStatus =
  (typeof AUTHORING_MATERIAL_STATUSES)[number];

export const PROPOSED_QUESTION_SCORING_MODES = [
  "LEAF_SCORABLE",
  "CONTAINER_DERIVED",
] as const;
export type ProposedQuestionScoringMode =
  (typeof PROPOSED_QUESTION_SCORING_MODES)[number];

/** B13 institution catalog resource kinds (no open-web discovery). */
export const CURRICULUM_RESOURCE_KINDS = [
  "PRACTICE_SET",
  "WORKED_EXAMPLE",
  "CONCEPT_NOTE",
  "INTERNAL_PACKET",
] as const;
export type CurriculumResourceKind =
  (typeof CURRICULUM_RESOURCE_KINDS)[number];

export const CURRICULUM_RESOURCE_STATUSES = [
  "DRAFT",
  "APPROVED",
  "ACTIVE",
  "DEACTIVATED",
] as const;
export type CurriculumResourceStatus =
  (typeof CURRICULUM_RESOURCE_STATUSES)[number];

export const STUDENT_RESOURCE_ASSIGNMENT_STATUSES = [
  "ASSIGNED",
  "CANCELLED",
] as const;
export type StudentResourceAssignmentStatus =
  (typeof STUDENT_RESOURCE_ASSIGNMENT_STATUSES)[number];

/** B14 reassessment lifecycle (distinct from Assessment status). */
export const REASSESSMENT_STATUSES = [
  "CREATED",
  "SUBMITTED",
  "PUBLISHED",
] as const;
export type ReassessmentStatus = (typeof REASSESSMENT_STATUSES)[number];

/** B15 gold benchmark dataset version status. */
export const BENCHMARK_VERSION_STATUSES = ["DRAFT", "LOCKED"] as const;
export type BenchmarkVersionStatus =
  (typeof BENCHMARK_VERSION_STATUSES)[number];

/** B15 isolated AI regression run status. */
export const BENCHMARK_RUN_STATUSES = [
  "QUEUED",
  "RUNNING",
  "PASSED",
  "FAILED",
  "ERROR",
] as const;
export type BenchmarkRunStatus = (typeof BENCHMARK_RUN_STATUSES)[number];

/** B15 regression / release-gate verdict. */
export const BENCHMARK_VERDICTS = ["PASS", "FAIL", "PENDING"] as const;
export type BenchmarkVerdict = (typeof BENCHMARK_VERDICTS)[number];

/** B16 publication effective-current vs historical superseded. */
export const PUBLICATION_STATUSES = [
  "READY",
  "GENERATING",
  "GENERATED",
  "PUBLISHED",
  "FAILED",
  "SUPERSEDED",
] as const;
export type PublicationStatusEnum = (typeof PUBLICATION_STATUSES)[number];

export const GRADING_POOL_STATUSES = ["DRAFT", "ACTIVE", "CLOSED"] as const;
export type GradingPoolStatusEnum = (typeof GRADING_POOL_STATUSES)[number];

/** B17 psychometric run lifecycle. */
export const PSYCHOMETRIC_RUN_STATUSES = [
  "PENDING",
  "COMPLETED",
  "INSUFFICIENT_SAMPLE",
  "FAILED",
] as const;
export type PsychometricRunStatusEnum =
  (typeof PSYCHOMETRIC_RUN_STATUSES)[number];

/** B17 calibration session lifecycle (reuses DRAFT/ACTIVE/CLOSED). */
export const CALIBRATION_SESSION_STATUSES = ["DRAFT", "ACTIVE", "CLOSED"] as const;
export type CalibrationSessionStatusEnum =
  (typeof CALIBRATION_SESSION_STATUSES)[number];

export const GRADING_WORK_ITEM_STATUSES = [
  "QUEUED",
  "IN_PROGRESS",
  "SUBMITTED",
  "RETURNED",
  "COMPLETED",
] as const;
export type GradingWorkItemStatusEnum =
  (typeof GRADING_WORK_ITEM_STATUSES)[number];

export const MODERATION_CASE_STATUSES = [
  "PENDING",
  "IN_PROGRESS",
  "APPROVED",
  "RETURNED",
  "REJECTED",
] as const;
export type ModerationCaseStatusEnum =
  (typeof MODERATION_CASE_STATUSES)[number];

export const GRIEVANCE_STATUSES = [
  "SUBMITTED",
  "UNDER_REVIEW",
  "ACCEPTED",
  "REJECTED",
  "RE_EVALUATING",
  "RESOLVED",
  "CLOSED",
] as const;
export type GrievanceStatusEnum = (typeof GRIEVANCE_STATUSES)[number];
