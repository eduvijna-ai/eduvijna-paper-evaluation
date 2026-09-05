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

export interface ImportRowResult {
  row_number?: number;
  outcome: ImportOutcome | string;
  student_code?: string;
  full_name?: string;
  academic_year?: string;
  class_section?: string;
  [key: string]: unknown;
}

export interface ImportValidationView {
  importSessionId: string;
  status: "VALIDATED";
  validRowCount: number;
  rowResults: ImportRowResult[];
  expiresAt: string;
  totalRows: number;
  invalidCount: number;
  duplicateCount: number;
}

export interface ImportCommitResult {
  created_count?: number;
  [key: string]: unknown;
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

export function importValidationApiToView(api: {
  import_session_id: string;
  status: "VALIDATED";
  valid_row_count: number;
  row_results: Array<Record<string, unknown>>;
  expires_at: string;
}): ImportValidationView {
  const rowResults = api.row_results as ImportRowResult[];
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
