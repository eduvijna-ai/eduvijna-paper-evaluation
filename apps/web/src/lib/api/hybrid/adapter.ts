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
import { AnalyticsHttpApi } from "../http/analytics";
import { LearningHttpApi } from "../http/learning";
import { ResourcesHttpApi } from "../http/resources";
import { ApiError } from "../http/errors";
import { httpRequest } from "../http/client";
import { getApiCapabilities } from "../capabilities";

const LIVE_UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function isLiveSubmissionId(id: string): boolean {
  return LIVE_UUID_RE.test(id) && !id.toLowerCase().includes("demo");
}

function b13MockDemoOnly(message: string): never {
  throw new ApiError({
    message,
    status: 404,
    kind: "not_found",
    code: "B13_MOCK_DEMO_ONLY",
  });
}

/**
 * Hybrid domain routing (B9):
 * - Auth, Institution, Academic Years, Class Sections, Students, Import, Guardians → A1 HTTP
 * - Curriculum and Assessment authoring → A2 HTTP
 * - Submissions + identity review → B3 HTTP
 * - Mapping review → B4 HTTP
 * - Transcription review → B5 HTTP
 * - Evaluation ledger review → B6 HTTP
 * - Publication + reports → B7 HTTP
 * - Analytics → B8 HTTP (+ B12 longitudinal when live)
 * - Learning + improvement blueprints → B9 HTTP
 * - Curriculum resources + assignments → B13 HTTP (mock demo fixtures only when learning is mock)
 *
 * Components use `api` only — they must not inspect mock vs HTTP.
 * Live learning errors must never silently fall back to mock.
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
  getLatestAssessmentVersion: (id) =>
    AuthoringHttpApi.getLatestAssessmentVersion(id),
  uploadQuestionPaper: (versionId, file) =>
    AuthoringHttpApi.uploadQuestionPaper(versionId, file),
  prepareQuestionPaperParse: (versionId) =>
    AuthoringHttpApi.prepareQuestionPaperParse(versionId),
  getLatestAuthoringAiRun: (versionId, operation) =>
    AuthoringHttpApi.getLatestAuthoringAiRun(versionId, operation),
  getAssessmentArtifact: (artifactId) =>
    AuthoringHttpApi.getAssessmentArtifact(artifactId),
  getAuthoringAiRun: (runId) => AuthoringHttpApi.getAuthoringAiRun(runId),
  updateQuestionTreeProposal: (runId, tree) =>
    AuthoringHttpApi.updateQuestionTreeProposal(runId, tree),
  applyQuestionTreeProposal: (runId) =>
    AuthoringHttpApi.applyQuestionTreeProposal(runId),
  createTeacherAnswerKey: (input) =>
    AuthoringHttpApi.createTeacherAnswerKey(input),
  updateAnswerKey: (id, patch) => AuthoringHttpApi.updateAnswerKey(id, patch),
  approveAnswerKey: (id) => AuthoringHttpApi.approveAnswerKey(id),
  prepareAiAnswerKeyProposal: (input) =>
    AuthoringHttpApi.prepareAiAnswerKeyProposal(input),
  createTeacherRubric: (input) => AuthoringHttpApi.createTeacherRubric(input),
  updateRubric: (id, patch) => AuthoringHttpApi.updateRubric(id, patch),
  approveRubric: (id) => AuthoringHttpApi.approveRubric(id),
  prepareAiRubricProposal: (input) =>
    AuthoringHttpApi.prepareAiRubricProposal(input),
  prepareAiCurriculumMappingProposal: (input) =>
    AuthoringHttpApi.prepareAiCurriculumMappingProposal(input),
  updateCurriculumMappingProposal: (runId, mappings) =>
    AuthoringHttpApi.updateCurriculumMappingProposal(runId, mappings),
  applyCurriculumMappings: (runId, selectedIndices) =>
    AuthoringHttpApi.applyCurriculumMappings(runId, selectedIndices),
  transitionAssessment: async (assessmentId, toStatus) => {
    const row = await AuthoringHttpApi.transitionAssessment(
      assessmentId,
      toStatus,
    );
    return AuthoringHttpApi.getAssessment(row.id);
  },

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
    if (isLiveSubmissionId(studentId) || isLiveSubmissionId(assessmentId)) {
      throw new ApiError({
        message: "Live reports are not enabled for this identity.",
        status: 404,
        kind: "not_found",
        code: "REPORTS_NOT_LIVE",
      });
    }
    return MockEduVijnaApi.getStudentReport(studentId, assessmentId);
  },
  getParentReport: async (studentId, assessmentId) => {
    if (getApiCapabilities().reports === "live") {
      if (isLiveSubmissionId(studentId) || isLiveSubmissionId(assessmentId)) {
        return ReportsHttpApi.getParentReport(studentId, assessmentId);
      }
      return MockEduVijnaApi.getParentReport(studentId, assessmentId);
    }
    if (isLiveSubmissionId(studentId) || isLiveSubmissionId(assessmentId)) {
      throw new ApiError({
        message: "Live reports are not enabled for this identity.",
        status: 404,
        kind: "not_found",
        code: "REPORTS_NOT_LIVE",
      });
    }
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
  getAssessmentAnalytics: async (assessmentId, options) => {
    if (getApiCapabilities().analytics === "live") {
      return AnalyticsHttpApi.getAssessmentAnalytics(assessmentId, options);
    }
    return MockEduVijnaApi.getAssessmentAnalytics(assessmentId);
  },
  getStudentAnalytics: async (studentId) => {
    if (getApiCapabilities().analytics === "live") {
      return AnalyticsHttpApi.getStudentAnalytics(studentId);
    }
    return MockEduVijnaApi.getStudentAnalytics(studentId);
  },
  getStudentMasteryEvidence: async (studentId, filters) => {
    if (getApiCapabilities().analytics === "live") {
      return AnalyticsHttpApi.getStudentMasteryEvidence(studentId, filters);
    }
    throw new ApiError({
      message: "Mastery evidence is only available for live analytics.",
      status: 404,
      kind: "not_found",
      code: "ANALYTICS_NOT_LIVE",
    });
  },
  prepareAnalyticsMaterialization: async (publishedResultId) => {
    if (getApiCapabilities().analytics === "live") {
      return AnalyticsHttpApi.prepareAnalyticsMaterialization(
        publishedResultId,
      );
    }
    throw new ApiError({
      message: "Analytics materialization is only available for live analytics.",
      status: 404,
      kind: "not_found",
      code: "ANALYTICS_NOT_LIVE",
    });
  },
  getStudentMasteryState: async (studentId) => {
    if (getApiCapabilities().analytics === "live") {
      return AnalyticsHttpApi.getStudentMasteryState(studentId);
    }
    if (isLiveSubmissionId(studentId)) {
      throw new ApiError({
        message: "B12 longitudinal mastery is not available for live student IDs in mock mode.",
        status: 404,
        kind: "not_found",
        code: "B12_MOCK_DEMO_ONLY",
      });
    }
    return MockEduVijnaApi.getStudentMasteryState(studentId);
  },
  getStudentMasteryTrend: async (studentId, options) => {
    if (getApiCapabilities().analytics === "live") {
      return AnalyticsHttpApi.getStudentMasteryTrend(studentId, options);
    }
    if (isLiveSubmissionId(studentId)) {
      throw new ApiError({
        message: "B12 mastery trend is not available for live student IDs in mock mode.",
        status: 404,
        kind: "not_found",
        code: "B12_MOCK_DEMO_ONLY",
      });
    }
    return MockEduVijnaApi.getStudentMasteryTrend(studentId, options);
  },
  getStudentRepeatedErrors: async (studentId) => {
    if (getApiCapabilities().analytics === "live") {
      return AnalyticsHttpApi.getStudentRepeatedErrors(studentId);
    }
    if (isLiveSubmissionId(studentId)) {
      throw new ApiError({
        message: "B12 repeated errors are not available for live student IDs in mock mode.",
        status: 404,
        kind: "not_found",
        code: "B12_MOCK_DEMO_ONLY",
      });
    }
    return MockEduVijnaApi.getStudentRepeatedErrors(studentId);
  },
  getStudentRecoverableMarks: async (studentId) => {
    if (getApiCapabilities().analytics === "live") {
      return AnalyticsHttpApi.getStudentRecoverableMarks(studentId);
    }
    if (isLiveSubmissionId(studentId)) {
      throw new ApiError({
        message: "B12 recoverable marks are not available for live student IDs in mock mode.",
        status: 404,
        kind: "not_found",
        code: "B12_MOCK_DEMO_ONLY",
      });
    }
    return MockEduVijnaApi.getStudentRecoverableMarks(studentId);
  },
  getStudentMistakeNotebook: async (studentId) => {
    if (getApiCapabilities().analytics === "live") {
      return AnalyticsHttpApi.getStudentMistakeNotebook(studentId);
    }
    if (isLiveSubmissionId(studentId)) {
      throw new ApiError({
        message: "B12 mistake notebook is not available for live student IDs in mock mode.",
        status: 404,
        kind: "not_found",
        code: "B12_MOCK_DEMO_ONLY",
      });
    }
    return MockEduVijnaApi.getStudentMistakeNotebook(studentId);
  },
  rebuildStudentB12: async (studentId) => {
    if (getApiCapabilities().analytics === "live") {
      return AnalyticsHttpApi.rebuildStudentB12(studentId);
    }
    throw new ApiError({
      message: "B12 rebuild is only available for live analytics.",
      status: 404,
      kind: "not_found",
      code: "ANALYTICS_NOT_LIVE",
    });
  },
  getAdaptiveLearning: async (studentId) => {
    if (getApiCapabilities().learning === "live") {
      throw new ApiError({
        message:
          "Use getLearningWorkspace for live learning. Mock adaptive learning is unavailable when learning is live.",
        status: 404,
        kind: "not_found",
        code: "LEARNING_USE_LIVE_WORKSPACE",
      });
    }
    return MockEduVijnaApi.getAdaptiveLearning(studentId);
  },
  getLearningWorkspace: async (studentId, curriculumId) => {
    if (getApiCapabilities().learning === "live") {
      return LearningHttpApi.getLearningWorkspace(studentId, curriculumId);
    }
    throw new ApiError({
      message: "Live learning workspace is only available when learning is live.",
      status: 404,
      kind: "not_found",
      code: "LEARNING_NOT_LIVE",
    });
  },
  prepareLearningPlan: async (studentId, curriculumId) => {
    if (getApiCapabilities().learning === "live") {
      return LearningHttpApi.prepareLearningPlan(studentId, curriculumId);
    }
    throw new ApiError({
      message: "prepareLearningPlan is only available for live learning.",
      status: 404,
      kind: "not_found",
      code: "LEARNING_NOT_LIVE",
    });
  },
  getLearningPlanRun: async (runId) => {
    if (getApiCapabilities().learning === "live") {
      return LearningHttpApi.getLearningPlanRun(runId);
    }
    throw new ApiError({
      message: "getLearningPlanRun is only available for live learning.",
      status: 404,
      kind: "not_found",
      code: "LEARNING_NOT_LIVE",
    });
  },
  prepareImprovementBlueprint: async (runId) => {
    if (getApiCapabilities().learning === "live") {
      return LearningHttpApi.prepareImprovementBlueprint(runId);
    }
    throw new ApiError({
      message:
        "prepareImprovementBlueprint is only available for live learning.",
      status: 404,
      kind: "not_found",
      code: "LEARNING_NOT_LIVE",
    });
  },
  getImprovementAssessment: async (id) => {
    if (getApiCapabilities().learning === "live") {
      return LearningHttpApi.getImprovementAssessment(id);
    }
    throw new ApiError({
      message: "getImprovementAssessment is only available for live learning.",
      status: 404,
      kind: "not_found",
      code: "LEARNING_NOT_LIVE",
    });
  },
  getImprovementBlueprint: async (studentId) => {
    if (getApiCapabilities().learning === "live") {
      throw new ApiError({
        message:
          "Use getImprovementAssessment / learning workspace for live blueprints.",
        status: 404,
        kind: "not_found",
        code: "LEARNING_USE_LIVE_BLUEPRINT",
      });
    }
    return MockEduVijnaApi.getImprovementBlueprint(studentId);
  },
  approveImprovementBlueprint: async (blueprintId) => {
    if (getApiCapabilities().learning === "live") {
      return LearningHttpApi.approveImprovementBlueprint(blueprintId);
    }
    return MockEduVijnaApi.approveImprovementBlueprint(blueprintId);
  },
  rejectImprovementBlueprint: async (blueprintId, reason) => {
    if (getApiCapabilities().learning === "live") {
      return LearningHttpApi.rejectImprovementBlueprint(blueprintId, reason);
    }
    throw new ApiError({
      message: "rejectImprovementBlueprint is only available for live learning.",
      status: 404,
      kind: "not_found",
      code: "LEARNING_NOT_LIVE",
    });
  },

  listCurriculumResources: async (filters) => {
    if (getApiCapabilities().learning === "live") {
      return ResourcesHttpApi.listCurriculumResources(filters);
    }
    return MockEduVijnaApi.listCurriculumResources!(filters);
  },
  getCurriculumResource: async (id) => {
    if (getApiCapabilities().learning === "live") {
      return ResourcesHttpApi.getCurriculumResource(id);
    }
    if (isLiveSubmissionId(id)) {
      b13MockDemoOnly(
        "B13 curriculum resources are not available for live IDs in mock mode.",
      );
    }
    return MockEduVijnaApi.getCurriculumResource!(id);
  },
  createCurriculumResource: async (input) => {
    if (getApiCapabilities().learning === "live") {
      return ResourcesHttpApi.createCurriculumResource(input);
    }
    if (isLiveSubmissionId(input.curriculum_id)) {
      b13MockDemoOnly(
        "B13 create is not available for live curriculum IDs in mock mode.",
      );
    }
    return MockEduVijnaApi.createCurriculumResource!(input);
  },
  updateCurriculumResource: async (id, input) => {
    if (getApiCapabilities().learning === "live") {
      return ResourcesHttpApi.updateCurriculumResource(id, input);
    }
    if (isLiveSubmissionId(id)) {
      b13MockDemoOnly(
        "B13 update is not available for live resource IDs in mock mode.",
      );
    }
    return MockEduVijnaApi.updateCurriculumResource!(id, input);
  },
  approveCurriculumResource: async (id) => {
    if (getApiCapabilities().learning === "live") {
      return ResourcesHttpApi.approveCurriculumResource(id);
    }
    if (isLiveSubmissionId(id)) {
      b13MockDemoOnly(
        "B13 approve is not available for live resource IDs in mock mode.",
      );
    }
    return MockEduVijnaApi.approveCurriculumResource!(id);
  },
  activateCurriculumResource: async (id) => {
    if (getApiCapabilities().learning === "live") {
      return ResourcesHttpApi.activateCurriculumResource(id);
    }
    if (isLiveSubmissionId(id)) {
      b13MockDemoOnly(
        "B13 activate is not available for live resource IDs in mock mode.",
      );
    }
    return MockEduVijnaApi.activateCurriculumResource!(id);
  },
  deactivateCurriculumResource: async (id) => {
    if (getApiCapabilities().learning === "live") {
      return ResourcesHttpApi.deactivateCurriculumResource(id);
    }
    if (isLiveSubmissionId(id)) {
      b13MockDemoOnly(
        "B13 deactivate is not available for live resource IDs in mock mode.",
      );
    }
    return MockEduVijnaApi.deactivateCurriculumResource!(id);
  },
  replaceCurriculumResourceNodes: async (id, nodeIds) => {
    if (getApiCapabilities().learning === "live") {
      return ResourcesHttpApi.replaceCurriculumResourceNodes(id, nodeIds);
    }
    if (isLiveSubmissionId(id)) {
      b13MockDemoOnly(
        "B13 node replace is not available for live resource IDs in mock mode.",
      );
    }
    return MockEduVijnaApi.replaceCurriculumResourceNodes!(id, nodeIds);
  },
  listStudentResourceAssignments: async (studentId, filters) => {
    if (getApiCapabilities().learning === "live") {
      return ResourcesHttpApi.listStudentResourceAssignments(studentId, filters);
    }
    if (isLiveSubmissionId(studentId)) {
      b13MockDemoOnly(
        "B13 assignments are not available for live student IDs in mock mode.",
      );
    }
    return MockEduVijnaApi.listStudentResourceAssignments!(studentId, filters);
  },
  assignStudentResource: async (studentId, input) => {
    if (getApiCapabilities().learning === "live") {
      return ResourcesHttpApi.assignStudentResource(studentId, input);
    }
    if (isLiveSubmissionId(studentId) || isLiveSubmissionId(input.resource_id)) {
      b13MockDemoOnly(
        "B13 assign is not available for live IDs in mock mode.",
      );
    }
    return MockEduVijnaApi.assignStudentResource!(studentId, input);
  },
  cancelStudentResourceAssignment: async (assignmentId) => {
    if (getApiCapabilities().learning === "live") {
      return ResourcesHttpApi.cancelStudentResourceAssignment(assignmentId);
    }
    if (isLiveSubmissionId(assignmentId)) {
      b13MockDemoOnly(
        "B13 cancel is not available for live assignment IDs in mock mode.",
      );
    }
    return MockEduVijnaApi.cancelStudentResourceAssignment!(assignmentId);
  },
};
