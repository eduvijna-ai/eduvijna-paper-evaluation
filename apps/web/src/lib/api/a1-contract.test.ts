import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import yaml from "yaml";

/**
 * Lightweight OpenAPI drift guards for A1 platform contracts used by B1.
 * Not full codegen — detects missing paths/schemas that would break adapters.
 */
const openapiPath = resolve(
  process.cwd(),
  "../../packages/contracts/openapi.yaml",
);

describe("A1 OpenAPI contract (B1)", () => {
  const doc = yaml.parse(readFileSync(openapiPath, "utf8")) as {
    paths: Record<string, unknown>;
    components: { schemas: Record<string, { properties?: Record<string, unknown>; required?: string[] }> };
  };

  it("exposes auth, institution, years, sections, students, import, guardians", () => {
    const required = [
      "/api/v1/auth/login",
      "/api/v1/auth/me",
      "/api/v1/institution",
      "/api/v1/academic-years",
      "/api/v1/class-sections",
      "/api/v1/students",
      "/api/v1/students/import/validate",
      "/api/v1/students/import/commit",
      "/api/v1/guardians",
      "/api/v1/students/{student_id}/guardians",
      "/api/v1/students/{student_id}/guardians/{guardian_id}",
    ];
    for (const path of required) {
      expect(doc.paths[path], path).toBeTruthy();
    }
  });

  it("documents ImportCommit committed_count and rubric POST bodies", () => {
    const commit = doc.components.schemas.ImportCommit;
    expect(commit.required).toEqual(
      expect.arrayContaining([
        "import_session_id",
        "status",
        "committed_count",
      ]),
    );
    expect(doc.components.schemas.RubricInput).toBeTruthy();
    expect(doc.components.schemas.RubricVersionInput).toBeTruthy();
    expect(doc.components.schemas.StudentGuardianLink).toBeTruthy();
    const createRubric = (
      doc.paths["/api/v1/assessments/{id}/rubrics"] as {
        post?: { requestBody?: unknown };
      }
    )?.post;
    const createVersion = (
      doc.paths["/api/v1/rubrics/{id}/versions"] as {
        post?: { requestBody?: unknown };
      }
    )?.post;
    expect(createRubric?.requestBody).toBeTruthy();
    expect(createVersion?.requestBody).toBeTruthy();
  });

  it("keeps Student transport fields expected by adapters", () => {
    const student = doc.components.schemas.StudentInput;
    expect(student.required).toEqual(
      expect.arrayContaining(["student_code", "full_name"]),
    );
    expect(student.properties).toHaveProperty("student_code");
    expect(student.properties).toHaveProperty("full_name");
    expect(student.properties).toHaveProperty("class_section_id");
  });

  it("keeps LoginRequest email/password", () => {
    const login = doc.components.schemas.LoginRequest;
    expect(login.properties).toHaveProperty("email");
    expect(login.properties).toHaveProperty("password");
  });

  it("keeps ImportValidation shape", () => {
    const schema = doc.components.schemas.ImportValidation;
    expect(schema.required).toEqual(
      expect.arrayContaining([
        "import_session_id",
        "status",
        "valid_row_count",
        "row_results",
        "expires_at",
      ]),
    );
  });
});
