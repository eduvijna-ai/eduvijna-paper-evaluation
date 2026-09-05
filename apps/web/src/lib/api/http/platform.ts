import type { ApiClient } from "../types";
import type {
  A1Student,
  AcademicYear,
  ClassSection,
  Guardian,
  LoginRequest,
  TokenResponse,
  A1User,
  Institution,
  ImportValidation,
  VersionResponse,
} from "../a1-types";
import { httpRequest } from "./client";
import {
  academicYearApiToView,
  academicYearFormToApi,
  classSectionApiToView,
  classSectionFormToApi,
  institutionApiToView,
  type AcademicYearFormValues,
  type ClassSectionFormValues,
} from "../mappers/platform";
import {
  guardianApiToViewModel,
  guardianFormToApi,
  type GuardianFormValues,
} from "../mappers/guardian";
import {
  studentApiToViewModel,
  studentFormToApi,
  type StudentFormValues,
} from "../mappers/student";
import { importValidationApiToView } from "../mappers/import";
import type { AuthSession } from "@/lib/types/domain";
import { clearSession, getSession, setBearerSession } from "@/lib/auth/session";
import type { UserRole } from "@/lib/types/enums";

function toAuthSession(
  user: A1User,
  expiresIn: number,
  institution?: Institution | null,
): AuthSession {
  const roles = user.roles ?? [];
  const primary = (roles[0] as UserRole | undefined) ?? "TEACHER";
  return {
    userId: user.id,
    displayName: user.display_name,
    email: user.email,
    role: primary,
    roles,
    permissions: user.permissions ?? [],
    tenantId: user.tenant_id,
    institutionId: institution?.id ?? "",
    institutionName: institution?.name,
    expiresAt: Date.now() + expiresIn * 1000,
    authMode: "bearer",
  };
}

async function mapStudents(list: A1Student[]) {
  const [sections, institution] = await Promise.all([
    httpRequest<ClassSection[]>("/api/v1/class-sections"),
    httpRequest<Institution>("/api/v1/institution").catch(() => null),
  ]);
  const byId = new Map(sections.map((s) => [s.id, s]));
  return list.map((s) =>
    studentApiToViewModel(s, {
      institutionId: institution?.id,
      section: s.class_section_id
        ? (byId.get(s.class_section_id) ?? null)
        : null,
    }),
  );
}

/**
 * HTTP implementations for A1 platform domains.
 * CVB domains are not implemented here — hybrid adapter routes those to mock.
 */
export const PlatformHttpApi = {
  async login(email: string, password: string): Promise<AuthSession> {
    const body: LoginRequest = { email, password };
    const token = await httpRequest<TokenResponse>("/api/v1/auth/login", {
      method: "POST",
      body,
      anonymous: true,
    });
    // TokenResponse.user may omit roles/permissions; prefer /auth/me.
    const user = await httpRequest<A1User>("/api/v1/auth/me", {
      token: token.access_token,
    });
    let institution: Institution | null = null;
    try {
      institution = await httpRequest<Institution>("/api/v1/institution", {
        token: token.access_token,
      });
    } catch {
      institution = null;
    }
    const session = toAuthSession(user, token.expires_in, institution);
    setBearerSession(session, token.access_token);
    return session;
  },

  async logout(): Promise<void> {
    clearSession();
  },

  async getCurrentUser(): Promise<AuthSession> {
    const user = await httpRequest<A1User>("/api/v1/auth/me");
    const existing = getSession();
    let institution: Institution | null = null;
    try {
      institution = await httpRequest<Institution>("/api/v1/institution");
    } catch {
      institution = null;
    }
    const ttlSec = existing
      ? Math.max(60, Math.floor((existing.expiresAt - Date.now()) / 1000))
      : 3600;
    const session = toAuthSession(user, ttlSec, institution);
    const { getAccessToken } = await import("@/lib/auth/token-store");
    const token = getAccessToken();
    if (token) setBearerSession(session, token);
    return session;
  },

  async getInstitution() {
    return institutionApiToView(
      await httpRequest<Institution>("/api/v1/institution"),
    );
  },

  async listAcademicYears() {
    const rows = await httpRequest<AcademicYear[]>("/api/v1/academic-years");
    return rows.map(academicYearApiToView);
  },

  async createAcademicYear(form: AcademicYearFormValues) {
    const row = await httpRequest<AcademicYear>("/api/v1/academic-years", {
      method: "POST",
      body: academicYearFormToApi(form),
    });
    return academicYearApiToView(row);
  },

  async updateAcademicYear(
    id: string,
    form: Partial<AcademicYearFormValues>,
  ) {
    const body: Record<string, unknown> = {};
    if (form.name !== undefined) body.name = form.name.trim();
    if (form.startsOn !== undefined) body.starts_on = form.startsOn;
    if (form.endsOn !== undefined) body.ends_on = form.endsOn;
    if (form.isCurrent !== undefined) body.is_current = form.isCurrent;
    const row = await httpRequest<AcademicYear>(
      `/api/v1/academic-years/${id}`,
      { method: "PATCH", body },
    );
    return academicYearApiToView(row);
  },

  async listClassSections() {
    const [sections, years] = await Promise.all([
      httpRequest<ClassSection[]>("/api/v1/class-sections"),
      httpRequest<AcademicYear[]>("/api/v1/academic-years"),
    ]);
    const yearNames = new Map(years.map((y) => [y.id, y.name]));
    return sections.map((s) =>
      classSectionApiToView(s, yearNames.get(s.academic_year_id)),
    );
  },

  async createClassSection(form: ClassSectionFormValues) {
    const row = await httpRequest<ClassSection>("/api/v1/class-sections", {
      method: "POST",
      body: classSectionFormToApi(form),
    });
    return classSectionApiToView(row);
  },

  async updateClassSection(
    id: string,
    form: Partial<ClassSectionFormValues>,
  ) {
    const body: Record<string, unknown> = {};
    if (form.name !== undefined) body.name = form.name.trim();
    if (form.gradeLabel !== undefined) body.grade_label = form.gradeLabel.trim();
    if (form.academicYearId !== undefined)
      body.academic_year_id = form.academicYearId;
    const row = await httpRequest<ClassSection>(
      `/api/v1/class-sections/${id}`,
      { method: "PATCH", body },
    );
    return classSectionApiToView(row);
  },

  async listStudents() {
    const list = await httpRequest<A1Student[]>("/api/v1/students");
    return mapStudents(list);
  },

  async getStudent(id: string) {
    const student = await httpRequest<A1Student>(`/api/v1/students/${id}`);
    const mapped = await mapStudents([student]);
    return mapped[0]!;
  },

  async createStudent(form: StudentFormValues) {
    const created = await httpRequest<A1Student>("/api/v1/students", {
      method: "POST",
      body: studentFormToApi(form),
    });
    const mapped = await mapStudents([created]);
    return mapped[0]!;
  },

  async updateStudent(id: string, form: Partial<StudentFormValues>) {
    const body: Record<string, unknown> = {};
    if (form.studentCode !== undefined) body.student_code = form.studentCode.trim();
    if (form.fullName !== undefined) body.full_name = form.fullName.trim();
    if (form.admissionNumber !== undefined)
      body.admission_number = form.admissionNumber.trim() || null;
    if (form.rollNumber !== undefined)
      body.roll_number = form.rollNumber.trim() || null;
    if (form.classSectionId !== undefined)
      body.class_section_id = form.classSectionId || null;
    if (form.academicYearId !== undefined)
      body.academic_year_id = form.academicYearId || null;
    if (form.status !== undefined) body.status = form.status;
    const updated = await httpRequest<A1Student>(`/api/v1/students/${id}`, {
      method: "PATCH",
      body,
    });
    const mapped = await mapStudents([updated]);
    return mapped[0]!;
  },

  async validateStudentImport(file: Blob) {
    const form = new FormData();
    form.append("file", file, "roster.csv");
    const result = await httpRequest<ImportValidation>(
      "/api/v1/students/import/validate",
      { method: "POST", formData: form },
    );
    return importValidationApiToView(result);
  },

  async commitStudentImport(importSessionId: string) {
    return httpRequest<Record<string, unknown>>(
      "/api/v1/students/import/commit",
      {
        method: "POST",
        body: { import_session_id: importSessionId },
      },
    );
  },

  async listGuardians() {
    const rows = await httpRequest<Guardian[]>("/api/v1/guardians");
    return rows.map(guardianApiToViewModel);
  },

  async getGuardian(id: string) {
    return guardianApiToViewModel(
      await httpRequest<Guardian>(`/api/v1/guardians/${id}`),
    );
  },

  async createGuardian(form: GuardianFormValues) {
    return guardianApiToViewModel(
      await httpRequest<Guardian>("/api/v1/guardians", {
        method: "POST",
        body: guardianFormToApi(form),
      }),
    );
  },

  async updateGuardian(id: string, form: Partial<GuardianFormValues>) {
    const body: Record<string, unknown> = {};
    if (form.displayName !== undefined)
      body.display_name = form.displayName.trim();
    if (form.email !== undefined) body.email = form.email.trim() || null;
    if (form.phone !== undefined) body.phone = form.phone.trim() || null;
    return guardianApiToViewModel(
      await httpRequest<Guardian>(`/api/v1/guardians/${id}`, {
        method: "PATCH",
        body,
      }),
    );
  },

  async linkStudentGuardian(
    studentId: string,
    guardianId: string,
    relationshipType: string,
  ) {
    await httpRequest(
      `/api/v1/students/${studentId}/guardians/${guardianId}`,
      {
        method: "POST",
        body: { relationship_type: relationshipType },
      },
    );
  },

  async unlinkStudentGuardian(studentId: string, guardianId: string) {
    await httpRequest(
      `/api/v1/students/${studentId}/guardians/${guardianId}`,
      { method: "DELETE" },
    );
  },
} satisfies Partial<ApiClient>;

export async function getHttpVersion() {
  const v = await httpRequest<VersionResponse>("/api/v1/system/version");
  return { version: v.api_version, build: v.git_sha };
}
