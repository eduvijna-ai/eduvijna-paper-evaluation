import type { ApiClient } from "./types";
import { MockEduVijnaApi } from "./mock/adapter";
import { HybridEduVijnaApi } from "./hybrid/adapter";

/**
 * API mode:
 * - mock (default for Playwright B0): all domains mock + demo auth
 * - hybrid (B3 default for local real APIs): A1/A2/B3 HTTP + mapping/eval/analytics mock
 *
 * Do not use a single boolean for all domains — hybrid routes by capability.
 */
export type ApiMode = "mock" | "hybrid";

export function getApiMode(): ApiMode {
  const mode = process.env.NEXT_PUBLIC_API_MODE ?? "mock";
  if (mode === "hybrid" || mode === "http") {
    // "http" accepted as alias for hybrid during B1 (A2+ domains still mock).
    return "hybrid";
  }
  return "mock";
}

export function createApiClient(): ApiClient {
  return getApiMode() === "hybrid" ? HybridEduVijnaApi : MockEduVijnaApi;
}

export const api = createApiClient();

export { MockEduVijnaApi, HybridEduVijnaApi };
export { PlatformHttpApi } from "./http/platform";
