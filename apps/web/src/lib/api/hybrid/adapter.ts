import type { ApiClient, OperationalHealth } from "../types";
import { MockEduVijnaApi } from "../mock/adapter";
import { PlatformHttpApi, getHttpVersion } from "../http/platform";
import { AuthoringHttpApi } from "../http/authoring";
import { SubmissionHttpApi } from "../http/submissions";
import { MappingHttpApi } from "../http/mapping";
import { TranscriptionHttpApi } from "../http/transcription";
import { ApiError } from "../http/errors";
import { httpRequest } from "../http/client";
import { getApiCapabilities } from "../capabilities";

const LIVE_UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function isLiveSubmissionId(id: string): boolean {
  return LIVE_UUID_RE.test(id) && !id.toLowerCase().includes("demo");
}

/**
 * Hybrid domain routing (B4):
 * - Auth, Institution, Academic Years, Class Sections, Students, Import, Guardians → A1 HTTP
 * - Curriculum and Assessment authoring → A2 HTTP
 * - Submissions + identity review → B3 HTTP
 * - Mapping review → B4 HTTP
 * - Transcription review → B5 HTTP
 * - Evaluation, Analytics, Reporting, Learning → MOCK until their backend phases land
 *
 * Components use `api` only — they must not inspect mock vs HTTP.
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

  getEvaluationWorkspace: async (submissionId, ...args) => {
    if (
      getApiCapabilities().submissions === "live" &&
      isLiveSubmissionId(submissionId)
    ) {
      throw new ApiError({
        message:
          "Live evaluation is not enabled for this submission. Complete transcription review first.",
        status: 404,
        kind: "not_found",
        code: "EVALUATION_NOT_LIVE",
      });
    }
    return MockEduVijnaApi.getEvaluationWorkspace(submissionId, ...args);
  },
  applyTeacherAction: async (submissionId, ...args) => {
    if (
      getApiCapabilities().submissions === "live" &&
      isLiveSubmissionId(submissionId)
    ) {
      throw new ApiError({
        message: "Live evaluation actions are not enabled for this submission.",
        status: 404,
        kind: "not_found",
        code: "EVALUATION_NOT_LIVE",
      });
    }
    return MockEduVijnaApi.applyTeacherAction(submissionId, ...args);
  },
  getStudentReport: (...args) => MockEduVijnaApi.getStudentReport(...args),
  getParentReport: (...args) => MockEduVijnaApi.getParentReport(...args),
  getAssessmentAnalytics: (...args) =>
    MockEduVijnaApi.getAssessmentAnalytics(...args),
  getStudentAnalytics: (...args) =>
    MockEduVijnaApi.getStudentAnalytics(...args),
  getAdaptiveLearning: (...args) =>
    MockEduVijnaApi.getAdaptiveLearning(...args),
  getImprovementBlueprint: (...args) =>
    MockEduVijnaApi.getImprovementBlueprint(...args),
  approveImprovementBlueprint: (...args) =>
    MockEduVijnaApi.approveImprovementBlueprint(...args),
};
