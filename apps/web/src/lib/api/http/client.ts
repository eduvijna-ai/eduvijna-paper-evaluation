import { ApiError } from "./errors";
import { clearAccessToken, getAccessToken } from "@/lib/auth/token-store";

const API_BASE = (() => {
  const raw = process.env.NEXT_PUBLIC_API_BASE_URL;
  // Empty / unset → same-origin (Next rewrites to API_UPSTREAM). Avoids CORS for CVB.
  if (raw === undefined || raw === "" || raw === "same-origin") {
    return "";
  }
  return raw.replace(/\/$/, "");
})();

export type HttpMethod = "GET" | "POST" | "PATCH" | "PUT" | "DELETE";

export interface HttpRequestOptions {
  method?: HttpMethod;
  body?: unknown;
  /** multipart FormData — Content-Type left for the browser */
  formData?: FormData;
  signal?: AbortSignal;
  /** Override bearer (login before store is set) */
  token?: string | null;
  /** Skip Authorization header */
  anonymous?: boolean;
}

type UnauthorizedHandler = () => void;

let onUnauthorized: UnauthorizedHandler | null = null;

export function setUnauthorizedHandler(handler: UnauthorizedHandler | null): void {
  onUnauthorized = handler;
}

function parseEnvelope(payload: unknown): {
  message: string;
  code?: string;
  details?: unknown;
} {
  if (!payload || typeof payload !== "object") {
    return { message: "Request failed" };
  }
  const root = payload as Record<string, unknown>;
  const error = root.error;
  if (error && typeof error === "object") {
    const e = error as Record<string, unknown>;
    const message =
      typeof e.message === "string"
        ? e.message
        : typeof e.detail === "string"
          ? e.detail
          : "Request failed";
    const code = typeof e.code === "string" ? e.code : undefined;
    return { message, code, details: e.details ?? e };
  }
  if (typeof root.detail === "string") {
    return { message: root.detail };
  }
  if (typeof root.message === "string") {
    return { message: root.message };
  }
  return { message: "Request failed" };
}

export async function httpRequest<T>(
  path: string,
  options: HttpRequestOptions = {},
): Promise<T> {
  const headers = new Headers();
  headers.set("Accept", "application/json");

  const token = options.anonymous
    ? null
    : (options.token ?? getAccessToken());
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  let body: BodyInit | undefined;
  if (options.formData) {
    body = options.formData;
  } else if (options.body !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(options.body);
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method: options.method ?? "GET",
      headers,
      body,
      signal: options.signal,
    });
  } catch (err) {
    throw new ApiError({
      message: err instanceof Error ? err.message : "Network error",
      status: 0,
      kind: "network",
    });
  }

  const requestId =
    response.headers.get("x-request-id") ??
    response.headers.get("x-correlation-id") ??
    undefined;

  if (response.status === 204) {
    return undefined as T;
  }

  const text = await response.text();
  let json: unknown = undefined;
  if (text) {
    try {
      json = JSON.parse(text) as unknown;
    } catch {
      json = undefined;
    }
  }

  if (!response.ok) {
    const parsed = parseEnvelope(json);
    const kind = ApiError.kindFromStatus(response.status);
    if (response.status === 401) {
      clearAccessToken();
      onUnauthorized?.();
    }
    throw new ApiError({
      message: parsed.message,
      status: response.status,
      kind,
      code: parsed.code,
      details: parsed.details,
      requestId: requestId ?? undefined,
    });
  }

  if (!text) {
    return undefined as T;
  }
  return (json ?? (JSON.parse(text) as unknown)) as T;
}

export function getApiBaseUrl(): string {
  return API_BASE;
}
