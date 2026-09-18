import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import yaml from "yaml";

const openapiPath = resolve(process.cwd(), "../../packages/contracts/openapi.yaml");

describe("B20 OpenAPI contract", () => {
  const doc = yaml.parse(readFileSync(openapiPath, "utf8")) as {
    paths: Record<string, Record<string, unknown>>;
    components: { schemas: Record<string, unknown> };
  };

  it("publishes language confirmation and B20 schemas", () => {
    expect(doc.paths["/api/v1/submissions/{id}/language"]).toBeTruthy();
    expect(doc.paths["/api/v1/submissions/{id}/language"]?.put).toBeTruthy();
    for (const schema of [
      "SubmissionLanguageInput",
      "SubjectProfile",
      "LanguageContext",
      "TranscriptionDerivedText",
    ]) {
      expect(doc.components.schemas[schema], schema).toBeTruthy();
    }
  });
});
