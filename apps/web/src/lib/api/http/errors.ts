/**
 * Typed API errors from A1 ErrorEnvelope (or transport failures).
 * Never include secrets/tokens in messages shown to users.
 */

export type ApiErrorKind =
  | "validation"
  | "unauthorized"
  | "forbidden"
  | "not_found"
  | "conflict"
  | "unprocessable"
  | "server"
  | "network"
  | "unknown";

export class ApiError extends Error {
  readonly status: number;
  readonly kind: ApiErrorKind;
  readonly code?: string;
  readonly details?: unknown;
  readonly requestId?: string;

  constructor(opts: {
    message: string;
    status: number;
    kind: ApiErrorKind;
    code?: string;
    details?: unknown;
    requestId?: string;
  }) {
    super(opts.message);
    this.name = "ApiError";
    this.status = opts.status;
    this.kind = opts.kind;
    this.code = opts.code;
    this.details = opts.details;
    this.requestId = opts.requestId;
  }

  static kindFromStatus(status: number): ApiErrorKind {
    if (status === 401) return "unauthorized";
    if (status === 403) return "forbidden";
    if (status === 404) return "not_found";
    if (status === 409) return "conflict";
    if (status === 422) return "unprocessable";
    if (status >= 500) return "server";
    if (status === 400) return "validation";
    return "unknown";
  }

  /** Safe user-facing copy — no stack/trace. */
  userMessage(): string {
    switch (this.kind) {
      case "unauthorized":
        return "Your session expired or credentials are invalid. Please sign in again.";
      case "forbidden":
        return "You do not have permission to perform this action.";
      case "not_found":
        return "The requested resource was not found.";
      case "conflict":
        return "This change conflicts with an existing record.";
      case "unprocessable":
      case "validation":
        return this.message || "Please check the form and try again.";
      case "network":
        return "Unable to reach the server. Check your connection and try again.";
      case "server":
        return "The server encountered an error. Try again later.";
      default:
        return "Something went wrong. Please try again.";
    }
  }
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}
