import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import yaml from "yaml";

const openapiPath = resolve(process.cwd(), "../../packages/contracts/openapi.yaml");

describe("B4 mapping OpenAPI contract", () => {
  const doc = yaml.parse(readFileSync(openapiPath, "utf8")) as {
    paths: Record<string, Record<string, unknown>>;
    components: { schemas: Record<string, unknown> };
  };

  it("publishes B4 mapping workspace and mutation paths", () => {
    for (const path of [
      "/api/v1/submissions/{id}/mapping/prepare",
      "/api/v1/submissions/{id}/mapping",
      "/api/v1/submissions/{id}/mapping/finalize",
      "/api/v1/submission-pages/{id}/answer-regions",
      "/api/v1/answer-regions/{id}",
      "/api/v1/submission-pages/{id}",
      "/api/v1/submissions/{id}/question-mappings/{questionVersionId}",
      "/api/v1/submissions/{id}/question-mappings/{questionVersionId}/confirm",
    ]) {
      expect(doc.paths[path], path).toBeTruthy();
    }
  });

  it("exposes expected verbs on mapping endpoints", () => {
    expect(doc.paths["/api/v1/submissions/{id}/mapping/prepare"]?.post).toBeTruthy();
    expect(doc.paths["/api/v1/submissions/{id}/mapping"]?.get).toBeTruthy();
    expect(doc.paths["/api/v1/submissions/{id}/mapping/finalize"]?.post).toBeTruthy();
    expect(
      doc.paths["/api/v1/submission-pages/{id}/answer-regions"]?.post,
    ).toBeTruthy();
    expect(doc.paths["/api/v1/answer-regions/{id}"]?.patch).toBeTruthy();
    expect(doc.paths["/api/v1/answer-regions/{id}"]?.delete).toBeTruthy();
    expect(doc.paths["/api/v1/submission-pages/{id}"]?.patch).toBeTruthy();
    expect(
      doc.paths["/api/v1/submissions/{id}/question-mappings/{questionVersionId}"]
        ?.put,
    ).toBeTruthy();
    expect(
      doc.paths[
        "/api/v1/submissions/{id}/question-mappings/{questionVersionId}/confirm"
      ]?.post,
    ).toBeTruthy();
  });

  it("types MappingWorkspace and answer-region schemas", () => {
    expect(doc.components.schemas.MappingWorkspace).toBeTruthy();
    expect(doc.components.schemas.AnswerRegion).toBeTruthy();
    expect(doc.components.schemas.AnswerRegionInput).toBeTruthy();
    expect(doc.components.schemas.QuestionAnswerMapping).toBeTruthy();
    expect(doc.components.schemas.QuestionMappingInput).toBeTruthy();
    expect(doc.components.schemas.MappingCompletionSummary).toBeTruthy();
  });
});
