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
