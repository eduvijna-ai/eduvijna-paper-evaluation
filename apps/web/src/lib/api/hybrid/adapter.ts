import type { ApiClient, OperationalHealth } from "../types";
import { MockEduVijnaApi } from "../mock/adapter";
import { PlatformHttpApi, getHttpVersion } from "../http/platform";
import { AuthoringHttpApi } from "../http/authoring";
import { SubmissionHttpApi } from "../http/submissions";
import { MappingHttpApi } from "../http/mapping";
import { TranscriptionHttpApi } from "../http/transcription";
import { EvaluationHttpApi } from "../http/evaluation";
import { PublicationHttpApi } from "../http/publication";
import { ReportsHttpApi } from "../http/reports";
import { ApiError } from "../http/errors";
import { httpRequest } from "../http/client";
import { getApiCapabilities } from "../capabilities";

const LIVE_UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function isLiveSubmissionId(id: string): boolean {
  return LIVE_UUID_RE.test(id) && !id.toLowerCase().includes("demo");
}

function refuseMockDownstream(
  domain: "reports" | "analytics" | "learning",
  entityId: string,
): void {
  if (!isLiveSubmissionId(entityId)) return;
  const caps = getApiCapabilities();
  if (caps[domain] !== "mock") return;
  throw new ApiError({
    message: `Live ${domain} is not enabled for this identity.`,
    status: 404,
    kind: "not_found",
    code: `${domain.toUpperCase()}_NOT_LIVE`,
  });
}

/**
 * Hybrid domain routing (B7):
 * - Auth, Institution, Academic Years, Class Sections, Students, Import, Guardians → A1 HTTP
 * - Curriculum and Assessment authoring → A2 HTTP
 * - Submissions + identity review → B3 HTTP
 * - Mapping review → B4 HTTP
 * - Transcription review → B5 HTTP
 * - Evaluation ledger review → B6 HTTP
 * - Publication + reports → B7 HTTP
 * - Analytics, Learning → MOCK (refuse live UUIDs)
 *
 * Components use `api` only — they must not inspect mock vs HTTP.
 * Live publication/report errors must never silently fall back to mock.
 */
export const HybridEduVijnaApi: ApiClient = {
  async getHealth() {
    try {
      return await httpRequest<OperationalHealth>("/health", {
        anonymous: true,
      });
    } catch {
      return MockEduVijnaApi.getHealth();
    }
  },
  async getReady() {
    try {
      return await httpRequest<OperationalHealth>("/ready", {
        anonymous: true,
      });
    } catch {
      return MockEduVijnaApi.getReady();
    }
  },
  async getVersion() {
    try {
      return await getHttpVersion();
    } catch {
      return MockEduVijnaApi.getVersion();
    }
  },

  login: (email, password) => PlatformHttpApi.login(email, password),
  logout: () => PlatformHttpApi.logout(),
  getCurrentUser: () => PlatformHttpApi.getCurrentUser(),

  getInstitution: () => PlatformHttpApi.getInstitution(),
  listAcademicYears: () => PlatformHttpApi.listAcademicYears(),
  createAcademicYear: (form) => PlatformHttpApi.createAcademicYear(form),
  updateAcademicYear: (id, form) =>
    PlatformHttpApi.updateAcademicYear(id, form),
  listClassSections: () => PlatformHttpApi.listClassSections(),
  createClassSection: (form) => PlatformHttpApi.createClassSection(form),
  updateClassSection: (id, form) =>
    PlatformHttpApi.updateClassSection(id, form),

  listStudents: () => PlatformHttpApi.listStudents(),
  getStudent: (id) => PlatformHttpApi.getStudent(id),
  createStudent: (form) => PlatformHttpApi.createStudent(form),
  updateStudent: (id, form) => PlatformHttpApi.updateStudent(id, form),
  validateStudentImport: (file) => PlatformHttpApi.validateStudentImport(file),
  commitStudentImport: (id) => PlatformHttpApi.commitStudentImport(id),

  listGuardians: () => PlatformHttpApi.listGuardians(),
  listStudentGuardians: (id) => PlatformHttpApi.listStudentGuardians(id),
  getGuardian: (id) => PlatformHttpApi.getGuardian(id),
  createGuardian: (form) => PlatformHttpApi.createGuardian(form),
  updateGuardian: (id, form) => PlatformHttpApi.updateGuardian(id, form),
  linkStudentGuardian: (s, g, r) =>
    PlatformHttpApi.linkStudentGuardian(s, g, r),
  unlinkStudentGuardian: (s, g) =>
    PlatformHttpApi.unlinkStudentGuardian(s, g),

  getDashboard: (...args) => MockEduVijnaApi.getDashboard(...args),

  listCurricula: () => AuthoringHttpApi.listCurricula(),
  getCurriculum: (id) => AuthoringHttpApi.getCurriculum(id),
  listAssessments: () => AuthoringHttpApi.listAssessments(),
  getAssessment: (id) => AuthoringHttpApi.getAssessment(id),
  createAssessment: (form) => AuthoringHttpApi.createAssessment(form),
  getAssessmentQuestions: (id) => AuthoringHttpApi.getAssessmentQuestions(id),
  getAssessmentRubric: (id) => AuthoringHttpApi.getAssessmentRubric(id),
  getAssessmentAnswerKey: (id) => AuthoringHttpApi.getAssessmentAnswerKey(id),
  getAssessmentCurriculumMap: (id) =>
    AuthoringHttpApi.getAssessmentCurriculumMap(id),

  listSubmissions: () => SubmissionHttpApi.listSubmissions(),
  getSubmission: (id) => SubmissionHttpApi.getSubmission(id),
  uploadSubmission: (input) => SubmissionHttpApi.uploadSubmission(input),
  getSubmissionPageImageBlob: (pageId) =>
    SubmissionHttpApi.getSubmissionPageImageBlob(pageId),
  getIdentityReview: (id) => SubmissionHttpApi.getIdentityReview(id),
  confirmIdentity: (id, studentId) =>
    SubmissionHttpApi.confirmIdentity(id, studentId),
  markIdentityUnmatched: (id) => SubmissionHttpApi.markIdentityUnmatched(id),

  getMappingReview: (id) => MappingHttpApi.getMappingReview(id),
  applyMappingAction: async () => {
    throw new ApiError({
      message:
        "Legacy applyMappingAction is not available for live mapping. Use explicit B4 mapping methods.",
      status: 400,
      kind: "validation",
      code: "MAPPING_USE_B4_METHODS",
    });
  },
  prepareMappingReview: (id) => MappingHttpApi.prepareMappingReview(id),
  createAnswerRegion: (pageId, input) =>
    MappingHttpApi.createAnswerRegion(pageId, input),
  updateAnswerRegion: (regionId, input) =>
    MappingHttpApi.updateAnswerRegion(regionId, input),
  deleteAnswerRegion: (regionId) => MappingHttpApi.deleteAnswerRegion(regionId),
  updateSubmissionPage: (pageId, input) =>
    MappingHttpApi.updateSubmissionPage(pageId, input),
  upsertQuestionMapping: (submissionId, questionVersionId, input) =>
    MappingHttpApi.upsertQuestionMapping(
      submissionId,
      questionVersionId,
      input,
    ),
  confirmQuestionMapping: (submissionId, questionVersionId) =>
    MappingHttpApi.confirmQuestionMapping(submissionId, questionVersionId),
  finalizeMappingReview: (id) => MappingHttpApi.finalizeMappingReview(id),

  prepareTranscription: (id) => TranscriptionHttpApi.prepareTranscription(id),
  getTranscriptionWorkspace: (id) =>
    TranscriptionHttpApi.getTranscriptionWorkspace(id),
  putRegionTranscription: (regionId, payload) =>
    TranscriptionHttpApi.putRegionTranscription(regionId, payload),
  confirmTranscription: (transcriptionId) =>
    TranscriptionHttpApi.confirmTranscription(transcriptionId),
  finalizeTranscription: (id) => TranscriptionHttpApi.finalizeTranscription(id),
  getRegionCropBlob: (regionId) => TranscriptionHttpApi.getRegionCropBlob(regionId),

  prepareEvaluation: async (submissionId) => {
    if (getApiCapabilities().evaluation === "live" && isLiveSubmissionId(submissionId)) {
      return EvaluationHttpApi.prepareEvaluation(submissionId);
    }
    throw new ApiError({
      message: "prepareEvaluation is only available for live evaluation submissions.",
      status: 404,
      kind: "not_found",
      code: "EVALUATION_NOT_LIVE",
    });
  },
  getEvaluationWorkspace: async (submissionId, questionId) => {
    if (getApiCapabilities().evaluation === "live") {
      if (isLiveSubmissionId(submissionId)) {
        return EvaluationHttpApi.getEvaluationWorkspace(
          submissionId,
          questionId,
        );
      }
      // Demo / mock IDs stay on mock fixtures even when capability is live.
      return MockEduVijnaApi.getEvaluationWorkspace(submissionId, questionId);
    }
    if (isLiveSubmissionId(submissionId)) {
      throw new ApiError({
        message:
          "Live evaluation is not enabled for this submission. Complete transcription review first.",
        status: 404,
        kind: "not_found",
        code: "EVALUATION_NOT_LIVE",
      });
    }
    return MockEduVijnaApi.getEvaluationWorkspace(submissionId, questionId);
  },
  applyTeacherAction: async (submissionId, ledgerId, action, payload) => {
    if (getApiCapabilities().evaluation === "live") {
      if (isLiveSubmissionId(submissionId)) {
        return EvaluationHttpApi.applyTeacherAction(
          submissionId,
          ledgerId,
          action,
          payload,
        );
      }
      return MockEduVijnaApi.applyTeacherAction(
        submissionId,
        ledgerId,
        action,
        payload,
      );
    }
    if (isLiveSubmissionId(submissionId)) {
      throw new ApiError({
        message: "Live evaluation actions are not enabled for this submission.",
        status: 404,
        kind: "not_found",
        code: "EVALUATION_NOT_LIVE",
      });
    }
    return MockEduVijnaApi.applyTeacherAction(
      submissionId,
      ledgerId,
      action,
      payload,
    );
  },
  finalizeEvaluation: async (submissionId) => {
    if (getApiCapabilities().evaluation === "live" && isLiveSubmissionId(submissionId)) {
      return EvaluationHttpApi.finalizeEvaluation(submissionId);
    }
    throw new ApiError({
      message: "finalizeEvaluation is only available for live evaluation submissions.",
      status: 404,
      kind: "not_found",
      code: "EVALUATION_NOT_LIVE",
    });
  },

  preparePublication: async (submissionId) => {
    if (
      getApiCapabilities().publication === "live" &&
      isLiveSubmissionId(submissionId)
    ) {
      return PublicationHttpApi.preparePublication(submissionId);
    }
    throw new ApiError({
      message: "preparePublication is only available for live publication submissions.",
      status: 404,
      kind: "not_found",
      code: "PUBLICATION_NOT_LIVE",
    });
  },
  getPublicationWorkspace: async (submissionId) => {
    if (getApiCapabilities().publication === "live") {
      if (isLiveSubmissionId(submissionId)) {
        return PublicationHttpApi.getPublicationWorkspace(submissionId);
      }
    }
    if (isLiveSubmissionId(submissionId)) {
      throw new ApiError({
        message: "Live publication is not enabled for this submission.",
        status: 404,
        kind: "not_found",
        code: "PUBLICATION_NOT_LIVE",
      });
    }
    throw new ApiError({
      message: "Publication workspace is not available in mock mode.",
      status: 404,
      kind: "not_found",
      code: "PUBLICATION_MOCK_UNSUPPORTED",
    });
  },
  regeneratePublication: async (publishedResultId) => {
    if (
      getApiCapabilities().publication === "live" &&
      isLiveSubmissionId(publishedResultId)
    ) {
      return PublicationHttpApi.regeneratePublication(publishedResultId);
    }
    throw new ApiError({
      message: "regeneratePublication is only available for live publication.",
      status: 404,
      kind: "not_found",
      code: "PUBLICATION_NOT_LIVE",
    });
  },
  publishPublication: async (publishedResultId) => {
    if (
      getApiCapabilities().publication === "live" &&
      isLiveSubmissionId(publishedResultId)
    ) {
      return PublicationHttpApi.publishPublication(publishedResultId);
    }
    throw new ApiError({
      message: "publishPublication is only available for live publication.",
      status: 404,
      kind: "not_found",
      code: "PUBLICATION_NOT_LIVE",
    });
  },
  getPublicationArtifactBlob: async (publishedResultId, artifactType) => {
    if (
      getApiCapabilities().publication === "live" &&
      isLiveSubmissionId(publishedResultId)
    ) {
      return PublicationHttpApi.getPublicationArtifactBlob(
        publishedResultId,
        artifactType,
      );
    }
    throw new ApiError({
      message: "Publication artifacts are only available for live publication.",
      status: 404,
      kind: "not_found",
      code: "PUBLICATION_NOT_LIVE",
    });
  },
  createPublicationAnnotation: async (publishedResultId, input) => {
    if (
      getApiCapabilities().publication === "live" &&
      isLiveSubmissionId(publishedResultId)
    ) {
      return PublicationHttpApi.createPublicationAnnotation(
        publishedResultId,
        input,
      );
    }
    throw new ApiError({
      message: "Publication annotations are only available for live publication.",
      status: 404,
      kind: "not_found",
      code: "PUBLICATION_NOT_LIVE",
    });
  },
  previewPublicationReport: async (publishedResultId, audience) => {
    if (
      getApiCapabilities().publication === "live" &&
      isLiveSubmissionId(publishedResultId)
    ) {
      return PublicationHttpApi.previewPublicationReport(
        publishedResultId,
        audience,
      );
    }
    throw new ApiError({
      message: "Publication report preview is only available for live publication.",
      status: 404,
      kind: "not_found",
      code: "PUBLICATION_NOT_LIVE",
    });
  },
  getAnnotatedPaperWorkspace: async (submissionId) => {
    if (getApiCapabilities().publication === "live") {
      if (isLiveSubmissionId(submissionId)) {
        return PublicationHttpApi.getAnnotatedPaperWorkspace(submissionId);
      }
    }
    if (isLiveSubmissionId(submissionId)) {
      throw new ApiError({
        message: "Live annotated paper is not enabled for this submission.",
        status: 404,
        kind: "not_found",
        code: "PUBLICATION_NOT_LIVE",
      });
    }
    throw new ApiError({
      message: "Use evaluation workspace annotated paper path in mock mode.",
      status: 404,
      kind: "not_found",
      code: "ANNOTATED_PAPER_USE_MOCK_EVAL",
    });
  },

  getStudentReport: async (studentId, assessmentId) => {
    if (getApiCapabilities().reports === "live") {
      if (isLiveSubmissionId(studentId) || isLiveSubmissionId(assessmentId)) {
        return ReportsHttpApi.getStudentReport(studentId, assessmentId);
      }
      return MockEduVijnaApi.getStudentReport(studentId, assessmentId);
    }
    refuseMockDownstream("reports", studentId);
    refuseMockDownstream("reports", assessmentId);
    return MockEduVijnaApi.getStudentReport(studentId, assessmentId);
  },
  getParentReport: async (studentId, assessmentId) => {
    if (getApiCapabilities().reports === "live") {
      if (isLiveSubmissionId(studentId) || isLiveSubmissionId(assessmentId)) {
        return ReportsHttpApi.getParentReport(studentId, assessmentId);
      }
      return MockEduVijnaApi.getParentReport(studentId, assessmentId);
    }
    refuseMockDownstream("reports", studentId);
    refuseMockDownstream("reports", assessmentId);
    return MockEduVijnaApi.getParentReport(studentId, assessmentId);
  },
  getTeacherReport: async (studentId, assessmentId) => {
    if (getApiCapabilities().reports === "live") {
      if (isLiveSubmissionId(studentId) || isLiveSubmissionId(assessmentId)) {
        return ReportsHttpApi.getTeacherReport(studentId, assessmentId);
      }
    }
    throw new ApiError({
      message: "Teacher report is only available for live published results.",
      status: 404,
      kind: "not_found",
      code: "TEACHER_REPORT_NOT_LIVE",
    });
  },
  getAssessmentAnalytics: async (assessmentId) => {
    refuseMockDownstream("analytics", assessmentId);
    return MockEduVijnaApi.getAssessmentAnalytics(assessmentId);
  },
  getStudentAnalytics: async (studentId) => {
    refuseMockDownstream("analytics", studentId);
    return MockEduVijnaApi.getStudentAnalytics(studentId);
  },
  getAdaptiveLearning: async (studentId) => {
    refuseMockDownstream("learning", studentId);
    return MockEduVijnaApi.getAdaptiveLearning(studentId);
  },
  getImprovementBlueprint: async (studentId) => {
    refuseMockDownstream("learning", studentId);
    return MockEduVijnaApi.getImprovementBlueprint(studentId);
  },
  approveImprovementBlueprint: (...args) =>
    MockEduVijnaApi.approveImprovementBlueprint(...args),
};
