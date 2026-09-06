/**
 * Import validation row outcomes from A1 CSV import.
 * Keep in sync with backend platform import validator.
 */
export const IMPORT_OUTCOMES = [
  "VALID",
  "DUPLICATE_IN_FILE",
  "DUPLICATE_EXISTING",
  "INVALID",
  "UNKNOWN_CLASS",
  "MISSING_REQUIRED_FIELD",
] as const;

export type ImportOutcome = (typeof IMPORT_OUTCOMES)[number];

/** Normalized UI row — never expose nested backend transport shape to components. */
export interface ImportRowView {
  rowNumber: number;
  outcome: ImportOutcome | string;
  studentCode: string;
  admissionNumber: string;
  rollNumber: string;
  fullName: string;
  academicYear: string;
  classSection: string;
  reasonCode?: string;
}

/** @deprecated Prefer ImportRowView — kept for transitional typing only */
export type ImportRowResult = ImportRowView;

export interface ImportValidationView {
  importSessionId: string;
  status: "VALIDATED";
  validRowCount: number;
  rowResults: ImportRowView[];
  expiresAt: string;
  totalRows: number;
  invalidCount: number;
  duplicateCount: number;
}

export interface ImportCommitResult {
  importSessionId: string;
  status: string;
  committedCount: number;
}

export const CSV_TEMPLATE_HEADERS = [
  "student_code",
  "admission_number",
  "roll_number",
  "full_name",
  "academic_year",
  "class_section",
] as const;

export function buildCsvTemplate(opts?: {
  academicYearName?: string;
  classSectionName?: string;
}): string {
  const year = opts?.academicYearName ?? "2026-27";
  const section = opts?.classSectionName ?? "A";
  const header = CSV_TEMPLATE_HEADERS.join(",");
  const example = [
    "STU-EXAMPLE-001",
    "ADM-001",
    "1",
    "Example Student",
    year,
    section,
  ].join(",");
  return `${header}\n${example}\n`;
}

export function downloadCsvTemplate(filename = "student-import-template.csv"): void {
  const content = buildCsvTemplate();
  const blob = new Blob([content], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object"
    ? (value as Record<string, unknown>)
    : {};
}

function asString(value: unknown): string {
  return typeof value === "string" ? value : value == null ? "" : String(value);
}

/** Normalize one backend import row (nested `data` or legacy flat). */
export function importRowApiToView(
  raw: Record<string, unknown>,
  index: number,
): ImportRowView {
  const data = asRecord(raw.data);
  const rowNumber =
    typeof raw.row === "number"
      ? raw.row
      : typeof raw.row_number === "number"
        ? raw.row_number
        : index + 2;
  return {
    rowNumber,
    outcome: asString(raw.outcome) || "INVALID",
    studentCode: asString(data.student_code ?? raw.student_code),
    admissionNumber: asString(data.admission_number ?? raw.admission_number),
    rollNumber: asString(data.roll_number ?? raw.roll_number),
    fullName: asString(data.full_name ?? raw.full_name),
    academicYear: asString(data.academic_year ?? raw.academic_year),
    classSection: asString(data.class_section ?? raw.class_section),
    reasonCode:
      typeof raw.reason_code === "string" ? raw.reason_code : undefined,
  };
}

export function importCommitApiToView(api: {
  import_session_id: string;
  status: string;
  committed_count: number;
}): ImportCommitResult {
  return {
    importSessionId: api.import_session_id,
    status: api.status,
    committedCount: api.committed_count,
  };
}

export function importCommitErrorMessage(err: {
  code?: string;
  status: number;
  userMessage: () => string;
}): string {
  switch (err.code) {
    case "IMPORT_SESSION_EXPIRED":
      return "The validated import session has expired. Validate the CSV again.";
    case "IMPORT_SESSION_INVALID":
      return "This import session is no longer valid. Validate the CSV again.";
    case "STUDENT_IMPORT_CONFLICT":
      return "Roster data changed after validation. Revalidate the CSV before importing.";
    default:
      break;
  }
  if (err.status === 409) {
    return "This change conflicts with an existing record.";
  }
  if (err.status === 422) {
    return "The import request failed validation. Check the CSV and try again.";
  }
  return err.userMessage();
}

export function importValidationApiToView(api: {
  import_session_id: string;
  status: "VALIDATED";
  valid_row_count: number;
  row_results: Array<Record<string, unknown>>;
  expires_at: string;
}): ImportValidationView {
  const rowResults = api.row_results.map((row, index) =>
    importRowApiToView(row, index),
  );
  const duplicateCount = rowResults.filter((r) =>
    String(r.outcome).startsWith("DUPLICATE"),
  ).length;
  const invalidCount = rowResults.filter(
    (r) => r.outcome !== "VALID" && !String(r.outcome).startsWith("DUPLICATE"),
  ).length;
  return {
    importSessionId: api.import_session_id,
    status: api.status,
    validRowCount: api.valid_row_count,
    rowResults,
    expiresAt: api.expires_at,
    totalRows: rowResults.length,
    invalidCount,
    duplicateCount,
  };
}
