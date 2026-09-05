import type {
  AdaptiveLearningPlan,
  AnswerKeyStep,
  Assessment,
  AssessmentAnalytics,
  Curriculum,
  CurriculumMapEntry,
  CurriculumNode,
  DashboardSummary,
  EvaluationWorkspacePayload,
  IdentityReviewPayload,
  ImprovementAssessmentBlueprint,
  MappingReviewPayload,
  ParentReport,
  Question,
  RubricCriterion,
  Student,
  StudentAnalytics,
  StudentReport,
  Submission,
} from "@/lib/types/domain";
import type { MappingAction, TeacherReviewAction } from "@/lib/types/enums";
import type { TeacherActionResult } from "@/lib/helpers/teacher-actions";

export interface OperationalHealth {
  status: "ok" | "degraded" | "error" | string;
  service?: string;
  version?: string;
  build?: string;
  [key: string]: string | number | boolean | undefined;
}

export interface ApiClient {
  getHealth(): Promise<OperationalHealth>;
  getReady(): Promise<OperationalHealth>;
  getVersion(): Promise<{ version: string; build?: string }>;

  getDashboard(): Promise<DashboardSummary>;
  listCurricula(): Promise<Curriculum[]>;
  getCurriculum(id: string): Promise<{
    curriculum: Curriculum;
    tree: CurriculumNode[];
  }>;
  listStudents(): Promise<Student[]>;
  getStudent(id: string): Promise<Student>;
  listAssessments(): Promise<Assessment[]>;
  getAssessment(id: string): Promise<Assessment>;
  getAssessmentQuestions(id: string): Promise<Question[]>;
  getAssessmentRubric(id: string): Promise<RubricCriterion[]>;
  getAssessmentAnswerKey(id: string): Promise<AnswerKeyStep[]>;
  getAssessmentCurriculumMap(id: string): Promise<CurriculumMapEntry[]>;
  listSubmissions(): Promise<Submission[]>;
  getSubmission(id: string): Promise<Submission>;
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
