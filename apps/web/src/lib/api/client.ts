import type { ApiClient } from "./types";
import { MockEduVijnaApi } from "./mock/adapter";
import { HybridEduVijnaApi } from "./hybrid/adapter";

/**
 * API mode:
 * - mock (default for Playwright B0): all domains mock + demo auth
 * - hybrid (B9 default for local real APIs): A1–B9 HTTP including learning
 *
 * Do not use a single boolean for all domains — hybrid routes by capability.
 *
 * Production builds must not silently ship the mock adapter.
 * Local MAT / Playwright may still use mock or hybrid via explicit env.
 */
export type ApiMode = "mock" | "hybrid";

export function assertApiModeAllowed(
  mode: ApiMode,
  env: {
    nodeEnv?: string;
    allowProductionMock?: string;
  } = {
    nodeEnv: process.env.NODE_ENV,
    allowProductionMock: process.env.ALLOW_PRODUCTION_MOCK_API,
  },
): void {
  if (
    env.nodeEnv === "production" &&
    mode === "mock" &&
    env.allowProductionMock !== "1"
  ) {
    throw new Error(
      "NEXT_PUBLIC_API_MODE=mock is forbidden in production builds. Set hybrid (or http) and a real API upstream.",
    );
  }
}

export function getApiMode(): ApiMode {
  const mode = process.env.NEXT_PUBLIC_API_MODE ?? "mock";
  const resolved: ApiMode =
    mode === "hybrid" || mode === "http" ? "hybrid" : "mock";
  assertApiModeAllowed(resolved);
  return resolved;
}

export function createApiClient(): ApiClient {
  return getApiMode() === "hybrid" ? HybridEduVijnaApi : MockEduVijnaApi;
}

export const api = createApiClient();

export { MockEduVijnaApi, HybridEduVijnaApi };
export { PlatformHttpApi } from "./http/platform";
