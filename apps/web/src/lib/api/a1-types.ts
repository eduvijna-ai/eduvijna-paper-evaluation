/**
 * A1 OpenAPI-aligned types (packages/contracts/openapi.yaml after PR #4).
 * Used by HttpEduVijnaApi platform stubs for B1 — do not invent alternate field names.
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

/** A1 Student schema — maps to UI Student at adapter boundary in B1. */
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
