import type {
  AdaptiveLearningPlan,
  AnswerKeyStep,
  Assessment,
  AssessmentAnalytics,
  AuthSession,
  Curriculum,
  CurriculumMapEntry,
  CurriculumNode,
  DashboardSummary,
  EvaluationWorkspacePayload,
  IdentityReviewPayload,
  ImprovementAssessmentBlueprint,
  EvidenceRegion,
  MappingReviewPayload,
  PaperPage,
  ParentReport,
  Question,
  QuestionAnswerMappingView,
  RubricCriterion,
  Student,
  StudentAnalytics,
  StudentReport,
  Submission,
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
  getStudentReport(
    studentId: string,
    assessmentId: string,
  ): Promise<StudentReport>;
  getParentReport(
    studentId: string,
    assessmentId: string,
  ): Promise<ParentReport>;
  getAssessmentAnalytics(assessmentId: string): Promise<AssessmentAnalytics>;
  getStudentAnalytics(studentId: string): Promise<StudentAnalytics>;
  getAdaptiveLearning(studentId: string): Promise<AdaptiveLearningPlan>;
  getImprovementBlueprint(
    studentId: string,
  ): Promise<ImprovementAssessmentBlueprint>;
  approveImprovementBlueprint(
    blueprintId: string,
  ): Promise<ImprovementAssessmentBlueprint>;
}
