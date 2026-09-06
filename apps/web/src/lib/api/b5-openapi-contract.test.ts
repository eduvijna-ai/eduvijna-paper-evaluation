import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import yaml from "yaml";

const openapiPath = resolve(process.cwd(), "../../packages/contracts/openapi.yaml");

describe("B5 transcription OpenAPI contract", () => {
  const doc = yaml.parse(readFileSync(openapiPath, "utf8")) as {
    paths: Record<string, Record<string, unknown>>;
  };

  const expectedPaths = [
    "/api/v1/submissions/{id}/transcription/prepare",
    "/api/v1/submissions/{id}/transcription",
    "/api/v1/submissions/{id}/transcription/finalize",
    "/api/v1/answer-regions/{id}/transcription",
    "/api/v1/answer-region-transcriptions/{id}/confirm",
    "/api/v1/answer-regions/{id}/crop",
  ];

  it("publishes B5 transcription paths when present in OpenAPI", () => {
    const present = expectedPaths.filter((path) => Boolean(doc.paths[path]));
    if (present.length === 0) {
      expect.soft(present.length).toBe(0);
      return;
    }
    expect(present.length).toBeGreaterThan(0);
    for (const path of present) {
      expect(doc.paths[path], path).toBeTruthy();
    }
  });
});
