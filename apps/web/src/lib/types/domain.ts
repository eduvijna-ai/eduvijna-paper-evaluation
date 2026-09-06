import type {
  AssessmentState,
  CriterionDecision,
  CurriculumNodeType,
  ErrorCode,
  EvaluationWorkflowState,
  IdentityMatchState,
  ImprovementBlueprintState,
  LearningPathStepKind,
  MappingNodeState,
  SubmissionState,
  TranscriptionState,
  UserRole,
} from "./enums";

export type {
  AssessmentState,
  CriterionDecision,
  CurriculumNodeType,
  ErrorCode,
  EvaluationWorkflowState,
  IdentityMatchState,
  ImprovementBlueprintState,
  LearningPathStepKind,
  MappingNodeState,
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
}

export interface AnswerKeyStep {
  id: string;
  question_id: string;
  step_index: number;
  content: string;
  marks: number;
}

export interface CriterionDecisionRow {
  rubric_criterion_id: string;
  criterion_label: string;
  max_marks: number;
  proposed_marks: number;
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
  proposed_ai_score: number;
  final_human_approved_score: number | null;
  error_codes: ErrorCode[];
  ecf_applied: boolean;
  identity_confidence: Confidence;
  mapping_confidence: Confidence;
  transcription_confidence: Confidence;
  evaluation_confidence: Confidence;
  math_verification_confidence: Confidence | null;
  workflow_state: EvaluationWorkflowState;
  ledger_version: number;
  feedback_draft: string;
  corrected_approach: string;
  teacher_notes: string | null;
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
}

export interface ParentReport {
  student_display_name: string;
  assessment_title: string;
  score_summary: string;
  what_went_well: string[];
  what_to_practice: string[];
  how_to_help: string[];
  next_step: string;
}

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

export interface StudentAnalytics {
  student: Student;
  assessments_taken: number;
  average_percentage: number;
  trend: Array<{ assessment_code: string; percentage: number }>;
  concept_mastery: Array<{ concept: string; mastery: number }>;
  recurring_errors: Array<{ code: ErrorCode; count: number }>;
}

export interface LearningPathStepItem {
  id: string;
  kind: LearningPathStepKind;
  title: string;
  description: string;
  estimated_minutes: number;
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

export interface DashboardSummary {
  pending_identity: number;
  pending_mapping: number;
  pending_evaluation: number;
  active_assessments: number;
  recent_submissions: Submission[];
  recent_assessments: Assessment[];
}
