import type {
  AdaptiveLearningPlan,
  Assessment,
  AssessmentAnalytics,
  BenchmarkCase,
  BenchmarkCaseCreate,
  BenchmarkCaseList,
  BenchmarkDataset,
  BenchmarkDatasetCreate,
  BenchmarkDatasetList,
  BenchmarkEligibleSources,
  BenchmarkGateVerdict,
  BenchmarkRegressionCaseResult,
  BenchmarkRegressionCaseResultList,
  BenchmarkRegressionRun,
  BenchmarkRegressionRunCreate,
  BenchmarkRegressionRunList,
  BenchmarkThresholdProfile,
  BenchmarkVersion,
  BenchmarkVersionCreate,
  BenchmarkVersionList,
  Curriculum,
  CurriculumNode,
  CurriculumResource,
  CurriculumResourceCreate,
  CurriculumResourceList,
  CurriculumResourceUpdate,
  DashboardSummary,
  EvaluationLedger,
  EvaluationWorkspacePayload,
  EvidenceRegion,
  IdentityReviewPayload,
  ImprovementAssessmentBlueprint,
  MappingReviewPayload,
  PaperPage,
  ParentReport,
  Question,
  Reassessment,
  ReassessmentInstantiateRequest,
  B14RebuildResult,
  RubricCriterion,
  AnswerKeyStep,
  CurriculumMapEntry,
  Student,
  StudentAnalytics,
  StudentMasteryState,
  StudentMasteryTrend,
  StudentMistakeNotebook,
  StudentRecoverableMarks,
  StudentRepeatedErrors,
  StudentResourceAssignment,
  StudentResourceAssignmentCreate,
  StudentResourceAssignmentList,
  StudentReport,
  Submission,
  TranscriptionWorkspacePayload,
} from "@/lib/types/domain";
import { B12_RECOVERABLE_MARKS_DISCLAIMER } from "@/lib/types/domain";
import {
  IMP_BLUEPRINT_ID,
  IMP_ITEM_ID_1,
  IMP_ITEM_ID_2,
  REASSESSMENT_ID,
  REASSESSMENT_ID_CREATED,
} from "@/lib/fixtures/b14-demo";

export {
  REASSESSMENT_ID,
  REASSESSMENT_ID_CREATED,
  IMP_BLUEPRINT_ID,
  IMP_ITEM_ID_1,
  IMP_ITEM_ID_2,
  getDemoApprovedBlueprintItems,
} from "@/lib/fixtures/b14-demo";

export const TENANT_ID = "tenant-demo-001";
export const INSTITUTION_ID = "inst-demo-001";
export const CURRICULUM_ID = "curr-demo-001";
export const ASSESSMENT_ID = "assess-demo-001";
export const ASSESSMENT_ID_2 = "assess-demo-002";
export const STUDENT_ID = "student-demo-001";
export const STUDENT_ID_2 = "student-demo-002";
export const STUDENT_ID_3 = "student-demo-003";
export const SUBMISSION_ID = "sub-demo-001";
export const SUBMISSION_ID_2 = "sub-demo-002";
export const SUBMISSION_ID_3 = "sub-demo-003";
export const CLASS_SECTION_ID = "class-demo-10a";

/** Thrown when a mock lookup would otherwise substitute another person's data. */
export class MockNotFoundError extends Error {
  constructor(message = "Data unavailable until this domain is connected") {
    super(message);
    this.name = "MockNotFoundError";
  }
}

export const students: Student[] = [
  {
    id: STUDENT_ID,
    tenant_id: TENANT_ID,
    institution_id: INSTITUTION_ID,
    class_section_id: CLASS_SECTION_ID,
    external_ref: "DEMO-001",
    first_name: "Demo",
    last_name: "Student 001",
    display_name: "Demo Student 001",
    grade: "10",
    section: "A",
    status: "ACTIVE",
    parent_email: "parent001@demo.eduvijna.local",
  },
  {
    id: STUDENT_ID_2,
    tenant_id: TENANT_ID,
    institution_id: INSTITUTION_ID,
    class_section_id: CLASS_SECTION_ID,
    external_ref: "DEMO-002",
    first_name: "Demo",
    last_name: "Student 002",
    display_name: "Demo Student 002",
    grade: "10",
    section: "A",
    status: "ACTIVE",
  },
  {
    id: STUDENT_ID_3,
    tenant_id: TENANT_ID,
    institution_id: INSTITUTION_ID,
    class_section_id: CLASS_SECTION_ID,
    external_ref: "DEMO-003",
    first_name: "Demo",
    last_name: "Student 003",
    display_name: "Demo Student 003",
    grade: "10",
    section: "A",
    status: "ACTIVE",
  },
];

export const curricula: Curriculum[] = [
  {
    id: CURRICULUM_ID,
    tenant_id: TENANT_ID,
    code: "CBSE-10-MATH-2025",
    title: "Grade 10 Mathematics",
    board: "CBSE",
    grade_label: "Grade 10",
    subject: "Mathematics",
    node_count: 12,
    updated_at: "2026-08-20T10:00:00Z",
  },
];

export const curriculumNodes: CurriculumNode[] = [
  {
    id: "node-grade-10",
    curriculum_id: CURRICULUM_ID,
    parent_id: null,
    node_type: "GRADE",
    code: "G10",
    title: "Grade 10",
    sort_order: 0,
  },
  {
    id: "node-subject-math",
    curriculum_id: CURRICULUM_ID,
    parent_id: "node-grade-10",
    node_type: "SUBJECT",
    code: "MATH",
    title: "Mathematics",
    sort_order: 0,
  },
  {
    id: "node-ch-quad",
    curriculum_id: CURRICULUM_ID,
    parent_id: "node-subject-math",
    node_type: "CHAPTER",
    code: "CH-QUAD",
    title: "Quadratic Equations",
    sort_order: 0,
  },
  {
    id: "node-topic-roots",
    curriculum_id: CURRICULUM_ID,
    parent_id: "node-ch-quad",
    node_type: "TOPIC",
    code: "T-ROOTS",
    title: "Nature of Roots",
    sort_order: 0,
  },
  {
    id: "node-concept-disc",
    curriculum_id: CURRICULUM_ID,
    parent_id: "node-topic-roots",
    node_type: "CONCEPT",
    code: "C-DISC",
    title: "Discriminant",
    sort_order: 0,
  },
  {
    id: "node-ch-tri",
    curriculum_id: CURRICULUM_ID,
    parent_id: "node-subject-math",
    node_type: "CHAPTER",
    code: "CH-TRI",
    title: "Triangles",
    sort_order: 1,
  },
  {
    id: "node-topic-sim",
    curriculum_id: CURRICULUM_ID,
    parent_id: "node-ch-tri",
    node_type: "TOPIC",
    code: "T-SIM",
    title: "Similarity",
    sort_order: 0,
  },
];

export const assessments: Assessment[] = [
  {
    id: ASSESSMENT_ID,
    tenant_id: TENANT_ID,
    institution_id: INSTITUTION_ID,
    title: "Mid-Term Mathematics — Demo Set A",
    code: "MATH-MT-DEMO-A",
    subject: "Mathematics",
    grade: "10",
    max_marks: 40,
    workflow_state: "ACTIVE",
    scheduled_at: "2026-08-15T09:00:00Z",
    question_count: 4,
    submission_count: 3,
    curriculum_id: CURRICULUM_ID,
    created_at: "2026-08-01T08:00:00Z",
    updated_at: "2026-08-14T12:00:00Z",
  },
  {
    id: ASSESSMENT_ID_2,
    tenant_id: TENANT_ID,
    institution_id: INSTITUTION_ID,
    title: "Unit Test — Quadratic Equations",
    code: "MATH-UT-QUAD",
    subject: "Mathematics",
    grade: "10",
    max_marks: 20,
    workflow_state: "RUBRIC_REVIEW",
    scheduled_at: null,
    question_count: 2,
    submission_count: 0,
    curriculum_id: CURRICULUM_ID,
    created_at: "2026-08-25T08:00:00Z",
    updated_at: "2026-08-28T12:00:00Z",
  },
];

export const questions: Question[] = [
  {
    id: "q-1",
    assessment_id: ASSESSMENT_ID,
    parent_id: null,
    code: "Q1",
    prompt: "Solve the quadratic equation x² − 5x + 6 = 0. Show all steps.",
    max_mark: 4,
    sort_order: 0,
    curriculum_node_ids: ["node-concept-disc", "node-topic-roots"],
  },
  {
    id: "q-1a",
    assessment_id: ASSESSMENT_ID,
    parent_id: "q-1",
    code: "Q1(a)",
    prompt: "Find the discriminant.",
    max_mark: 1,
    sort_order: 0,
    curriculum_node_ids: ["node-concept-disc"],
  },
  {
    id: "q-1b",
    assessment_id: ASSESSMENT_ID,
    parent_id: "q-1",
    code: "Q1(b)",
    prompt: "Find the roots.",
    max_mark: 3,
    sort_order: 1,
    curriculum_node_ids: ["node-topic-roots"],
  },
  {
    id: "q-2",
    assessment_id: ASSESSMENT_ID,
    parent_id: null,
    code: "Q2",
    prompt: "In △ABC, DE ∥ BC. If AD = 2 cm, DB = 3 cm, AE = 2.4 cm, find EC.",
    max_mark: 4,
    sort_order: 1,
    curriculum_node_ids: ["node-topic-sim"],
  },
  {
    id: "q-3",
    assessment_id: ASSESSMENT_ID,
    parent_id: null,
    code: "Q3",
    prompt: "Prove that the sum of angles in a triangle is 180°.",
    max_mark: 6,
    sort_order: 2,
    curriculum_node_ids: ["node-ch-tri"],
  },
  {
    id: "q-4",
    assessment_id: ASSESSMENT_ID,
    parent_id: null,
    code: "Q4",
    prompt: "A shopkeeper sells an article for ₹1,200 at 20% profit. Find CP.",
    max_mark: 4,
    sort_order: 3,
    curriculum_node_ids: ["node-subject-math"],
  },
];

export const rubrics: RubricCriterion[] = [
  {
    id: "rub-1a",
    question_id: "q-1a",
    label: "Discriminant formula",
    description: "Correctly states and computes D = b² − 4ac",
    max_marks: 1,
    sort_order: 0,
  },
  {
    id: "rub-1b-1",
    question_id: "q-1b",
    label: "Root formula",
    description: "Applies x = (−b ± √D) / 2a",
    max_marks: 1,
    sort_order: 0,
  },
  {
    id: "rub-1b-2",
    question_id: "q-1b",
    label: "Correct roots",
    description: "Obtains x = 2 and x = 3",
    max_marks: 2,
    sort_order: 1,
  },
  {
    id: "rub-2-1",
    question_id: "q-2",
    label: "Similarity / BPT setup",
    description: "Uses basic proportionality theorem correctly",
    max_marks: 2,
    sort_order: 0,
  },
  {
    id: "rub-2-2",
    question_id: "q-2",
    label: "Computation",
    description: "Computes EC = 3.6 cm",
    max_marks: 2,
    sort_order: 1,
  },
];

export const answerKeys: AnswerKeyStep[] = [
  {
    id: "ak-1a-1",
    question_id: "q-1a",
    step_index: 0,
    content: "D = (−5)² − 4(1)(6) = 25 − 24 = 1",
    marks: 1,
  },
  {
    id: "ak-1b-1",
    question_id: "q-1b",
    step_index: 0,
    content: "x = (5 ± 1) / 2 → x = 3 or x = 2",
    marks: 3,
  },
  {
    id: "ak-2-1",
    question_id: "q-2",
    step_index: 0,
    content: "AD/DB = AE/EC ⇒ 2/3 = 2.4/EC ⇒ EC = 3.6 cm",
    marks: 4,
  },
];

export const paperPages: PaperPage[] = [
  { id: "page-1", page_number: 1, label: "Page 1", width: 800, height: 1100 },
  { id: "page-2", page_number: 2, label: "Page 2", width: 800, height: 1100 },
];

/** Evidence regions use normalized 0–1 page coords (PDF.js-compatible). */
export const evidenceRegions: EvidenceRegion[] = [
  {
    id: "reg-1",
    page_id: "page-1",
    page_number: 1,
    x: 0.08,
    y: 0.12,
    width: 0.4,
    height: 0.08,
    label: "Roll / Name block",
    confidence: 0.72,
    question_id: null,
    crossed_out: false,
    annotation_kind: "NEUTRAL",
  },
  {
    id: "reg-2",
    page_id: "page-1",
    page_number: 1,
    x: 0.1,
    y: 0.24,
    width: 0.78,
    height: 0.22,
    label: "Q1 working",
    confidence: 0.91,
    question_id: "q-1",
    crossed_out: false,
    annotation_kind: "FULL",
  },
  {
    id: "reg-3",
    page_id: "page-1",
    page_number: 1,
    x: 0.1,
    y: 0.5,
    width: 0.78,
    height: 0.18,
    label: "Q2 working",
    confidence: 0.58,
    question_id: "q-2",
    crossed_out: false,
    annotation_kind: "PARTIAL",
  },
  {
    id: "reg-4",
    page_id: "page-2",
    page_number: 2,
    x: 0.12,
    y: 0.18,
    width: 0.75,
    height: 0.28,
    label: "Q3 proof",
    confidence: 0.87,
    question_id: "q-3",
    crossed_out: false,
    annotation_kind: "FULL",
  },
  {
    id: "reg-5",
    page_id: "page-2",
    page_number: 2,
    x: 0.12,
    y: 0.55,
    width: 0.7,
    height: 0.16,
    label: "Crossed-out attempt",
    confidence: 0.45,
    question_id: "q-4",
    crossed_out: true,
    annotation_kind: "DEDUCTION",
  },
];

export const submissions: Submission[] = [
  {
    id: SUBMISSION_ID,
    tenant_id: TENANT_ID,
    assessment_id: ASSESSMENT_ID,
    assessment_title: "Mid-Term Mathematics — Demo Set A",
    student_id: STUDENT_ID,
    student_display_name: "Demo Student 001",
    roll_number_detected: "DEMO-001",
    name_detected: "Demo Student 001",
    workflow_state: "EVALUATION_REVIEW",
    student_match_state: "CONFIRMED",
    identity_confidence: 0.94,
    mapping_confidence: 0.88,
    transcription_state: "READY",
    page_count: 2,
    uploaded_at: "2026-08-16T10:15:00Z",
    updated_at: "2026-08-16T11:40:00Z",
  },
  {
    id: SUBMISSION_ID_2,
    tenant_id: TENANT_ID,
    assessment_id: ASSESSMENT_ID,
    assessment_title: "Mid-Term Mathematics — Demo Set A",
    student_id: null,
    student_display_name: null,
    roll_number_detected: "DEMO-00?",
    name_detected: "Demo Stud…",
    workflow_state: "IDENTITY_REVIEW",
    student_match_state: "REVIEW_REQUIRED",
    identity_confidence: 0.48,
    mapping_confidence: 0.0,
    transcription_state: "NOT_STARTED",
    page_count: 2,
    uploaded_at: "2026-08-16T10:20:00Z",
    updated_at: "2026-08-16T10:35:00Z",
  },
  {
    id: SUBMISSION_ID_3,
    tenant_id: TENANT_ID,
    assessment_id: ASSESSMENT_ID,
    assessment_title: "Mid-Term Mathematics — Demo Set A",
    student_id: STUDENT_ID_2,
    student_display_name: "Demo Student 002",
    roll_number_detected: "DEMO-002",
    name_detected: "Demo Student 002",
    workflow_state: "MAPPING_REVIEW",
    student_match_state: "AUTO_MATCHED",
    identity_confidence: 0.9,
    mapping_confidence: 0.52,
    transcription_state: "NOT_STARTED",
    page_count: 2,
    uploaded_at: "2026-08-16T10:25:00Z",
    updated_at: "2026-08-16T10:50:00Z",
  },
];

function ledgerBase(
  overrides: Partial<EvaluationLedger> &
    Pick<EvaluationLedger, "id" | "question_id" | "proposed_ai_score" | "max_mark">,
): EvaluationLedger {
  return {
    tenant_id: TENANT_ID,
    evaluation_run_id: "erun-demo-001",
    submission_id: SUBMISSION_ID,
    student_id: STUDENT_ID,
    assessment_id: ASSESSMENT_ID,
    assessment_version_id: "av-demo-001",
    question_version_id: "qv-demo-001",
    rubric_version_id: "rv-demo-001",
    answer_key_version_id: "akv-demo-001",
    answer_region_ids: ["reg-2"],
    criterion_decisions: [],
    final_human_approved_score: null,
    error_codes: [],
    ecf_applied: false,
    identity_confidence: 0.94,
    mapping_confidence: 0.88,
    transcription_confidence: 0.82,
    evaluation_confidence: 0.76,
    math_verification_confidence: 0.8,
    workflow_state: "PROPOSED",
    ledger_version: 1,
    feedback_draft: "",
    corrected_approach: "",
    teacher_notes: null,
    ...overrides,
  };
}

export const evaluationLedgers: EvaluationLedger[] = [
  ledgerBase({
    id: "led-q1a",
    question_id: "q-1a",
    max_mark: 1,
    proposed_ai_score: 1,
    answer_region_ids: ["reg-2"],
    evaluation_confidence: 0.93,
    workflow_state: "PROPOSED",
    criterion_decisions: [
      {
        rubric_criterion_id: "rub-1a",
        criterion_label: "Discriminant formula",
        max_marks: 1,
        proposed_marks: 1,
        final_marks: null,
        decision: "AWARDED",
        error_code: null,
        deduction_reason: null,
        step_index: 0,
      },
    ],
    feedback_draft: "Discriminant correctly computed as 1.",
    corrected_approach: "D = b² − 4ac = 25 − 24 = 1.",
  }),
  ledgerBase({
    id: "led-q1b",
    question_id: "q-1b",
    max_mark: 3,
    proposed_ai_score: 2,
    answer_region_ids: ["reg-2"],
    evaluation_confidence: 0.71,
    workflow_state: "REVIEW_REQUIRED",
    error_codes: ["CALCULATION"],
    ecf_applied: true,
    criterion_decisions: [
      {
        rubric_criterion_id: "rub-1b-1",
        criterion_label: "Root formula",
        max_marks: 1,
        proposed_marks: 1,
        final_marks: null,
        decision: "AWARDED",
        error_code: null,
        deduction_reason: null,
        step_index: 0,
      },
      {
        rubric_criterion_id: "rub-1b-2",
        criterion_label: "Correct roots",
        max_marks: 2,
        proposed_marks: 1,
        final_marks: null,
        decision: "PARTIAL",
        error_code: "CALCULATION",
        deduction_reason: "Arithmetic slip in one root; ECF applied.",
        step_index: 1,
      },
    ],
    feedback_draft:
      "Formula correct. One root arithmetic error; method credit retained.",
    corrected_approach: "x = (5 ± 1)/2 → x = 3 or x = 2.",
  }),
  ledgerBase({
    id: "led-q2",
    question_id: "q-2",
    max_mark: 4,
    proposed_ai_score: 2,
    answer_region_ids: ["reg-3"],
    evaluation_confidence: 0.55,
    mapping_confidence: 0.58,
    transcription_confidence: 0.6,
    workflow_state: "REVIEW_REQUIRED",
    error_codes: ["METHOD", "CALCULATION"],
    criterion_decisions: [
      {
        rubric_criterion_id: "rub-2-1",
        criterion_label: "Similarity / BPT setup",
        max_marks: 2,
        proposed_marks: 1,
        final_marks: null,
        decision: "PARTIAL",
        error_code: "METHOD",
        deduction_reason: "Ratio inverted in setup.",
        step_index: 0,
      },
      {
        rubric_criterion_id: "rub-2-2",
        criterion_label: "Computation",
        max_marks: 2,
        proposed_marks: 1,
        final_marks: null,
        decision: "PARTIAL",
        error_code: "CALCULATION",
        deduction_reason: "Final value incorrect due to inverted ratio.",
        step_index: 1,
      },
    ],
    feedback_draft: "BPT identified but ratio orientation incorrect.",
    corrected_approach: "AD/DB = AE/EC ⇒ 2/3 = 2.4/EC ⇒ EC = 3.6 cm.",
    ecf_applied: true,
  }),
  ledgerBase({
    id: "led-q3",
    question_id: "q-3",
    max_mark: 6,
    proposed_ai_score: 5,
    answer_region_ids: ["reg-4"],
    evaluation_confidence: 0.86,
    workflow_state: "PROPOSED",
    error_codes: ["PRESENTATION"],
    criterion_decisions: [],
    feedback_draft: "Proof substantially correct; minor labelling gaps.",
    corrected_approach:
      "Draw line through A parallel to BC; alternate interior angles…",
  }),
  ledgerBase({
    id: "led-q4",
    question_id: "q-4",
    max_mark: 4,
    proposed_ai_score: 0,
    answer_region_ids: ["reg-5"],
    evaluation_confidence: 0.4,
    workflow_state: "REVIEW_REQUIRED",
    error_codes: ["INCOMPLETE"],
    criterion_decisions: [],
    feedback_draft: "Primary attempt crossed out; no complete final answer.",
    corrected_approach: "SP = CP × 1.2 ⇒ CP = 1200 / 1.2 = ₹1,000.",
  }),
];

export function getDashboardSummary(): DashboardSummary {
  return {
    pending_identity: submissions.filter(
      (s) => s.workflow_state === "IDENTITY_REVIEW",
    ).length,
    pending_mapping: submissions.filter(
      (s) => s.workflow_state === "MAPPING_REVIEW",
    ).length,
    pending_evaluation: submissions.filter(
      (s) => s.workflow_state === "EVALUATION_REVIEW",
    ).length,
    active_assessments: assessments.filter((a) => a.workflow_state === "ACTIVE")
      .length,
    recent_submissions: submissions,
    recent_assessments: assessments,
  };
}

export function getIdentityReview(submissionId: string): IdentityReviewPayload {
  const submission = submissions.find((s) => s.id === submissionId);
  if (!submission) {
    throw new MockNotFoundError("Submission not found");
  }
  return {
    submission,
    candidates: [
      {
        student_id: STUDENT_ID,
        display_name: "Demo Student 001",
        external_ref: "DEMO-001",
        grade: "10",
        section: "A",
        confidence: 0.62,
        match_reasons: ["Partial roll match", "Name OCR similarity"],
      },
      {
        student_id: STUDENT_ID_2,
        display_name: "Demo Student 002",
        external_ref: "DEMO-002",
        grade: "10",
        section: "A",
        confidence: 0.41,
        match_reasons: ["Same section roster"],
      },
      {
        student_id: STUDENT_ID_3,
        display_name: "Demo Student 003",
        external_ref: "DEMO-003",
        grade: "10",
        section: "A",
        confidence: 0.22,
        match_reasons: ["Weak name token overlap"],
      },
    ],
    pages: paperPages,
  };
}

export function getMappingReview(submissionId: string): MappingReviewPayload {
  const submission = submissions.find((s) => s.id === submissionId);
  if (!submission) {
    throw new MockNotFoundError("Submission not found");
  }
  return {
    submission,
    pages: paperPages,
    regions: evidenceRegions,
    mapping: [
      {
        question_id: "q-1",
        question_code: "Q1",
        region_ids: ["reg-2"],
        confidence: 0.91,
        status: "CONFIRMED",
      },
      {
        question_id: "q-2",
        question_code: "Q2",
        region_ids: ["reg-3"],
        confidence: 0.58,
        status: "REVIEW_REQUIRED",
      },
      {
        question_id: "q-3",
        question_code: "Q3",
        region_ids: ["reg-4"],
        confidence: 0.87,
        status: "PROPOSED",
      },
      {
        question_id: "q-4",
        question_code: "Q4",
        region_ids: ["reg-5"],
        confidence: 0.45,
        status: "CROSSED_OUT",
      },
    ],
    questions: questions.filter((q) => q.parent_id === null),
  };
}

export function getTranscriptionWorkspace(
  submissionId: string,
): TranscriptionWorkspacePayload {
  const submission = submissions.find((s) => s.id === submissionId);
  if (!submission) {
    throw new MockNotFoundError("Submission not found");
  }
  const aiProposal = {
    id: "tx-ai-1",
    answer_region_id: "reg-2",
    version_number: 1,
    source_type: "AI" as const,
    text: "x = 4",
    latex: null,
    transcription_confidence: 0.78,
    unreadable: false,
    visual_only: false,
    status: "PROPOSED",
    confirmed_by: null,
    confirmed_at: null,
  };
  const humanCorrected = {
    id: "tx-human-1",
    answer_region_id: "reg-3",
    version_number: 2,
    source_type: "HUMAN" as const,
    text: "x = 5 (corrected)",
    latex: null,
    transcription_confidence: null,
    unreadable: false,
    visual_only: false,
    status: "CONFIRMED",
    confirmed_by: "user-teacher-001",
    confirmed_at: "2026-08-16T11:00:00Z",
  };
  return {
    submission_id: submission.id,
    workflow_state: submission.workflow_state,
    transcription_state: submission.transcription_state ?? "REVIEW_REQUIRED",
    automated_transcription_active: true,
    progress: {
      reviewed: 1,
      required: 2,
      label: "1 of 2 evidence regions reviewed",
    },
    items: [
      {
        question_version_id: "q-1",
        question_label: "Q1",
        disposition: "ANSWERED",
        mapping_state: "CONFIRMED",
        requires_transcription: true,
        regions: [
          {
            id: "reg-2",
            label: "Q1 answer",
            region_type: "ANSWER",
            source_type: "AI",
            detection_confidence: 0.91,
            bbox: { x: 0.1, y: 0.2, width: 0.3, height: 0.15 },
            crop_url: null,
            page_index: 0,
            latest_ai_proposal: aiProposal,
            active_transcription: aiProposal,
            requires_transcription: true,
          },
        ],
      },
      {
        question_version_id: "q-2",
        question_label: "Q2",
        disposition: "ANSWERED",
        mapping_state: "CONFIRMED",
        requires_transcription: true,
        regions: [
          {
            id: "reg-3",
            label: "Q2 answer",
            region_type: "ANSWER",
            source_type: "HUMAN",
            detection_confidence: 0.88,
            bbox: { x: 0.15, y: 0.35, width: 0.35, height: 0.12 },
            crop_url: null,
            page_index: 0,
            latest_ai_proposal: {
              ...aiProposal,
              id: "tx-ai-2",
              answer_region_id: "reg-3",
              text: "x = 5",
            },
            active_transcription: humanCorrected,
            requires_transcription: true,
          },
        ],
      },
    ],
  };
}

export function getEvaluationWorkspace(
  submissionId: string,
  questionId?: string,
): EvaluationWorkspacePayload {
  const submission = submissions.find((s) => s.id === submissionId);
  if (!submission) {
    throw new MockNotFoundError("Submission not found");
  }
  const assessment = assessments.find((a) => a.id === submission.assessment_id);
  if (!assessment) {
    throw new MockNotFoundError("Assessment not found");
  }
  const student =
    students.find((s) => s.id === (submission.student_id ?? "")) ?? null;
  const selected =
    questionId ??
    evaluationLedgers.find((l) => l.workflow_state === "REVIEW_REQUIRED")
      ?.question_id ??
    "q-1b";

  return {
    submission,
    assessment,
    student,
    pages: paperPages,
    regions: evidenceRegions,
    questions: buildQuestionTree(assessment.id),
    ledgers: evaluationLedgers,
    rubrics,
    answer_keys: answerKeys,
    selected_question_id: selected,
  };
}

export function getStudentReport(
  studentId: string,
  assessmentId: string,
): StudentReport {
  const student = students.find((s) => s.id === studentId);
  if (!student) {
    throw new MockNotFoundError(
      "Data unavailable until this domain is connected",
    );
  }
  const assessment = assessments.find((a) => a.id === assessmentId);
  if (!assessment) {
    throw new MockNotFoundError(
      "Data unavailable until this domain is connected",
    );
  }
  return {
    student,
    assessment,
    total_score: 28,
    max_marks: 40,
    percentage: 70,
    question_summaries: [
      {
        question_id: "q-1a",
        question_code: "Q1(a)",
        max_mark: 1,
        proposed_score: 1,
        final_score: 1,
        workflow_state: "ACCEPTED",
        error_codes: [],
      },
      {
        question_id: "q-1b",
        question_code: "Q1(b)",
        max_mark: 3,
        proposed_score: 2,
        final_score: 2,
        workflow_state: "OVERRIDDEN",
        error_codes: ["CALCULATION"],
      },
      {
        question_id: "q-2",
        question_code: "Q2",
        max_mark: 4,
        proposed_score: 2,
        final_score: 2,
        workflow_state: "ACCEPTED",
        error_codes: ["METHOD", "CALCULATION"],
      },
      {
        question_id: "q-3",
        question_code: "Q3",
        max_mark: 6,
        proposed_score: 5,
        final_score: 5,
        workflow_state: "ACCEPTED",
        error_codes: ["PRESENTATION"],
      },
      {
        question_id: "q-4",
        question_code: "Q4",
        max_mark: 4,
        proposed_score: 0,
        final_score: 0,
        workflow_state: "ACCEPTED",
        error_codes: ["INCOMPLETE"],
      },
    ],
    strengths: [
      "Strong grasp of discriminant and quadratic formula setup",
      "Geometry proof structure mostly complete",
    ],
    weaknesses: [
      "Ratio orientation in similarity applications",
      "Careless arithmetic under exam pressure",
    ],
    patterns: [
      "Method often correct with late-stage calculation slips",
      "Crossed-out work left without a replacement answer",
    ],
    next_actions: [
      "Complete Priority 1 path on Basic Proportionality Theorem",
      "Timed drill: 8 quadratic root calculations",
    ],
    topic_focus: [
      { topic: "Similarity / BPT", mastery: 0.45, priority: 1 },
      { topic: "Quadratic roots", mastery: 0.72, priority: 2 },
      { topic: "Profit & loss", mastery: 0.3, priority: 3 },
    ],
    evidence_highlights: [
      {
        question_code: "Q1(a)",
        excerpt: "D = 25 − 24 = 1",
        outcome: "CORRECT",
      },
      {
        question_code: "Q2",
        excerpt: "Used DB/AD instead of AD/DB",
        outcome: "DEDUCTED",
      },
    ],
    corrected_approaches: [
      {
        question_code: "Q2",
        approach: "AD/DB = AE/EC ⇒ 2/3 = 2.4/EC ⇒ EC = 3.6 cm",
      },
      {
        question_code: "Q4",
        approach: "CP = SP / 1.2 = 1200 / 1.2 = ₹1,000",
      },
    ],
  };
}

export function getParentReport(
  studentId: string,
  assessmentId: string,
): ParentReport {
  const student = students.find((s) => s.id === studentId);
  if (!student) {
    throw new MockNotFoundError(
      "Data unavailable until this domain is connected",
    );
  }
  const assessment = assessments.find((a) => a.id === assessmentId);
  if (!assessment) {
    throw new MockNotFoundError(
      "Data unavailable until this domain is connected",
    );
  }
  return {
    student_display_name: student.display_name,
    assessment_title: assessment.title,
    score_summary: `${student.display_name} scored 28 out of 40 (70%).`,
    what_went_well: [
      "Understood how to set up quadratic equations",
      "Wrote a mostly complete geometry proof",
    ],
    what_to_practice: [
      "Careful checking of ratios in triangle similarity",
      "Finishing questions instead of leaving crossed-out work",
    ],
    how_to_help: [
      "Ask your child to explain one similarity problem aloud this weekend",
      "Encourage a 10-minute check of arithmetic before submitting",
    ],
    next_step:
      "Complete the teacher-approved short practice set on similarity.",
  };
}

export function getAssessmentAnalytics(
  assessmentId: string,
): AssessmentAnalytics {
  const assessment = assessments.find((a) => a.id === assessmentId);
  if (!assessment) {
    throw new MockNotFoundError(
      "Data unavailable until this domain is connected",
    );
  }
  return {
    assessment,
    mean_score: 26.4,
    median_score: 27,
    pass_rate: 0.78,
    question_difficulty: [
      {
        question_code: "Q1",
        mean_score_pct: 82,
        common_errors: ["CALCULATION"],
      },
      {
        question_code: "Q2",
        mean_score_pct: 54,
        common_errors: ["METHOD", "CALCULATION"],
      },
      {
        question_code: "Q3",
        mean_score_pct: 71,
        common_errors: ["PRESENTATION", "LOGIC_REASONING"],
      },
      {
        question_code: "Q4",
        mean_score_pct: 48,
        common_errors: ["INCOMPLETE", "FORMULA"],
      },
    ],
    error_distribution: [
      { code: "CALCULATION", count: 14 },
      { code: "METHOD", count: 9 },
      { code: "INCOMPLETE", count: 7 },
      { code: "PRESENTATION", count: 5 },
      { code: "CONCEPT", count: 3 },
    ],
    score_bands: [
      { label: "0–39%", count: 2 },
      { label: "40–59%", count: 5 },
      { label: "60–79%", count: 12 },
      { label: "80–100%", count: 6 },
    ],
  };
}

export function getStudentAnalytics(studentId: string): StudentAnalytics {
  const student = students.find((s) => s.id === studentId);
  // Do not substitute a different student — avoids hybrid HTTP/mock identity mixups.
  if (!student) {
    throw new MockNotFoundError(
      "Data unavailable until this domain is connected",
    );
  }
  return {
    student,
    assessments_taken: 3,
    average_percentage: 68.5,
    trend: [
      { assessment_code: "MATH-UT-1", percentage: 62 },
      { assessment_code: "MATH-UT-2", percentage: 66 },
      { assessment_code: "MATH-MT-DEMO-A", percentage: 70 },
    ],
    concept_mastery: [
      { concept: "Discriminant", mastery: 0.85 },
      { concept: "Quadratic roots", mastery: 0.72 },
      { concept: "Similarity / BPT", mastery: 0.45 },
      { concept: "Angle sum proof", mastery: 0.78 },
      { concept: "Profit & loss", mastery: 0.3 },
    ],
    recurring_errors: [
      { code: "CALCULATION", count: 6 },
      { code: "METHOD", count: 4 },
      { code: "INCOMPLETE", count: 3 },
    ],
  };
}

function emptyB12AsOf(): string {
  return "2026-09-07T12:00:00.000Z";
}

/** Demo-only B12 fixtures — never invent longitudinal data for live UUIDs. */
export function getStudentMasteryState(
  studentId: string,
): StudentMasteryState {
  const student = students.find((s) => s.id === studentId);
  if (!student) {
    throw new MockNotFoundError(
      "Data unavailable until this domain is connected",
    );
  }
  if (studentId !== STUDENT_ID) {
    return {
      student_id: studentId,
      items: [],
      algorithm_version: "B12_V1",
      source: "MASTERY_EVIDENCE",
      as_of: emptyB12AsOf(),
    };
  }
  return {
    student_id: studentId,
    items: [
      {
        id: "ms-demo-001",
        curriculum_node_id: "node-demo-disc",
        curriculum_id: CURRICULUM_ID,
        code: "DISC",
        title: "Discriminant",
        node_type: "TOPIC",
        concept_mastery: 0.85,
        execution_accuracy: 0.6,
        concept_decisive_count: 4,
        execution_decisive_count: 5,
        concept_inconclusive_count: 0,
        execution_inconclusive_count: 1,
        evidence_count: 6,
        insufficient_concept_evidence: false,
        insufficient_execution_evidence: false,
        source_evidence_hash: "demo-hash-disc",
        algorithm_version: "B12_V1",
        last_updated_at: emptyB12AsOf(),
      },
      {
        id: "ms-demo-002",
        curriculum_node_id: "node-demo-bpt",
        curriculum_id: CURRICULUM_ID,
        code: "BPT",
        title: "Similarity / BPT",
        node_type: "TOPIC",
        concept_mastery: null,
        execution_accuracy: 0.4,
        concept_decisive_count: 0,
        execution_decisive_count: 3,
        concept_inconclusive_count: 2,
        execution_inconclusive_count: 0,
        evidence_count: 3,
        insufficient_concept_evidence: true,
        insufficient_execution_evidence: false,
        source_evidence_hash: "demo-hash-bpt",
        algorithm_version: "B12_V1",
        last_updated_at: emptyB12AsOf(),
      },
    ],
    algorithm_version: "B12_V1",
    source: "MASTERY_EVIDENCE",
    as_of: emptyB12AsOf(),
  };
}

export function getStudentMasteryTrend(
  studentId: string,
  _options?: { curriculumNodeId?: string },
): StudentMasteryTrend {
  const student = students.find((s) => s.id === studentId);
  if (!student) {
    throw new MockNotFoundError(
      "Data unavailable until this domain is connected",
    );
  }
  if (studentId !== STUDENT_ID) {
    return {
      student_id: studentId,
      curriculum_node_id: _options?.curriculumNodeId ?? null,
      points: [],
      algorithm_version: "B12_V1",
      source: "MASTERY_EVIDENCE",
      as_of: emptyB12AsOf(),
    };
  }
  return {
    student_id: studentId,
    curriculum_node_id: _options?.curriculumNodeId ?? null,
    points: [
      {
        curriculum_node_id: "node-demo-disc",
        curriculum_id: CURRICULUM_ID,
        code: "DISC",
        title: "Discriminant",
        published_result_id: "pr-demo-001",
        assessment_id: ASSESSMENT_ID,
        assessment_code: "MATH-UT-1",
        effective_at: "2026-08-01T10:00:00.000Z",
        concept_mastery: 0.5,
        execution_accuracy: 0.4,
        concept_decisive_count: 2,
        execution_decisive_count: 2,
        evidence_count: 2,
        insufficient_concept_evidence: false,
        insufficient_execution_evidence: false,
        source_evidence_hash: "demo-hash-t1",
        algorithm_version: "B12_V1",
      },
      {
        curriculum_node_id: "node-demo-disc",
        curriculum_id: CURRICULUM_ID,
        code: "DISC",
        title: "Discriminant",
        published_result_id: "pr-demo-002",
        assessment_id: ASSESSMENT_ID_2,
        assessment_code: "MATH-MT-DEMO-A",
        effective_at: "2026-09-01T10:00:00.000Z",
        concept_mastery: 0.85,
        execution_accuracy: 0.6,
        concept_decisive_count: 4,
        execution_decisive_count: 5,
        evidence_count: 6,
        insufficient_concept_evidence: false,
        insufficient_execution_evidence: false,
        source_evidence_hash: "demo-hash-t2",
        algorithm_version: "B12_V1",
      },
    ],
    algorithm_version: "B12_V1",
    source: "MASTERY_EVIDENCE",
    as_of: emptyB12AsOf(),
  };
}

export function getStudentRepeatedErrors(
  studentId: string,
): StudentRepeatedErrors {
  const student = students.find((s) => s.id === studentId);
  if (!student) {
    throw new MockNotFoundError(
      "Data unavailable until this domain is connected",
    );
  }
  if (studentId !== STUDENT_ID) {
    return {
      student_id: studentId,
      items: [],
      recurrence_threshold: 2,
      algorithm_version: "B12_V1",
      source: "MASTERY_EVIDENCE",
      as_of: emptyB12AsOf(),
    };
  }
  return {
    student_id: studentId,
    items: [
      {
        error_code: "CALCULATION",
        occurrence_count: 4,
        distinct_published_result_count: 2,
        distinct_assessment_count: 2,
        first_seen_at: "2026-08-01T10:00:00.000Z",
        last_seen_at: "2026-09-01T10:00:00.000Z",
        affected_question_evaluations: [
          {
            published_result_id: "pr-demo-001",
            assessment_id: ASSESSMENT_ID,
            question_evaluation_id: "qe-demo-001",
            question_version_id: "qv-demo-001",
          },
          {
            published_result_id: "pr-demo-002",
            assessment_id: ASSESSMENT_ID_2,
            question_evaluation_id: "qe-demo-002",
            question_version_id: "qv-demo-002",
          },
        ],
        curriculum_node_ids: ["node-demo-disc"],
      },
    ],
    recurrence_threshold: 2,
    algorithm_version: "B12_V1",
    source: "MASTERY_EVIDENCE",
    as_of: emptyB12AsOf(),
  };
}

export function getStudentRecoverableMarks(
  studentId: string,
): StudentRecoverableMarks {
  const student = students.find((s) => s.id === studentId);
  if (!student) {
    throw new MockNotFoundError(
      "Data unavailable until this domain is connected",
    );
  }
  if (studentId !== STUDENT_ID) {
    return {
      student_id: studentId,
      total_lost_marks: "0.00",
      attributed_potentially_recoverable_marks: "0.00",
      unattributed_lost_marks: "0.00",
      items: [],
      disclaimer: B12_RECOVERABLE_MARKS_DISCLAIMER,
      algorithm_version: "B12_V1",
      source: "PUBLISHED_LEDGER",
      as_of: emptyB12AsOf(),
    };
  }
  return {
    student_id: studentId,
    total_lost_marks: "7.50",
    attributed_potentially_recoverable_marks: "5.00",
    unattributed_lost_marks: "2.50",
    items: [
      {
        error_code: "CALCULATION",
        potentially_recoverable_marks: "5.00",
        occurrence_count: 2,
        percent_of_total_lost: 66.67,
        affected_references: [
          {
            published_result_id: "pr-demo-001",
            assessment_id: ASSESSMENT_ID,
            question_evaluation_id: "qe-demo-001",
            criterion_evaluation_id: "ce-demo-001",
          },
        ],
      },
    ],
    disclaimer: B12_RECOVERABLE_MARKS_DISCLAIMER,
    algorithm_version: "B12_V1",
    source: "PUBLISHED_LEDGER",
    as_of: emptyB12AsOf(),
  };
}

export function getStudentMistakeNotebook(
  studentId: string,
): StudentMistakeNotebook {
  const student = students.find((s) => s.id === studentId);
  if (!student) {
    throw new MockNotFoundError(
      "Data unavailable until this domain is connected",
    );
  }
  if (studentId !== STUDENT_ID) {
    return {
      student_id: studentId,
      entries: [],
      algorithm_version: "B12_V1",
      source: "PUBLISHED_LEDGER",
      as_of: emptyB12AsOf(),
    };
  }
  return {
    student_id: studentId,
    entries: [
      {
        id: "nb-demo-001",
        published_result_id: "pr-demo-001",
        assessment_id: ASSESSMENT_ID,
        assessment_code: "MATH-UT-1",
        submission_id: SUBMISSION_ID,
        question_evaluation_id: "qe-demo-001",
        question_version_id: "qv-demo-001",
        question_code: "Q1",
        academic_error_code: "CALCULATION",
        final_score: "3.00",
        max_mark: "5.00",
        deduction_reasons: ["Arithmetic slip in discriminant expansion"],
        first_divergence_step: "2",
        curriculum_nodes: [
          {
            id: "node-demo-disc",
            code: "DISC",
            title: "Discriminant",
            node_type: "TOPIC",
          },
        ],
        recommended_practice_kind: "EXECUTION_PRACTICE",
        linked_learning_recommendation_ids: ["rec-demo-001"],
        source_ledger_snapshot_hash: "demo-ledger-hash-1",
        algorithm_version: "B12_V1",
        materialized_at: emptyB12AsOf(),
        effective_at: "2026-08-01T10:00:00.000Z",
      },
      {
        id: "nb-demo-002",
        published_result_id: "pr-demo-002",
        assessment_id: ASSESSMENT_ID_2,
        assessment_code: "MATH-MT-DEMO-A",
        submission_id: "sub-demo-002",
        question_evaluation_id: "qe-demo-002",
        question_version_id: "qv-demo-002",
        question_code: "Q2",
        academic_error_code: "METHOD",
        final_score: "2.00",
        max_mark: "5.00",
        deduction_reasons: ["Incorrect approach to BPT application"],
        first_divergence_step: "1",
        curriculum_nodes: [
          {
            id: "node-demo-bpt",
            code: "BPT",
            title: "Similarity / BPT",
            node_type: "TOPIC",
          },
        ],
        recommended_practice_kind: "CONCEPT_CHECK",
        linked_learning_recommendation_ids: [],
        source_ledger_snapshot_hash: "demo-ledger-hash-2",
        algorithm_version: "B12_V1",
        materialized_at: emptyB12AsOf(),
        effective_at: "2026-09-01T10:00:00.000Z",
      },
    ],
    algorithm_version: "B12_V1",
    source: "PUBLISHED_LEDGER",
    as_of: emptyB12AsOf(),
  };
}

export function getAdaptiveLearning(studentId: string): AdaptiveLearningPlan {
  const student = students.find((s) => s.id === studentId);
  if (!student) {
    throw new MockNotFoundError(
      "Data unavailable until this domain is connected",
    );
  }
  return {
    student,
    priorities: [
      {
        id: "prio-1",
        topic: "Similarity / Basic Proportionality Theorem",
        priority: 1,
        reason: "Lowest mastery with recurring METHOD errors on Q2-type items",
        mastery: 0.45,
        error_codes: ["METHOD", "CALCULATION"],
      },
      {
        id: "prio-2",
        topic: "Quadratic root arithmetic",
        priority: 2,
        reason: "Formula known; late-stage CALCULATION slips",
        mastery: 0.72,
        error_codes: ["CALCULATION"],
      },
      {
        id: "prio-3",
        topic: "Profit & loss applications",
        priority: 3,
        reason: "Incomplete attempts and formula recall gaps",
        mastery: 0.3,
        error_codes: ["INCOMPLETE", "FORMULA"],
      },
    ],
    path: [
      {
        id: "lp-1",
        kind: "PREREQUISITE",
        title: "Refresh ratios and proportions",
        description: "Quick check that ratio language is secure",
        estimated_minutes: 10,
        completed: true,
      },
      {
        id: "lp-2",
        kind: "LEARN",
        title: "Learn BPT statement and diagram",
        description: "Concept card with labelled similar triangles",
        estimated_minutes: 15,
        completed: true,
      },
      {
        id: "lp-3",
        kind: "WORKED_EXAMPLE",
        title: "Worked example: AD/DB = AE/EC",
        description: "Step-by-step solution with orientation callouts",
        estimated_minutes: 12,
        completed: false,
      },
      {
        id: "lp-4",
        kind: "GUIDED",
        title: "Guided practice (hints on)",
        description: "3 items with progressive hint release",
        estimated_minutes: 20,
        completed: false,
      },
      {
        id: "lp-5",
        kind: "INDEPENDENT",
        title: "Independent practice",
        description: "4 items without hints",
        estimated_minutes: 20,
        completed: false,
      },
      {
        id: "lp-6",
        kind: "EXAM_STYLE",
        title: "Exam-style mixed set",
        description: "Timed mini-set matching assessment language",
        estimated_minutes: 25,
        completed: false,
      },
      {
        id: "lp-7",
        kind: "MASTERY_CHECK",
        title: "Mastery check",
        description: "Short checkpoint before improvement assessment",
        estimated_minutes: 15,
        completed: false,
      },
    ],
    error_distribution: [
      { code: "METHOD", count: 4 },
      { code: "CALCULATION", count: 6 },
      { code: "INCOMPLETE", count: 3 },
      { code: "FORMULA", count: 2 },
    ],
  };
}

export function getImprovementBlueprint(
  studentId: string,
): ImprovementAssessmentBlueprint {
  return {
    id: "imp-demo-001",
    student_id: studentId,
    title: "Improvement Check — Calculus & Statistics",
    workflow_state: "PENDING_APPROVAL",
    target_topics: [
      "Second Derivatives",
      "Maxima/Minima",
      "Variance",
      "Regression",
    ],
    question_outline: [
      {
        code: "I1",
        focus: "Second Derivatives (2q)",
        max_mark: 4,
        difficulty: "MEDIUM",
      },
      {
        code: "I2",
        focus: "Second Derivatives — application",
        max_mark: 4,
        difficulty: "MEDIUM",
      },
      {
        code: "I3",
        focus: "Maxima/Minima (2q)",
        max_mark: 4,
        difficulty: "MEDIUM",
      },
      {
        code: "I4",
        focus: "Maxima/Minima — word problem",
        max_mark: 4,
        difficulty: "HARD",
      },
      {
        code: "I5",
        focus: "Variance (2q)",
        max_mark: 3,
        difficulty: "EASY",
      },
      {
        code: "I6",
        focus: "Variance — interpretation",
        max_mark: 3,
        difficulty: "MEDIUM",
      },
      {
        code: "I7",
        focus: "Regression (1q)",
        max_mark: 5,
        difficulty: "HARD",
      },
    ],
    teacher_notes:
      "Awaiting teacher approval before student release. Recommendations restricted to student's curriculum.",
    created_at: "2026-08-18T09:00:00Z",
  };
}

export function getAssessmentCurriculumMap(
  assessmentId: string,
): CurriculumMapEntry[] {
  const qs = questions.filter(
    (q) => q.assessment_id === assessmentId && q.parent_id === null,
  );
  const titleById = new Map(curriculumNodes.map((n) => [n.id, n.title]));
  return qs.map((q) => ({
    question_id: q.id,
    question_code: q.code,
    curriculum_node_ids: q.curriculum_node_ids,
    node_titles: q.curriculum_node_ids.map(
      (id) => titleById.get(id) ?? id,
    ),
  }));
}

export function buildCurriculumTree(): CurriculumNode[] {
  const byParent = new Map<string | null, CurriculumNode[]>();
  for (const node of curriculumNodes) {
    const list = byParent.get(node.parent_id) ?? [];
    list.push({ ...node, children: [] });
    byParent.set(node.parent_id, list);
  }
  const attach = (parentId: string | null): CurriculumNode[] => {
    const nodes = (byParent.get(parentId) ?? []).sort(
      (a, b) => a.sort_order - b.sort_order,
    );
    return nodes.map((n) => ({ ...n, children: attach(n.id) }));
  };
  return attach(null);
}

export function buildQuestionTree(assessmentId: string): Question[] {
  const qs = questions.filter((q) => q.assessment_id === assessmentId);
  const byParent = new Map<string | null, Question[]>();
  for (const q of qs) {
    const list = byParent.get(q.parent_id) ?? [];
    list.push({ ...q, children: [] });
    byParent.set(q.parent_id, list);
  }
  const attach = (parentId: string | null): Question[] => {
    const nodes = (byParent.get(parentId) ?? []).sort(
      (a, b) => a.sort_order - b.sort_order,
    );
    return nodes.map((n) => ({ ...n, children: attach(n.id) }));
  };
  return attach(null);
}

/** Demo-only B13 fixtures — never invent catalog data for live UUIDs. */
export const RESOURCE_ID = "resource-demo-001";
export const RESOURCE_ID_DRAFT = "resource-demo-draft";
export const ASSIGNMENT_ID = "assignment-demo-001";

const B13_AS_OF = "2026-09-07T12:00:00.000Z";

let demoResources: CurriculumResource[] = [
  {
    id: RESOURCE_ID,
    curriculum_id: CURRICULUM_ID,
    code: "RES-DEMO-001",
    title: "Discriminant practice packet",
    description: "Institution-approved practice set for discriminant mastery",
    resource_kind: "PRACTICE_SET",
    status: "ACTIVE",
    content_ref: "internal://catalog/demo-disc-practice",
    curriculum_node_ids: ["node-concept-disc"],
    created_by: null,
    approved_by: null,
    approved_at: B13_AS_OF,
    created_at: B13_AS_OF,
    updated_at: B13_AS_OF,
  },
  {
    id: RESOURCE_ID_DRAFT,
    curriculum_id: CURRICULUM_ID,
    code: "RES-DEMO-DRAFT",
    title: "Draft concept note",
    description: null,
    resource_kind: "CONCEPT_NOTE",
    status: "DRAFT",
    content_ref: "internal://catalog/demo-draft-note",
    curriculum_node_ids: ["node-topic-sim"],
    created_by: null,
    approved_by: null,
    approved_at: null,
    created_at: B13_AS_OF,
    updated_at: B13_AS_OF,
  },
];

let demoAssignments: StudentResourceAssignment[] = [
  {
    id: ASSIGNMENT_ID,
    student_id: STUDENT_ID,
    resource_id: RESOURCE_ID,
    resource: demoResources[0]!,
    learning_recommendation_id: null,
    status: "ASSIGNED",
    assigned_by: null,
    assigned_at: B13_AS_OF,
    cancelled_at: null,
    cancelled_by: null,
  },
];

function cloneResource(r: CurriculumResource): CurriculumResource {
  return { ...r, curriculum_node_ids: [...r.curriculum_node_ids] };
}

function findResourceOrThrow(id: string): CurriculumResource {
  const found = demoResources.find((r) => r.id === id);
  if (!found) {
    throw new MockNotFoundError("Curriculum resource not found");
  }
  return found;
}

export function listCurriculumResources(filters?: {
  curriculumId?: string;
  status?: string;
}): CurriculumResourceList {
  let items = demoResources.map(cloneResource);
  if (filters?.curriculumId) {
    items = items.filter((r) => r.curriculum_id === filters.curriculumId);
  }
  if (filters?.status) {
    items = items.filter((r) => r.status === filters.status);
  }
  return {
    curriculum_id: filters?.curriculumId ?? null,
    status_filter: filters?.status ?? null,
    items,
  };
}

export function getCurriculumResource(id: string): CurriculumResource {
  return cloneResource(findResourceOrThrow(id));
}

export function createCurriculumResource(
  input: CurriculumResourceCreate,
): CurriculumResource {
  if (/^https?:\/\//i.test(input.content_ref) || input.content_ref.startsWith("//")) {
    throw new MockNotFoundError("content_ref must not be an open-web URL");
  }
  const now = new Date().toISOString();
  const resource: CurriculumResource = {
    id: `resource-demo-${crypto.randomUUID().slice(0, 8)}`,
    curriculum_id: input.curriculum_id,
    code: input.code,
    title: input.title,
    description: input.description ?? null,
    resource_kind: input.resource_kind,
    status: "DRAFT",
    content_ref: input.content_ref,
    curriculum_node_ids: [...input.curriculum_node_ids],
    created_by: null,
    approved_by: null,
    approved_at: null,
    created_at: now,
    updated_at: now,
  };
  demoResources = [resource, ...demoResources];
  return cloneResource(resource);
}

export function updateCurriculumResource(
  id: string,
  input: CurriculumResourceUpdate,
): CurriculumResource {
  const resource = findResourceOrThrow(id);
  if (input.title !== undefined) resource.title = input.title;
  if (input.description !== undefined) resource.description = input.description;
  if (input.resource_kind !== undefined) resource.resource_kind = input.resource_kind;
  if (input.content_ref !== undefined) resource.content_ref = input.content_ref;
  resource.updated_at = new Date().toISOString();
  return cloneResource(resource);
}

export function approveCurriculumResource(id: string): CurriculumResource {
  const resource = findResourceOrThrow(id);
  if (resource.status !== "DRAFT") {
    throw new MockNotFoundError("Resource cannot be approved from current status");
  }
  resource.status = "APPROVED";
  resource.approved_at = new Date().toISOString();
  resource.updated_at = resource.approved_at;
  return cloneResource(resource);
}

export function activateCurriculumResource(id: string): CurriculumResource {
  const resource = findResourceOrThrow(id);
  if (resource.status !== "APPROVED" && resource.status !== "DEACTIVATED") {
    throw new MockNotFoundError("Resource cannot be activated from current status");
  }
  resource.status = "ACTIVE";
  resource.updated_at = new Date().toISOString();
  return cloneResource(resource);
}

export function deactivateCurriculumResource(id: string): CurriculumResource {
  const resource = findResourceOrThrow(id);
  if (resource.status !== "ACTIVE") {
    throw new MockNotFoundError("Only ACTIVE resources can be deactivated");
  }
  resource.status = "DEACTIVATED";
  resource.updated_at = new Date().toISOString();
  return cloneResource(resource);
}

export function replaceCurriculumResourceNodes(
  id: string,
  nodeIds: string[],
): CurriculumResource {
  const resource = findResourceOrThrow(id);
  resource.curriculum_node_ids = [...nodeIds];
  resource.updated_at = new Date().toISOString();
  return cloneResource(resource);
}

export function listStudentResourceAssignments(
  studentId: string,
  filters?: { curriculumId?: string; status?: string },
): StudentResourceAssignmentList {
  if (studentId !== STUDENT_ID && !students.some((s) => s.id === studentId)) {
    throw new MockNotFoundError("Student not found");
  }
  let items = demoAssignments
    .filter((a) => a.student_id === studentId)
    .map((a) => ({
      ...a,
      resource: cloneResource(
        demoResources.find((r) => r.id === a.resource_id) ?? a.resource,
      ),
    }));
  if (filters?.curriculumId) {
    items = items.filter(
      (a) => a.resource.curriculum_id === filters.curriculumId,
    );
  }
  if (filters?.status) {
    items = items.filter((a) => a.status === filters.status);
  }
  return {
    student_id: studentId,
    curriculum_id: filters?.curriculumId ?? null,
    items,
  };
}

export function assignStudentResource(
  studentId: string,
  input: StudentResourceAssignmentCreate,
): StudentResourceAssignment {
  if (studentId !== STUDENT_ID && !students.some((s) => s.id === studentId)) {
    throw new MockNotFoundError("Student not found");
  }
  const resource = findResourceOrThrow(input.resource_id);
  if (resource.status !== "ACTIVE") {
    throw new MockNotFoundError("Only ACTIVE resources can be assigned");
  }
  const existing = demoAssignments.find(
    (a) =>
      a.student_id === studentId &&
      a.resource_id === input.resource_id &&
      a.status === "ASSIGNED",
  );
  if (existing) {
    return {
      ...existing,
      resource: cloneResource(resource),
    };
  }
  const now = new Date().toISOString();
  const assignment: StudentResourceAssignment = {
    id: `assignment-demo-${crypto.randomUUID().slice(0, 8)}`,
    student_id: studentId,
    resource_id: resource.id,
    resource: cloneResource(resource),
    learning_recommendation_id: input.learning_recommendation_id ?? null,
    status: "ASSIGNED",
    assigned_by: null,
    assigned_at: now,
    cancelled_at: null,
    cancelled_by: null,
  };
  demoAssignments = [assignment, ...demoAssignments];
  return { ...assignment, resource: cloneResource(resource) };
}

export function cancelStudentResourceAssignment(
  assignmentId: string,
): StudentResourceAssignment {
  const assignment = demoAssignments.find((a) => a.id === assignmentId);
  if (!assignment) {
    throw new MockNotFoundError("Resource assignment not found");
  }
  if (assignment.status === "CANCELLED") {
    throw new MockNotFoundError("Assignment already cancelled");
  }
  assignment.status = "CANCELLED";
  assignment.cancelled_at = new Date().toISOString();
  const resource =
    demoResources.find((r) => r.id === assignment.resource_id) ??
    assignment.resource;
  return { ...assignment, resource: cloneResource(resource) };
}

/** Demo-only B14 fixtures — never invent reassessments for live UUIDs. */
export const REASSESSMENT_ASSESSMENT_ID = "assess-reassess-demo-001";

const B14_AS_OF = "2026-09-08T12:00:00.000Z";

function cloneReassessment(row: Reassessment): Reassessment {
  return {
    ...row,
    items: row.items.map((i) => ({ ...i })),
    mastery_deltas: row.mastery_deltas.map((d) => ({ ...d })),
  };
}

let demoReassessments: Reassessment[] = [
  {
    id: REASSESSMENT_ID,
    improvement_assessment_id: IMP_BLUEPRINT_ID,
    blueprint_title: "Improvement Check — Calculus & Statistics",
    blueprint_version_number: 1,
    student_id: STUDENT_ID,
    curriculum_id: CURRICULUM_ID,
    assessment_id: REASSESSMENT_ASSESSMENT_ID,
    assessment_status: "ACTIVE",
    assessment_version_id: "assess-ver-reassess-demo-001",
    submission_id: "sub-reassess-demo-001",
    published_result_id: "pub-reassess-demo-001",
    status: "PUBLISHED",
    algorithm_version: "B14_V1",
    instantiation_hash: "b".repeat(64),
    baseline_captured_at: B14_AS_OF,
    created_at: B14_AS_OF,
    updated_at: B14_AS_OF,
    items: [
      {
        id: "reassess-item-demo-001",
        improvement_assessment_item_id: IMP_ITEM_ID_1,
        question_version_id: "qv-reassess-demo-001",
        curriculum_node_id: "node-concept-disc",
        item_code_snapshot: "I1",
        template_kind_snapshot: "CONCEPT_CHECK",
        question_template_ref_snapshot: "tmpl://concept-check",
      },
      {
        id: "reassess-item-demo-002",
        improvement_assessment_item_id: IMP_ITEM_ID_2,
        question_version_id: "qv-reassess-demo-002",
        curriculum_node_id: "node-topic-sim",
        item_code_snapshot: "I2",
        template_kind_snapshot: "APPLICATION",
        question_template_ref_snapshot: "tmpl://application",
      },
    ],
    mastery_deltas: [
      {
        curriculum_node_id: "node-concept-disc",
        baseline_concept_mastery: 0.25,
        baseline_execution_accuracy: 0.4,
        baseline_concept_decisive_count: 2,
        baseline_execution_decisive_count: 2,
        baseline_concept_inconclusive_count: 0,
        baseline_execution_inconclusive_count: 0,
        baseline_evidence_count: 2,
        baseline_source_evidence_hash: "c".repeat(64),
        post_snapshot_id: "snap-reassess-demo-001",
        post_published_result_id: "pub-reassess-demo-001",
        post_concept_mastery: 0.55,
        post_execution_accuracy: 0.35,
        post_concept_decisive_count: 3,
        post_execution_decisive_count: 3,
        post_concept_inconclusive_count: 0,
        post_execution_inconclusive_count: 0,
        post_evidence_count: 3,
        post_source_evidence_hash: "d".repeat(64),
        concept_delta: 0.3,
        execution_delta: -0.05,
        materialized_at: B14_AS_OF,
        algorithm_version: "B14_V1",
      },
      {
        curriculum_node_id: "node-topic-sim",
        baseline_concept_mastery: null,
        baseline_execution_accuracy: 0.5,
        baseline_concept_decisive_count: 0,
        baseline_execution_decisive_count: 1,
        baseline_concept_inconclusive_count: 2,
        baseline_execution_inconclusive_count: 0,
        baseline_evidence_count: 2,
        baseline_source_evidence_hash: "e".repeat(64),
        post_snapshot_id: "snap-reassess-demo-002",
        post_published_result_id: "pub-reassess-demo-001",
        post_concept_mastery: null,
        post_execution_accuracy: 0.7,
        post_concept_decisive_count: 0,
        post_execution_decisive_count: 2,
        post_concept_inconclusive_count: 1,
        post_execution_inconclusive_count: 0,
        post_evidence_count: 2,
        post_source_evidence_hash: "f".repeat(64),
        concept_delta: null,
        execution_delta: 0.2,
        materialized_at: B14_AS_OF,
        algorithm_version: "B14_V1",
      },
    ],
  },
  {
    id: REASSESSMENT_ID_CREATED,
    improvement_assessment_id: IMP_BLUEPRINT_ID,
    blueprint_title: "Improvement Check — Calculus & Statistics",
    blueprint_version_number: 1,
    student_id: STUDENT_ID,
    curriculum_id: CURRICULUM_ID,
    assessment_id: "assess-reassess-demo-created",
    assessment_status: "DRAFT",
    assessment_version_id: "assess-ver-reassess-demo-created",
    submission_id: null,
    published_result_id: null,
    status: "CREATED",
    algorithm_version: "B14_V1",
    instantiation_hash: "a".repeat(64),
    baseline_captured_at: B14_AS_OF,
    created_at: B14_AS_OF,
    updated_at: B14_AS_OF,
    items: [
      {
        id: "reassess-item-demo-created-001",
        improvement_assessment_item_id: IMP_ITEM_ID_1,
        question_version_id: "qv-reassess-demo-created-001",
        curriculum_node_id: "node-concept-disc",
        item_code_snapshot: "I1",
        template_kind_snapshot: "CONCEPT_CHECK",
        question_template_ref_snapshot: "tmpl://concept-check",
      },
    ],
    mastery_deltas: [
      {
        curriculum_node_id: "node-concept-disc",
        baseline_concept_mastery: 0.25,
        baseline_execution_accuracy: 0.4,
        baseline_concept_decisive_count: 2,
        baseline_execution_decisive_count: 2,
        baseline_concept_inconclusive_count: 0,
        baseline_execution_inconclusive_count: 0,
        baseline_evidence_count: 2,
        baseline_source_evidence_hash: "g".repeat(64),
        post_snapshot_id: null,
        post_published_result_id: null,
        post_concept_mastery: null,
        post_execution_accuracy: null,
        post_concept_decisive_count: null,
        post_execution_decisive_count: null,
        post_concept_inconclusive_count: null,
        post_execution_inconclusive_count: null,
        post_evidence_count: null,
        post_source_evidence_hash: null,
        concept_delta: null,
        execution_delta: null,
        materialized_at: null,
        algorithm_version: "B14_V1",
      },
    ],
  },
];

export function listStudentReassessments(studentId: string): Reassessment[] {
  if (studentId !== STUDENT_ID && !students.some((s) => s.id === studentId)) {
    throw new MockNotFoundError("Student not found");
  }
  return demoReassessments
    .filter((r) => r.student_id === studentId)
    .map(cloneReassessment);
}

export function getReassessment(id: string): Reassessment {
  const found = demoReassessments.find((r) => r.id === id);
  if (!found) {
    throw new MockNotFoundError("Reassessment not found");
  }
  return cloneReassessment(found);
}

export function instantiateReassessment(
  blueprintId: string,
  input: ReassessmentInstantiateRequest,
): Reassessment {
  if (blueprintId !== IMP_BLUEPRINT_ID && !blueprintId.startsWith("imp-demo")) {
    throw new MockNotFoundError("Improvement blueprint not found");
  }
  if (!input.items?.length) {
    throw new MockNotFoundError("At least one item is required");
  }
  const now = new Date().toISOString();
  const assessmentId = `assess-reassess-demo-${crypto.randomUUID().slice(0, 8)}`;
  const created: Reassessment = {
    id: `reassessment-demo-${crypto.randomUUID().slice(0, 8)}`,
    improvement_assessment_id: blueprintId,
    blueprint_title: "Improvement Check — Calculus & Statistics",
    blueprint_version_number: 1,
    student_id: STUDENT_ID,
    curriculum_id: CURRICULUM_ID,
    assessment_id: assessmentId,
    assessment_status: "DRAFT",
    assessment_version_id: `assess-ver-${assessmentId}`,
    submission_id: null,
    published_result_id: null,
    status: "CREATED",
    algorithm_version: "B14_V1",
    instantiation_hash: "h".repeat(64),
    baseline_captured_at: now,
    created_at: now,
    updated_at: now,
    items: input.items.map((item, index) => ({
      id: `reassess-item-new-${index}`,
      improvement_assessment_item_id: item.improvement_assessment_item_id,
      question_version_id: `qv-new-${index}`,
      curriculum_node_id: "node-concept-disc",
      item_code_snapshot: `I${index + 1}`,
      template_kind_snapshot: "CONCEPT_CHECK",
      question_template_ref_snapshot: null,
    })),
    mastery_deltas: [
      {
        curriculum_node_id: "node-concept-disc",
        baseline_concept_mastery: 0.25,
        baseline_execution_accuracy: 0.4,
        baseline_concept_decisive_count: 1,
        baseline_execution_decisive_count: 1,
        baseline_concept_inconclusive_count: 0,
        baseline_execution_inconclusive_count: 0,
        baseline_evidence_count: 1,
        baseline_source_evidence_hash: "i".repeat(64),
        post_snapshot_id: null,
        post_published_result_id: null,
        post_concept_mastery: null,
        post_execution_accuracy: null,
        post_concept_decisive_count: null,
        post_execution_decisive_count: null,
        post_concept_inconclusive_count: null,
        post_execution_inconclusive_count: null,
        post_evidence_count: null,
        post_source_evidence_hash: null,
        concept_delta: null,
        execution_delta: null,
        materialized_at: null,
        algorithm_version: "B14_V1",
      },
    ],
  };
  demoReassessments = [created, ...demoReassessments];
  return cloneReassessment(created);
}

export function rebuildReassessmentB14(id: string): B14RebuildResult {
  const found = demoReassessments.find((r) => r.id === id);
  if (!found) {
    throw new MockNotFoundError("Reassessment not found");
  }
  return {
    reassessment_id: found.id,
    algorithm_version: "B14_V1",
    delta_count: found.mastery_deltas.length,
    published_result_id: found.published_result_id,
    source: "MASTERY_STATE_SNAPSHOT",
  };
}

/** Demo-only B15 fixtures — never invent benchmark data for live UUIDs. */
export const BENCHMARK_DATASET_ID = "benchmark-demo-001";
export const BENCHMARK_VERSION_DRAFT_ID = "benchmark-version-demo-draft";
export const BENCHMARK_VERSION_LOCKED_ID = "benchmark-version-demo-locked";
export const BENCHMARK_CASE_ID = "benchmark-case-demo-001";
export const BENCHMARK_RUN_PASS_ID = "benchmark-run-demo-pass";
export const BENCHMARK_RUN_FAIL_ID = "benchmark-run-demo-fail";
export const BENCHMARK_PUBLISHED_RESULT_ID = "published-result-demo-001";
export const BENCHMARK_QE_ID = "question-eval-demo-001";
export const BENCHMARK_EVAL_RUN_ID = "eval-run-demo-001";
export const BENCHMARK_QUESTION_VERSION_ID = "question-version-demo-001";
export const BENCHMARK_RUBRIC_VERSION_ID = "rubric-version-demo-001";
export const BENCHMARK_ASSESSMENT_VERSION_ID = "assessment-version-demo-001";

const B15_AS_OF = "2026-09-09T10:00:00.000Z";
const B15_LOCKED_AT = "2026-09-09T11:00:00.000Z";

export const B15_DEFAULT_THRESHOLDS: BenchmarkThresholdProfile = {
  profile_code: "B15_DEFAULT_V1",
  algorithm_version: "B15_V1",
  max_missing_output_rate: 0,
  max_mean_abs_score_error: 0.25,
  min_exact_score_agreement_rate: 1,
  min_taxonomy_agreement_rate: 1,
  max_safety_invariant_failure_rate: 0,
  score_tolerance: 0,
};

const B15_REPLAY_FIXTURE: Record<string, unknown> = {
  question_version_id: BENCHMARK_QUESTION_VERSION_ID,
  assessment_version_id: BENCHMARK_ASSESSMENT_VERSION_ID,
  rubric_version_id: BENCHMARK_RUBRIC_VERSION_ID,
  criterion_snapshot: [
    {
      id: "criterion-demo-001",
      code: "C1",
      label: "Method",
      max_marks: "3.0000",
      sequence: 1,
    },
    {
      id: "criterion-demo-002",
      code: "C2",
      label: "Answer",
      max_marks: "2.0000",
      sequence: 2,
    },
  ],
  transcription_text: "EXERCISE:PARTIAL anonymized answer text",
  blank_flag: false,
  unreadable_flag: false,
  expected_final_marks: "3.5",
  expected_max_marks: "5",
  expected_error_codes: ["ARITHMETIC_ERROR"],
  max_mark: "5",
};

let demoDatasets: BenchmarkDataset[] = [
  {
    id: BENCHMARK_DATASET_ID,
    code: "GOLD-DEMO-001",
    title: "Demo gold math set",
    description: "Frozen human-final gold cases for isolated AI regression",
    created_by: null,
    created_at: B15_AS_OF,
    updated_at: B15_AS_OF,
  },
];

let demoVersions: BenchmarkVersion[] = [
  {
    id: BENCHMARK_VERSION_DRAFT_ID,
    dataset_id: BENCHMARK_DATASET_ID,
    version_number: 1,
    status: "DRAFT",
    threshold_profile_snapshot: { ...B15_DEFAULT_THRESHOLDS },
    case_count: 0,
    content_hash: null,
    locked_by: null,
    locked_at: null,
    created_by: null,
    created_at: B15_AS_OF,
    updated_at: B15_AS_OF,
  },
  {
    id: BENCHMARK_VERSION_LOCKED_ID,
    dataset_id: BENCHMARK_DATASET_ID,
    version_number: 2,
    status: "LOCKED",
    threshold_profile_snapshot: { ...B15_DEFAULT_THRESHOLDS },
    case_count: 1,
    content_hash: "a".repeat(64),
    locked_by: "user-admin-001",
    locked_at: B15_LOCKED_AT,
    created_by: null,
    created_at: B15_AS_OF,
    updated_at: B15_LOCKED_AT,
  },
];

let demoCases: BenchmarkCase[] = [
  {
    id: BENCHMARK_CASE_ID,
    dataset_version_id: BENCHMARK_VERSION_LOCKED_ID,
    published_result_id: BENCHMARK_PUBLISHED_RESULT_ID,
    evaluation_run_id: BENCHMARK_EVAL_RUN_ID,
    question_evaluation_id: BENCHMARK_QE_ID,
    question_version_id: BENCHMARK_QUESTION_VERSION_ID,
    rubric_version_id: BENCHMARK_RUBRIC_VERSION_ID,
    assessment_version_id: BENCHMARK_ASSESSMENT_VERSION_ID,
    expected_final_marks: 3.5,
    expected_max_marks: 5,
    expected_error_codes: ["ARITHMETIC_ERROR"],
    source_ledger_hash: "b".repeat(64),
    evidence_hash: "c".repeat(64),
    adjudicated_by: "user-teacher-001",
    adjudicated_at: B15_AS_OF,
    replay_fixture: { ...B15_REPLAY_FIXTURE },
    created_at: B15_AS_OF,
    updated_at: B15_AS_OF,
  },
];

const PASS_METRICS: Record<string, unknown> = {
  case_count: 1,
  missing_count: 0,
  missing_output_rate: 0,
  mean_abs_score_error: 0,
  exact_score_agreement_rate: 1,
  taxonomy_agreement_rate: 1,
  safety_invariant_failure_rate: 0,
  exact_match_count: 1,
  taxonomy_match_count: 1,
  taxonomy_applicable_count: 1,
  safety_fail_count: 0,
  verdict: "PASS",
};

const FAIL_METRICS: Record<string, unknown> = {
  case_count: 1,
  missing_count: 0,
  missing_output_rate: 0,
  mean_abs_score_error: 1,
  exact_score_agreement_rate: 0,
  taxonomy_agreement_rate: 0,
  safety_invariant_failure_rate: 0,
  exact_match_count: 0,
  taxonomy_match_count: 0,
  taxonomy_applicable_count: 1,
  safety_fail_count: 0,
  verdict: "FAIL",
};

let demoRuns: BenchmarkRegressionRun[] = [
  {
    id: BENCHMARK_RUN_PASS_ID,
    dataset_version_id: BENCHMARK_VERSION_LOCKED_ID,
    status: "PASSED",
    verdict: "PASS",
    idempotency_key: "demo-pass-key",
    candidate_provider: "fixed",
    candidate_model: "fixed-benchmark-pass",
    candidate_model_version: "B15_V1",
    candidate_prompt_template_version: "fixed-benchmark-v1",
    candidate_config: {},
    threshold_snapshot: { ...B15_DEFAULT_THRESHOLDS },
    aggregate_metrics: { ...PASS_METRICS },
    initiated_by: "user-admin-001",
    started_at: B15_LOCKED_AT,
    finished_at: B15_LOCKED_AT,
    failure_code: null,
    failure_detail: null,
    created_at: B15_LOCKED_AT,
    updated_at: B15_LOCKED_AT,
  },
  {
    id: BENCHMARK_RUN_FAIL_ID,
    dataset_version_id: BENCHMARK_VERSION_LOCKED_ID,
    status: "FAILED",
    verdict: "FAIL",
    idempotency_key: "demo-fail-key",
    candidate_provider: "fixed",
    candidate_model: "fixed-benchmark-regress",
    candidate_model_version: "B15_V1",
    candidate_prompt_template_version: "fixed-benchmark-v1",
    candidate_config: {},
    threshold_snapshot: { ...B15_DEFAULT_THRESHOLDS },
    aggregate_metrics: { ...FAIL_METRICS },
    initiated_by: "user-admin-001",
    started_at: B15_LOCKED_AT,
    finished_at: B15_LOCKED_AT,
    failure_code: null,
    failure_detail: null,
    created_at: B15_LOCKED_AT,
    updated_at: B15_LOCKED_AT,
  },
];

let demoCaseResults: BenchmarkRegressionCaseResult[] = [
  {
    id: "benchmark-case-result-demo-pass",
    regression_run_id: BENCHMARK_RUN_PASS_ID,
    benchmark_case_id: BENCHMARK_CASE_ID,
    missing_output: false,
    actual_marks: 3.5,
    actual_error_codes: ["ARITHMETIC_ERROR"],
    score_abs_error: 0,
    exact_score_match: true,
    taxonomy_match: true,
    safety_invariant_failed: false,
    diff: {
      expected_final_marks: "3.5",
      actual_marks: "3.5",
      score_abs_error: "0",
      expected_error_codes: ["ARITHMETIC_ERROR"],
      actual_error_codes: ["ARITHMETIC_ERROR"],
      safety_invariant_failed: false,
    },
    ai_execution_record_id: null,
    created_at: B15_LOCKED_AT,
    updated_at: B15_LOCKED_AT,
  },
  {
    id: "benchmark-case-result-demo-fail",
    regression_run_id: BENCHMARK_RUN_FAIL_ID,
    benchmark_case_id: BENCHMARK_CASE_ID,
    missing_output: false,
    actual_marks: 4.5,
    actual_error_codes: ["CONCEPT_ERROR"],
    score_abs_error: 1,
    exact_score_match: false,
    taxonomy_match: false,
    safety_invariant_failed: false,
    diff: {
      expected_final_marks: "3.5",
      actual_marks: "4.5",
      score_abs_error: "1",
      expected_error_codes: ["ARITHMETIC_ERROR"],
      actual_error_codes: ["CONCEPT_ERROR"],
      safety_invariant_failed: false,
    },
    ai_execution_record_id: null,
    created_at: B15_LOCKED_AT,
    updated_at: B15_LOCKED_AT,
  },
];

function cloneDataset(d: BenchmarkDataset): BenchmarkDataset {
  return { ...d };
}

function cloneVersion(v: BenchmarkVersion): BenchmarkVersion {
  return {
    ...v,
    threshold_profile_snapshot: { ...v.threshold_profile_snapshot },
  };
}

function cloneCase(c: BenchmarkCase): BenchmarkCase {
  return {
    ...c,
    expected_error_codes: [...c.expected_error_codes],
    replay_fixture: { ...c.replay_fixture },
  };
}

function cloneRun(r: BenchmarkRegressionRun): BenchmarkRegressionRun {
  return {
    ...r,
    candidate_config: { ...r.candidate_config },
    threshold_snapshot: { ...r.threshold_snapshot },
    aggregate_metrics: { ...r.aggregate_metrics },
  };
}

function cloneCaseResult(
  r: BenchmarkRegressionCaseResult,
): BenchmarkRegressionCaseResult {
  return {
    ...r,
    actual_error_codes: [...r.actual_error_codes],
    diff: { ...r.diff },
  };
}

function findDatasetOrThrow(id: string): BenchmarkDataset {
  const found = demoDatasets.find((d) => d.id === id);
  if (!found) throw new MockNotFoundError("Benchmark dataset not found");
  return found;
}

function findVersionOrThrow(id: string): BenchmarkVersion {
  const found = demoVersions.find((v) => v.id === id);
  if (!found) throw new MockNotFoundError("Benchmark version not found");
  return found;
}

function findRunOrThrow(id: string): BenchmarkRegressionRun {
  const found = demoRuns.find((r) => r.id === id);
  if (!found) throw new MockNotFoundError("Benchmark regression run not found");
  return found;
}

export function listBenchmarkDatasets(): BenchmarkDatasetList {
  return { items: demoDatasets.map(cloneDataset) };
}

export function getBenchmarkDataset(id: string): BenchmarkDataset {
  return cloneDataset(findDatasetOrThrow(id));
}

export function createBenchmarkDataset(
  input: BenchmarkDatasetCreate,
): BenchmarkDataset {
  const now = new Date().toISOString();
  const created: BenchmarkDataset = {
    id: `benchmark-demo-${crypto.randomUUID().slice(0, 8)}`,
    code: input.code,
    title: input.title,
    description: input.description ?? null,
    created_by: null,
    created_at: now,
    updated_at: now,
  };
  demoDatasets = [created, ...demoDatasets];
  return cloneDataset(created);
}

export function listBenchmarkVersions(
  datasetId: string,
): BenchmarkVersionList {
  findDatasetOrThrow(datasetId);
  return {
    items: demoVersions
      .filter((v) => v.dataset_id === datasetId)
      .map(cloneVersion),
  };
}

export function createBenchmarkVersion(
  datasetId: string,
  input?: BenchmarkVersionCreate,
): BenchmarkVersion {
  findDatasetOrThrow(datasetId);
  const siblings = demoVersions.filter((v) => v.dataset_id === datasetId);
  const nextNumber =
    siblings.reduce((max, v) => Math.max(max, v.version_number), 0) + 1;
  const now = new Date().toISOString();
  const created: BenchmarkVersion = {
    id: `benchmark-version-demo-${crypto.randomUUID().slice(0, 8)}`,
    dataset_id: datasetId,
    version_number: nextNumber,
    status: "DRAFT",
    threshold_profile_snapshot: {
      ...B15_DEFAULT_THRESHOLDS,
      ...(input?.threshold_profile_snapshot ?? {}),
    },
    case_count: 0,
    content_hash: null,
    locked_by: null,
    locked_at: null,
    created_by: null,
    created_at: now,
    updated_at: now,
  };
  demoVersions = [created, ...demoVersions];
  return cloneVersion(created);
}

export function getBenchmarkVersion(versionId: string): BenchmarkVersion {
  return cloneVersion(findVersionOrThrow(versionId));
}

export function listBenchmarkEligibleSources(
  versionId: string,
): BenchmarkEligibleSources {
  findVersionOrThrow(versionId);
  return {
    items: [
      {
        published_result_id: BENCHMARK_PUBLISHED_RESULT_ID,
        evaluation_run_id: BENCHMARK_EVAL_RUN_ID,
        submission_id: SUBMISSION_ID,
        assessment_version_id: BENCHMARK_ASSESSMENT_VERSION_ID,
        ledger_snapshot_hash: "b".repeat(64),
        question_evaluations: [
          {
            question_evaluation_id: BENCHMARK_QE_ID,
            question_version_id: BENCHMARK_QUESTION_VERSION_ID,
            workflow_state: "ACCEPTED",
            final_human_approved_score: 3.5,
            max_mark: 5,
            error_codes: ["ARITHMETIC_ERROR"],
          },
        ],
      },
    ],
  };
}

export function listBenchmarkCases(versionId: string): BenchmarkCaseList {
  findVersionOrThrow(versionId);
  return {
    items: demoCases
      .filter((c) => c.dataset_version_id === versionId)
      .map(cloneCase),
  };
}

export function addBenchmarkCase(
  versionId: string,
  input: BenchmarkCaseCreate,
): BenchmarkCase {
  const version = findVersionOrThrow(versionId);
  if (version.status === "LOCKED") {
    throw new MockNotFoundError("Benchmark version is locked");
  }
  const existing = demoCases.find(
    (c) =>
      c.dataset_version_id === versionId &&
      c.published_result_id === input.published_result_id &&
      c.question_evaluation_id === input.question_evaluation_id,
  );
  if (existing) return cloneCase(existing);

  const now = new Date().toISOString();
  const created: BenchmarkCase = {
    id: `benchmark-case-demo-${crypto.randomUUID().slice(0, 8)}`,
    dataset_version_id: versionId,
    published_result_id: input.published_result_id,
    evaluation_run_id: BENCHMARK_EVAL_RUN_ID,
    question_evaluation_id: input.question_evaluation_id,
    question_version_id: BENCHMARK_QUESTION_VERSION_ID,
    rubric_version_id: BENCHMARK_RUBRIC_VERSION_ID,
    assessment_version_id: BENCHMARK_ASSESSMENT_VERSION_ID,
    expected_final_marks: 3.5,
    expected_max_marks: 5,
    expected_error_codes: ["ARITHMETIC_ERROR"],
    source_ledger_hash: "b".repeat(64),
    evidence_hash: "c".repeat(64),
    adjudicated_by: null,
    adjudicated_at: now,
    replay_fixture: { ...B15_REPLAY_FIXTURE },
    created_at: now,
    updated_at: now,
  };
  demoCases = [created, ...demoCases];
  version.case_count += 1;
  version.updated_at = now;
  return cloneCase(created);
}

export function removeBenchmarkCase(
  versionId: string,
  caseId: string,
): BenchmarkCase {
  const version = findVersionOrThrow(versionId);
  if (version.status === "LOCKED") {
    throw new MockNotFoundError("Benchmark version is locked");
  }
  const idx = demoCases.findIndex(
    (c) => c.id === caseId && c.dataset_version_id === versionId,
  );
  if (idx < 0) throw new MockNotFoundError("Benchmark case not found");
  const [removed] = demoCases.splice(idx, 1);
  version.case_count = Math.max(0, version.case_count - 1);
  version.updated_at = new Date().toISOString();
  return cloneCase(removed!);
}

export function lockBenchmarkVersion(versionId: string): BenchmarkVersion {
  const version = findVersionOrThrow(versionId);
  if (version.status === "LOCKED") return cloneVersion(version);
  if (version.case_count < 1) {
    throw new MockNotFoundError("Cannot lock empty benchmark version");
  }
  const now = new Date().toISOString();
  version.status = "LOCKED";
  version.locked_by = "user-admin-001";
  version.locked_at = now;
  version.content_hash = "d".repeat(64);
  version.updated_at = now;
  return cloneVersion(version);
}

export function listBenchmarkRegressionRuns(
  versionId: string,
): BenchmarkRegressionRunList {
  findVersionOrThrow(versionId);
  return {
    items: demoRuns
      .filter((r) => r.dataset_version_id === versionId)
      .map(cloneRun),
  };
}

export function startBenchmarkRegressionRun(
  versionId: string,
  input: BenchmarkRegressionRunCreate,
): BenchmarkRegressionRun {
  const version = findVersionOrThrow(versionId);
  if (version.status !== "LOCKED") {
    throw new MockNotFoundError("Benchmark version must be locked");
  }
  const pass = input.candidate_model === "fixed-benchmark-pass";
  const now = new Date().toISOString();
  const runId = `benchmark-run-demo-${crypto.randomUUID().slice(0, 8)}`;
  const caseId =
    demoCases.find((c) => c.dataset_version_id === versionId)?.id ??
    BENCHMARK_CASE_ID;
  const gold = demoCases.find((c) => c.id === caseId);
  const expectedMarks = gold?.expected_final_marks ?? 3.5;
  const expectedCodes = gold?.expected_error_codes ?? ["ARITHMETIC_ERROR"];
  const actualMarks = pass ? expectedMarks : expectedMarks + 1;
  const actualCodes = pass ? expectedCodes : ["CONCEPT_ERROR"];

  const run: BenchmarkRegressionRun = {
    id: runId,
    dataset_version_id: versionId,
    status: pass ? "PASSED" : "FAILED",
    verdict: pass ? "PASS" : "FAIL",
    idempotency_key: input.idempotency_key ?? null,
    candidate_provider: input.candidate_provider,
    candidate_model: input.candidate_model,
    candidate_model_version: input.candidate_model_version,
    candidate_prompt_template_version: input.candidate_prompt_template_version,
    candidate_config: { ...(input.candidate_config ?? {}) },
    threshold_snapshot: {
      ...B15_DEFAULT_THRESHOLDS,
      ...version.threshold_profile_snapshot,
    },
    aggregate_metrics: pass ? { ...PASS_METRICS } : { ...FAIL_METRICS },
    initiated_by: "user-admin-001",
    started_at: now,
    finished_at: now,
    failure_code: null,
    failure_detail: null,
    created_at: now,
    updated_at: now,
  };
  demoRuns = [run, ...demoRuns];
  demoCaseResults = [
    {
      id: `benchmark-case-result-demo-${crypto.randomUUID().slice(0, 8)}`,
      regression_run_id: runId,
      benchmark_case_id: caseId,
      missing_output: false,
      actual_marks: actualMarks,
      actual_error_codes: [...actualCodes],
      score_abs_error: Math.abs(actualMarks - expectedMarks),
      exact_score_match: pass,
      taxonomy_match: pass,
      safety_invariant_failed: false,
      diff: {
        expected_final_marks: String(expectedMarks),
        actual_marks: String(actualMarks),
        score_abs_error: String(Math.abs(actualMarks - expectedMarks)),
        expected_error_codes: [...expectedCodes],
        actual_error_codes: [...actualCodes],
        safety_invariant_failed: false,
      },
      ai_execution_record_id: null,
      created_at: now,
      updated_at: now,
    },
    ...demoCaseResults,
  ];
  return cloneRun(run);
}

export function getBenchmarkRegressionRun(
  runId: string,
): BenchmarkRegressionRun {
  return cloneRun(findRunOrThrow(runId));
}

export function listBenchmarkRegressionCaseResults(
  runId: string,
): BenchmarkRegressionCaseResultList {
  findRunOrThrow(runId);
  return {
    items: demoCaseResults
      .filter((r) => r.regression_run_id === runId)
      .map(cloneCaseResult),
  };
}

export function getBenchmarkGateVerdict(runId: string): BenchmarkGateVerdict {
  const run = findRunOrThrow(runId);
  const passed = run.verdict === "PASS" && run.status === "PASSED";
  return {
    verdict: run.verdict,
    passed,
    run_id: run.id,
    status: run.status,
    candidate_provider: run.candidate_provider,
    candidate_model: run.candidate_model,
    candidate_model_version: run.candidate_model_version,
    candidate_prompt_template_version: run.candidate_prompt_template_version,
    metrics: { ...run.aggregate_metrics },
    threshold_snapshot: { ...run.threshold_snapshot },
  };
}


/** Demo-only B16 enterprise operations fixtures. */
export const GRADING_POOL_DEMO_ID = "grading-pool-demo-001";
export const GRADING_WORK_DEMO_ID = "grading-work-demo-001";
export const MODERATION_CASE_DEMO_ID = "moderation-case-demo-001";
export const GRIEVANCE_DEMO_ID = "grievance-demo-001";

let demoPools: import("@/lib/types/domain").GradingPool[] = [
  {
    id: GRADING_POOL_DEMO_ID,
    assessment_id: "assess-demo-001",
    assessment_version_id: "assess-version-demo-001",
    grading_mode: "HORIZONTAL_QUESTION",
    status: "ACTIVE",
    allocation_strategy: "ROUND_ROBIN",
    created_at: "2026-09-01T10:00:00.000Z",
    updated_at: "2026-09-01T10:00:00.000Z",
    member_count: 2,
  },
];

const demoWorkItems: import("@/lib/types/domain").GradingWorkItem[] = [
  {
    id: GRADING_WORK_DEMO_ID,
    pool_id: GRADING_POOL_DEMO_ID,
    submission_id: "sub-demo-001",
    evaluation_run_id: "eval-run-demo-001",
    question_evaluation_id: "qe-demo-001",
    assigned_evaluator_id: "user-admin-001",
    status: "QUEUED",
    created_at: "2026-09-01T10:05:00.000Z",
    updated_at: "2026-09-01T10:05:00.000Z",
  },
];

let demoModerationCases: import("@/lib/types/domain").ModerationCase[] = [
  {
    id: MODERATION_CASE_DEMO_ID,
    policy_id: "moderation-policy-demo-001",
    submission_id: "sub-demo-002",
    evaluation_run_id: "eval-run-demo-002",
    current_stage_order: 1,
    status: "PENDING",
    created_at: "2026-09-01T11:00:00.000Z",
    updated_at: "2026-09-01T11:00:00.000Z",
    actions: [],
  },
];

let demoGrievances: import("@/lib/types/domain").GrievanceCase[] = [
  {
    id: GRIEVANCE_DEMO_ID,
    submission_id: "sub-demo-003",
    original_published_result_id: "pub-demo-001",
    original_evaluation_run_id: "eval-run-demo-003",
    requester_reference: "parent-of-student-demo",
    submitted_by: "user-admin-001",
    reason: "Request recheck of Q2 marking",
    status: "SUBMITTED",
    decision_reason: null,
    reevaluation_run_id: null,
    revised_published_result_id: null,
    created_at: "2026-09-01T12:00:00.000Z",
    updated_at: "2026-09-01T12:00:00.000Z",
  },
];

export function listGradingPools() {
  return { items: [...demoPools] };
}
export function getGradingPool(poolId: string) {
  const pool = demoPools.find((p) => p.id === poolId);
  if (!pool) throw new MockNotFoundError("Grading pool not found");
  return { ...pool };
}
export function createGradingPool(input: {
  assessment_id: string;
  assessment_version_id: string;
  allocation_strategy: "MANUAL" | "ROUND_ROBIN";
}) {
  const now = new Date().toISOString();
  const pool = {
    id: `grading-pool-demo-${crypto.randomUUID().slice(0, 8)}`,
    assessment_id: input.assessment_id,
    assessment_version_id: input.assessment_version_id,
    grading_mode: "HORIZONTAL_QUESTION",
    status: "DRAFT" as const,
    allocation_strategy: input.allocation_strategy,
    created_at: now,
    updated_at: now,
    member_count: 0,
  };
  demoPools = [pool, ...demoPools];
  return pool;
}
export function activateGradingPool(poolId: string) {
  const pool = getGradingPool(poolId);
  pool.status = "ACTIVE";
  pool.updated_at = new Date().toISOString();
  demoPools = demoPools.map((p) => (p.id === poolId ? pool : p));
  return pool;
}
export function closeGradingPool(poolId: string) {
  const pool = getGradingPool(poolId);
  pool.status = "CLOSED";
  pool.updated_at = new Date().toISOString();
  demoPools = demoPools.map((p) => (p.id === poolId ? pool : p));
  return pool;
}
export function getGradingPoolProgress(_poolId: string) {
  return {
    counts: {
      QUEUED: demoWorkItems.filter((w) => w.status === "QUEUED").length,
      IN_PROGRESS: demoWorkItems.filter((w) => w.status === "IN_PROGRESS").length,
      SUBMITTED: demoWorkItems.filter((w) => w.status === "SUBMITTED").length,
      RETURNED: demoWorkItems.filter((w) => w.status === "RETURNED").length,
      COMPLETED: demoWorkItems.filter((w) => w.status === "COMPLETED").length,
    },
  };
}
export function myGradingQueue() {
  return { items: [...demoWorkItems] };
}
export function startGradingWorkItem(workItemId: string) {
  const item = demoWorkItems.find((w) => w.id === workItemId);
  if (!item) throw new MockNotFoundError("Work item not found");
  item.status = "IN_PROGRESS";
  item.updated_at = new Date().toISOString();
  return { ...item };
}
export function submitGradingWorkItem(workItemId: string) {
  const item = demoWorkItems.find((w) => w.id === workItemId);
  if (!item) throw new MockNotFoundError("Work item not found");
  item.status = "SUBMITTED";
  item.updated_at = new Date().toISOString();
  return { ...item };
}
export function listModerationCases() {
  return { items: [...demoModerationCases] };
}
export function getModerationCase(caseId: string) {
  const row = demoModerationCases.find((c) => c.id === caseId);
  if (!row) throw new MockNotFoundError("Moderation case not found");
  return { ...row, actions: [...(row.actions ?? [])] };
}
export function decideModerationCase(
  caseId: string,
  input: { decision: "APPROVE" | "RETURN" | "REJECT"; reason?: string | null },
) {
  const row = getModerationCase(caseId);
  if (input.decision === "RETURN" || input.decision === "REJECT") {
    if (!input.reason?.trim()) {
      throw new MockNotFoundError("RETURN/REJECT require a reason");
    }
  }
  const now = new Date().toISOString();
  const action = {
    id: `mod-action-${crypto.randomUUID().slice(0, 8)}`,
    stage_order: row.current_stage_order,
    actor_user_id: "user-admin-001",
    decision: input.decision,
    reason: input.reason ?? null,
    created_at: now,
  };
  row.actions = [...(row.actions ?? []), action];
  if (input.decision === "RETURN") row.status = "RETURNED";
  else if (input.decision === "REJECT") row.status = "REJECTED";
  else row.status = "APPROVED";
  row.updated_at = now;
  demoModerationCases = demoModerationCases.map((c) =>
    c.id === caseId ? row : c,
  );
  return row;
}
export function listGrievances() {
  return { items: [...demoGrievances] };
}
export function getGrievance(id: string) {
  const row = demoGrievances.find((g) => g.id === id);
  if (!row) throw new MockNotFoundError("Grievance not found");
  return { ...row };
}
export function createGrievance(input: {
  published_result_id: string;
  requester_reference: string;
  reason: string;
}) {
  const now = new Date().toISOString();
  const row: import("@/lib/types/domain").GrievanceCase = {
    id: `grievance-demo-${crypto.randomUUID().slice(0, 8)}`,
    submission_id: "sub-demo-003",
    original_published_result_id: input.published_result_id,
    original_evaluation_run_id: "eval-run-demo-003",
    requester_reference: input.requester_reference,
    submitted_by: "user-admin-001",
    reason: input.reason,
    status: "SUBMITTED",
    decision_reason: null,
    reevaluation_run_id: null,
    revised_published_result_id: null,
    created_at: now,
    updated_at: now,
  };
  demoGrievances = [row, ...demoGrievances];
  return row;
}
export function acceptGrievance(id: string, decision_reason?: string | null) {
  const row = getGrievance(id);
  row.status = "RE_EVALUATING";
  row.decision_reason = decision_reason ?? null;
  row.reevaluation_run_id = `eval-run-re-${crypto.randomUUID().slice(0, 8)}`;
  row.updated_at = new Date().toISOString();
  demoGrievances = demoGrievances.map((g) => (g.id === id ? row : g));
  return row;
}
export function rejectGrievance(id: string, decision_reason: string) {
  const row = getGrievance(id);
  row.status = "REJECTED";
  row.decision_reason = decision_reason;
  row.updated_at = new Date().toISOString();
  demoGrievances = demoGrievances.map((g) => (g.id === id ? row : g));
  return row;
}

/** B17 demo fixtures */
export const PSYCHOMETRIC_RUN_DEMO_ID = "psychometric-run-demo-001";
export const CALIBRATION_SESSION_DEMO_ID = "calibration-session-demo-001";
export const CALIBRATION_CASE_DEMO_ID = "calibration-case-demo-001";

let demoPsychometricRuns: import("@/lib/types/domain").PsychometricRun[] = [
  {
    id: PSYCHOMETRIC_RUN_DEMO_ID,
    assessment_id: "assess-demo-001",
    assessment_version_id: "assess-ver-demo-001",
    cohort_definition: {
      scope: "assessment_version",
      status_filter: ["PUBLISHED"],
      exclude_superseded: true,
    },
    algorithm_version: "B17_PSYCHOMETRICS_V1",
    min_cohort_size: 20,
    source_set_hash: "demo-hash",
    source_result_count: 24,
    source_published_result_ids: ["pub-demo-001"],
    status: "COMPLETED",
    requested_by: "user-admin-001",
    requested_at: "2026-09-10T05:00:00.000Z",
    completed_at: "2026-09-10T05:00:01.000Z",
    failure_code: null,
    failure_detail: null,
    created_at: "2026-09-10T05:00:00.000Z",
    updated_at: "2026-09-10T05:00:01.000Z",
  },
];

const demoItemMetrics: import("@/lib/types/domain").ItemPsychometricMetric[] = [
  {
    id: "item-metric-demo-001",
    run_id: PSYCHOMETRIC_RUN_DEMO_ID,
    question_id: "q-demo-001",
    question_version_id: "qv-demo-001",
    question_code: "Q1",
    attempt_count: 24,
    max_mark: 5,
    mean_raw_score: 3.2,
    std_dev: 1.1,
    difficulty_index: 0.64,
    discrimination_index: 0.42,
    discrimination_method: "CORRECTED_ITEM_TOTAL_PEARSON_V1",
    discrimination_status: "OK",
    full_credit_rate: 0.25,
    zero_score_rate: 0.08,
    blank_rate: null,
    difficulty_band: "MODERATE",
    discrimination_band: "HIGH",
  },
];

let demoCalibrationSessions: import("@/lib/types/domain").CalibrationSession[] =
  [
    {
      id: CALIBRATION_SESSION_DEMO_ID,
      assessment_id: "assess-demo-001",
      assessment_version_id: "assess-ver-demo-001",
      title: "Demo Calibration Session",
      status: "ACTIVE",
      algorithm_version: "B17_CALIBRATION_V1",
      score_tolerance_abs: 0.5,
      score_tolerance_pct: 0.05,
      min_cases: 10,
      activated_by: "user-admin-001",
      activated_at: "2026-09-10T05:10:00.000Z",
      closed_by: null,
      closed_at: null,
      created_by: "user-admin-001",
      created_at: "2026-09-10T05:05:00.000Z",
      updated_at: "2026-09-10T05:10:00.000Z",
      case_count: 1,
      cases: [
        {
          id: CALIBRATION_CASE_DEMO_ID,
          session_id: CALIBRATION_SESSION_DEMO_ID,
          case_code: "C0001",
          published_result_id: "pub-demo-001",
          evaluation_run_id: "eval-run-demo-001",
          question_evaluation_id: "qe-demo-001",
          question_version_id: "qv-demo-001",
          rubric_version_id: "rv-demo-001",
          max_mark: 5,
          reference_score: 4,
          source_snapshot_hash: "case-hash",
          created_at: "2026-09-10T05:06:00.000Z",
        },
      ],
      participants: [
        { id: "cal-part-demo-001", user_id: "user-eval-001" },
      ],
    },
  ];

export function listPsychometricRuns(assessmentVersionId?: string) {
  const items = assessmentVersionId
    ? demoPsychometricRuns.filter(
        (r) => r.assessment_version_id === assessmentVersionId,
      )
    : demoPsychometricRuns;
  return { items: items.map((r) => ({ ...r })) };
}

export function createPsychometricRun(assessmentVersionId: string) {
  const existing = demoPsychometricRuns.find(
    (r) => r.assessment_version_id === assessmentVersionId,
  );
  if (existing) return { ...existing };
  const now = new Date().toISOString();
  const run: import("@/lib/types/domain").PsychometricRun = {
    id: `psychometric-run-demo-${crypto.randomUUID().slice(0, 8)}`,
    assessment_id: "assess-demo-001",
    assessment_version_id: assessmentVersionId,
    cohort_definition: { scope: "assessment_version" },
    algorithm_version: "B17_PSYCHOMETRICS_V1",
    min_cohort_size: 20,
    source_set_hash: "new-hash",
    source_result_count: 0,
    source_published_result_ids: [],
    status: "INSUFFICIENT_SAMPLE",
    requested_by: "user-admin-001",
    requested_at: now,
    completed_at: now,
    failure_code: "INSUFFICIENT_SAMPLE",
    failure_detail: "Published cohort size 0 < minimum 20",
    created_at: now,
    updated_at: now,
  };
  demoPsychometricRuns = [run, ...demoPsychometricRuns];
  return run;
}

export function getPsychometricRun(runId: string) {
  const run = demoPsychometricRuns.find((r) => r.id === runId);
  if (!run) throw new MockNotFoundError("Psychometric run not found");
  return { ...run };
}

export function listPsychometricRunItems(runId: string) {
  getPsychometricRun(runId);
  return {
    items: demoItemMetrics
      .filter((m) => m.run_id === runId)
      .map((m) => ({ ...m })),
  };
}

export function getLatestPsychometricRun(assessmentVersionId: string) {
  const run = demoPsychometricRuns.find(
    (r) => r.assessment_version_id === assessmentVersionId,
  );
  if (!run) throw new MockNotFoundError("No psychometric run");
  return { ...run };
}

export function listCalibrationSessions() {
  return {
    items: demoCalibrationSessions.map((s) => ({
      ...s,
      cases: undefined,
      participants: undefined,
    })),
  };
}

export function createCalibrationSession(input: {
  assessment_version_id: string;
  title: string;
  min_cases?: number;
}) {
  const now = new Date().toISOString();
  const session: import("@/lib/types/domain").CalibrationSession = {
    id: `calibration-session-demo-${crypto.randomUUID().slice(0, 8)}`,
    assessment_id: "assess-demo-001",
    assessment_version_id: input.assessment_version_id,
    title: input.title,
    status: "DRAFT",
    algorithm_version: "B17_CALIBRATION_V1",
    score_tolerance_abs: 0.5,
    score_tolerance_pct: 0.05,
    min_cases: input.min_cases ?? 10,
    activated_by: null,
    activated_at: null,
    closed_by: null,
    closed_at: null,
    created_by: "user-admin-001",
    created_at: now,
    updated_at: now,
    case_count: 0,
    cases: [],
    participants: [],
  };
  demoCalibrationSessions = [session, ...demoCalibrationSessions];
  return session;
}

export function getCalibrationSession(sessionId: string) {
  const session = demoCalibrationSessions.find((s) => s.id === sessionId);
  if (!session) throw new MockNotFoundError("Calibration session not found");
  return {
    ...session,
    cases: [...(session.cases ?? [])],
    participants: [...(session.participants ?? [])],
  };
}

export function activateCalibrationSession(sessionId: string) {
  const session = getCalibrationSession(sessionId);
  session.status = "ACTIVE";
  session.activated_at = new Date().toISOString();
  session.updated_at = session.activated_at;
  demoCalibrationSessions = demoCalibrationSessions.map((s) =>
    s.id === sessionId ? { ...session } : s,
  );
  return session;
}

export function closeCalibrationSession(sessionId: string) {
  const session = getCalibrationSession(sessionId);
  session.status = "CLOSED";
  session.closed_at = new Date().toISOString();
  session.updated_at = session.closed_at;
  demoCalibrationSessions = demoCalibrationSessions.map((s) =>
    s.id === sessionId ? { ...session } : s,
  );
  return session;
}

export function listMyCalibrationSessions() {
  return {
    items: demoCalibrationSessions
      .filter((s) => s.status === "ACTIVE" || s.status === "CLOSED")
      .map((s) => ({ ...s, cases: undefined, participants: undefined })),
  };
}

export function getBlindCalibrationCase(sessionId: string, caseId: string) {
  const session = getCalibrationSession(sessionId);
  const c = (session.cases ?? []).find((x) => x.id === caseId);
  if (!c) throw new MockNotFoundError("Calibration case not found");
  return {
    id: c.id,
    session_id: sessionId,
    case_code: c.case_code,
    question_version_id: c.question_version_id,
    rubric_version_id: c.rubric_version_id,
    max_mark: c.max_mark,
    criterion_snapshot: [],
    evidence_snapshot: { transcription_refs: [] },
  };
}

export function submitCalibrationResponse(
  sessionId: string,
  caseId: string,
  input: { score: number; comment?: string | null },
) {
  getBlindCalibrationCase(sessionId, caseId);
  return {
    id: `cal-resp-${crypto.randomUUID().slice(0, 8)}`,
    session_id: sessionId,
    case_id: caseId,
    participant_id: "cal-part-demo-001",
    user_id: "user-eval-001",
    score: input.score,
    max_mark: 5,
    comment: input.comment ?? null,
    submitted_at: new Date().toISOString(),
  };
}

export function getCalibrationProgress(sessionId: string) {
  const session = getCalibrationSession(sessionId);
  return {
    case_count: session.case_count ?? session.cases?.length ?? 0,
    participant_count: session.participants?.length ?? 0,
    response_count: 0,
    status: session.status,
  };
}

export function getCalibrationSessionMetrics(sessionId: string) {
  getCalibrationSession(sessionId);
  return {
    items: [
      {
        id: "cal-metric-demo-001",
        session_id: sessionId,
        metric_name: "ICC_A1",
        algorithm_version: "B17_CALIBRATION_V1",
        evaluator_count: 2,
        common_case_count: 1,
        icc_value: 0.91,
        status: "COMPLETED",
      },
    ],
  };
}

export function getCalibrationEvaluatorMetrics(sessionId: string) {
  getCalibrationSession(sessionId);
  return {
    items: [
      {
        id: "cal-eval-metric-demo-001",
        session_id: sessionId,
        user_id: "user-eval-001",
        case_count: 1,
        mean_signed_diff: 0.1,
        mae: 0.2,
        nmae: 0.04,
        exact_match_rate: 0.8,
        within_tolerance_rate: 1.0,
      },
    ],
  };
}

export function getMyCalibrationMetrics(sessionId: string) {
  return getCalibrationEvaluatorMetrics(sessionId).items[0];
}

/** B18 demo fixtures */
export const ANSWER_CLUSTER_RUN_DEMO_ID = "answer-cluster-run-demo-001";
export const ANSWER_CLUSTER_DEMO_ID = "answer-cluster-demo-001";
export const OUTCOME_DEFINITION_CO_DEMO_ID = "outcome-def-co-demo-001";
export const OUTCOME_MAPPING_SET_DEMO_ID = "outcome-mapping-set-demo-001";
export const OUTCOME_ATTAINMENT_REPORT_DEMO_ID = "outcome-attainment-report-demo-001";

let demoAnswerClusterRuns: import("@/lib/types/domain").AnswerClusterRun[] = [
  {
    id: ANSWER_CLUSTER_RUN_DEMO_ID,
    assessment_id: "assess-demo-001",
    assessment_version_id: "assess-ver-demo-001",
    question_id: "q-demo-001",
    question_version_id: "qv-demo-001",
    cohort_definition: {
      scope: "assessment_version",
      status_filter: ["PUBLISHED"],
      exclude_superseded: true,
    },
    algorithm_version: "COSINE_GRAPH_V1",
    similarity_threshold: 0.75,
    source_set_hash: "cluster-demo-hash",
    source_result_count: 24,
    source_published_result_ids: ["pub-demo-001"],
    embedding_provider: "mock",
    embedding_model: "mock-embedding-v1",
    embedding_model_version: "1",
    embedding_dim: 32,
    cluster_count: 2,
    status: "COMPLETED",
    requested_by: "user-admin-001",
    requested_at: "2026-09-10T06:00:00.000Z",
    completed_at: "2026-09-10T06:00:01.000Z",
    failure_code: null,
    failure_detail: null,
    created_at: "2026-09-10T06:00:00.000Z",
    updated_at: "2026-09-10T06:00:01.000Z",
  },
];

const demoAnswerClusters: import("@/lib/types/domain").AnswerCluster[] = [
  {
    id: ANSWER_CLUSTER_DEMO_ID,
    run_id: ANSWER_CLUSTER_RUN_DEMO_ID,
    cluster_index: 0,
    member_count: 3,
    label: "Common partial derivation",
    created_at: "2026-09-10T06:00:01.000Z",
  },
  {
    id: "answer-cluster-demo-002",
    run_id: ANSWER_CLUSTER_RUN_DEMO_ID,
    cluster_index: 1,
    member_count: 2,
    label: "Sign error pattern",
    created_at: "2026-09-10T06:00:01.000Z",
  },
];

const demoClusterMembers: import("@/lib/types/domain").AnswerClusterMember[] = [
  {
    id: "cluster-member-demo-001",
    run_id: ANSWER_CLUSTER_RUN_DEMO_ID,
    cluster_id: ANSWER_CLUSTER_DEMO_ID,
    published_result_id: "pub-demo-001",
    evaluation_run_id: "eval-run-demo-001",
    question_evaluation_id: "qe-demo-001",
    submission_id: "sub-demo-001",
    transcription_text: "Used chain rule but missed constant factor.",
    transcription_hash: "tx-hash-001",
    embedding: [0.1, 0.2, 0.3],
    final_human_approved_score: 3,
    created_at: "2026-09-10T06:00:01.000Z",
  },
];

let demoClusterReviews: import("@/lib/types/domain").AnswerClusterReview[] = [];

let demoOutcomeDefinitions: import("@/lib/types/domain").OutcomeDefinition[] = [
  {
    id: OUTCOME_DEFINITION_CO_DEMO_ID,
    outcome_type: "CO",
    code: "CO1",
    title: "Apply differentiation rules",
    description: "Students apply product and chain rules correctly.",
    status: "ACTIVE",
    created_by: "user-admin-001",
    created_at: "2026-09-10T06:10:00.000Z",
    updated_at: "2026-09-10T06:10:00.000Z",
  },
  {
    id: "outcome-def-po-demo-001",
    outcome_type: "PO",
    code: "PO2",
    title: "Problem solving",
    description: "Analyze and solve applied problems.",
    status: "ACTIVE",
    created_by: "user-admin-001",
    created_at: "2026-09-10T06:10:00.000Z",
    updated_at: "2026-09-10T06:10:00.000Z",
  },
];

let demoOutcomeMappingSets: import("@/lib/types/domain").OutcomeMappingSet[] = [
  {
    id: OUTCOME_MAPPING_SET_DEMO_ID,
    assessment_id: "assess-demo-001",
    assessment_version_id: "assess-ver-demo-001",
    version_number: 1,
    title: "Demo CO/PO mapping v1",
    status: "ACTIVE",
    created_by: "user-admin-001",
    activated_by: "user-admin-001",
    activated_at: "2026-09-10T06:15:00.000Z",
    retired_by: null,
    retired_at: null,
    created_at: "2026-09-10T06:12:00.000Z",
    updated_at: "2026-09-10T06:15:00.000Z",
    mapping_count: 1,
    mappings: [
      {
        id: "outcome-mapping-demo-001",
        mapping_set_id: OUTCOME_MAPPING_SET_DEMO_ID,
        question_id: "q-demo-001",
        question_version_id: "qv-demo-001",
        outcome_definition_id: OUTCOME_DEFINITION_CO_DEMO_ID,
        weight: 1,
        created_at: "2026-09-10T06:13:00.000Z",
      },
    ],
  },
];

let demoOutcomeAttainmentReports: import("@/lib/types/domain").OutcomeAttainmentReport[] =
  [
    {
      id: OUTCOME_ATTAINMENT_REPORT_DEMO_ID,
      assessment_id: "assess-demo-001",
      assessment_version_id: "assess-ver-demo-001",
      mapping_set_id: OUTCOME_MAPPING_SET_DEMO_ID,
      mapping_set_version_number: 1,
      cohort_definition: { scope: "assessment_version" },
      algorithm_version: "MARKS_WEIGHTED_V1",
      source_set_hash: "attainment-demo-hash",
      source_result_count: 24,
      source_published_result_ids: ["pub-demo-001"],
      status: "COMPLETED",
      requested_by: "user-admin-001",
      requested_at: "2026-09-10T06:20:00.000Z",
      completed_at: "2026-09-10T06:20:01.000Z",
      failure_code: null,
      failure_detail: null,
      created_at: "2026-09-10T06:20:00.000Z",
      updated_at: "2026-09-10T06:20:01.000Z",
      metrics: [
        {
          id: "attainment-metric-demo-001",
          report_run_id: OUTCOME_ATTAINMENT_REPORT_DEMO_ID,
          outcome_definition_id: OUTCOME_DEFINITION_CO_DEMO_ID,
          outcome_type: "CO",
          outcome_code: "CO1",
          outcome_title: "Apply differentiation rules",
          weighted_earned: 72,
          weighted_max: 120,
          attainment_pct: 60,
          denom_status: "OK",
          mapped_question_count: 1,
          contribution_count: 24,
          created_at: "2026-09-10T06:20:01.000Z",
        },
      ],
    },
  ];

export function listAnswerClusterRuns(
  assessmentVersionId?: string,
  questionId?: string,
) {
  let items = demoAnswerClusterRuns;
  if (assessmentVersionId) {
    items = items.filter(
      (r) => r.assessment_version_id === assessmentVersionId,
    );
  }
  if (questionId) {
    items = items.filter((r) => r.question_id === questionId);
  }
  return { items: items.map((r) => ({ ...r })) };
}

export function createAnswerClusterRun(input: {
  assessment_version_id: string;
  question_id: string;
  similarity_threshold?: number;
}) {
  const now = new Date().toISOString();
  const run: import("@/lib/types/domain").AnswerClusterRun = {
    id: `answer-cluster-run-demo-${crypto.randomUUID().slice(0, 8)}`,
    assessment_id: "assess-demo-001",
    assessment_version_id: input.assessment_version_id,
    question_id: input.question_id,
    question_version_id: "qv-demo-001",
    cohort_definition: { scope: "assessment_version" },
    algorithm_version: "COSINE_GRAPH_V1",
    similarity_threshold: input.similarity_threshold ?? 0.75,
    source_set_hash: "new-cluster-hash",
    source_result_count: 0,
    source_published_result_ids: [],
    embedding_provider: "mock",
    embedding_model: "mock-embedding-v1",
    embedding_model_version: "1",
    embedding_dim: 32,
    cluster_count: 0,
    status: "INSUFFICIENT_SAMPLE",
    requested_by: "user-admin-001",
    requested_at: now,
    completed_at: now,
    failure_code: "INSUFFICIENT_SAMPLE",
    failure_detail: "Published cohort size 0 < minimum 2",
    created_at: now,
    updated_at: now,
  };
  demoAnswerClusterRuns = [run, ...demoAnswerClusterRuns];
  return run;
}

export function getAnswerClusterRun(runId: string) {
  const run = demoAnswerClusterRuns.find((r) => r.id === runId);
  if (!run) throw new MockNotFoundError("Answer cluster run not found");
  return { ...run };
}

export function listAnswerClusters(runId: string) {
  getAnswerClusterRun(runId);
  return {
    items: demoAnswerClusters
      .filter((c) => c.run_id === runId)
      .map((c) => ({ ...c })),
  };
}

export function getAnswerCluster(clusterId: string) {
  const cluster = demoAnswerClusters.find((c) => c.id === clusterId);
  if (!cluster) throw new MockNotFoundError("Answer cluster not found");
  return {
    ...cluster,
    members: demoClusterMembers
      .filter((m) => m.cluster_id === clusterId)
      .map((m) => ({ ...m })),
    reviews: demoClusterReviews
      .filter((r) => r.cluster_id === clusterId)
      .map((r) => ({ ...r })),
  };
}

export function submitAnswerClusterReview(
  clusterId: string,
  input: { observation: string; suggested_rubric_refinement?: string | null },
) {
  const cluster = getAnswerCluster(clusterId);
  const review: import("@/lib/types/domain").AnswerClusterReview = {
    id: `cluster-review-demo-${crypto.randomUUID().slice(0, 8)}`,
    run_id: cluster.run_id,
    cluster_id: clusterId,
    reviewer_user_id: "user-admin-001",
    observation: input.observation,
    suggested_rubric_refinement: input.suggested_rubric_refinement ?? null,
    submitted_at: new Date().toISOString(),
    created_at: new Date().toISOString(),
  };
  demoClusterReviews = [...demoClusterReviews, review];
  return review;
}

export function listOutcomeDefinitions(outcomeType?: string) {
  const items = outcomeType
    ? demoOutcomeDefinitions.filter(
        (d) => d.outcome_type === outcomeType.toUpperCase(),
      )
    : demoOutcomeDefinitions;
  return { items: items.map((d) => ({ ...d })) };
}

export function createOutcomeDefinition(input: {
  outcome_type: string;
  code: string;
  title: string;
  description?: string | null;
}) {
  const now = new Date().toISOString();
  const row: import("@/lib/types/domain").OutcomeDefinition = {
    id: `outcome-def-demo-${crypto.randomUUID().slice(0, 8)}`,
    outcome_type: input.outcome_type.toUpperCase(),
    code: input.code,
    title: input.title,
    description: input.description ?? null,
    status: "ACTIVE",
    created_by: "user-admin-001",
    created_at: now,
    updated_at: now,
  };
  demoOutcomeDefinitions = [row, ...demoOutcomeDefinitions];
  return row;
}

export function getOutcomeDefinition(id: string) {
  const row = demoOutcomeDefinitions.find((d) => d.id === id);
  if (!row) throw new MockNotFoundError("Outcome definition not found");
  return { ...row };
}

export function updateOutcomeDefinition(
  id: string,
  input: {
    title?: string;
    description?: string | null;
    status?: string;
  },
) {
  const row = getOutcomeDefinition(id);
  const updated = {
    ...row,
    ...input,
    updated_at: new Date().toISOString(),
  };
  demoOutcomeDefinitions = demoOutcomeDefinitions.map((d) =>
    d.id === id ? updated : d,
  );
  return updated;
}

export function listOutcomeMappingSets(assessmentVersionId?: string) {
  const items = assessmentVersionId
    ? demoOutcomeMappingSets.filter(
        (s) => s.assessment_version_id === assessmentVersionId,
      )
    : demoOutcomeMappingSets;
  return {
    items: items.map((s) => ({
      ...s,
      mappings: undefined,
    })),
  };
}

export function createOutcomeMappingSet(input: {
  assessment_version_id: string;
  title: string;
}) {
  const now = new Date().toISOString();
  const row: import("@/lib/types/domain").OutcomeMappingSet = {
    id: `outcome-mapping-set-demo-${crypto.randomUUID().slice(0, 8)}`,
    assessment_id: "assess-demo-001",
    assessment_version_id: input.assessment_version_id,
    version_number: 1,
    title: input.title,
    status: "DRAFT",
    created_by: "user-admin-001",
    activated_by: null,
    activated_at: null,
    retired_by: null,
    retired_at: null,
    created_at: now,
    updated_at: now,
    mapping_count: 0,
    mappings: [],
  };
  demoOutcomeMappingSets = [row, ...demoOutcomeMappingSets];
  return row;
}

export function getOutcomeMappingSet(id: string) {
  const row = demoOutcomeMappingSets.find((s) => s.id === id);
  if (!row) throw new MockNotFoundError("Outcome mapping set not found");
  return {
    ...row,
    mappings: [...(row.mappings ?? [])],
  };
}

export function addOutcomeMapping(
  mappingSetId: string,
  input: {
    question_id: string;
    outcome_definition_id: string;
    weight?: number;
  },
) {
  const set = getOutcomeMappingSet(mappingSetId);
  if (set.status !== "DRAFT") {
    throw new MockNotFoundError("Only DRAFT mapping sets accept new mappings");
  }
  const mapping: import("@/lib/types/domain").QuestionOutcomeMapping = {
    id: `outcome-mapping-demo-${crypto.randomUUID().slice(0, 8)}`,
    mapping_set_id: mappingSetId,
    question_id: input.question_id,
    question_version_id: "qv-demo-001",
    outcome_definition_id: input.outcome_definition_id,
    weight: input.weight ?? 1,
    created_at: new Date().toISOString(),
  };
  const updated = {
    ...set,
    mappings: [...(set.mappings ?? []), mapping],
    mapping_count: (set.mapping_count ?? 0) + 1,
    updated_at: new Date().toISOString(),
  };
  demoOutcomeMappingSets = demoOutcomeMappingSets.map((s) =>
    s.id === mappingSetId ? updated : s,
  );
  return mapping;
}

export function removeOutcomeMapping(mappingId: string) {
  let found = false;
  demoOutcomeMappingSets = demoOutcomeMappingSets.map((set) => {
    const mappings = (set.mappings ?? []).filter((m) => m.id !== mappingId);
    if (mappings.length !== (set.mappings ?? []).length) {
      found = true;
      return {
        ...set,
        mappings,
        mapping_count: mappings.length,
        updated_at: new Date().toISOString(),
      };
    }
    return set;
  });
  if (!found) throw new MockNotFoundError("Outcome mapping not found");
  return { ok: true as const };
}

export function activateOutcomeMappingSet(mappingSetId: string) {
  const set = getOutcomeMappingSet(mappingSetId);
  if ((set.mappings ?? []).length === 0) {
    throw new MockNotFoundError("Cannot activate empty mapping set");
  }
  const now = new Date().toISOString();
  const updated = {
    ...set,
    status: "ACTIVE",
    activated_by: "user-admin-001",
    activated_at: now,
    updated_at: now,
  };
  demoOutcomeMappingSets = demoOutcomeMappingSets.map((s) =>
    s.id === mappingSetId ? updated : s,
  );
  return updated;
}

export function listOutcomeAttainmentReports(assessmentVersionId?: string) {
  const items = assessmentVersionId
    ? demoOutcomeAttainmentReports.filter(
        (r) => r.assessment_version_id === assessmentVersionId,
      )
    : demoOutcomeAttainmentReports;
  return {
    items: items.map((r) => ({
      ...r,
      metrics: undefined,
    })),
  };
}

export function createOutcomeAttainmentReport(input: {
  assessment_version_id: string;
  mapping_set_id?: string;
}) {
  const mappingSetId =
    input.mapping_set_id ?? OUTCOME_MAPPING_SET_DEMO_ID;
  const mappingSet = getOutcomeMappingSet(mappingSetId);
  const now = new Date().toISOString();
  const report: import("@/lib/types/domain").OutcomeAttainmentReport = {
    id: `outcome-attainment-report-demo-${crypto.randomUUID().slice(0, 8)}`,
    assessment_id: "assess-demo-001",
    assessment_version_id: input.assessment_version_id,
    mapping_set_id: mappingSetId,
    mapping_set_version_number: mappingSet.version_number,
    cohort_definition: { scope: "assessment_version" },
    algorithm_version: "MARKS_WEIGHTED_V1",
    source_set_hash: "new-attainment-hash",
    source_result_count: 24,
    source_published_result_ids: ["pub-demo-001"],
    status: "COMPLETED",
    requested_by: "user-admin-001",
    requested_at: now,
    completed_at: now,
    failure_code: null,
    failure_detail: null,
    created_at: now,
    updated_at: now,
    metrics: (mappingSet.mappings ?? []).map((m, idx) => {
      const def = getOutcomeDefinition(m.outcome_definition_id);
      return {
        id: `attainment-metric-demo-${idx}`,
        report_run_id: "",
        outcome_definition_id: def.id,
        outcome_type: def.outcome_type,
        outcome_code: def.code,
        outcome_title: def.title,
        weighted_earned: 60,
        weighted_max: 100,
        attainment_pct: 60,
        denom_status: "OK",
        mapped_question_count: 1,
        contribution_count: 24,
        created_at: now,
      };
    }),
  };
  report.metrics = (report.metrics ?? []).map((m) => ({
    ...m,
    report_run_id: report.id,
  }));
  demoOutcomeAttainmentReports = [report, ...demoOutcomeAttainmentReports];
  return report;
}

export function getOutcomeAttainmentReport(reportId: string) {
  const report = demoOutcomeAttainmentReports.find((r) => r.id === reportId);
  if (!report) throw new MockNotFoundError("Attainment report not found");
  return {
    ...report,
    metrics: [...(report.metrics ?? [])],
  };
}

export function exportOutcomeAttainmentReportCsv(reportId: string) {
  const report = getOutcomeAttainmentReport(reportId);
  const header =
    "report_id,outcome_type,outcome_code,outcome_title,weighted_earned,weighted_max,attainment_pct,denom_status,mapped_question_count,contribution_count";
  const rows = (report.metrics ?? []).map(
    (m) =>
      `${report.id},${m.outcome_type},${m.outcome_code},${m.outcome_title},${m.weighted_earned},${m.weighted_max},${m.attainment_pct},${m.denom_status},${m.mapped_question_count},${m.contribution_count}`,
  );
  return [header, ...rows].join("\n");
}
