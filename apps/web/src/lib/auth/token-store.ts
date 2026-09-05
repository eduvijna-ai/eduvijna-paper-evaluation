/**
 * In-memory access-token holder.
 *
 * CVB technical debt: A1 currently returns a bearer JWT with no HttpOnly cookie
 * session. We keep the token in memory and optionally mirror metadata to
 * sessionStorage (see session.ts) so a refresh does not immediately log out.
 * Prefer migrating to secure cookie sessions when backend supports it.
 *
 * Never log token values.
 */

let accessToken: string | null = null;

export function getAccessToken(): string | null {
  return accessToken;
}

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function clearAccessToken(): void {
  accessToken = null;
}
