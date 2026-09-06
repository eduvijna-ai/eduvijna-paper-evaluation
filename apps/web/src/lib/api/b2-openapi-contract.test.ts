import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import yaml from "yaml";

const openapiPath = resolve(process.cwd(), "../../packages/contracts/openapi.yaml");

type OpenApiSchema = {
  type?: string;
  required?: string[];
  properties?: Record<string, unknown>;
  items?: { $ref?: string };
  content?: {
    "application/json"?: {
      schema?: { type?: string; items?: { $ref?: string } };
    };
  };
};

describe("B2 A2 OpenAPI contract", () => {
  const doc = yaml.parse(readFileSync(openapiPath, "utf8")) as {
    paths: Record<string, { get?: OpenApiSchema; post?: unknown }>;
    components: { schemas: Record<string, OpenApiSchema> };
  };

  it("publishes curriculum and assessment authoring paths", () => {
    for (const path of [
      "/api/v1/curricula",
      "/api/v1/curricula/{id}/tree",
      "/api/v1/assessments",
      "/api/v1/assessments/{id}/versions",
      "/api/v1/assessment-versions/{id}/questions",
      "/api/v1/assessments/{id}/answer-key-versions",
      "/api/v1/assessments/{id}/rubrics",
      "/api/v1/rubric-versions/{id}/criteria",
      "/api/v1/question-versions/{id}/curriculum-mappings",
    ]) {
      expect(doc.paths[path], path).toBeTruthy();
    }
  });

  it("publishes typed rubric-version discovery used by the live adapter", () => {
    const get = doc.paths["/api/v1/rubrics/{id}/versions"]?.get as
      | { responses?: Record<string, OpenApiSchema> }
      | undefined;
    expect(get).toBeTruthy();

    const ok = get?.responses?.["200"];
    expect(ok).toBeTruthy();
    const schema = ok?.content?.["application/json"]?.schema;
    expect(schema?.type).toBe("array");
    expect(schema?.items?.$ref).toBe("#/components/schemas/RubricVersion");

    const rubricVersion = doc.components.schemas.RubricVersion;
    expect(rubricVersion).toBeTruthy();
    for (const field of [
      "id",
      "tenant_id",
      "rubric_id",
      "question_version_id",
      "version_number",
      "status",
      "source_type",
      "approved_by",
      "approved_at",
    ]) {
      expect(rubricVersion.properties, field).toHaveProperty(field);
    }
  });

  it("keeps the A2 creation schemas required by the live adapter", () => {
    expect(doc.components.schemas.AssessmentInput).toBeTruthy();
    expect(doc.components.schemas.RubricInput).toBeTruthy();
    expect(doc.components.schemas.RubricVersionInput).toBeTruthy();
  });
});
