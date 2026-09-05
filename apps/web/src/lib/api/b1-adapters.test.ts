import { describe, expect, it } from "vitest";
import { ApiError } from "@/lib/api/http/errors";
import {
  studentApiToViewModel,
  studentFormToApi,
} from "@/lib/api/mappers/student";
import { guardianFormToApi, guardianApiToViewModel } from "@/lib/api/mappers/guardian";
import { importValidationApiToView, buildCsvTemplate } from "@/lib/api/mappers/import";
import { hasPermission } from "@/lib/auth/session";
import type { AuthSession } from "@/lib/types/domain";

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
});

describe("import mapper", () => {
  it("summarizes validation rows and builds template headers", () => {
    const view = importValidationApiToView({
      import_session_id: "s1",
      status: "VALIDATED",
      valid_row_count: 1,
      expires_at: "2026-01-01T00:00:00Z",
      row_results: [
        { outcome: "VALID", student_code: "A" },
        { outcome: "DUPLICATE_IN_FILE", student_code: "B" },
        { outcome: "MISSING_REQUIRED_FIELD", student_code: "" },
      ],
    });
    expect(view.totalRows).toBe(3);
    expect(view.duplicateCount).toBe(1);
    expect(view.invalidCount).toBe(1);
    expect(buildCsvTemplate()).toContain("student_code,admission_number");
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
