import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import yaml from "yaml";

const openapiPath = resolve(process.cwd(), "../../packages/contracts/openapi.yaml");

describe("B19 OpenAPI contract", () => {
  const doc = yaml.parse(readFileSync(openapiPath, "utf8")) as {
    paths: Record<string, unknown>;
  };

  const expectedPaths = [
    "/api/v1/integrations/identity-providers",
    "/api/v1/sso/exchange",
    "/scim/v2/Users",
    "/scim/v2/ServiceProviderConfig",
    "/lti/launch",
    "/lti/jwks/{platform_id}",
    "/api/integration/v1/health",
    "/api/integration/v1/roster/upsert",
    "/api/integration/v1/results/published",
  ];

  it("registers enterprise identity and machine API paths", () => {
    for (const route of expectedPaths) {
      expect(doc.paths[route], route).toBeTruthy();
    }
  });
});
