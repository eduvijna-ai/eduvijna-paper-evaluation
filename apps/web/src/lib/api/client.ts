import type { ApiClient } from "./types";
import { mockApiClient } from "./mock/adapter";

/**
 * API mode is selected via NEXT_PUBLIC_API_MODE.
 * Default: mock (synthetic fixtures for CVB frontend).
 * Future: http adapter against OpenAPI domain endpoints.
 */
export function getApiMode(): "mock" | "http" {
  const mode = process.env.NEXT_PUBLIC_API_MODE ?? "mock";
  return mode === "http" ? "http" : "mock";
}

export function createApiClient(): ApiClient {
  const mode = getApiMode();
  if (mode === "http") {
    // Domain OpenAPI endpoints are not yet available — fall back to mock.
    // See docs/engineering/FRONTEND_CONTRACT_REQUESTS.md
    return mockApiClient;
  }
  return mockApiClient;
}

export const api = createApiClient();
