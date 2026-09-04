import type { ApiClient, OperationalHealth } from "../types";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ??
  "http://localhost:8000";

async function fetchJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { Accept: "application/json" },
  });
  if (!res.ok) {
    throw new Error(`HTTP ${res.status} for ${path}`);
  }
  return res.json() as Promise<T>;
}

function notImplemented(method: string): never {
  throw new Error(
    `HttpEduVijnaApi.${method} is not implemented — domain OpenAPI endpoints are not yet available. See docs/engineering/FRONTEND_CONTRACT_REQUESTS.md`,
  );
}

/**
 * HTTP adapter shell.
 * Implements OpenAPI operational endpoints (health / ready / version).
 * Domain methods throw until contracts land.
 */
export const HttpEduVijnaApi: ApiClient = {
  async getHealth() {
    return fetchJson<OperationalHealth>("/health");
  },
  async getReady() {
    return fetchJson<OperationalHealth>("/ready");
  },
  async getVersion() {
    return fetchJson<{ version: string; build?: string }>("/version");
  },
  getDashboard: () => notImplemented("getDashboard"),
  listCurricula: () => notImplemented("listCurricula"),
  getCurriculum: () => notImplemented("getCurriculum"),
  listStudents: () => notImplemented("listStudents"),
  getStudent: () => notImplemented("getStudent"),
  listAssessments: () => notImplemented("listAssessments"),
  getAssessment: () => notImplemented("getAssessment"),
  getAssessmentQuestions: () => notImplemented("getAssessmentQuestions"),
  getAssessmentRubric: () => notImplemented("getAssessmentRubric"),
  getAssessmentAnswerKey: () => notImplemented("getAssessmentAnswerKey"),
  getAssessmentCurriculumMap: () =>
    notImplemented("getAssessmentCurriculumMap"),
  listSubmissions: () => notImplemented("listSubmissions"),
  getSubmission: () => notImplemented("getSubmission"),
  getIdentityReview: () => notImplemented("getIdentityReview"),
  confirmIdentity: () => notImplemented("confirmIdentity"),
  markIdentityUnmatched: () => notImplemented("markIdentityUnmatched"),
  getMappingReview: () => notImplemented("getMappingReview"),
  applyMappingAction: () => notImplemented("applyMappingAction"),
  getEvaluationWorkspace: () => notImplemented("getEvaluationWorkspace"),
  applyTeacherAction: () => notImplemented("applyTeacherAction"),
  getStudentReport: () => notImplemented("getStudentReport"),
  getParentReport: () => notImplemented("getParentReport"),
  getAssessmentAnalytics: () => notImplemented("getAssessmentAnalytics"),
  getStudentAnalytics: () => notImplemented("getStudentAnalytics"),
  getAdaptiveLearning: () => notImplemented("getAdaptiveLearning"),
  getImprovementBlueprint: () => notImplemented("getImprovementBlueprint"),
  approveImprovementBlueprint: () =>
    notImplemented("approveImprovementBlueprint"),
};
