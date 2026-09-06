import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import yaml from "yaml";

const openapiPath = resolve(process.cwd(), "../../packages/contracts/openapi.yaml");

describe("B2 A2 OpenAPI contract", () => {
  const doc = yaml.parse(readFileSync(openapiPath, "utf8")) as {
    paths: Record<string, { get?: unknown; post?: unknown }>;
    components: { schemas: Record<string, unknown> };
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

  it("keeps the A2 creation schemas required by the live adapter", () => {
    expect(doc.components.schemas.AssessmentInput).toBeTruthy();
    expect(doc.components.schemas.RubricInput).toBeTruthy();
    expect(doc.components.schemas.RubricVersionInput).toBeTruthy();
  });
});
