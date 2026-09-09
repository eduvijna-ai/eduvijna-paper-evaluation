import { applyTeacherReviewAction } from "@/lib/helpers/teacher-actions";
import type { MappingAction, TeacherReviewAction } from "@/lib/types/enums";
import type { ApiClient } from "../types";
import type { AuthSession, Student } from "@/lib/types/domain";
import { clearSession, getSession, loginAs } from "@/lib/auth/session";
import { ApiError } from "../http/errors";
import type {
  AcademicYearFormValues,
  AcademicYearView,
  ClassSectionFormValues,
  ClassSectionView,
  InstitutionView,
} from "../mappers/platform";
import type { GuardianFormValues, GuardianView } from "../mappers/guardian";
import type { StudentFormValues } from "../mappers/student";
import { studentFormToApi } from "../mappers/student";
import type {
  ImportCommitResult,
  ImportValidationView,
} from "../mappers/import";
import {
  answerKeys,
  assessments,
  buildCurriculumTree,
  buildQuestionTree,
  curricula,
  getAdaptiveLearning,
  getAssessmentAnalytics,
  getAssessmentCurriculumMap,
  getDashboardSummary,
  getEvaluationWorkspace,
  getIdentityReview,
  getImprovementBlueprint,
  getMappingReview,
  getTranscriptionWorkspace,
  getParentReport,
  getStudentAnalytics,
  getStudentMasteryState,
  getStudentMasteryTrend,
  getStudentMistakeNotebook,
  getStudentRecoverableMarks,
  getStudentRepeatedErrors,
  getStudentReport,
  listCurriculumResources,
  getCurriculumResource,
  createCurriculumResource,
  updateCurriculumResource,
  approveCurriculumResource,
  activateCurriculumResource,
  deactivateCurriculumResource,
  replaceCurriculumResourceNodes,
  listStudentResourceAssignments,
  assignStudentResource,
  cancelStudentResourceAssignment,
  getReassessment,
  instantiateReassessment,
  rebuildReassessmentB14,
  listStudentReassessments,
  listBenchmarkDatasets,
  getBenchmarkDataset,
  createBenchmarkDataset,
  listBenchmarkVersions,
  createBenchmarkVersion,
  getBenchmarkVersion,
  listBenchmarkEligibleSources,
  listBenchmarkCases,
  addBenchmarkCase,
  removeBenchmarkCase,
  lockBenchmarkVersion,
  listBenchmarkRegressionRuns,
  startBenchmarkRegressionRun,
  getBenchmarkRegressionRun,
  listBenchmarkRegressionCaseResults,
  getBenchmarkGateVerdict,
  MockNotFoundError,
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

async function mockCall<T>(fn: () => T): Promise<T> {
  try {
    return await delay(fn());
  } catch (err) {
    if (err instanceof MockNotFoundError) {
      throw new ApiError({
        message: err.message,
        status: 404,
        kind: "not_found",
        code: "MOCK_NOT_FOUND",
      });
    }
    throw err;
  }
}

const mockYears: AcademicYearView[] = [
  {
    id: "year-demo-001",
    name: "2026-27",
    startsOn: "2026-04-01",
    endsOn: "2027-03-31",
    isCurrent: true,
    institutionId: "inst-demo-001",
  },
];

const mockSections: ClassSectionView[] = [
  {
    id: "section-demo-001",
    name: "A",
    gradeLabel: "Grade 10",
    academicYearId: "year-demo-001",
    academicYearName: "2026-27",
  },
];

const mockGuardians: GuardianView[] = [
  {
    id: "guardian-demo-001",
    tenantId: "tenant-demo-001",
    displayName: "Demo Guardian",
    email: "guardian@demo.eduvijna.local",
    phone: null,
  },
];

const mockLinks = new Set<string>();
let mockStudentStore: Student[] = [...students];

/** Active mock adapter — all domains against synthetic fixtures (B0 E2E). */
export const MockEduVijnaApi: ApiClient = {
  async getHealth() {
    return delay({ status: "ok" as const, service: "web-mock" });
  },
  async getReady() {
    return delay({ status: "ok" as const, service: "web-mock" });
  },
  async getVersion() {
    return delay({ version: "0.1.0-cvb", build: "mock" });
  },

  async login(email, _password) {
    void _password;
    const role =
      email.includes("admin")
        ? ("PLATFORM_ADMIN" as const)
        : email.includes("parent")
          ? ("PARENT" as const)
          : email.includes("student")
            ? ("STUDENT" as const)
            : ("TEACHER" as const);
    return delay(loginAs(role));
  },
  async logout() {
    clearSession();
  },
  async getCurrentUser() {
    const session = getSession();
    if (!session) throw new Error("Not authenticated");
    return delay(session);
  },

  async getInstitution(): Promise<InstitutionView> {
    return delay({
      id: "inst-demo-001",
      code: "DEMO",
      name: "Demo Institution",
      tenantId: "tenant-demo-001",
    });
  },
  async listAcademicYears() {
    return delay([...mockYears]);
  },
  async createAcademicYear(form: AcademicYearFormValues) {
    const row: AcademicYearView = {
      id: `year-${crypto.randomUUID().slice(0, 8)}`,
      name: form.name,
      startsOn: form.startsOn,
      endsOn: form.endsOn,
      isCurrent: form.isCurrent ?? false,
      institutionId: "inst-demo-001",
    };
    mockYears.push(row);
    return delay(row);
  },
  async updateAcademicYear(id, form) {
    const row = mockYears.find((y) => y.id === id);
    if (!row) throw new Error("Academic year not found");
    Object.assign(row, {
      name: form.name ?? row.name,
      startsOn: form.startsOn ?? row.startsOn,
      endsOn: form.endsOn ?? row.endsOn,
      isCurrent: form.isCurrent ?? row.isCurrent,
    });
    return delay({ ...row });
  },
  async listClassSections() {
    return delay([...mockSections]);
  },
  async createClassSection(form: ClassSectionFormValues) {
    const year = mockYears.find((y) => y.id === form.academicYearId);
    const row: ClassSectionView = {
      id: `section-${crypto.randomUUID().slice(0, 8)}`,
      name: form.name,
      gradeLabel: form.gradeLabel,
      academicYearId: form.academicYearId,
      academicYearName: year?.name,
    };
    mockSections.push(row);
    return delay(row);
  },
  async updateClassSection(id, form) {
    const row = mockSections.find((s) => s.id === id);
    if (!row) throw new Error("Class section not found");
    Object.assign(row, {
      name: form.name ?? row.name,
      gradeLabel: form.gradeLabel ?? row.gradeLabel,
      academicYearId: form.academicYearId ?? row.academicYearId,
    });
    return delay({ ...row });
  },

  async listStudents() {
    return delay([...mockStudentStore]);
  },
  async getStudent(id) {
    const student = mockStudentStore.find((s) => s.id === id);
    if (!student) throw new Error(`Student not found: ${id}`);
    return delay(student);
  },
  async createStudent(form: StudentFormValues) {
    const api = studentFormToApi(form);
    const section = mockSections.find((s) => s.id === form.classSectionId);
    const student: Student = {
      id: `student-${crypto.randomUUID().slice(0, 8)}`,
      tenant_id: "tenant-demo-001",
      institution_id: "inst-demo-001",
      class_section_id: form.classSectionId ?? "",
      external_ref: api.roll_number || api.student_code,
      student_code: api.student_code,
      first_name: api.full_name.split(" ")[0] ?? api.full_name,
      last_name: api.full_name.split(" ").slice(1).join(" "),
      display_name: api.full_name,
      grade: section?.gradeLabel ?? "—",
      section: section?.name ?? "—",
      status: "ACTIVE",
      academic_year_id: form.academicYearId ?? null,
      admission_number: api.admission_number ?? null,
      roll_number: api.roll_number ?? null,
    };
    mockStudentStore = [...mockStudentStore, student];
    return delay(student);
  },
  async updateStudent(id, form) {
    const current = mockStudentStore.find((s) => s.id === id);
    if (!current) throw new Error(`Student not found: ${id}`);
    const section = mockSections.find(
      (s) => s.id === (form.classSectionId ?? current.class_section_id),
    );
    const fullName = form.fullName ?? current.display_name;
    const code =
      form.studentCode ?? current.student_code ?? current.external_ref;
    const updated: Student = {
      ...current,
      student_code: code,
      external_ref: form.rollNumber ?? current.roll_number ?? code,
      display_name: fullName,
      first_name: fullName.split(" ")[0] ?? fullName,
      last_name: fullName.split(" ").slice(1).join(" "),
      admission_number:
        form.admissionNumber !== undefined
          ? form.admissionNumber
          : current.admission_number,
      roll_number:
        form.rollNumber !== undefined ? form.rollNumber : current.roll_number,
      class_section_id: form.classSectionId ?? current.class_section_id,
      academic_year_id:
        form.academicYearId !== undefined
          ? form.academicYearId
          : current.academic_year_id,
      grade: section?.gradeLabel ?? current.grade,
      section: section?.name ?? current.section,
    };
    mockStudentStore = mockStudentStore.map((s) =>
      s.id === id ? updated : s,
    );
    return delay(updated);
  },
  async validateStudentImport(_file) {
    void _file;
    return delay({
      importSessionId: "00000000-0000-4000-8000-000000000099",
      status: "VALIDATED" as const,
      validRowCount: 1,
      totalRows: 2,
      invalidCount: 1,
      duplicateCount: 0,
      expiresAt: new Date(Date.now() + 3600_000).toISOString(),
      rowResults: [
        {
          rowNumber: 2,
          outcome: "VALID",
          studentCode: "STU-MOCK-1",
          admissionNumber: "",
          rollNumber: "1",
          fullName: "Mock Student",
          academicYear: "2026-27",
          classSection: "A",
        },
        {
          rowNumber: 3,
          outcome: "MISSING_REQUIRED_FIELD",
          studentCode: "",
          admissionNumber: "",
          rollNumber: "",
          fullName: "",
          academicYear: "",
          classSection: "",
        },
      ],
    } satisfies ImportValidationView);
  },
  async commitStudentImport(_id): Promise<ImportCommitResult> {
    void _id;
    return delay({
      importSessionId: "00000000-0000-4000-8000-000000000099",
      status: "COMMITTED",
      committedCount: 1,
    });
  },

  async listGuardians() {
    return delay([...mockGuardians]);
  },
  async listStudentGuardians(studentId) {
    const links = [...mockLinks]
      .filter((key) => key.startsWith(`${studentId}:`))
      .map((key) => {
        const guardianId = key.slice(studentId.length + 1);
        const g = mockGuardians.find((x) => x.id === guardianId);
        return {
          studentId,
          guardianId,
          displayName: g?.displayName ?? "Unknown",
          email: g?.email ?? null,
          phone: g?.phone ?? null,
          relationshipType: "PARENT",
        };
      });
    return delay(links);
  },
  async getGuardian(id) {
    const g = mockGuardians.find((x) => x.id === id);
    if (!g) throw new Error("Guardian not found");
    return delay(g);
  },
  async createGuardian(form: GuardianFormValues) {
    const g: GuardianView = {
      id: `guardian-${crypto.randomUUID().slice(0, 8)}`,
      tenantId: "tenant-demo-001",
      displayName: form.displayName,
      email: form.email ?? null,
      phone: form.phone ?? null,
    };
    mockGuardians.push(g);
    return delay(g);
  },
  async updateGuardian(id, form) {
    const g = mockGuardians.find((x) => x.id === id);
    if (!g) throw new Error("Guardian not found");
    Object.assign(g, {
      displayName: form.displayName ?? g.displayName,
      email: form.email !== undefined ? form.email || null : g.email,
      phone: form.phone !== undefined ? form.phone || null : g.phone,
    });
    return delay({ ...g });
  },
  async linkStudentGuardian(studentId, guardianId, _rel) {
    void _rel;
    mockLinks.add(`${studentId}:${guardianId}`);
  },
  async unlinkStudentGuardian(studentId, guardianId) {
    mockLinks.delete(`${studentId}:${guardianId}`);
  },

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
    return delay(
      rubrics.filter(
        (r) =>
          r.question_id.startsWith("q-") &&
          assessments.some((a) => a.id === id),
      ),
    );
  },
  async getAssessmentAnswerKey(id) {
    void id;
    return delay(answerKeys);
  },
  async getAssessmentCurriculumMap(id) {
    return delay(getAssessmentCurriculumMap(id));
  },
  async listSubmissions() {
    return delay(submissions);
  },
  async getSubmission(id) {
    const submission = submissions.find((s) => s.id === id);
    if (!submission) throw new Error(`Submission not found: ${id}`);
    return delay(submission);
  },
  async uploadSubmission(input) {
    void input;
    // B0 demo upload UI does not call this — it navigates to sub-demo-002 directly.
    const demo = submissions.find((s) => s.id === "sub-demo-002") ?? submissions[0];
    if (!demo) throw new Error("No demo submissions available");
    return delay({ ...demo });
  },
  async getSubmissionPageImageBlob(pageId) {
    void pageId;
    throw new Error("Page images are not available in mock mode");
  },
  async getIdentityReview(submissionId) {
    return mockCall(() => getIdentityReview(submissionId));
  },
  async confirmIdentity(submissionId, studentId) {
    const submission = submissions.find((s) => s.id === submissionId);
    if (!submission) throw new Error(`Submission not found: ${submissionId}`);
    const student = mockStudentStore.find((s) => s.id === studentId);
    if (!student) throw new Error(`Student not found: ${studentId}`);
    submission.student_id = student.id;
    submission.student_display_name = student.display_name;
    submission.student_match_state = "CONFIRMED";
    submission.identity_confidence = 1;
    submission.workflow_state = "MAPPING_REVIEW";
    return delay({ ...submission });
  },
  async markIdentityUnmatched(submissionId) {
    const submission = submissions.find((s) => s.id === submissionId);
    if (!submission) throw new Error(`Submission not found: ${submissionId}`);
    submission.student_id = null;
    submission.student_display_name = null;
    submission.student_match_state = "UNMATCHED";
    submission.identity_confidence = 0;
    return delay({ ...submission });
  },
  async getMappingReview(submissionId) {
    return mockCall(() => getMappingReview(submissionId));
  },
  async prepareTranscription(submissionId) {
    const submission = submissions.find((s) => s.id === submissionId);
    if (!submission) throw new Error(`Submission not found: ${submissionId}`);
    submission.transcription_state = "REVIEW_REQUIRED";
    return delay({ ...submission });
  },
  async getTranscriptionWorkspace(submissionId) {
    return mockCall(() => getTranscriptionWorkspace(submissionId));
  },
  async putRegionTranscription(regionId, payload) {
    void regionId;
    return delay({
      id: "tx-human-new",
      answer_region_id: regionId,
      version_number: 1,
      source_type: "HUMAN",
      text: payload.text ?? null,
      latex: payload.latex ?? null,
      transcription_confidence: null,
      unreadable: Boolean(payload.unreadable),
      visual_only: Boolean(payload.visual_only),
      status: "REVIEW_REQUIRED",
      confirmed_by: null,
      confirmed_at: null,
    });
  },
  async confirmTranscription(transcriptionId) {
    return delay({
      id: transcriptionId,
      answer_region_id: "reg-2",
      version_number: 1,
      source_type: "HUMAN",
      text: "confirmed text",
      latex: null,
      transcription_confidence: 0.9,
      unreadable: false,
      visual_only: false,
      status: "CONFIRMED",
      confirmed_by: "user-teacher-001",
      confirmed_at: new Date().toISOString(),
    });
  },
  async finalizeTranscription(submissionId) {
    const submission = submissions.find((s) => s.id === submissionId);
    if (!submission) throw new Error(`Submission not found: ${submissionId}`);
    submission.transcription_state = "READY";
    return delay({ ...submission });
  },
  async getRegionCropBlob(regionId) {
    void regionId;
    throw new Error("Region crops are not available in mock mode");
  },
  async applyMappingAction(submissionId, regionId, action: MappingAction) {
    void submissionId;
    void regionId;
    return delay({ ok: true as const, action });
  },
  async getEvaluationWorkspace(submissionId, questionId) {
    return mockCall(() => getEvaluationWorkspace(submissionId, questionId));
  },
  async applyTeacherAction(
    submissionId,
    ledgerId,
    action: TeacherReviewAction,
    payload,
  ) {
    void ledgerId;
    const workspace = await mockCall(() => getEvaluationWorkspace(submissionId));
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
    return mockCall(() => getStudentReport(studentId, assessmentId));
  },
  async getParentReport(studentId, assessmentId) {
    return mockCall(() => getParentReport(studentId, assessmentId));
  },
  async getAssessmentAnalytics(assessmentId) {
    return mockCall(() => getAssessmentAnalytics(assessmentId));
  },
  async getStudentAnalytics(studentId) {
    return mockCall(() => getStudentAnalytics(studentId));
  },
  async getStudentMasteryState(studentId) {
    return mockCall(() => getStudentMasteryState(studentId));
  },
  async getStudentMasteryTrend(studentId, options) {
    return mockCall(() => getStudentMasteryTrend(studentId, options));
  },
  async getStudentRepeatedErrors(studentId) {
    return mockCall(() => getStudentRepeatedErrors(studentId));
  },
  async getStudentRecoverableMarks(studentId) {
    return mockCall(() => getStudentRecoverableMarks(studentId));
  },
  async getStudentMistakeNotebook(studentId) {
    return mockCall(() => getStudentMistakeNotebook(studentId));
  },
  async getAdaptiveLearning(studentId) {
    return mockCall(() => getAdaptiveLearning(studentId));
  },
  async getImprovementBlueprint(studentId) {
    return mockCall(() => getImprovementBlueprint(studentId));
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
  async listCurriculumResources(filters) {
    return mockCall(() => listCurriculumResources(filters));
  },
  async getCurriculumResource(id) {
    return mockCall(() => getCurriculumResource(id));
  },
  async createCurriculumResource(input) {
    return mockCall(() => createCurriculumResource(input));
  },
  async updateCurriculumResource(id, input) {
    return mockCall(() => updateCurriculumResource(id, input));
  },
  async approveCurriculumResource(id) {
    return mockCall(() => approveCurriculumResource(id));
  },
  async activateCurriculumResource(id) {
    return mockCall(() => activateCurriculumResource(id));
  },
  async deactivateCurriculumResource(id) {
    return mockCall(() => deactivateCurriculumResource(id));
  },
  async replaceCurriculumResourceNodes(id, nodeIds) {
    return mockCall(() => replaceCurriculumResourceNodes(id, nodeIds));
  },
  async listStudentResourceAssignments(studentId, filters) {
    return mockCall(() => listStudentResourceAssignments(studentId, filters));
  },
  async assignStudentResource(studentId, input) {
    return mockCall(() => assignStudentResource(studentId, input));
  },
  async cancelStudentResourceAssignment(assignmentId) {
    return mockCall(() => cancelStudentResourceAssignment(assignmentId));
  },
  async instantiateReassessment(blueprintId, items) {
    const payload = Array.isArray(items) ? { items } : items;
    return mockCall(() => instantiateReassessment(blueprintId, payload));
  },
  async getReassessment(id) {
    return mockCall(() => getReassessment(id));
  },
  async rebuildReassessmentB14(id) {
    return mockCall(() => rebuildReassessmentB14(id));
  },
  async listBenchmarkDatasets() {
    return mockCall(() => listBenchmarkDatasets());
  },
  async getBenchmarkDataset(id) {
    return mockCall(() => getBenchmarkDataset(id));
  },
  async createBenchmarkDataset(input) {
    return mockCall(() => createBenchmarkDataset(input));
  },
  async listBenchmarkVersions(datasetId) {
    return mockCall(() => listBenchmarkVersions(datasetId));
  },
  async createBenchmarkVersion(datasetId, input) {
    return mockCall(() => createBenchmarkVersion(datasetId, input));
  },
  async getBenchmarkVersion(versionId) {
    return mockCall(() => getBenchmarkVersion(versionId));
  },
  async listBenchmarkEligibleSources(versionId) {
    return mockCall(() => listBenchmarkEligibleSources(versionId));
  },
  async listBenchmarkCases(versionId) {
    return mockCall(() => listBenchmarkCases(versionId));
  },
  async addBenchmarkCase(versionId, input) {
    return mockCall(() => addBenchmarkCase(versionId, input));
  },
  async removeBenchmarkCase(versionId, caseId) {
    return mockCall(() => removeBenchmarkCase(versionId, caseId));
  },
  async lockBenchmarkVersion(versionId) {
    return mockCall(() => lockBenchmarkVersion(versionId));
  },
  async listBenchmarkRegressionRuns(versionId) {
    return mockCall(() => listBenchmarkRegressionRuns(versionId));
  },
  async startBenchmarkRegressionRun(versionId, input) {
    return mockCall(() => startBenchmarkRegressionRun(versionId, input));
  },
  async getBenchmarkRegressionRun(runId) {
    return mockCall(() => getBenchmarkRegressionRun(runId));
  },
  async listBenchmarkRegressionCaseResults(runId) {
    return mockCall(() => listBenchmarkRegressionCaseResults(runId));
  },
  async getBenchmarkGateVerdict(runId) {
    return mockCall(() => getBenchmarkGateVerdict(runId));
  },
};

/** @deprecated Prefer MockEduVijnaApi */
export const mockApiClient = MockEduVijnaApi;

// silence unused AuthSession in type-only path
export type { AuthSession };
