import type { ApiClient } from "./types";
import { MockEduVijnaApi } from "./mock/adapter";
import { HttpEduVijnaApi } from "./http/adapter";

/**
 * API mode is selected via NEXT_PUBLIC_API_MODE.
 * Default: mock (synthetic fixtures for CVB frontend).
 * http: operational health/ready/version live; domain methods throw until OpenAPI lands.
 */
export function getApiMode(): "mock" | "http" {
  const mode = process.env.NEXT_PUBLIC_API_MODE ?? "mock";
  return mode === "http" ? "http" : "mock";
}

export function createApiClient(): ApiClient {
  return getApiMode() === "http" ? HttpEduVijnaApi : MockEduVijnaApi;
}

export const api = createApiClient();

export { MockEduVijnaApi, HttpEduVijnaApi };
