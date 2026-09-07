import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import yaml from "yaml";

const openapiPath = resolve(process.cwd(), "../../packages/contracts/openapi.yaml");
const studentSchemaPath = resolve(
  process.cwd(),
  "../../packages/contracts/schemas/student-report.schema.json",
);
const parentSchemaPath = resolve(
  process.cwd(),
  "../../packages/contracts/schemas/parent-report.schema.json",
);
const teacherSchemaPath = resolve(
  process.cwd(),
  "../../packages/contracts/schemas/teacher-report.schema.json",
);
const evaluatedSchemaPath = resolve(
  process.cwd(),
  "../../packages/contracts/schemas/evaluated-paper.schema.json",
);

describe("B7 publication OpenAPI + report schema contracts", () => {
  const doc = yaml.parse(readFileSync(openapiPath, "utf8")) as {
    paths: Record<string, Record<string, unknown>>;
    components: { schemas: Record<string, Record<string, unknown>> };
  };

  const expectedPaths = [
    "/api/v1/submissions/{id}/publication/prepare",
    "/api/v1/submissions/{id}/publication",
    "/api/v1/submissions/{id}/published-result",
    "/api/v1/publication-results/{id}/regenerate",
    "/api/v1/publication-results/{id}/publish",
    "/api/v1/publication-results/{id}/artifacts/{artifact_type}",
    "/api/v1/publication-results/{id}/reports/{audience}",
    "/api/v1/publication-results/{id}/annotations",
    "/api/v1/reports/student/{student_id}/assessments/{assessment_id}",
    "/api/v1/reports/parent/{student_id}/assessments/{assessment_id}",
    "/api/v1/reports/teacher/{student_id}/assessments/{assessment_id}",
  ];

  it("publishes B7 publication and report paths", () => {
    for (const path of expectedPaths) {
      expect(doc.paths[path], path).toBeTruthy();
    }
  });

  it("types PublicationWorkspace and PublishedResultSummary", () => {
    expect(doc.components.schemas.PublicationWorkspace).toBeTruthy();
    expect(doc.components.schemas.PublishedResultSummary).toBeTruthy();
    expect(doc.components.schemas.PublicationPrepareResult).toBeTruthy();
    expect(doc.components.schemas.PublicationAnnotation).toBeTruthy();
    const summary = doc.components.schemas.PublishedResultSummary;
    const props = summary.properties as Record<string, unknown>;
    expect(props.ledger_snapshot_hash).toBeTruthy();
    expect(props.total_score).toBeTruthy();
    expect(props.artifacts).toBeTruthy();
  });

  it("student/parent/teacher report schemas forbid proposed_ai_score property", () => {
    for (const path of [
      studentSchemaPath,
      parentSchemaPath,
      teacherSchemaPath,
      evaluatedSchemaPath,
    ]) {
      const schema = JSON.parse(readFileSync(path, "utf8")) as {
        additionalProperties?: boolean;
        properties?: Record<string, unknown>;
      };
      expect(schema.additionalProperties).toBe(false);
      expect(schema.properties?.proposed_ai_score).toBeUndefined();
      const stringifiedProps = JSON.stringify(schema.properties ?? {});
      expect(stringifiedProps).not.toMatch(/"proposed_ai_score"/);
    }
  });

  it("student report requires final_score on questions", () => {
    const schema = JSON.parse(readFileSync(studentSchemaPath, "utf8")) as {
      properties: {
        questions: {
          items: { required?: string[]; properties?: Record<string, unknown> };
        };
      };
    };
    expect(schema.properties.questions.items.required).toContain("final_score");
    expect(schema.properties.questions.items.properties?.proposed_ai_score).toBeUndefined();
  });
});
