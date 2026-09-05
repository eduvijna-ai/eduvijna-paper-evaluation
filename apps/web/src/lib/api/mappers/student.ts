import type { A1Student, A1StudentInput } from "@/lib/api/a1-types";
import type { Student } from "@/lib/types/domain";

export interface StudentFormValues {
  studentCode: string;
  fullName: string;
  admissionNumber?: string;
  rollNumber?: string;
  classSectionId?: string | null;
  academicYearId?: string | null;
  status?: string;
}

export interface ClassSectionLookup {
  id: string;
  name: string;
  grade_label: string;
  academic_year_id: string;
}

function splitName(fullName: string): { first: string; last: string } {
  const parts = fullName.trim().split(/\s+/);
  if (parts.length === 0) return { first: "", last: "" };
  if (parts.length === 1) return { first: parts[0]!, last: "" };
  return { first: parts[0]!, last: parts.slice(1).join(" ") };
}

function mapStatus(status: string | undefined): Student["status"] {
  const s = (status ?? "active").toLowerCase();
  if (s === "transferred") return "TRANSFERRED";
  if (s === "withdrawn") return "WITHDRAWN";
  return "ACTIVE";
}

/** Map A1 Student transport → UI Student view-model. */
export function studentApiToViewModel(
  api: A1Student,
  opts?: {
    institutionId?: string;
    section?: ClassSectionLookup | null;
  },
): Student {
  const { first, last } = splitName(api.full_name);
  const section = opts?.section;
  return {
    id: api.id,
    tenant_id: api.tenant_id,
    institution_id: opts?.institutionId ?? "",
    class_section_id: api.class_section_id ?? "",
    external_ref: api.roll_number || api.student_code,
    student_code: api.student_code,
    first_name: first,
    last_name: last,
    display_name: api.full_name,
    grade: section?.grade_label ?? "—",
    section: section?.name ?? "—",
    status: mapStatus(api.status),
    academic_year_id: api.academic_year_id ?? null,
    admission_number: api.admission_number ?? null,
    roll_number: api.roll_number ?? null,
  };
}

/** Map UI form → A1 StudentInput. */
export function studentFormToApi(form: StudentFormValues): A1StudentInput {
  return {
    student_code: form.studentCode.trim(),
    full_name: form.fullName.trim(),
    admission_number: form.admissionNumber?.trim() || null,
    roll_number: form.rollNumber?.trim() || null,
    class_section_id: form.classSectionId || null,
    academic_year_id: form.academicYearId || null,
    status: form.status ?? "active",
  };
}

export function studentViewToForm(student: Student): StudentFormValues {
  return {
    studentCode: student.student_code ?? student.external_ref,
    fullName: student.display_name,
    admissionNumber: student.admission_number ?? undefined,
    rollNumber: student.roll_number ?? undefined,
    classSectionId: student.class_section_id || null,
    academicYearId: student.academic_year_id ?? null,
    status: student.status === "ACTIVE" ? "active" : student.status.toLowerCase(),
  };
}
