import type {
  AcademicYear,
  AcademicYearInput,
  ClassSection,
  ClassSectionInput,
  Institution,
} from "@/lib/api/a1-types";

export interface InstitutionView {
  id: string;
  code: string;
  name: string;
  /** Intentionally omitted from casual UI — available when needed */
  tenantId: string;
}

export interface AcademicYearView {
  id: string;
  name: string;
  startsOn: string;
  endsOn: string;
  isCurrent: boolean;
  institutionId: string;
}

export interface AcademicYearFormValues {
  name: string;
  startsOn: string;
  endsOn: string;
  isCurrent?: boolean;
}

export interface ClassSectionView {
  id: string;
  name: string;
  gradeLabel: string;
  academicYearId: string;
  academicYearName?: string;
}

export interface ClassSectionFormValues {
  name: string;
  gradeLabel: string;
  academicYearId: string;
}

export function institutionApiToView(api: Institution): InstitutionView {
  return {
    id: api.id,
    code: api.code,
    name: api.name,
    tenantId: api.tenant_id,
  };
}

export function academicYearApiToView(api: AcademicYear): AcademicYearView {
  return {
    id: api.id,
    name: api.name,
    startsOn: api.starts_on,
    endsOn: api.ends_on,
    isCurrent: Boolean(api.is_current),
    institutionId: api.institution_id,
  };
}

export function academicYearFormToApi(
  form: AcademicYearFormValues,
): AcademicYearInput {
  return {
    name: form.name.trim(),
    starts_on: form.startsOn,
    ends_on: form.endsOn,
    is_current: form.isCurrent ?? false,
  };
}

export function classSectionApiToView(
  api: ClassSection,
  yearName?: string,
): ClassSectionView {
  return {
    id: api.id,
    name: api.name,
    gradeLabel: api.grade_label,
    academicYearId: api.academic_year_id,
    academicYearName: yearName,
  };
}

export function classSectionFormToApi(
  form: ClassSectionFormValues,
): ClassSectionInput {
  return {
    academic_year_id: form.academicYearId,
    name: form.name.trim(),
    grade_label: form.gradeLabel.trim(),
  };
}
