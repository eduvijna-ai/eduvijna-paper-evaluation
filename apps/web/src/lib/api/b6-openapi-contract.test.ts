import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import yaml from "yaml";

const openapiPath = resolve(process.cwd(), "../../packages/contracts/openapi.yaml");
const ledgerSchemaPath = resolve(
  process.cwd(),
  "../../packages/contracts/schemas/evaluation-ledger.schema.json",
);

describe("B6 evaluation OpenAPI + ledger schema contracts", () => {
  const doc = yaml.parse(readFileSync(openapiPath, "utf8")) as {
    paths: Record<string, Record<string, unknown>>;
    components: { schemas: Record<string, Record<string, unknown>> };
  };
  const ledger = JSON.parse(readFileSync(ledgerSchemaPath, "utf8")) as {
    properties: Record<string, { type?: unknown; items?: unknown }>;
    required?: string[];
  };

  const expectedPaths = [
    "/api/v1/submissions/{id}/evaluation/prepare",
    "/api/v1/submissions/{id}/evaluation",
    "/api/v1/submissions/{id}/evaluation/finalize",
    "/api/v1/evaluation-runs/{id}",
    "/api/v1/question-evaluations/{id}",
    "/api/v1/question-evaluations/{id}/accept",
    "/api/v1/question-evaluations/{id}/override",
    "/api/v1/question-evaluations/{id}/feedback",
    "/api/v1/question-evaluations/{id}/escalate",
  ];

  it("publishes B6 evaluation paths", () => {
    for (const path of expectedPaths) {
      expect(doc.paths[path], path).toBeTruthy();
    }
  });

  it("types EvaluationWorkspace and QuestionEvaluation via schema refs", () => {
    expect(doc.components.schemas.EvaluationWorkspace).toBeTruthy();
    expect(doc.components.schemas.QuestionEvaluation).toBeTruthy();
    expect(doc.components.schemas.EvaluationRun).toBeTruthy();
    expect(doc.components.schemas.ReviewAction).toBeTruthy();
    const qe = doc.components.schemas.QuestionEvaluation;
    expect(qe.properties).toBeTruthy();
    const props = qe.properties as Record<string, { type?: unknown }>;
    expect(props.proposed_ai_score).toBeTruthy();
    expect(props.identity_confidence).toBeTruthy();
    expect(props.mapping_confidence).toBeTruthy();
    expect(props.transcription_confidence).toBeTruthy();
    expect(props.evaluation_confidence).toBeTruthy();
    expect(props.math_verification_confidence).toBeTruthy();
    expect(props.overall_confidence).toBeUndefined();
  });

  it("allows null proposed_ai_score in evaluation-ledger JSON Schema", () => {
    const proposed = ledger.properties.proposed_ai_score;
    expect(proposed).toBeTruthy();
    const type = proposed.type;
    const allowsNull =
      type === "null" ||
      (Array.isArray(type) && type.includes("null")) ||
      JSON.stringify(proposed).includes('"null"');
    expect(allowsNull).toBe(true);
  });

  it("includes ESCALATED in ledger workflow states when present", () => {
    const wf = ledger.properties.workflow_state as {
      enum?: string[];
    };
    if (wf?.enum) {
      expect(wf.enum).toContain("ESCALATED");
    }
  });
});
