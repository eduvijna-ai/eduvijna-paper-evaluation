import type {
  AdaptiveLearningPlan,
  AnalyticsMaterializationPrepareResult,
  AnnotatedPaperWorkspace,
  AnswerKeyStep,
  Assessment,
  AssessmentAnalyticsView,
  AuthSession,
  Curriculum,
  CurriculumMapEntry,
  CurriculumNode,
  DashboardSummary,
  EvaluationWorkspacePayload,
  IdentityReviewPayload,
  ImprovementAssessmentBlueprint,
  ImprovementBlueprintPrepareResult,
  LearningPlanPrepareResult,
  LiveImprovementAssessment,
  LiveLearningPlan,
  LiveLearningWorkspace,
  EvidenceRegion,
  MappingReviewPayload,
  PaperPage,
  ParentReport,
  PublicationAnnotation,
  PublicationArtifactType,
  PublicationPrepareResult,
  PublicationPublishResult,
  PublicationRegenerateResult,
  PublicationWorkspace,
  Question,
  QuestionAnswerMappingView,
  RubricCriterion,
  Student,
  StudentAnalyticsView,
  StudentMasteryEvidenceList,
  StudentMasteryState,
  StudentMasteryTrend,
  StudentMistakeNotebook,
  StudentRecoverableMarks,
  StudentRepeatedErrors,
  B12RebuildResult,
  StudentReport,
  Submission,
  TeacherReport,
  TranscriptionWorkspacePayload,
  RegionTranscriptionView,
} from "@/lib/types/domain";
import type { MappingAction, TeacherReviewAction } from "@/lib/types/enums";
import type { TeacherActionResult } from "@/lib/helpers/teacher-actions";
import type {
  AcademicYearFormValues,
  AcademicYearView,
  ClassSectionFormValues,
  ClassSectionView,
  InstitutionView,
} from "@/lib/api/mappers/platform";
import type {
  GuardianFormValues,
  GuardianView,
  StudentGuardianLinkView,
} from "@/lib/api/mappers/guardian";
import type { StudentFormValues } from "@/lib/api/mappers/student";
import type { AssessmentFormValues } from "@/lib/api/mappers/authoring";
import type {
  ImportCommitResult,
  ImportValidationView,
} from "@/lib/api/mappers/import";
import type { A2AssessmentVersion, A2AnswerKeyVersion, A2Rubric, A2RubricCriterion, A2RubricVersion } from "@/lib/api/a2-types";
import type {
  AssessmentArtifact,
  AuthoringAiRun,
  ProposedQuestionNode,
} from "@/lib/types/domain";

export interface OperationalHealth {
  status: "ok" | "degraded" | "error" | string;
  service?: string;
  version?: string;
  build?: string;
  [key: string]: string | number | boolean | undefined;
}

/**
 * Unified API surface. Components must not branch on mock vs HTTP.
 * Domain routing is an adapter concern (hybrid client).
 */
export interface ApiClient {
  getHealth(): Promise<OperationalHealth>;
  getReady(): Promise<OperationalHealth>;
  getVersion(): Promise<{ version: string; build?: string }>;

  login(email: string, password: string): Promise<AuthSession>;
  logout(): Promise<void>;
  getCurrentUser(): Promise<AuthSession>;

  getInstitution(): Promise<InstitutionView>;
  listAcademicYears(): Promise<AcademicYearView[]>;
  createAcademicYear(form: AcademicYearFormValues): Promise<AcademicYearView>;
  updateAcademicYear(
    id: string,
    form: Partial<AcademicYearFormValues>,
  ): Promise<AcademicYearView>;
  listClassSections(): Promise<ClassSectionView[]>;
  createClassSection(form: ClassSectionFormValues): Promise<ClassSectionView>;
  updateClassSection(
    id: string,
    form: Partial<ClassSectionFormValues>,
  ): Promise<ClassSectionView>;

  listStudents(): Promise<Student[]>;
  getStudent(id: string): Promise<Student>;
  createStudent(form: StudentFormValues): Promise<Student>;
  updateStudent(id: string, form: Partial<StudentFormValues>): Promise<Student>;
  validateStudentImport(file: Blob): Promise<ImportValidationView>;
  commitStudentImport(importSessionId: string): Promise<ImportCommitResult>;

  listGuardians(): Promise<GuardianView[]>;
  listStudentGuardians(studentId: string): Promise<StudentGuardianLinkView[]>;
  getGuardian(id: string): Promise<GuardianView>;
  createGuardian(form: GuardianFormValues): Promise<GuardianView>;
  updateGuardian(
    id: string,
    form: Partial<GuardianFormValues>,
  ): Promise<GuardianView>;
  linkStudentGuardian(
    studentId: string,
    guardianId: string,
    relationshipType: string,
  ): Promise<void>;
  unlinkStudentGuardian(studentId: string, guardianId: string): Promise<void>;

  getDashboard(): Promise<DashboardSummary>;
  listCurricula(): Promise<Curriculum[]>;
  getCurriculum(id: string): Promise<{
    curriculum: Curriculum;
    tree: CurriculumNode[];
  }>;
  listAssessments(): Promise<Assessment[]>;
  getAssessment(id: string): Promise<Assessment>;
  /** B2 live authoring. Optional so the preserved B0 mock client remains source-compatible. */
  createAssessment?(form: AssessmentFormValues): Promise<Assessment>;
  getAssessmentQuestions(id: string): Promise<Question[]>;
  getAssessmentRubric(id: string): Promise<RubricCriterion[]>;
  getAssessmentAnswerKey(id: string): Promise<AnswerKeyStep[]>;
  getAssessmentCurriculumMap(id: string): Promise<CurriculumMapEntry[]>;
  /** B10 live authoring. Optional so the preserved B0 mock client remains source-compatible. */
  getLatestAssessmentVersion?(assessmentId: string): Promise<A2AssessmentVersion>;
  uploadQuestionPaper?(
    versionId: string,
    file: File,
  ): Promise<AssessmentArtifact>;
  prepareQuestionPaperParse?(versionId: string): Promise<AuthoringAiRun>;
  getLatestAuthoringAiRun?(
    versionId: string,
    operation?: string,
  ): Promise<AuthoringAiRun | null>;
  getAssessmentArtifact?(artifactId: string): Promise<AssessmentArtifact>;
  getAuthoringAiRun?(runId: string): Promise<AuthoringAiRun>;
  updateQuestionTreeProposal?(
    runId: string,
    tree: { roots: ProposedQuestionNode[]; notes?: string | null },
  ): Promise<AuthoringAiRun>;
  applyQuestionTreeProposal?(runId: string): Promise<AuthoringAiRun>;
  createTeacherAnswerKey?(input: {
    assessmentId: string;
    assessmentVersionId: string;
    questionVersionId: string;
    answerText: string;
  }): Promise<A2AnswerKeyVersion>;
  updateAnswerKey?(
    answerKeyVersionId: string,
    patch: { answerText?: string; status?: "DRAFT" | "REVIEW_REQUIRED" },
  ): Promise<A2AnswerKeyVersion>;
  approveAnswerKey?(answerKeyVersionId: string): Promise<A2AnswerKeyVersion>;
  prepareAiAnswerKeyProposal?(input: {
    questionVersionId: string;
    assessmentVersionId?: string;
    instructions?: string;
  }): Promise<AuthoringAiRun>;
  createTeacherRubric?(input: {
    assessmentId: string;
    questionVersionId: string;
    title: string;
    criteria: Array<{
      criterionCode: string;
      description: string;
      maxMarks: number | string;
      sequence: number;
      scoringMode?: "ADDITIVE" | "DEDUCTIVE" | "ALL_OR_NOTHING";
      partialCreditAllowed?: boolean;
    }>;
  }): Promise<{
    rubric: A2Rubric;
    version: A2RubricVersion;
    criteria: A2RubricCriterion[];
  }>;
  updateRubric?(
    rubricVersionId: string,
    patch: {
      questionVersionId: string;
      status?: "DRAFT" | "REVIEW_REQUIRED";
      sourceType?: "TEACHER" | "IMPORTED";
    },
  ): Promise<A2RubricVersion>;
  approveRubric?(rubricVersionId: string): Promise<A2RubricVersion>;
  prepareAiRubricProposal?(input: {
    questionVersionId: string;
    assessmentVersionId?: string;
    instructions?: string;
  }): Promise<AuthoringAiRun>;
  prepareAiCurriculumMappingProposal?(input: {
    questionVersionId: string;
    curriculumId?: string;
    instructions?: string;
  }): Promise<AuthoringAiRun>;
  updateCurriculumMappingProposal?(
    runId: string,
    mappings: Array<{
      curriculum_node_id: string;
      mapping_type: "PRIMARY" | "SECONDARY" | "LEARNING_OUTCOME" | "SKILL";
      weight?: string | number | null;
      rationale?: string | null;
    }>,
  ): Promise<AuthoringAiRun>;
  applyCurriculumMappings?(
    runId: string,
    selectedIndices?: number[] | null,
  ): Promise<AuthoringAiRun>;
  transitionAssessment?(
    assessmentId: string,
    toStatus: string,
  ): Promise<Assessment>;
  listSubmissions(): Promise<Submission[]>;
  getSubmission(id: string): Promise<Submission>;
  /** B3 live upload. Optional so the preserved B0 mock client remains source-compatible. */
  uploadSubmission?(input: {
    assessmentId: string;
    bundleName?: string;
    file: File;
  }): Promise<Submission>;
  /** B3 live page PNG. Optional — only wired in hybrid/live. */
  getSubmissionPageImageBlob?(pageId: string): Promise<Blob>;
  getIdentityReview(submissionId: string): Promise<IdentityReviewPayload>;
  confirmIdentity(
    submissionId: string,
    studentId: string,
  ): Promise<Submission>;
  markIdentityUnmatched(submissionId: string): Promise<Submission>;
  getMappingReview(submissionId: string): Promise<MappingReviewPayload>;
  applyMappingAction(
    submissionId: string,
    regionId: string,
    action: MappingAction,
    targetQuestionId?: string,
  ): Promise<{ ok: true; action: MappingAction }>;
  /** B4 live mapping. Optional so the preserved B0 mock client remains source-compatible. */
  prepareMappingReview?(submissionId: string): Promise<Submission>;
  createAnswerRegion?(
    pageId: string,
    input: {
      label: string;
      region_type: "ANSWER" | "SCRATCH" | "DIAGRAM" | "IDENTITY";
      bbox: { x: number; y: number; width: number; height: number };
    },
  ): Promise<EvidenceRegion>;
  updateAnswerRegion?(
    regionId: string,
    input: {
      label?: string;
      region_type?: "ANSWER" | "SCRATCH" | "DIAGRAM" | "IDENTITY";
      bbox?: { x: number; y: number; width: number; height: number };
      crossed_out?: boolean;
      ignored?: boolean;
      is_continuation?: boolean;
    },
  ): Promise<EvidenceRegion>;
  deleteAnswerRegion?(regionId: string): Promise<void>;
  updateSubmissionPage?(
    pageId: string,
    input: { is_continuation: boolean },
  ): Promise<PaperPage>;
  upsertQuestionMapping?(
    submissionId: string,
    questionVersionId: string,
    input: {
      disposition: "ANSWERED" | "BLANK";
      region_ids: string[];
    },
  ): Promise<QuestionAnswerMappingView>;
  confirmQuestionMapping?(
    submissionId: string,
    questionVersionId: string,
  ): Promise<QuestionAnswerMappingView>;
  finalizeMappingReview?(submissionId: string): Promise<Submission>;
  /** B5 live transcription. Optional so the preserved B0 mock client remains source-compatible. */
  prepareTranscription?(submissionId: string): Promise<Submission>;
  getTranscriptionWorkspace?(
    submissionId: string,
  ): Promise<TranscriptionWorkspacePayload>;
  putRegionTranscription?(
    regionId: string,
    payload: {
      text?: string | null;
      latex?: string | null;
      unreadable?: boolean;
      visual_only?: boolean;
      outcome?: "TRANSCRIBED" | "UNREADABLE" | "VISUAL_ONLY";
    },
  ): Promise<RegionTranscriptionView>;
  confirmTranscription?(transcriptionId: string): Promise<RegionTranscriptionView>;
  finalizeTranscription?(submissionId: string): Promise<Submission>;
  getRegionCropBlob?(regionId: string): Promise<Blob>;
  getEvaluationWorkspace(
    submissionId: string,
    questionId?: string,
  ): Promise<EvaluationWorkspacePayload>;
  applyTeacherAction(
    submissionId: string,
    ledgerId: string,
    action: TeacherReviewAction,
    payload?: { newScore?: number; feedback?: string },
  ): Promise<TeacherActionResult>;
  /** B6 live evaluation. Optional for mock-source compatibility. */
  prepareEvaluation?(submissionId: string): Promise<Submission>;
  finalizeEvaluation?(submissionId: string): Promise<Submission>;
  /** B7 live publication. Optional for mock-source compatibility. */
  preparePublication?(submissionId: string): Promise<PublicationPrepareResult>;
  getPublicationWorkspace?(
    submissionId: string,
  ): Promise<PublicationWorkspace>;
  regeneratePublication?(
    publishedResultId: string,
  ): Promise<PublicationRegenerateResult>;
  publishPublication?(
    publishedResultId: string,
  ): Promise<PublicationPublishResult>;
  getPublicationArtifactBlob?(
    publishedResultId: string,
    artifactType: PublicationArtifactType,
  ): Promise<Blob>;
  createPublicationAnnotation?(
    publishedResultId: string,
    input: {
      annotation_type: "COMMENT" | "HIGHLIGHT";
      submission_page_id: string;
      x: number;
      y: number;
      width: number;
      height: number;
      payload?: Record<string, unknown>;
    },
  ): Promise<PublicationAnnotation>;
  previewPublicationReport?(
    publishedResultId: string,
    audience: "student" | "parent" | "teacher",
  ): Promise<StudentReport | ParentReport | TeacherReport>;
  getAnnotatedPaperWorkspace?(
    submissionId: string,
  ): Promise<AnnotatedPaperWorkspace>;
  getStudentReport(
    studentId: string,
    assessmentId: string,
  ): Promise<StudentReport>;
  getParentReport(
    studentId: string,
    assessmentId: string,
  ): Promise<ParentReport>;
  getTeacherReport?(
    studentId: string,
    assessmentId: string,
  ): Promise<TeacherReport>;
  getAssessmentAnalytics(
    assessmentId: string,
    options?: { passThresholdPercent?: number },
  ): Promise<AssessmentAnalyticsView>;
  getStudentAnalytics(studentId: string): Promise<StudentAnalyticsView>;
  getStudentMasteryEvidence?(
    studentId: string,
    filters?: {
      assessmentId?: string;
      curriculumId?: string;
      curriculumNodeId?: string;
    },
  ): Promise<StudentMasteryEvidenceList>;
  prepareAnalyticsMaterialization?(
    publishedResultId: string,
  ): Promise<AnalyticsMaterializationPrepareResult>;
  getStudentMasteryState(studentId: string): Promise<StudentMasteryState>;
  getStudentMasteryTrend(
    studentId: string,
    options?: { curriculumNodeId?: string },
  ): Promise<StudentMasteryTrend>;
  getStudentRepeatedErrors(studentId: string): Promise<StudentRepeatedErrors>;
  getStudentRecoverableMarks(
    studentId: string,
  ): Promise<StudentRecoverableMarks>;
  getStudentMistakeNotebook(
    studentId: string,
  ): Promise<StudentMistakeNotebook>;
  rebuildStudentB12?(studentId: string): Promise<B12RebuildResult>;
  getAdaptiveLearning(studentId: string): Promise<AdaptiveLearningPlan>;
  getLearningWorkspace?(
    studentId: string,
    curriculumId?: string,
  ): Promise<LiveLearningWorkspace>;
  prepareLearningPlan?(
    studentId: string,
    curriculumId: string,
  ): Promise<LearningPlanPrepareResult>;
  getLearningPlanRun?(runId: string): Promise<LiveLearningPlan>;
  prepareImprovementBlueprint?(
    runId: string,
  ): Promise<ImprovementBlueprintPrepareResult>;
  getImprovementAssessment?(
    id: string,
  ): Promise<LiveImprovementAssessment>;
  getImprovementBlueprint(
    studentId: string,
  ): Promise<ImprovementAssessmentBlueprint>;
  approveImprovementBlueprint(
    blueprintId: string,
  ): Promise<
    ImprovementAssessmentBlueprint | LiveImprovementAssessment
  >;
  rejectImprovementBlueprint?(
    blueprintId: string,
    reason: string,
  ): Promise<LiveImprovementAssessment>;
}
