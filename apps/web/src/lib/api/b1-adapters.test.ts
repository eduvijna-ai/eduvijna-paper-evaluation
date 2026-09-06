import { describe, expect, it } from "vitest";
import { ApiError } from "@/lib/api/http/errors";
import { __test__ } from "@/lib/api/http/client";
import {
  buildCsvTemplate,
  importCommitApiToView,
  importCommitErrorMessage,
  importRowApiToView,
  importValidationApiToView,
} from "@/lib/api/mappers/import";
import { studentGuardianLinkApiToView } from "@/lib/api/mappers/guardian";
import { getApiCapabilities } from "@/lib/api/capabilities";
import {
  ASSESSMENT_ID,
  getAdaptiveLearning,
  getParentReport,
  getStudentAnalytics,
  getStudentReport,
  MockNotFoundError,
  STUDENT_ID,
} from "@/lib/api/mock/data";
import { guardianFormToApi, guardianApiToViewModel } from "@/lib/api/mappers/guardian";
import {
  studentApiToViewModel,
  studentFormToApi,
} from "@/lib/api/mappers/student";
import { hasPermission } from "@/lib/auth/session";
import type { AuthSession } from "@/lib/types/domain";

const { parseEnvelope } = __test__;

describe("ApiError", () => {
  it("maps status kinds and safe user messages", () => {
    const err = new ApiError({
      message: "nope",
      status: 401,
      kind: "unauthorized",
      code: "AUTH_FAILED",
    });
    expect(err.kind).toBe("unauthorized");
    expect(err.userMessage()).toMatch(/sign in/i);
    expect(ApiError.kindFromStatus(403)).toBe("forbidden");
    expect(ApiError.kindFromStatus(404)).toBe("not_found");
    expect(ApiError.kindFromStatus(409)).toBe("conflict");
    expect(ApiError.kindFromStatus(422)).toBe("unprocessable");
    expect(ApiError.kindFromStatus(500)).toBe("server");
  });
});

describe("FastAPI detail-object parsing", () => {
  it("parses error envelope with structured code", () => {
    const parsed = parseEnvelope({
      error: {
        code: "IMPORT_SESSION_EXPIRED",
        message: "The validated import session has expired.",
        correlation_id: "c1",
        details: null,
      },
    });
    expect(parsed.code).toBe("IMPORT_SESSION_EXPIRED");
    expect(parsed.message).toMatch(/expired/i);
  });

  it("parses detail object {code, message}", () => {
    const parsed = parseEnvelope({
      detail: {
        code: "STUDENT_IMPORT_CONFLICT",
        message: "Roster data changed after validation. Revalidate the CSV before importing.",
      },
    });
    expect(parsed.code).toBe("STUDENT_IMPORT_CONFLICT");
    expect(parsed.message).toMatch(/revalidate/i);
  });

  it("promotes nested details.code when envelope code is http_409", () => {
    const parsed = parseEnvelope({
      error: {
        code: "http_409",
        message: "Request failed",
        details: {
          code: "IMPORT_SESSION_INVALID",
          message: "The import session is not available for commit.",
        },
      },
    });
    expect(parsed.code).toBe("IMPORT_SESSION_INVALID");
    expect(parsed.message).toMatch(/not available|Request failed/i);
  });

  it("never returns object JSON as message", () => {
    const parsed = parseEnvelope({
      detail: { code: "X", message: "Safe text" },
    });
    expect(parsed.message).toBe("Safe text");
    expect(parsed.message).not.toContain("{");
  });
});

describe("import commit error UX", () => {
  it("maps IMPORT_SESSION_EXPIRED", () => {
    expect(
      importCommitErrorMessage({
        code: "IMPORT_SESSION_EXPIRED",
        status: 409,
        userMessage: () => "fallback",
      }),
    ).toMatch(/expired.*Validate the CSV again/i);
  });

  it("maps IMPORT_SESSION_INVALID", () => {
    expect(
      importCommitErrorMessage({
        code: "IMPORT_SESSION_INVALID",
        status: 409,
        userMessage: () => "fallback",
      }),
    ).toMatch(/no longer valid/i);
  });

  it("maps STUDENT_IMPORT_CONFLICT", () => {
    expect(
      importCommitErrorMessage({
        code: "STUDENT_IMPORT_CONFLICT",
        status: 409,
        userMessage: () => "fallback",
      }),
    ).toMatch(/Roster data changed/i);
  });

  it("uses generic conflict for unknown 409", () => {
    expect(
      importCommitErrorMessage({
        code: "http_409",
        status: 409,
        userMessage: () => "fallback",
      }),
    ).toMatch(/conflicts with an existing record/i);
  });

  it("uses safe validation message for 422", () => {
    expect(
      importCommitErrorMessage({
        status: 422,
        userMessage: () => "fallback",
      }),
    ).toMatch(/failed validation/i);
  });
});

describe("student DTO adapters", () => {
  it("maps A1 student to UI view-model", () => {
    const vm = studentApiToViewModel(
      {
        id: "11111111-1111-4111-8111-111111111111",
        tenant_id: "t1",
        student_code: "STU-1",
        full_name: "Ada Lovelace",
        roll_number: "7",
        admission_number: "A1",
        class_section_id: "sec1",
        academic_year_id: "year1",
        status: "active",
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
      },
      {
        institutionId: "inst1",
        section: {
          id: "sec1",
          name: "A",
          grade_label: "Grade 10",
          academic_year_id: "year1",
        },
      },
    );
    expect(vm.display_name).toBe("Ada Lovelace");
    expect(vm.external_ref).toBe("7");
    expect(vm.student_code).toBe("STU-1");
    expect(vm.grade).toBe("Grade 10");
    expect(vm.section).toBe("A");
    expect(vm.status).toBe("ACTIVE");
  });

  it("maps form to A1 input", () => {
    const api = studentFormToApi({
      studentCode: " STU-2 ",
      fullName: " Alan Turing ",
      rollNumber: "3",
      classSectionId: "sec",
      academicYearId: "year",
    });
    expect(api.student_code).toBe("STU-2");
    expect(api.full_name).toBe("Alan Turing");
    expect(api.roll_number).toBe("3");
  });
});

describe("guardian adapters", () => {
  it("round-trips form and API shapes", () => {
    const input = guardianFormToApi({
      displayName: "Parent One",
      email: "p@example.com",
      phone: "123",
    });
    expect(input.display_name).toBe("Parent One");
    const view = guardianApiToViewModel({
      id: "g1",
      tenant_id: "t1",
      ...input,
    });
    expect(view.displayName).toBe("Parent One");
  });

  it("maps student guardian link GET", () => {
    const view = studentGuardianLinkApiToView({
      student_id: "s1",
      guardian_id: "g1",
      display_name: "Parent",
      email: "p@x.com",
      phone: null,
      relationship_type: "PARENT",
    });
    expect(view.studentId).toBe("s1");
    expect(view.guardianId).toBe("g1");
    expect(view.displayName).toBe("Parent");
    expect(view.relationshipType).toBe("PARENT");
  });
});

describe("import mapper", () => {
  it("normalizes nested backend row_results fixture", () => {
    const view = importValidationApiToView({
      import_session_id: "s1",
      status: "VALIDATED",
      valid_row_count: 1,
      expires_at: "2026-01-01T00:00:00Z",
      row_results: [
        {
          row: 2,
          outcome: "VALID",
          reason_code: undefined,
          data: {
            student_code: "STU-A",
            admission_number: "ADM-1",
            roll_number: "1",
            full_name: "Ada",
            academic_year: "2026-27",
            class_section: "A",
          },
          academic_year_id: "y1",
          class_section_id: "c1",
        },
        {
          row: 3,
          outcome: "DUPLICATE_IN_FILE",
          reason_code: "STUDENT_CODE_DUPLICATE_IN_FILE",
          data: {
            student_code: "STU-A",
            admission_number: "",
            roll_number: "2",
            full_name: "Ada2",
            academic_year: "2026-27",
            class_section: "A",
          },
        },
        {
          row: 4,
          outcome: "MISSING_REQUIRED_FIELD",
          data: {
            student_code: "",
            admission_number: "",
            roll_number: "",
            full_name: "",
            academic_year: "",
            class_section: "",
          },
        },
      ],
    });
    expect(view.totalRows).toBe(3);
    expect(view.duplicateCount).toBe(1);
    expect(view.invalidCount).toBe(1);
    expect(view.rowResults[0]?.studentCode).toBe("STU-A");
    expect(view.rowResults[0]?.fullName).toBe("Ada");
    expect(view.rowResults[0]?.rowNumber).toBe(2);
    expect(view.rowResults[1]?.reasonCode).toBe(
      "STUDENT_CODE_DUPLICATE_IN_FILE",
    );
    expect(buildCsvTemplate()).toContain("student_code,admission_number");
  });

  it("maps committed_count to committedCount", () => {
    const commit = importCommitApiToView({
      import_session_id: "s1",
      status: "COMMITTED",
      committed_count: 3,
    });
    expect(commit.committedCount).toBe(3);
    expect(commit.importSessionId).toBe("s1");
  });

  it("importRowApiToView reads nested data", () => {
    const row = importRowApiToView(
      {
        row: 5,
        outcome: "VALID",
        data: { student_code: "X", full_name: "Y" },
      },
      0,
    );
    expect(row.studentCode).toBe("X");
    expect(row.fullName).toBe("Y");
    expect(row.rowNumber).toBe(5);
  });
});

describe("mock identity safety", () => {
  it("known mock student returns correct identity", () => {
    const report = getStudentReport(STUDENT_ID, ASSESSMENT_ID);
    expect(report.student.id).toBe(STUDENT_ID);
    const parent = getParentReport(STUDENT_ID, ASSESSMENT_ID);
    expect(parent.student_display_name).toBe(report.student.display_name);
    const learning = getAdaptiveLearning(STUDENT_ID);
    expect(learning.student.id).toBe(STUDENT_ID);
    const analytics = getStudentAnalytics(STUDENT_ID);
    expect(analytics.student.id).toBe(STUDENT_ID);
  });

  it("unknown student does not substitute another student", () => {
    expect(() =>
      getStudentReport("00000000-0000-4000-8000-000000000099", ASSESSMENT_ID),
    ).toThrow(MockNotFoundError);
    expect(() =>
      getParentReport("00000000-0000-4000-8000-000000000099", ASSESSMENT_ID),
    ).toThrow(MockNotFoundError);
    expect(() =>
      getStudentAnalytics("00000000-0000-4000-8000-000000000099"),
    ).toThrow(MockNotFoundError);
    expect(() =>
      getAdaptiveLearning("00000000-0000-4000-8000-000000000099"),
    ).toThrow(MockNotFoundError);
  });

  it("real UUID does not leak Demo Student 001", () => {
    try {
      getStudentReport("11111111-1111-4111-8111-111111111111", ASSESSMENT_ID);
      expect.unreachable("should throw");
    } catch (err) {
      expect(err).toBeInstanceOf(MockNotFoundError);
      expect(String(err)).not.toMatch(/Demo Student 001/);
    }
  });
});

describe("API capabilities", () => {
  it("exposes semantic domain capabilities without requiring page-level getApiMode", () => {
    const caps = getApiCapabilities();
    expect(caps).toHaveProperty("students");
    expect(caps).toHaveProperty("assessments");
    expect(["live", "mock"]).toContain(caps.students);
  });
});

describe("permission gating", () => {
  it("uses backend permission codes for bearer sessions", () => {
    const session: AuthSession = {
      userId: "u",
      displayName: "U",
      email: "u@x",
      role: "EVALUATOR",
      roles: ["EVALUATOR"],
      permissions: ["student:read"],
      tenantId: "t",
      institutionId: "i",
      expiresAt: Date.now() + 60_000,
      authMode: "bearer",
    };
    expect(hasPermission(session, "student:read")).toBe(true);
    expect(hasPermission(session, "student:write")).toBe(false);
  });
});
