/**
 * A1 OpenAPI-aligned transport types (packages/contracts/openapi.yaml).
 * UI view-models live in mappers — do not use these snake_case shapes in components.
 */

export interface LoginRequest {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
  user: A1User;
}

export interface A1User {
  id: string;
  tenant_id: string;
  email: string;
  display_name: string;
  status: string;
  roles?: string[];
  permissions?: string[];
}

export interface Institution {
  id: string;
  tenant_id: string;
  code: string;
  name: string;
}

export interface AcademicYearInput {
  name: string;
  starts_on: string;
  ends_on: string;
  is_current?: boolean;
}

export interface AcademicYear extends AcademicYearInput {
  id: string;
  tenant_id: string;
  institution_id: string;
}

export interface ClassSectionInput {
  academic_year_id: string;
  name: string;
  grade_label: string;
}

export interface ClassSection extends ClassSectionInput {
  id: string;
  tenant_id: string;
}

export interface A1StudentInput {
  student_code: string;
  admission_number?: string | null;
  roll_number?: string | null;
  full_name: string;
  class_section_id?: string | null;
  academic_year_id?: string | null;
  status?: string;
}

export interface A1Student extends A1StudentInput {
  id: string;
  tenant_id: string;
  created_at: string;
  updated_at: string;
}

export interface GuardianInput {
  display_name: string;
  email?: string | null;
  phone?: string | null;
}

export interface Guardian extends GuardianInput {
  id: string;
  tenant_id: string;
}

export interface ImportValidation {
  import_session_id: string;
  status: "VALIDATED";
  valid_row_count: number;
  row_results: Array<Record<string, unknown>>;
  expires_at: string;
}

export interface VersionResponse {
  application: string;
  environment: string;
  git_sha: string;
  api_version: string;
}

export interface StatusResponse {
  status: string;
}

/** A1 permission codes — frontend convenience only; backend is authoritative. */
export const A1_PERMISSIONS = {
  institutionRead: "institution:read",
  academicYearRead: "academic_year:read",
  academicYearWrite: "academic_year:write",
  classSectionRead: "class_section:read",
  classSectionWrite: "class_section:write",
  studentRead: "student:read",
  studentWrite: "student:write",
  studentImport: "student:import",
  guardianRead: "guardian:read",
  guardianWrite: "guardian:write",
  /** B15 quality benchmark (also granted on teacher/admin roles server-side). */
  qualityRead: "quality:read",
  qualityManage: "quality:manage",
  calibrationParticipate: "calibration:participate",
  gradingRead: "grading:read",
  gradingManage: "grading:manage",
  gradingWork: "grading:work",
  moderationRead: "moderation:read",
  moderationReview: "moderation:review",
  grievanceRead: "grievance:read",
  grievanceCreate: "grievance:create",
  grievanceManage: "grievance:manage",
} as const;
