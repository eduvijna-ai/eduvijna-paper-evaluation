import { readFile, readdir } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import yaml from "js-yaml";

const packageRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const schemasDirectory = join(packageRoot, "schemas");
const requiredPaths = [
  "/health",
  "/ready",
  "/api/v1/system/version",
  "/api/v1/auth/login",
  "/api/v1/auth/me",
  "/api/v1/institution",
  "/api/v1/academic-years",
  "/api/v1/class-sections",
  "/api/v1/students",
  "/api/v1/students/import/validate",
  "/api/v1/students/import/commit",
  "/api/v1/guardians",
  "/api/v1/students/{student_id}/guardians/{guardian_id}",
  "/api/v1/curricula",
  "/api/v1/curricula/{id}/tree",
  "/api/v1/curricula/{id}/nodes",
  "/api/v1/curricula/{id}/prerequisites",
  "/api/v1/assessments",
  "/api/v1/assessments/{id}/versions",
  "/api/v1/assessments/{id}/transition",
  "/api/v1/assessment-versions/{id}/questions",
  "/api/v1/assessment-versions/{id}/marks/reconcile",
  "/api/v1/assessments/{id}/answer-key-versions",
  "/api/v1/answer-key-versions/{id}/approve",
  "/api/v1/assessments/{id}/rubrics",
  "/api/v1/rubric-versions/{id}/criteria",
  "/api/v1/rubric-versions/{id}/approve",
  "/api/v1/question-versions/{id}/curriculum-mappings",
  "/api/v1/ai/proposals/answer-key",
  "/api/v1/ai/proposals/rubric",
  "/api/v1/ai/proposals/curriculum-mapping",
  "/api/v1/assessment-versions/{id}/question-paper",
  "/api/v1/assessment-versions/{id}/question-paper/parse",
  "/api/v1/authoring-ai-runs/{id}",
  "/api/v1/authoring-ai-runs/{id}/question-tree-proposal",
  "/api/v1/authoring-ai-runs/{id}/apply-question-tree",
  "/api/v1/analytics/students/{id}/mastery-state",
  "/api/v1/analytics/students/{id}/mastery-trend",
  "/api/v1/analytics/students/{id}/repeated-errors",
  "/api/v1/analytics/students/{id}/recoverable-marks",
  "/api/v1/analytics/students/{id}/mistake-notebook",
  "/api/v1/analytics/students/{id}/b12/rebuild",
  "/api/v1/learning/resources",
  "/api/v1/learning/resources/{id}",
  "/api/v1/learning/resources/{id}/approve",
  "/api/v1/learning/resources/{id}/activate",
  "/api/v1/learning/resources/{id}/deactivate",
  "/api/v1/learning/resources/{id}/nodes",
  "/api/v1/learning/students/{id}/resource-assignments",
  "/api/v1/learning/resource-assignments/{id}/cancel",
  "/api/v1/improvement-assessments/{id}/reassessment",
  "/api/v1/reassessments/{id}",
  "/api/v1/reassessments/{id}/b14/rebuild",
  "/api/v1/quality/benchmark-datasets",
  "/api/v1/quality/benchmark-datasets/{dataset_id}",
  "/api/v1/quality/benchmark-datasets/{dataset_id}/versions",
  "/api/v1/quality/benchmark-versions/{version_id}",
  "/api/v1/quality/benchmark-versions/{version_id}/eligible-sources",
  "/api/v1/quality/benchmark-versions/{version_id}/cases",
  "/api/v1/quality/benchmark-versions/{version_id}/cases/{case_id}",
  "/api/v1/quality/benchmark-versions/{version_id}/lock",
  "/api/v1/quality/benchmark-versions/{version_id}/regression-runs",
  "/api/v1/quality/regression-runs/{run_id}",
  "/api/v1/quality/regression-runs/{run_id}/case-results",
  "/api/v1/quality/regression-runs/{run_id}/gate",
  "/api/v1/quality/psychometrics/runs",
  "/api/v1/quality/psychometrics/runs/{run_id}",
  "/api/v1/quality/psychometrics/runs/{run_id}/items",
  "/api/v1/quality/psychometrics/latest",
  "/api/v1/quality/calibration/sessions",
  "/api/v1/quality/calibration/sessions/{session_id}",
  "/api/v1/quality/calibration/sessions/{session_id}/cases",
  "/api/v1/quality/calibration/sessions/{session_id}/participants",
  "/api/v1/quality/calibration/sessions/{session_id}/activate",
  "/api/v1/quality/calibration/sessions/{session_id}/close",
  "/api/v1/quality/calibration/my-sessions",
  "/api/v1/quality/calibration/sessions/{session_id}/cases/{case_id}/blind",
  "/api/v1/quality/calibration/sessions/{session_id}/cases/{case_id}/responses",
  "/api/v1/quality/calibration/sessions/{session_id}/progress",
  "/api/v1/quality/calibration/sessions/{session_id}/metrics",
  "/api/v1/quality/calibration/sessions/{session_id}/evaluator-metrics",
  "/api/v1/quality/calibration/sessions/{session_id}/my-metrics",
  "/api/v1/operations/grading-pools",
  "/api/v1/operations/grading-pools/{pool_id}",
  "/api/v1/operations/grading-pools/{pool_id}/members",
  "/api/v1/operations/grading-pools/{pool_id}/activate",
  "/api/v1/operations/grading-pools/{pool_id}/close",
  "/api/v1/operations/grading-pools/{pool_id}/allocate",
  "/api/v1/operations/grading-pools/{pool_id}/assign",
  "/api/v1/operations/grading-pools/{pool_id}/progress",
  "/api/v1/operations/grading/my-queue",
  "/api/v1/operations/grading/work-items/{work_item_id}/start",
  "/api/v1/operations/grading/work-items/{work_item_id}/submit",
  "/api/v1/operations/moderation-policies",
  "/api/v1/operations/moderation-policies/{policy_id}/activate",
  "/api/v1/operations/moderation-policies/{policy_id}/retire",
  "/api/v1/operations/moderation-cases",
  "/api/v1/operations/moderation-cases/{case_id}",
  "/api/v1/operations/moderation-cases/{case_id}/decide",
  "/api/v1/operations/grievances",
  "/api/v1/operations/grievances/{grievance_id}",
  "/api/v1/operations/grievances/{grievance_id}/accept",
  "/api/v1/operations/grievances/{grievance_id}/reject",
  "/api/v1/operations/grievances/{grievance_id}/resolve",
];

const schemaFiles = (await readdir(schemasDirectory))
  .filter((name) => name.endsWith(".schema.json"))
  .sort();

if (schemaFiles.length === 0) {
  throw new Error("No JSON Schema files found");
}

for (const file of schemaFiles) {
  const schema = JSON.parse(await readFile(join(schemasDirectory, file), "utf8"));
  if (typeof schema.$schema !== "string" || typeof schema.title !== "string") {
    throw new Error(`${file} must declare $schema and title`);
  }
}

const document = yaml.load(await readFile(join(packageRoot, "openapi.yaml"), "utf8"));
if (!document || typeof document !== "object" || document.openapi !== "3.1.0") {
  throw new Error("openapi.yaml must be an OpenAPI 3.1.0 document");
}

for (const path of requiredPaths) {
  if (!document.paths?.[path]) {
    throw new Error(`openapi.yaml is missing ${path}`);
  }
}

console.log(`Validated ${schemaFiles.length} JSON Schemas and openapi.yaml`);
