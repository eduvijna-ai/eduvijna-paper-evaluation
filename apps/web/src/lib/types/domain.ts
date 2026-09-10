import type {
  AssessmentArtifactScanStatus,
  AssessmentState,
  AuthoringAiOperation,
  AuthoringAiRunStatus,
  AuthoringMaterialStatus,
  AuthoringSourceType,
  CriterionDecision,
  CurriculumNodeType,
  ErrorCode,
  EvaluationWorkflowState,
  IdentityMatchState,
  ImprovementBlueprintState,
  ImprovementTemplateKind,
  BenchmarkRunStatus,
  BenchmarkVerdict,
  BenchmarkVersionStatus,
  CurriculumResourceKind,
  CurriculumResourceStatus,
  LearningPathStepKind,
  LearningPlanRunStatus,
  LearningRecommendationKind,
  LearningRecommendationStatus,
  MappingNodeState,
  ProposedQuestionScoringMode,
  ReassessmentStatus,
  StudentResourceAssignmentStatus,
  SubmissionState,
  TranscriptionState,
  UserRole,
} from "./enums";

export type {
  AssessmentArtifactScanStatus,
  AssessmentState,
  AuthoringAiOperation,
  AuthoringAiRunStatus,
  AuthoringMaterialStatus,
  AuthoringSourceType,
  BenchmarkRunStatus,
  BenchmarkVerdict,
  BenchmarkVersionStatus,
  CriterionDecision,
  CurriculumNodeType,
  CurriculumResourceKind,
  CurriculumResourceStatus,
  ErrorCode,
  EvaluationWorkflowState,
  IdentityMatchState,
  ImprovementBlueprintState,
  ImprovementTemplateKind,
  LearningPathStepKind,
  LearningPlanRunStatus,
  LearningRecommendationKind,
  LearningRecommendationStatus,
  MappingNodeState,
  ProposedQuestionScoringMode,
  ReassessmentStatus,
  StudentResourceAssignmentStatus,
  SubmissionState,
  TranscriptionState,
  UserRole,
};
export type Confidence = number;

export interface DemoSession {
  userId: string;
  displayName: string;
  email: string;
  role: UserRole;
  tenantId: string;
  institutionId: string;
}

/** Authenticated session used by B1 hybrid/HTTP modes. */
export interface AuthSession {
  userId: string;
  displayName: string;
  email: string;
  /** Primary role for display; prefer permissions for gating */
  role: UserRole | string;
  roles: string[];
  permissions: string[];
  tenantId: string;
  institutionId: string;
  institutionName?: string;
  /** Epoch ms when access token is expected to expire */
  expiresAt: number;
  /** Auth mode: demo mock login vs real A1 bearer */
  authMode: "demo" | "bearer";
}

export interface Curriculum {
  id: string;
  tenant_id: string;
  code: string;
  title: string;
  board: string;
  grade_label: string;
  subject: string;
  node_count: number;
  updated_at: string;
}

export interface CurriculumNode {
  id: string;
  curriculum_id: string;
  parent_id: string | null;
  node_type: CurriculumNodeType;
  code: string;
  title: string;
  sort_order: number;
  metadata?: Record<string, string | number | boolean>;
  children?: CurriculumNode[];
}

export interface Student {
  id: string;
  tenant_id: string;
  institution_id: string;
  class_section_id: string;
  external_ref: string;
  first_name: string;
  last_name: string;
  display_name: string;
  grade: string;
  section: string;
  status: "ACTIVE" | "TRANSFERRED" | "WITHDRAWN";
  parent_email?: string;
  /** A1 student_code when sourced from HTTP */
  student_code?: string;
  academic_year_id?: string | null;
  admission_number?: string | null;
  roll_number?: string | null;
}

export interface Assessment {
  id: string;
  tenant_id: string;
  institution_id: string;
  title: string;
  code: string;
  subject: string;
  grade: string;
  max_marks: number;
  workflow_state: AssessmentState;
  scheduled_at: string | null;
  question_count: number;
  submission_count: number;
  curriculum_id: string;
  created_at: string;
  updated_at: string;
}

export interface Question {
  id: string;
  assessment_id: string;
  parent_id: string | null;
  code: string;
  prompt: string;
  max_mark: number;
  sort_order: number;
  curriculum_node_ids: string[];
  children?: Question[];
  /** Live B4 question-version id (often equal to `id` in the mapping tree). */
  question_version_id?: string;
  scoring_mode?: string;
  is_leaf_scorable?: boolean;
}

export interface RubricCriterion {
  id: string;
  question_id: string;
  label: string;
  description: string;
  max_marks: number;
  sort_order: number;
  /** B10 live rubric version provenance */
  rubric_version_id?: string;
  source_type?: AuthoringSourceType | string;
  status?: AuthoringMaterialStatus | string;
}

export interface AnswerKeyStep {
  id: string;
  question_id: string;
  step_index: number;
  content: string;
  marks: number;
  /** B10 live answer-key provenance */
  source_type?: AuthoringSourceType | string;
  status?: AuthoringMaterialStatus | string;
}

/** B10 nested AI question-tree proposal node. */
export interface ProposedQuestionNode {
  stable_code: string;
  display_label: string;
  sequence: number;
  prompt_text: string;
  max_marks: string | number;
  question_type: string;
  scoring_mode: ProposedQuestionScoringMode | string;
  instructions?: string | null;
  children?: ProposedQuestionNode[];
}

export interface AssessmentArtifact {
  id: string;
  tenant_id: string;
  assessment_id: string;
  artifact_type: string;
  original_filename: string;
  mime_type: string;
  byte_size: number;
  content_sha256: string;
  storage_key: string;
  security_scan_status: AssessmentArtifactScanStatus | string;
  uploaded_by?: string | null;
  uploaded_at: string;
  created_at?: string | null;
}

export interface AuthoringAiRun {
  id: string;
  tenant_id: string;
  assessment_id: string;
  assessment_version_id: string;
  question_version_id?: string | null;
  assessment_artifact_id?: string | null;
  operation: AuthoringAiOperation | string;
  status: AuthoringAiRunStatus | string;
  input_hash: string;
  proposal_payload?: {
    roots?: ProposedQuestionNode[];
    notes?: string | null;
    answer_text_length?: number;
    has_structured_answer?: boolean;
    mappings?: Array<{
      curriculum_node_id: string;
      mapping_type?: string;
      weight?: string | number | null;
      rationale?: string | null;
    }>;
    curriculum_id?: string;
    candidate_node_ids?: string[];
    [key: string]: unknown;
  } | null;
  requested_by: string;
  requested_at?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  celery_task_id?: string | null;
  answer_key_version_id?: string | null;
  rubric_version_id?: string | null;
  correlation_id?: string | null;
  failure_code?: string | null;
  failure_detail?: string | null;
  enqueue_error?: string | null;
}

export interface CriterionDecisionRow {
  rubric_criterion_id: string;
  criterion_label: string;
  max_marks: number;
  /** Null when unscorable / unreadable — must not render as 0. */
  proposed_marks: number | null;
  final_marks: number | null;
  decision: CriterionDecision;
  error_code: ErrorCode | null;
  deduction_reason: string | null;
  step_index: number | null;
}

export interface EvaluationLedger {
  id: string;
  tenant_id: string;
  evaluation_run_id: string;
  submission_id: string;
  student_id: string | null;
  assessment_id: string;
  assessment_version_id: string;
  question_id: string;
  question_version_id: string;
  rubric_version_id: string;
  answer_key_version_id: string;
  answer_region_ids: string[];
  max_mark: number;
  criterion_decisions: CriterionDecisionRow[];
  /** Null when unreadable / no proposal — must not display as 0. */
  proposed_ai_score: number | null;
  final_human_approved_score: number | null;
  error_codes: ErrorCode[];
  ecf_applied: boolean;
  identity_confidence: Confidence | null;
  mapping_confidence: Confidence | null;
  transcription_confidence: Confidence | null;
  evaluation_confidence: Confidence | null;
  math_verification_confidence: Confidence | null;
  /** Optional deterministic verification summary for UI. */
  math_verification_summary?: string | null;
  workflow_state: EvaluationWorkflowState;
  ledger_version: number;
  feedback_draft: string;
  corrected_approach: string;
  teacher_notes: string | null;
  /** Joined transcription evidence for the evaluation center column. */
  transcription_text?: string | null;
  alternative_method_id?: string | null;
  alternative_method_label?: string | null;
  /** Distinguishes AI proposal vs human final vs deterministic verify. */
  score_sources?: {
    ai_proposal: boolean;
    deterministic_verification: boolean;
    human_final: boolean;
  };
}

export interface PaperPage {
  id: string;
  page_number: number;
  label: string;
  width: number;
  height: number;
  /** Live B4 — page continues an answer from a prior page. */
  is_continuation?: boolean;
}

/** Normalized rect relative to a page: all values in [0, 1]. */
export interface NormalizedRect {
  page_number: number;
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface PaperDocument {
  id: string;
  title: string;
  page_count: number;
  pages: PaperPage[];
}

export interface EvidenceRegion {
  id: string;
  page_id: string;
  page_number: number;
  /** Normalized 0–1 relative to page width */
  x: number;
  /** Normalized 0–1 relative to page height */
  y: number;
  width: number;
  height: number;
  label: string;
  confidence: Confidence;
  question_id: string | null;
  crossed_out: boolean;
  annotation_kind?: "FULL" | "PARTIAL" | "DEDUCTION" | "NEUTRAL";
  /** Live B4 answer-region metadata */
  region_type?: "ANSWER" | "SCRATCH" | "DIAGRAM" | "IDENTITY" | string;
  source_type?: "HUMAN" | "AI" | string;
  ignored?: boolean;
  is_continuation?: boolean;
}

export interface MappingNode {
  question_id: string;
  question_code: string;
  region_ids: string[];
  confidence: Confidence;
  status: MappingNodeState;
}

export interface CurriculumMapEntry {
  question_id: string;
  question_code: string;
  curriculum_node_ids: string[];
  node_titles: string[];
}

export interface StudentMatchCandidate {
  student_id: string;
  display_name: string;
  external_ref: string;
  grade: string;
  section: string;
  confidence: Confidence;
  match_reasons: string[];
  /** Live B3/B5 — AI-assisted suggestion vs manual roster row */
  source_type?: "HUMAN" | "AI" | string;
}

export interface IdentityDetectedFields {
  name: string | null;
  roll: string | null;
  identity_confidence: Confidence;
}

export interface Submission {
  id: string;
  tenant_id: string;
  assessment_id: string;
  assessment_title: string;
  student_id: string | null;
  student_display_name: string | null;
  roll_number_detected: string | null;
  name_detected: string | null;
  workflow_state: SubmissionState;
  student_match_state: IdentityMatchState;
  identity_confidence: Confidence;
  mapping_confidence: Confidence;
  page_count: number;
  uploaded_at: string;
  updated_at: string;
  /** Present on live B3 ingestion payloads */
  original_filename?: string | null;
  source_content_sha256?: string | null;
  bundle_name?: string | null;
  mime_type?: string | null;
  byte_size?: number | null;
  storage_status?: string | null;
  /** Live B5 — transcription pipeline state */
  transcription_state?: TranscriptionState;
}

export interface IdentityReviewPayload {
  submission: Submission;
  candidates: StudentMatchCandidate[];
  pages: PaperPage[];
  /** Live B3 — OCR/extraction summary when automated matching is active */
  detected?: IdentityDetectedFields;
  automated_matching_active?: boolean;
}

export interface RegionTranscriptionView {
  id: string;
  answer_region_id: string;
  version_number: number;
  source_type: "HUMAN" | "AI" | string;
  text: string | null;
  latex: string | null;
  transcription_confidence: Confidence | null;
  unreadable: boolean;
  visual_only: boolean;
  status: string;
  confirmed_by?: string | null;
  confirmed_at?: string | null;
}

export interface TranscriptionRegionView {
  id: string;
  label: string;
  region_type?: string;
  source_type?: string;
  detection_confidence: Confidence;
  bbox: { x: number; y: number; width: number; height: number };
  /** Authenticated API path for region crop PNG */
  crop_url: string | null;
  page_image_url?: string | null;
  page_index?: number | null;
  latest_ai_proposal: RegionTranscriptionView | null;
  active_transcription: RegionTranscriptionView | null;
  requires_transcription: boolean;
}

export interface TranscriptionQuestionItem {
  question_version_id: string;
  question_label: string;
  disposition: "ANSWERED" | "BLANK";
  mapping_state: string;
  regions: TranscriptionRegionView[];
  requires_transcription: boolean;
}

export interface TranscriptionWorkspacePayload {
  submission_id: string;
  workflow_state: SubmissionState;
  transcription_state: TranscriptionState;
  automated_transcription_active: boolean;
  progress: {
    reviewed: number;
    required: number;
    label: string;
  };
  items: TranscriptionQuestionItem[];
}

export interface MappingCompletionSummary {
  leaf_total: number;
  confirmed_count: number;
  unresolved_question_codes: string[];
}

export interface QuestionAnswerMappingView {
  id: string;
  question_id: string;
  question_version_id: string;
  question_code: string;
  disposition: "ANSWERED" | "BLANK";
  mapping_state: "PROPOSED" | "REVIEW_REQUIRED" | "CONFIRMED";
  mapped_by: "HUMAN" | "AI";
  mapping_confidence: number;
  region_ids: string[];
  confirmed_by: string | null;
  confirmed_at: string | null;
}

export interface MappingReviewPayload {
  submission: Submission;
  pages: PaperPage[];
  regions: EvidenceRegion[];
  /** Legacy mock + live compatibility array (question_id may be version id). */
  mapping: MappingNode[];
  questions: Question[];
  /** Live B4 question↔region mappings */
  mappings?: QuestionAnswerMappingView[];
  completion?: MappingCompletionSummary;
  assessment_version_id?: string;
  automated_region_detection_active?: boolean;
  automated_mapping_active?: boolean;
}

export interface EvaluationWorkspacePayload {
  submission: Submission;
  assessment: Assessment;
  student: Student | null;
  pages: PaperPage[];
  regions: EvidenceRegion[];
  questions: Question[];
  ledgers: EvaluationLedger[];
  rubrics: RubricCriterion[];
  answer_keys: AnswerKeyStep[];
  selected_question_id: string;
}

export interface QuestionScoreSummary {
  question_id: string;
  question_code: string;
  max_mark: number;
  proposed_score: number;
  final_score: number | null;
  workflow_state: EvaluationWorkflowState;
  error_codes: ErrorCode[];
}

export interface StudentReport {
  student: Student;
  assessment: Assessment;
  total_score: number;
  max_marks: number;
  percentage: number;
  question_summaries: QuestionScoreSummary[];
  strengths: string[];
  weaknesses: string[];
  patterns: string[];
  next_actions: string[];
  topic_focus: Array<{ topic: string; mastery: number; priority: 1 | 2 | 3 }>;
  evidence_highlights: Array<{
    question_code: string;
    excerpt: string;
    outcome: "CORRECT" | "PARTIAL" | "DEDUCTED";
  }>;
  corrected_approaches: Array<{ question_code: string; approach: string }>;
  /** Live B7 — hide Topics/mastery when true */
  live_published?: boolean;
  ledger_snapshot_hash?: string;
  narrative_source?: "AI" | "FIXED" | "RULES_FALLBACK";
  published_result_id?: string;
}

export interface ParentReport {
  student_display_name: string;
  assessment_title: string;
  score_summary: string;
  what_went_well: string[];
  what_to_practice: string[];
  how_to_help: string[];
  next_step: string;
  total_score?: number;
  max_total_score?: number;
  percentage?: number;
  live_published?: boolean;
  ledger_snapshot_hash?: string;
  narrative_source?: "AI" | "FIXED" | "RULES_FALLBACK";
  published_result_id?: string;
}

export type PublicationStatus =
  | "READY"
  | "GENERATING"
  | "GENERATED"
  | "PUBLISHED"
  | "FAILED"
  | "SUPERSEDED";

/** B16 horizontal grading pool. */
export type GradingPoolStatus = "DRAFT" | "ACTIVE" | "CLOSED";
export type GradingWorkItemStatus =
  | "QUEUED"
  | "IN_PROGRESS"
  | "SUBMITTED"
  | "RETURNED"
  | "COMPLETED";
export type ModerationCaseStatus =
  | "PENDING"
  | "IN_PROGRESS"
  | "APPROVED"
  | "RETURNED"
  | "REJECTED";
export type GrievanceStatus =
  | "SUBMITTED"
  | "UNDER_REVIEW"
  | "ACCEPTED"
  | "REJECTED"
  | "RE_EVALUATING"
  | "RESOLVED"
  | "CLOSED";

export interface GradingPool {
  id: string;
  assessment_id: string;
  assessment_version_id: string;
  grading_mode: string;
  status: GradingPoolStatus;
  allocation_strategy: "MANUAL" | "ROUND_ROBIN";
  created_at: string;
  updated_at: string;
  member_count?: number;
}

export interface GradingWorkItem {
  id: string;
  pool_id: string;
  submission_id: string;
  evaluation_run_id: string;
  question_evaluation_id: string;
  assigned_evaluator_id: string;
  status: GradingWorkItemStatus;
  created_at: string;
  updated_at: string;
}

export interface ModerationCase {
  id: string;
  policy_id: string;
  submission_id: string;
  evaluation_run_id: string;
  current_stage_order: number;
  status: ModerationCaseStatus;
  created_at: string;
  updated_at: string;
  actions?: Array<{
    id: string;
    stage_order: number;
    actor_user_id: string;
    decision: "APPROVE" | "RETURN" | "REJECT";
    reason: string | null;
    created_at: string;
  }>;
}

export interface GrievanceCase {
  id: string;
  submission_id: string;
  original_published_result_id: string;
  original_evaluation_run_id: string;
  requester_reference: string;
  submitted_by: string;
  reason: string;
  status: GrievanceStatus;
  decision_reason: string | null;
  reevaluation_run_id: string | null;
  revised_published_result_id: string | null;
  created_at: string;
  updated_at: string;
}

export type PublicationArtifactType =
  | "ANNOTATED_PDF"
  | "STUDENT_REPORT_PDF"
  | "PARENT_REPORT_PDF"
  | "TEACHER_REPORT_PDF";

export interface PublicationArtifactInfo {
  available: boolean;
  sha256: string | null;
  byte_size: number | null;
}

export interface PublicationAnnotation {
  id: string;
  annotation_type:
    | "TICK"
    | "CROSS"
    | "PARTIAL"
    | "MARK"
    | "COMMENT"
    | "HIGHLIGHT";
  submission_page_id: string;
  question_evaluation_id: string | null;
  answer_region_id: string | null;
  x: number;
  y: number;
  width: number;
  height: number;
  payload: Record<string, unknown>;
  source_type: "LEDGER" | "HUMAN" | string;
}

export interface PublishedResultSummary {
  id: string;
  submission_id: string;
  student_id: string | null;
  assessment_id: string;
  assessment_version_id: string;
  evaluation_run_id: string;
  version_number: number;
  status: PublicationStatus;
  ledger_snapshot_hash: string;
  total_score: number | null;
  max_total_score: number | null;
  narrative_source: "AI" | "FIXED" | "RULES_FALLBACK" | null;
  generated_at: string | null;
  published_at: string | null;
  failure_code: string | null;
  failure_detail: string | null;
  artifacts: Partial<Record<PublicationArtifactType, PublicationArtifactInfo>>;
}

export interface PublicationWorkspace {
  submission_id: string;
  workflow_state: string;
  latest: PublishedResultSummary | null;
  versions: PublishedResultSummary[];
  annotations: PublicationAnnotation[];
}

export interface PublicationPrepareResult {
  submission_id: string;
  workflow_state: string;
  published_result_id: string;
  status: PublicationStatus;
  version_number: number;
  job_id: string | null;
}

export interface PublicationRegenerateResult {
  published_result_id: string;
  status: PublicationStatus | string;
  version_number: number;
  job_id: string;
  supersedes_result_id: string | null;
}

export interface PublicationPublishResult {
  published_result_id: string;
  status: "PUBLISHED";
  submission_id: string;
  published_at: string | null;
}

export interface AnnotatedPaperQuestionScore {
  id: string;
  question_code: string;
  /** Always final human-approved score for live; never proposed_ai_score */
  final_score: number | null;
  max_mark: number;
  feedback?: string | null;
}

export interface AnnotatedPaperWorkspace {
  submission_id: string;
  workflow_state: string;
  pages: PaperPage[];
  regions: EvidenceRegion[];
  annotations: PublicationAnnotation[];
  published_result: PublishedResultSummary | null;
  questions: AnnotatedPaperQuestionScore[];
  live: boolean;
}

export interface TeacherReportQuestion {
  question_id: string;
  question_version_id?: string;
  question_code: string;
  final_score: number;
  max_mark: number;
  workflow_state: "ACCEPTED" | "OVERRIDDEN" | string;
  criterion_decisions: Array<Record<string, unknown>>;
  error_codes: string[];
  deduction_reasons?: string[];
  first_divergence_step?: number | null;
  ecf_applied?: boolean;
  alternative_method_label?: string | null;
  confidences?: {
    identity?: number | null;
    mapping?: number | null;
    transcription?: number | null;
    evaluation?: number | null;
    math_verification?: number | null;
  };
}

export interface TeacherReport {
  published_result_id: string;
  student: { id: string; display_name: string };
  assessment: {
    id: string;
    title: string;
    code?: string;
    assessment_version_id: string;
  };
  total_score: number;
  max_total_score: number;
  questions: TeacherReportQuestion[];
  ledger_snapshot_hash: string;
  evaluation_run_id?: string;
  generated_at?: string;
  published_at?: string | null;
}

/** Mock-mode assessment analytics (demo fixtures). */
export interface AssessmentAnalytics {
  assessment: Assessment;
  mean_score: number;
  median_score: number;
  pass_rate: number;
  question_difficulty: Array<{
    question_code: string;
    mean_score_pct: number;
    common_errors: ErrorCode[];
  }>;
  error_distribution: Array<{ code: ErrorCode; count: number }>;
  score_bands: Array<{ label: string; count: number }>;
}

export interface LiveAnalyticsErrorCount {
  code: ErrorCode | string;
  count: number;
  category?: "academic" | "review_condition" | string;
}

export interface LiveQuestionPerformance {
  question_id: string;
  question_code: string;
  question_version_ids: string[];
  attempt_count: number;
  blank_count: number;
  mean_score_percent: number | null;
  median_score_percent: number | null;
  full_credit_count: number;
  zero_score_count: number;
  common_errors: LiveAnalyticsErrorCount[];
}

export interface LiveScoreDistributionBand {
  lower_bound: number;
  upper_bound: number;
  count: number;
}

export interface LiveCurriculumPerformance {
  curriculum_node_id: string;
  code: string;
  title: string;
  node_type: string;
  question_count: number;
  evidence_count: number;
  mean_score_ratio: number | null;
  strong_signal_count: number;
  weak_signal_count: number;
  inconclusive_signal_count: number;
  common_academic_errors: LiveAnalyticsErrorCount[];
}

export interface LiveAssessmentSummary {
  id: string;
  code: string;
  title: string;
  curriculum_id: string;
  status: string;
}

/** Live B8 assessment analytics (published-ledger projections). */
export interface LiveAssessmentAnalytics {
  assessment: LiveAssessmentSummary;
  class_section_id: string | null;
  published_attempt_count: number;
  unique_student_count: number;
  mean_percentage: number | null;
  median_percentage: number | null;
  pass_threshold_percent: number | null;
  pass_rate: number | null;
  score_distribution: LiveScoreDistributionBand[];
  question_performance: LiveQuestionPerformance[];
  error_distribution: {
    academic: LiveAnalyticsErrorCount[];
    review_conditions: LiveAnalyticsErrorCount[];
  };
  curriculum_performance: LiveCurriculumPerformance[];
  mapped_scorable_question_count: number;
  unmapped_scorable_question_count: number;
  mastery_coverage_ratio: number | null;
  source: "PUBLISHED_LEDGER";
  as_of: string;
}

/** Mock-mode student analytics (demo fixtures). */
export interface StudentAnalytics {
  student: Student;
  assessments_taken: number;
  average_percentage: number;
  trend: Array<{ assessment_code: string; percentage: number }>;
  concept_mastery: Array<{ concept: string; mastery: number }>;
  recurring_errors: Array<{ code: ErrorCode; count: number }>;
}

export interface LiveConceptSignalBucket {
  strong_count: number;
  weak_count: number;
  inconclusive_count: number;
  signal: string;
}

export interface LiveConceptSignal {
  curriculum_node_id: string;
  code: string;
  title: string;
  node_type: string;
  concept: LiveConceptSignalBucket;
  execution: LiveConceptSignalBucket;
  procedure: LiveConceptSignalBucket;
  evidence_count: number;
  mean_score_ratio: number | null;
}

export interface LiveStudentSummary {
  id: string;
  display_name: string;
  student_code: string | null;
  external_ref: string | null;
}

export type AnalyticsMaterializationStatus =
  | "NOT_STARTED"
  | "QUEUED"
  | "RUNNING"
  | "READY"
  | "PARTIAL"
  | "FAILED";

/** Live B8 student analytics (published-ledger projections). */
export interface LiveStudentAnalytics {
  student: LiveStudentSummary;
  published_assessment_count: number;
  published_attempt_count: number;
  average_percentage: number | null;
  concept_signals: LiveConceptSignal[];
  error_distribution: LiveAnalyticsErrorCount[];
  mastery_coverage: {
    curriculum_node_count: number;
    evidence_row_count: number;
  };
  materialization_status: AnalyticsMaterializationStatus | string;
  published_result_count: number;
  materialized_result_count: number;
  source: "PUBLISHED_LEDGER";
  as_of: string;
}

export interface MasteryEvidenceItem {
  id: string;
  published_result_id: string;
  assessment_id: string;
  assessment_version_id: string;
  submission_id: string;
  evaluation_run_id: string;
  question_evaluation_id: string;
  question_version_id: string;
  curriculum_id: string;
  curriculum_node_id: string;
  evidence_type: string;
  strength: string;
  score_ratio: number;
  source_final_score: number;
  source_max_mark: number;
  mapping_types: string[];
  mapping_weight: number | null;
  academic_error_codes: string[];
  review_condition_codes: string[];
  reason_codes: string[];
  source_ledger_snapshot_hash: string;
  algorithm_version: string;
  created_at: string;
}

export interface StudentMasteryEvidenceList {
  student_id: string;
  items: MasteryEvidenceItem[];
}

export interface AnalyticsMaterializationPrepareResult {
  published_result_id: string;
  pipeline_job_id: string;
  job_status: string;
  celery_task_id: string | null;
  enqueue_error: string | null;
  algorithm_version: string;
}

/** B12 PEV-036 disclaimer (contract const). */
export const B12_RECOVERABLE_MARKS_DISCLAIMER =
  "Potentially recoverable marks are an analytical estimate from final criterion deductions, not guaranteed recovery.";

export type B12AlgorithmVersion = "B12_V1";
export type B12MasterySource = "MASTERY_EVIDENCE";
export type B12LedgerSource = "PUBLISHED_LEDGER";
export type B12RecommendedPracticeKind =
  | "CONCEPT_CHECK"
  | "EXECUTION_PRACTICE"
  | "PROCEDURE_PRACTICE";

/** B12 longitudinal MasteryState item (null mastery = insufficient decisive evidence). */
export interface MasteryStateItem {
  id: string | null;
  curriculum_node_id: string;
  curriculum_id: string;
  code: string;
  title: string;
  node_type: string;
  concept_mastery: number | null;
  execution_accuracy: number | null;
  concept_decisive_count: number;
  execution_decisive_count: number;
  concept_inconclusive_count: number;
  execution_inconclusive_count: number;
  evidence_count: number;
  insufficient_concept_evidence: boolean;
  insufficient_execution_evidence: boolean;
  source_evidence_hash: string;
  algorithm_version: B12AlgorithmVersion | string;
  last_updated_at: string;
}

export interface StudentMasteryState {
  student_id: string;
  items: MasteryStateItem[];
  algorithm_version: B12AlgorithmVersion | string;
  source: B12MasterySource;
  as_of: string;
}

export interface MasteryTrendPoint {
  curriculum_node_id: string;
  curriculum_id: string;
  code: string;
  title: string;
  published_result_id: string;
  assessment_id: string;
  assessment_code: string;
  effective_at: string;
  concept_mastery: number | null;
  execution_accuracy: number | null;
  concept_decisive_count: number;
  execution_decisive_count: number;
  evidence_count: number;
  insufficient_concept_evidence: boolean;
  insufficient_execution_evidence: boolean;
  source_evidence_hash: string;
  algorithm_version: B12AlgorithmVersion | string;
}

export interface StudentMasteryTrend {
  student_id: string;
  curriculum_node_id: string | null;
  points: MasteryTrendPoint[];
  algorithm_version: B12AlgorithmVersion | string;
  source: B12MasterySource;
  as_of: string;
}

export interface RepeatedErrorAffectedQuestion {
  published_result_id: string;
  assessment_id: string;
  question_evaluation_id: string;
  question_version_id: string;
}

export interface RepeatedErrorItem {
  error_code: string;
  occurrence_count: number;
  distinct_published_result_count: number;
  distinct_assessment_count: number;
  first_seen_at: string;
  last_seen_at: string;
  affected_question_evaluations: RepeatedErrorAffectedQuestion[];
  curriculum_node_ids: string[];
}

export interface StudentRepeatedErrors {
  student_id: string;
  items: RepeatedErrorItem[];
  recurrence_threshold: 2 | number;
  algorithm_version: B12AlgorithmVersion | string;
  source: B12MasterySource;
  as_of: string;
}

export interface RecoverableMarksAffectedReference {
  published_result_id: string;
  assessment_id: string;
  question_evaluation_id: string;
  criterion_evaluation_id: string;
}

export interface RecoverableMarksItem {
  error_code: string;
  /** Decimal string from ledger. */
  potentially_recoverable_marks: string;
  occurrence_count: number;
  percent_of_total_lost: number | null;
  affected_references: RecoverableMarksAffectedReference[];
}

export interface StudentRecoverableMarks {
  student_id: string;
  /** Decimal strings — keep as strings in view types. */
  total_lost_marks: string;
  attributed_potentially_recoverable_marks: string;
  unattributed_lost_marks: string;
  items: RecoverableMarksItem[];
  disclaimer: string;
  algorithm_version: B12AlgorithmVersion | string;
  source: B12LedgerSource;
  as_of: string;
}

export interface MistakeNotebookCurriculumNode {
  id: string;
  code: string;
  title: string;
  node_type: string;
}

export interface MistakeNotebookEntry {
  id: string;
  published_result_id: string;
  assessment_id: string;
  assessment_code: string;
  submission_id: string;
  question_evaluation_id: string;
  question_version_id: string;
  question_code: string;
  academic_error_code: string;
  /** Decimal strings. */
  final_score: string;
  max_mark: string;
  deduction_reasons: string[];
  first_divergence_step: string | null;
  curriculum_nodes: MistakeNotebookCurriculumNode[];
  recommended_practice_kind: B12RecommendedPracticeKind | string;
  linked_learning_recommendation_ids: string[];
  source_ledger_snapshot_hash: string;
  algorithm_version: B12AlgorithmVersion | string;
  materialized_at: string;
  effective_at: string;
}

export interface StudentMistakeNotebook {
  student_id: string;
  entries: MistakeNotebookEntry[];
  algorithm_version: B12AlgorithmVersion | string;
  source: B12LedgerSource;
  as_of: string;
}

export interface B12RebuildResult {
  student_id: string;
  algorithm_version: B12AlgorithmVersion | string;
  mastery_state_count: number;
  snapshot_count: number;
  notebook_entry_count: number;
  source_evidence_hash: string;
  source: B12MasterySource;
}

/** Format 0–1 mastery ratio; null = insufficient decisive evidence. */
export function formatMasteryRatio(
  value: number | null | undefined,
): string {
  if (value === null || value === undefined) return "Insufficient evidence";
  return `${Math.round(value * 100)}%`;
}

export type AssessmentAnalyticsView =
  | AssessmentAnalytics
  | LiveAssessmentAnalytics;
export type StudentAnalyticsView = StudentAnalytics | LiveStudentAnalytics;

export function isLiveAssessmentAnalytics(
  value: AssessmentAnalyticsView,
): value is LiveAssessmentAnalytics {
  return (
    "source" in value &&
    value.source === "PUBLISHED_LEDGER" &&
    "question_performance" in value
  );
}

export function isLiveStudentAnalytics(
  value: StudentAnalyticsView,
): value is LiveStudentAnalytics {
  return (
    "source" in value &&
    value.source === "PUBLISHED_LEDGER" &&
    "concept_signals" in value
  );
}

/** Pass-rate display helper for live analytics (null threshold = Not configured). */
export function formatAnalyticsPassRate(
  passRate: number | null | undefined,
  passThresholdPercent: number | null | undefined,
): string {
  if (passThresholdPercent === null || passThresholdPercent === undefined) {
    return "Not configured";
  }
  if (passRate === null || passRate === undefined) {
    return "—";
  }
  return `${Math.round(passRate * 100)}%`;
}

export function formatAnalyticsPercentage(
  value: number | null | undefined,
  digits = 1,
): string {
  if (value === null || value === undefined) return "—";
  return `${value.toFixed(digits)}%`;
}

export interface LearningPathStepItem {
  id: string;
  kind: LearningPathStepKind;
  title: string;
  description: string;
  /** Optional — omit/null for live B9 (no invented study-time). */
  estimated_minutes?: number | null;
  completed: boolean;
}

export interface TopicPriority {
  id: string;
  topic: string;
  priority: 1 | 2 | 3;
  reason: string;
  mastery: number;
  error_codes: ErrorCode[];
}

export interface AdaptiveLearningPlan {
  student: Student;
  priorities: TopicPriority[];
  path: LearningPathStepItem[];
  error_distribution: Array<{ code: ErrorCode; count: number }>;
}

export interface ImprovementAssessmentBlueprint {
  id: string;
  student_id: string;
  title: string;
  workflow_state: ImprovementBlueprintState;
  target_topics: string[];
  question_outline: Array<{
    code: string;
    focus: string;
    max_mark: number;
    difficulty: "EASY" | "MEDIUM" | "HARD";
  }>;
  teacher_notes: string | null;
  created_at: string;
}

export interface LiveLearningCurriculumOption {
  id: string;
  code: string;
  name: string;
}

export interface LiveLearningPrerequisiteRef {
  curriculum_node_id: string;
  code: string;
  title: string;
  relationship_type: "REQUIRED" | "RECOMMENDED";
}

/** Live B9 recommendation — signals only; never mastery %. */
export interface LiveLearningRecommendation {
  id: string;
  curriculum_node_id: string;
  code: string;
  title: string;
  node_type: string;
  recommendation_kind: LearningRecommendationKind | string;
  priority: 1 | 2 | 3;
  rationale: string;
  concept_signal: string;
  execution_signal: string;
  procedure_signal: string;
  evidence_count: number;
  mean_evidence_score_ratio: number | null;
  status: LearningRecommendationStatus | string;
  prerequisites: LiveLearningPrerequisiteRef[];
}

export interface LiveLearningPathStep {
  id: string;
  kind: LearningPathStepKind | string;
  sequence: number;
  title: string;
  description: string;
  curriculum_node_id: string | null;
  node_code: string | null;
  node_title: string | null;
  evidence_basis: string | null;
  relationship_type: "REQUIRED" | "RECOMMENDED" | null;
  estimated_minutes: number | null;
  learning_recommendation_id: string | null;
}

export interface LiveLearningPlanRunSummary {
  id: string;
  version_number: number;
  status: LearningPlanRunStatus | string;
  generation_source: string | null;
  algorithm_version: string;
  source_evidence_hash: string;
  curriculum_graph_hash: string;
  input_hash: string;
  failure_code: string | null;
  failure_detail: string | null;
  requested_at: string | null;
  finished_at: string | null;
}

export interface LiveLearningPlan {
  run_id: string;
  version_number: number;
  status: LearningPlanRunStatus | string;
  generation_source: string | null;
  algorithm_version: string;
  source_evidence_hash: string;
  curriculum_graph_hash: string;
  input_hash: string;
  is_stale: boolean;
  recommendations: LiveLearningRecommendation[];
  path: LiveLearningPathStep[];
  materialization_status: string | null;
  evidence_coverage: {
    curriculum_node_count: number;
    evidence_row_count: number;
  };
}

/** B13 institution-approved curriculum catalog resource (PEV-041). */
export interface CurriculumResource {
  id: string;
  curriculum_id: string;
  code: string;
  title: string;
  description: string | null;
  resource_kind: CurriculumResourceKind | string;
  status: CurriculumResourceStatus | string;
  content_ref: string;
  curriculum_node_ids: string[];
  created_by: string | null;
  approved_by: string | null;
  approved_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface CurriculumResourceList {
  curriculum_id: string | null;
  status_filter: CurriculumResourceStatus | string | null;
  items: CurriculumResource[];
}

export interface CurriculumResourceCreate {
  curriculum_id: string;
  code: string;
  title: string;
  description?: string | null;
  resource_kind: CurriculumResourceKind | string;
  content_ref: string;
  curriculum_node_ids: string[];
}

export interface CurriculumResourceUpdate {
  title?: string;
  description?: string | null;
  resource_kind?: CurriculumResourceKind | string;
  content_ref?: string;
}

export interface CurriculumResourceNodesReplace {
  curriculum_node_ids: string[];
}

/** B13 persistent student assignment — distinct from B9 LearningRecommendation. */
export interface StudentResourceAssignment {
  id: string;
  student_id: string;
  resource_id: string;
  resource: CurriculumResource;
  learning_recommendation_id: string | null;
  status: StudentResourceAssignmentStatus | string;
  assigned_by: string | null;
  assigned_at: string;
  cancelled_at: string | null;
  cancelled_by: string | null;
}

export interface StudentResourceAssignmentList {
  student_id: string;
  curriculum_id: string | null;
  items: StudentResourceAssignment[];
}

export interface StudentResourceAssignmentCreate {
  resource_id: string;
  learning_recommendation_id?: string | null;
}

/** B14 reassessment item linkage (PEV-043). */
export interface ReassessmentItem {
  id: string;
  improvement_assessment_item_id: string;
  question_version_id: string;
  curriculum_node_id: string;
  item_code_snapshot: string;
  template_kind_snapshot: string;
  question_template_ref_snapshot: string | null;
}

/**
 * B14 mastery baseline → post delta.
 * Null mastery/delta means insufficient decisive evidence — never treat as 0.
 */
export interface ReassessmentMasteryDelta {
  curriculum_node_id: string;
  baseline_concept_mastery: number | null;
  baseline_execution_accuracy: number | null;
  baseline_concept_decisive_count: number;
  baseline_execution_decisive_count: number;
  baseline_concept_inconclusive_count: number;
  baseline_execution_inconclusive_count: number;
  baseline_evidence_count: number;
  baseline_source_evidence_hash: string;
  post_snapshot_id: string | null;
  post_published_result_id: string | null;
  post_concept_mastery: number | null;
  post_execution_accuracy: number | null;
  post_concept_decisive_count: number | null;
  post_execution_decisive_count: number | null;
  post_concept_inconclusive_count: number | null;
  post_execution_inconclusive_count: number | null;
  post_evidence_count: number | null;
  post_source_evidence_hash: string | null;
  concept_delta: number | null;
  execution_delta: number | null;
  materialized_at: string | null;
  algorithm_version: string;
}

export interface Reassessment {
  id: string;
  improvement_assessment_id: string;
  blueprint_title: string;
  blueprint_version_number: number;
  student_id: string;
  curriculum_id: string;
  assessment_id: string;
  assessment_status: string;
  assessment_version_id: string;
  submission_id: string | null;
  published_result_id: string | null;
  status: ReassessmentStatus | string;
  algorithm_version: string;
  instantiation_hash: string;
  baseline_captured_at: string;
  created_at: string;
  updated_at: string;
  items: ReassessmentItem[];
  mastery_deltas: ReassessmentMasteryDelta[];
}

export interface ReassessmentInstantiateItem {
  improvement_assessment_item_id: string;
  prompt_text: string;
  max_marks: string;
  question_type?: string | null;
  instructions?: string | null;
}

export interface ReassessmentInstantiateRequest {
  items: ReassessmentInstantiateItem[];
}

export interface B14RebuildResult {
  reassessment_id: string;
  algorithm_version: string;
  delta_count: number;
  published_result_id: string | null;
  source: string;
}

/** B15 release-gate threshold profile snapshot. */
export interface BenchmarkThresholdProfile {
  profile_code: string;
  algorithm_version: string;
  max_missing_output_rate: number;
  max_mean_abs_score_error: number;
  min_exact_score_agreement_rate: number;
  min_taxonomy_agreement_rate: number;
  max_safety_invariant_failure_rate: number;
  score_tolerance: number;
}

/** B15 gold benchmark dataset (PEV-058). */
export interface BenchmarkDataset {
  id: string;
  code: string;
  title: string;
  description: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface BenchmarkDatasetList {
  items: BenchmarkDataset[];
}

export interface BenchmarkDatasetCreate {
  code: string;
  title: string;
  description?: string | null;
}

/** B15 gold benchmark dataset version (DRAFT or LOCKED). */
export interface BenchmarkVersion {
  id: string;
  dataset_id: string;
  version_number: number;
  status: BenchmarkVersionStatus | string;
  threshold_profile_snapshot: BenchmarkThresholdProfile | Record<string, unknown>;
  case_count: number;
  content_hash: string | null;
  locked_by: string | null;
  locked_at: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface BenchmarkVersionList {
  items: BenchmarkVersion[];
}

export interface BenchmarkVersionCreate {
  threshold_profile_snapshot?: BenchmarkThresholdProfile | Record<string, unknown> | null;
}

/** B15 frozen gold case — no student PII. */
export interface BenchmarkCase {
  id: string;
  dataset_version_id: string;
  published_result_id: string;
  evaluation_run_id: string;
  question_evaluation_id: string;
  question_version_id: string;
  rubric_version_id: string;
  assessment_version_id: string;
  expected_final_marks: number;
  expected_max_marks: number;
  expected_error_codes: string[];
  source_ledger_hash: string;
  evidence_hash: string;
  adjudicated_by: string | null;
  adjudicated_at: string;
  replay_fixture: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface BenchmarkCaseList {
  items: BenchmarkCase[];
}

export interface BenchmarkCaseCreate {
  published_result_id: string;
  question_evaluation_id: string;
}

export interface BenchmarkEligibleQuestionEvaluation {
  question_evaluation_id: string;
  question_version_id: string;
  workflow_state: "ACCEPTED" | "OVERRIDDEN" | string;
  final_human_approved_score: number;
  max_mark: number;
  error_codes: string[];
}

export interface BenchmarkEligibleSource {
  published_result_id: string;
  evaluation_run_id: string;
  submission_id: string;
  assessment_version_id: string;
  ledger_snapshot_hash: string;
  question_evaluations: BenchmarkEligibleQuestionEvaluation[];
}

export interface BenchmarkEligibleSources {
  items: BenchmarkEligibleSource[];
}

/** B15 isolated AI regression run. */
export interface BenchmarkRegressionRun {
  id: string;
  dataset_version_id: string;
  status: BenchmarkRunStatus | string;
  verdict: BenchmarkVerdict | string;
  idempotency_key: string | null;
  candidate_provider: string;
  candidate_model: string;
  candidate_model_version: string;
  candidate_prompt_template_version: string;
  candidate_config: Record<string, unknown>;
  threshold_snapshot: BenchmarkThresholdProfile | Record<string, unknown>;
  aggregate_metrics: Record<string, unknown>;
  initiated_by: string | null;
  started_at: string | null;
  finished_at: string | null;
  failure_code: string | null;
  failure_detail: string | null;
  created_at: string;
  updated_at: string;
}

export interface BenchmarkRegressionRunList {
  items: BenchmarkRegressionRun[];
}

export interface BenchmarkRegressionRunCreate {
  candidate_provider: string;
  candidate_model: string;
  candidate_model_version: string;
  candidate_prompt_template_version: string;
  candidate_config?: Record<string, unknown> | null;
  idempotency_key?: string | null;
}

/** Per-case isolated regression comparison against frozen gold. */
export interface BenchmarkRegressionCaseResult {
  id: string;
  regression_run_id: string;
  benchmark_case_id: string;
  missing_output: boolean;
  actual_marks: number | null;
  actual_error_codes: string[];
  score_abs_error: number | null;
  exact_score_match: boolean;
  taxonomy_match: boolean | null;
  safety_invariant_failed: boolean;
  diff: Record<string, unknown>;
  ai_execution_record_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface BenchmarkRegressionCaseResultList {
  items: BenchmarkRegressionCaseResult[];
}

export interface BenchmarkGateVerdict {
  verdict: BenchmarkVerdict | string;
  passed: boolean;
  run_id: string;
  status?: BenchmarkRunStatus | string;
  candidate_provider: string;
  candidate_model: string;
  candidate_model_version: string;
  candidate_prompt_template_version: string;
  metrics: Record<string, unknown>;
  threshold_snapshot: BenchmarkThresholdProfile | Record<string, unknown>;
}

export interface LiveLearningWorkspace {
  student: LiveStudentSummary;
  available_curricula: LiveLearningCurriculumOption[];
  selected_curriculum: LiveLearningCurriculumOption | null;
  materialization_status: AnalyticsMaterializationStatus | string;
  evidence_coverage: {
    curriculum_node_count: number;
    evidence_row_count: number;
  };
  latest_run: LiveLearningPlanRunSummary | null;
  latest_plan: LiveLearningPlan | null;
  is_stale: boolean;
  latest_improvement_blueprint: LiveImprovementAssessment | null;
  /** B13 assigned catalog resources (ASSIGNED only when from workspace). */
  resource_assignments?: StudentResourceAssignment[];
  /** B14 reassessment history (newest first). */
  reassessments?: Reassessment[];
}

export interface LearningPlanPrepareResult {
  run_id: string;
  student_id: string;
  curriculum_id: string;
  version_number: number;
  status: LearningPlanRunStatus | string;
  celery_task_id: string | null;
  enqueue_error: string | null;
  algorithm_version: string;
  is_idempotent_reuse: boolean;
}

export interface LiveImprovementAssessmentItem {
  id: string;
  learning_recommendation_id: string | null;
  curriculum_node_id: string;
  node_code: string | null;
  node_title: string | null;
  item_code: string;
  template_kind: ImprovementTemplateKind | string;
  question_template_ref: string;
  focus: string;
  difficulty: "EASY" | "MEDIUM" | "HARD" | string;
  suggested_marks: number | null;
  sort_order: number;
}

export interface LiveImprovementAssessment {
  id: string;
  student_id: string;
  curriculum_id: string;
  learning_plan_run_id: string;
  version_number: number;
  title: string;
  status: ImprovementBlueprintState | string;
  generation_source: string | null;
  algorithm_version: string | null;
  source_evidence_hash: string | null;
  curriculum_graph_hash: string | null;
  input_hash: string | null;
  is_stale: boolean;
  rejection_reason: string | null;
  failure_code: string | null;
  failure_detail: string | null;
  items: LiveImprovementAssessmentItem[];
  generated_at: string | null;
  approved_at: string | null;
  rejected_at: string | null;
  created_at: string;
}

export interface ImprovementBlueprintPrepareResult {
  improvement_assessment_id: string;
  learning_plan_run_id: string;
  version_number: number;
  status: ImprovementBlueprintState | string;
  celery_task_id: string | null;
  enqueue_error: string | null;
}

export interface DashboardSummary {
  pending_identity: number;
  pending_mapping: number;
  pending_evaluation: number;
  active_assessments: number;
  recent_submissions: Submission[];
  recent_assessments: Assessment[];
}

/** B17 psychometric run (PEV-048). */
export interface PsychometricRun {
  id: string;
  assessment_id: string;
  assessment_version_id: string;
  cohort_definition: Record<string, unknown>;
  algorithm_version: string;
  min_cohort_size: number;
  source_set_hash: string;
  source_result_count: number;
  source_published_result_ids: string[];
  status: string;
  requested_by: string | null;
  requested_at: string | null;
  completed_at: string | null;
  failure_code: string | null;
  failure_detail: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface PsychometricRunList {
  items: PsychometricRun[];
}

export interface ItemPsychometricMetric {
  id: string;
  run_id: string;
  question_id: string;
  question_version_id: string;
  question_code: string;
  attempt_count: number;
  max_mark: number;
  mean_raw_score: number;
  std_dev: number;
  difficulty_index: number;
  discrimination_index: number | null;
  discrimination_method: string;
  discrimination_status: string;
  full_credit_rate: number;
  zero_score_rate: number;
  blank_rate: number | null;
  difficulty_band: string | null;
  discrimination_band: string | null;
}

export interface ItemPsychometricMetricList {
  items: ItemPsychometricMetric[];
}

/** B17 calibration session (PEV-049). */
export interface CalibrationSession {
  id: string;
  assessment_id: string;
  assessment_version_id: string;
  title: string;
  status: string;
  algorithm_version: string;
  score_tolerance_abs: number;
  score_tolerance_pct: number;
  min_cases: number;
  activated_by: string | null;
  activated_at: string | null;
  closed_by: string | null;
  closed_at: string | null;
  created_by: string | null;
  created_at: string | null;
  updated_at: string | null;
  case_count?: number;
  cases?: CalibrationCase[];
  participants?: { id: string; user_id: string }[];
}

export interface CalibrationSessionList {
  items: CalibrationSession[];
}

export interface CalibrationCase {
  id: string;
  session_id: string;
  case_code: string;
  published_result_id: string;
  evaluation_run_id: string;
  question_evaluation_id: string;
  question_version_id: string;
  rubric_version_id: string;
  max_mark: number;
  reference_score: number;
  source_snapshot_hash: string;
  created_at: string | null;
}

export interface CalibrationCaseBlind {
  id: string;
  session_id: string;
  case_code: string;
  question_version_id: string;
  rubric_version_id: string;
  max_mark: number;
  criterion_snapshot: unknown[];
  evidence_snapshot: Record<string, unknown>;
}

export interface CalibrationResponse {
  id: string;
  session_id: string;
  case_id: string;
  participant_id: string;
  user_id: string;
  score: number;
  max_mark: number;
  comment: string | null;
  submitted_at: string | null;
}

export interface CalibrationSessionMetric {
  id: string;
  session_id: string;
  metric_name: string;
  algorithm_version: string;
  evaluator_count: number;
  common_case_count: number;
  icc_value: number | null;
  status: string;
}

export interface CalibrationEvaluatorMetric {
  id: string;
  session_id: string;
  user_id: string;
  case_count: number;
  mean_signed_diff: number;
  mae: number;
  nmae: number;
  exact_match_rate: number;
  within_tolerance_rate: number;
}

/** B18 answer cluster run (PEV-050). */
export interface AnswerClusterRun {
  id: string;
  assessment_id: string;
  assessment_version_id: string;
  question_id: string;
  question_version_id: string;
  cohort_definition: Record<string, unknown>;
  algorithm_version: string;
  similarity_threshold: number;
  source_set_hash: string;
  source_result_count: number;
  source_published_result_ids: string[];
  embedding_provider: string;
  embedding_model: string;
  embedding_model_version: string;
  embedding_dim: number;
  cluster_count: number;
  status: string;
  requested_by: string | null;
  requested_at: string | null;
  completed_at: string | null;
  failure_code: string | null;
  failure_detail: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface AnswerClusterRunList {
  items: AnswerClusterRun[];
}

export interface AnswerCluster {
  id: string;
  run_id: string;
  cluster_index: number;
  member_count: number;
  label: string | null;
  created_at: string | null;
}

export interface AnswerClusterList {
  items: AnswerCluster[];
}

export interface AnswerClusterMember {
  id: string;
  run_id: string;
  cluster_id: string;
  published_result_id: string;
  evaluation_run_id: string;
  question_evaluation_id: string;
  submission_id: string;
  transcription_text: string | null;
  transcription_hash: string;
  embedding: number[];
  final_human_approved_score: number | null;
  created_at: string | null;
}

export interface AnswerClusterReview {
  id: string;
  run_id: string;
  cluster_id: string;
  reviewer_user_id: string;
  observation: string;
  suggested_rubric_refinement: string | null;
  submitted_at: string | null;
  created_at: string | null;
}

export interface AnswerClusterDetail extends AnswerCluster {
  members: AnswerClusterMember[];
  reviews: AnswerClusterReview[];
}

/** B18 CO/PO outcome definition (PEV-051). */
export interface OutcomeDefinition {
  id: string;
  outcome_type: string;
  code: string;
  title: string;
  description: string | null;
  status: string;
  created_by: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface OutcomeDefinitionList {
  items: OutcomeDefinition[];
}

export interface QuestionOutcomeMapping {
  id: string;
  mapping_set_id: string;
  question_id: string;
  question_version_id: string;
  outcome_definition_id: string;
  weight: number | null;
  created_at: string | null;
}

export interface OutcomeMappingSet {
  id: string;
  assessment_id: string;
  assessment_version_id: string;
  version_number: number;
  title: string;
  status: string;
  created_by: string | null;
  activated_by: string | null;
  activated_at: string | null;
  retired_by: string | null;
  retired_at: string | null;
  activation_hash: string | null;
  created_at: string | null;
  updated_at: string | null;
  mapping_count?: number;
  mappings?: QuestionOutcomeMapping[];
}

export interface OutcomeMappingSetList {
  items: OutcomeMappingSet[];
}

export interface OutcomeAttainmentReport {
  id: string;
  assessment_id: string;
  assessment_version_id: string;
  mapping_set_id: string;
  mapping_set_version_number: number;
  mapping_activation_hash: string | null;
  cohort_definition: Record<string, unknown>;
  algorithm_version: string;
  source_set_hash: string;
  source_result_count: number;
  source_published_result_ids: string[];
  status: string;
  requested_by: string | null;
  requested_at: string | null;
  completed_at: string | null;
  failure_code: string | null;
  failure_detail: string | null;
  created_at: string | null;
  updated_at: string | null;
  metrics?: OutcomeAttainmentMetric[];
}

export interface OutcomeAttainmentReportList {
  items: OutcomeAttainmentReport[];
}

export interface OutcomeAttainmentMetric {
  id: string;
  report_run_id: string;
  outcome_definition_id: string;
  outcome_type: string;
  outcome_code: string;
  outcome_title: string;
  weighted_earned: number | null;
  weighted_max: number | null;
  attainment_pct: number | null;
  denom_status: string;
  mapped_question_count: number;
  contribution_count: number;
  created_at: string | null;
}
