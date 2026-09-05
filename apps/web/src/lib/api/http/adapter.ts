import type { ApiClient, OperationalHealth } from "../types";
import type {
  A1Student,
  AcademicYear,
  ClassSection,
  Guardian,
  Institution,
  LoginRequest,
  TokenResponse,
  A1User,
  VersionResponse,
  ImportValidation,
} from "../a1-types";

// A1 StatusResponse available via OpenAPI /health|/ready — kept in a1-types for B1.

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ??
  "http://localhost:8000";

async function fetchJson<T>(
  path: string,
  init?: RequestInit & { token?: string },
): Promise<T> {
  const headers = new Headers(init?.headers);
  headers.set("Accept", "application/json");
  if (init?.token) {
    headers.set("Authorization", `Bearer ${init.token}`);
  }
  if (init?.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const { token: _token, ...rest } = init ?? {};
  void _token;
  const res = await fetch(`${API_BASE}${path}`, { ...rest, headers });
  if (!res.ok) {
    throw new Error(`HTTP ${res.status} for ${path}`);
  }
  if (res.status === 204) {
    return undefined as T;
  }
  return res.json() as Promise<T>;
}

function notImplemented(method: string, phase = "A2+"): never {
  throw new Error(
    `HttpEduVijnaApi.${method} is not wired for B0 — domain contract pending (${phase}). MockEduVijnaApi remains active. See docs/engineering/FRONTEND_CONTRACT_REQUESTS.md`,
  );
}

/**
 * HTTP adapter.
 * - Operational + A1 platform paths are typed and callable for B1 prep.
 * - CVB evaluation/assessment/submission domain methods still throw (OPEN_FOR_A2+).
 * - Active UI adapter for B0 remains MockEduVijnaApi via NEXT_PUBLIC_API_MODE=mock.
 */
export const HttpEduVijnaApi: ApiClient & {
  /** A1 platform helpers — for B1 auth/roster integration only */
  a1: {
    login(body: LoginRequest): Promise<TokenResponse>;
    me(token: string): Promise<A1User>;
    getInstitution(token: string): Promise<Institution>;
    listAcademicYears(token: string): Promise<AcademicYear[]>;
    listClassSections(token: string): Promise<ClassSection[]>;
    listStudents(token: string): Promise<A1Student[]>;
    getStudent(token: string, id: string): Promise<A1Student>;
    validateStudentImport(token: string, file: Blob): Promise<ImportValidation>;
    commitStudentImport(
      token: string,
      importSessionId: string,
    ): Promise<Record<string, unknown>>;
    listGuardians(token: string): Promise<Guardian[]>;
  };
} = {
  async getHealth() {
    return fetchJson<OperationalHealth>("/health");
  },
  async getReady() {
    return fetchJson<OperationalHealth>("/ready");
  },
  async getVersion() {
    const v = await fetchJson<VersionResponse>("/api/v1/system/version");
    return { version: v.api_version, build: v.git_sha };
  },

  a1: {
    login: (body) =>
      fetchJson<TokenResponse>("/api/v1/auth/login", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    me: (token) => fetchJson<A1User>("/api/v1/auth/me", { token }),
    getInstitution: (token) =>
      fetchJson<Institution>("/api/v1/institution", { token }),
    listAcademicYears: (token) =>
      fetchJson<AcademicYear[]>("/api/v1/academic-years", { token }),
    listClassSections: (token) =>
      fetchJson<ClassSection[]>("/api/v1/class-sections", { token }),
    listStudents: (token) =>
      fetchJson<A1Student[]>("/api/v1/students", { token }),
    getStudent: (token, id) =>
      fetchJson<A1Student>(`/api/v1/students/${id}`, { token }),
    validateStudentImport: async (token, file) => {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(`${API_BASE}/api/v1/students/import/validate`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, Accept: "application/json" },
        body: form,
      });
      if (!res.ok) throw new Error(`HTTP ${res.status} for import validate`);
      return res.json() as Promise<ImportValidation>;
    },
    commitStudentImport: (token, importSessionId) =>
      fetchJson<Record<string, unknown>>("/api/v1/students/import/commit", {
        method: "POST",
        token,
        body: JSON.stringify({ import_session_id: importSessionId }),
      }),
    listGuardians: (token) =>
      fetchJson<Guardian[]>("/api/v1/guardians", { token }),
  },

  getDashboard: () => notImplemented("getDashboard", "A2"),
  listCurricula: () => notImplemented("listCurricula", "A2"),
  getCurriculum: () => notImplemented("getCurriculum", "A2"),
  // A1 has students — mapping into CVB Student DTO is B1 work; ApiClient still throws in http mode
  listStudents: () => notImplemented("listStudents", "B1 (map A1 Student → UI)"),
  getStudent: () => notImplemented("getStudent", "B1 (map A1 Student → UI)"),
  listAssessments: () => notImplemented("listAssessments", "A2"),
  getAssessment: () => notImplemented("getAssessment", "A2"),
  getAssessmentQuestions: () => notImplemented("getAssessmentQuestions", "A2"),
  getAssessmentRubric: () => notImplemented("getAssessmentRubric", "A2"),
  getAssessmentAnswerKey: () => notImplemented("getAssessmentAnswerKey", "A2"),
  getAssessmentCurriculumMap: () =>
    notImplemented("getAssessmentCurriculumMap", "A2"),
  listSubmissions: () => notImplemented("listSubmissions", "INGESTION"),
  getSubmission: () => notImplemented("getSubmission", "INGESTION"),
  getIdentityReview: () => notImplemented("getIdentityReview", "INGESTION"),
  confirmIdentity: () => notImplemented("confirmIdentity", "INGESTION"),
  markIdentityUnmatched: () =>
    notImplemented("markIdentityUnmatched", "INGESTION"),
  getMappingReview: () => notImplemented("getMappingReview", "INGESTION"),
  applyMappingAction: () => notImplemented("applyMappingAction", "INGESTION"),
  getEvaluationWorkspace: () =>
    notImplemented("getEvaluationWorkspace", "EVALUATION"),
  applyTeacherAction: () => notImplemented("applyTeacherAction", "EVALUATION"),
  getStudentReport: () => notImplemented("getStudentReport", "REPORTING"),
  getParentReport: () => notImplemented("getParentReport", "REPORTING"),
  getAssessmentAnalytics: () =>
    notImplemented("getAssessmentAnalytics", "REPORTING"),
  getStudentAnalytics: () => notImplemented("getStudentAnalytics", "REPORTING"),
  getAdaptiveLearning: () => notImplemented("getAdaptiveLearning", "LEARNING"),
  getImprovementBlueprint: () =>
    notImplemented("getImprovementBlueprint", "LEARNING"),
  approveImprovementBlueprint: () =>
    notImplemented("approveImprovementBlueprint", "LEARNING"),
};
