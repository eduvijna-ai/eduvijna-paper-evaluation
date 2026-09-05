import type {
  AdaptiveLearningPlan,
  Assessment,
  AssessmentAnalytics,
  Curriculum,
  CurriculumNode,
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
  RubricCriterion,
  AnswerKeyStep,
  CurriculumMapEntry,
  Student,
  StudentAnalytics,
  StudentReport,
  Submission,
} from "@/lib/types/domain";

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
  const submission =
    submissions.find((s) => s.id === submissionId) ?? submissions[1];
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
  const submission =
    submissions.find((s) => s.id === submissionId) ?? submissions[2];
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

export function getEvaluationWorkspace(
  submissionId: string,
  questionId?: string,
): EvaluationWorkspacePayload {
  const submission =
    submissions.find((s) => s.id === submissionId) ?? submissions[0];
  const assessment =
    assessments.find((a) => a.id === submission.assessment_id) ??
    assessments[0];
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
  const student = students.find((s) => s.id === studentId) ?? students[0];
  const assessment =
    assessments.find((a) => a.id === assessmentId) ?? assessments[0];
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
  const student = students.find((s) => s.id === studentId) ?? students[0];
  const assessment =
    assessments.find((a) => a.id === assessmentId) ?? assessments[0];
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
  const assessment =
    assessments.find((a) => a.id === assessmentId) ?? assessments[0];
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
    return {
      student: {
        id: studentId,
        tenant_id: "",
        institution_id: "",
        class_section_id: "",
        external_ref: "—",
        first_name: "",
        last_name: "",
        display_name: "Analytics unavailable",
        grade: "—",
        section: "—",
        status: "ACTIVE",
      },
      assessments_taken: 0,
      average_percentage: 0,
      trend: [],
      concept_mastery: [],
      recurring_errors: [],
    };
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

export function getAdaptiveLearning(studentId: string): AdaptiveLearningPlan {
  const student = students.find((s) => s.id === studentId) ?? students[0];
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
