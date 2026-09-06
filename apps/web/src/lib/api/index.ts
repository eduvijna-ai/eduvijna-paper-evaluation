export {
  api,
  createApiClient,
  getApiMode,
  MockEduVijnaApi,
  HybridEduVijnaApi,
  PlatformHttpApi,
} from "./client";
export type { ApiClient, OperationalHealth } from "./types";
export type { ApiMode } from "./client";
export type * from "./a1-types";
export { ApiError, isApiError } from "./http/errors";
export { getApiCapabilities } from "./capabilities";
export type { ApiCapabilities, DomainCapability } from "./capabilities";
