import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import yaml from "yaml";

const openapiPath = resolve(process.cwd(), "../../packages/contracts/openapi.yaml");

describe("B3 submissions OpenAPI contract", () => {
  const doc = yaml.parse(readFileSync(openapiPath, "utf8")) as {
    paths: Record<string, Record<string, unknown>>;
    components: { schemas: Record<string, unknown> };
  };

  it("publishes submission ingestion and identity review paths", () => {
    for (const path of [
      "/api/v1/submissions",
      "/api/v1/submissions/{id}",
      "/api/v1/submissions/{id}/pages",
      "/api/v1/submissions/{id}/identity",
      "/api/v1/submissions/{id}/identity/confirm",
      "/api/v1/submissions/{id}/identity/unmatched",
      "/api/v1/submissions/{id}/source",
      "/api/v1/submission-pages/{id}/image",
    ]) {
      expect(doc.paths[path], path).toBeTruthy();
    }
  });

  it("exposes upload and list verbs on /api/v1/submissions", () => {
    const submissions = doc.paths["/api/v1/submissions"] as {
      get?: { security?: unknown; responses?: Record<string, unknown> };
      post?: {
        requestBody?: {
          content?: { "multipart/form-data"?: { schema?: { $ref?: string } } };
        };
      };
    };
    expect(submissions?.get, "GET list").toBeTruthy();
    expect(submissions?.post, "POST upload").toBeTruthy();
    expect(submissions.get?.security).toBeTruthy();
    expect(
      submissions.post?.requestBody?.content?.["multipart/form-data"]?.schema?.$ref,
    ).toBe("#/components/schemas/SubmissionUploadRequest");
  });

  it("types identity and binary responses", () => {
    expect(doc.components.schemas.Submission).toBeTruthy();
    expect(doc.components.schemas.SubmissionPage).toBeTruthy();
    expect(doc.components.schemas.IdentityReview).toBeTruthy();
    expect(doc.components.schemas.IdentityConfirmInput).toBeTruthy();
    expect(
      doc.paths["/api/v1/submissions/{id}/identity/confirm"]?.post,
    ).toBeTruthy();
    expect(
      doc.paths["/api/v1/submissions/{id}/identity/unmatched"]?.post,
    ).toBeTruthy();
    const source = doc.paths["/api/v1/submissions/{id}/source"]?.get as {
      responses?: Record<string, { content?: Record<string, unknown> }>;
    };
    expect(source?.responses?.["200"]?.content?.["application/pdf"]).toBeTruthy();
    const image = doc.paths["/api/v1/submission-pages/{id}/image"]?.get as {
      responses?: Record<string, { content?: Record<string, unknown> }>;
    };
    expect(image?.responses?.["200"]?.content?.["image/png"]).toBeTruthy();
  });
});
