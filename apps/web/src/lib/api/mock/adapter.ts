import { applyTeacherReviewAction } from "@/lib/helpers/teacher-actions";
import type { MappingAction, TeacherReviewAction } from "@/lib/types/enums";
import type { ApiClient } from "../types";
import {
  assessments,
  buildCurriculumTree,
  buildQuestionTree,
  curricula,
  getAdaptiveLearning,
  getAssessmentAnalytics,
  getDashboardSummary,
  getEvaluationWorkspace,
  getIdentityReview,
  getImprovementBlueprint,
  getMappingReview,
  getParentReport,
  getStudentAnalytics,
  getStudentReport,
  rubrics,
  students,
  submissions,
} from "./data";

function delay<T>(value: T, ms = 120): Promise<T> {
  if (typeof window === "undefined") {
    return Promise.resolve(value);
  }
  return new Promise((resolve) => {
    setTimeout(() => resolve(value), ms);
  });
}

export const mockApiClient: ApiClient = {
  async getDashboard() {
    return delay(getDashboardSummary());
  },
  async listCurricula() {
    return delay(curricula);
  },
  async getCurriculum(id) {
    const curriculum = curricula.find((c) => c.id === id) ?? curricula[0];
    return delay({ curriculum, tree: buildCurriculumTree() });
  },
  async listStudents() {
    return delay(students);
  },
  async getStudent(id) {
    const student = students.find((s) => s.id === id);
    if (!student) throw new Error(`Student not found: ${id}`);
    return delay(student);
  },
  async listAssessments() {
    return delay(assessments);
  },
  async getAssessment(id) {
    const assessment = assessments.find((a) => a.id === id);
    if (!assessment) throw new Error(`Assessment not found: ${id}`);
    return delay(assessment);
  },
  async getAssessmentQuestions(id) {
    return delay(buildQuestionTree(id));
  },
  async getAssessmentRubric(id) {
    return delay(rubrics.filter((r) => r.question_id.startsWith("q-") && assessments.some((a) => a.id === id)));
  },
  async listSubmissions() {
    return delay(submissions);
  },
  async getSubmission(id) {
    const submission = submissions.find((s) => s.id === id);
    if (!submission) throw new Error(`Submission not found: ${id}`);
    return delay(submission);
  },
  async getIdentityReview(submissionId) {
    return delay(getIdentityReview(submissionId));
  },
  async confirmIdentity(submissionId, studentId) {
    const submission = submissions.find((s) => s.id === submissionId);
    if (!submission) throw new Error(`Submission not found: ${submissionId}`);
    const student = students.find((s) => s.id === studentId);
    if (!student) throw new Error(`Student not found: ${studentId}`);
    submission.student_id = student.id;
    submission.student_display_name = student.display_name;
    submission.student_match_state = "CONFIRMED";
    submission.identity_confidence = 1;
    submission.workflow_state = "MAPPING_REVIEW";
    return delay({ ...submission });
  },
  async getMappingReview(submissionId) {
    return delay(getMappingReview(submissionId));
  },
  async applyMappingAction(submissionId, regionId, action: MappingAction) {
    void submissionId;
    void regionId;
    return delay({ ok: true as const, action });
  },
  async getEvaluationWorkspace(submissionId, questionId) {
    return delay(getEvaluationWorkspace(submissionId, questionId));
  },
  async applyTeacherAction(
    submissionId,
    ledgerId,
    action: TeacherReviewAction,
    payload,
  ) {
    void submissionId;
    void ledgerId;
    const workspace = getEvaluationWorkspace(submissionId);
    const ledger = workspace.ledgers.find((l) => l.id === ledgerId);
    if (!ledger) throw new Error(`Ledger not found: ${ledgerId}`);
    return delay(
      applyTeacherReviewAction({
        action,
        proposedScore: ledger.proposed_ai_score,
        maxMark: ledger.max_mark,
        newScore: payload?.newScore,
        feedback: payload?.feedback,
      }),
    );
  },
  async getStudentReport(studentId, assessmentId) {
    return delay(getStudentReport(studentId, assessmentId));
  },
  async getParentReport(studentId, assessmentId) {
    return delay(getParentReport(studentId, assessmentId));
  },
  async getAssessmentAnalytics(assessmentId) {
    return delay(getAssessmentAnalytics(assessmentId));
  },
  async getStudentAnalytics(studentId) {
    return delay(getStudentAnalytics(studentId));
  },
  async getAdaptiveLearning(studentId) {
    return delay(getAdaptiveLearning(studentId));
  },
  async getImprovementBlueprint(studentId) {
    return delay(getImprovementBlueprint(studentId));
  },
  async approveImprovementBlueprint(blueprintId) {
    const blueprint = getImprovementBlueprint("student-demo-001");
    return delay({
      ...blueprint,
      id: blueprintId,
      workflow_state: "APPROVED" as const,
      teacher_notes: "Approved for student release.",
    });
  },
};
