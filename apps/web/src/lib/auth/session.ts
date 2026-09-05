"use client";

/**
 * Session helpers for B0 mock demo auth and B1 bearer auth.
 *
 * Token persistence (bearer mode):
 * - Access token is held in memory (`token-store`) and mirrored to sessionStorage
 *   under SESSION_META_KEY.payload.accessToken for CVB page-refresh survival.
 * - This is NOT production architecture. Prefer HttpOnly secure cookies when A1
 *   adds cookie sessions. Documented in B1_PLATFORM_API_INTEGRATION_REPORT.md.
 * - Passwords are never stored. Tokens must never be logged.
 */
import type { AuthSession, DemoSession } from "@/lib/types/domain";
import type { UserRole } from "@/lib/types/enums";
import {
  clearAccessToken,
  getAccessToken,
  setAccessToken,
} from "@/lib/auth/token-store";

const DEMO_SESSION_KEY = "eduvijna_demo_session";
const SESSION_META_KEY = "eduvijna_auth_session";

export const DEMO_USERS: Record<
  UserRole,
  Omit<DemoSession, "role"> & { role: UserRole }
> = {
  PLATFORM_ADMIN: {
    userId: "user-admin-001",
    displayName: "Demo Admin",
    email: "admin@demo.eduvijna.local",
    role: "PLATFORM_ADMIN",
    tenantId: "tenant-demo-001",
    institutionId: "inst-demo-001",
  },
  TEACHER: {
    userId: "user-teacher-001",
    displayName: "Demo Teacher",
    email: "teacher@demo.eduvijna.local",
    role: "TEACHER",
    tenantId: "tenant-demo-001",
    institutionId: "inst-demo-001",
  },
  STUDENT: {
    userId: "user-student-001",
    displayName: "Demo Student Viewer",
    email: "student@demo.eduvijna.local",
    role: "STUDENT",
    tenantId: "tenant-demo-001",
    institutionId: "inst-demo-001",
  },
  PARENT: {
    userId: "user-parent-001",
    displayName: "Demo Parent Viewer",
    email: "parent@demo.eduvijna.local",
    role: "PARENT",
    tenantId: "tenant-demo-001",
    institutionId: "inst-demo-001",
  },
};

function isBrowser(): boolean {
  return typeof window !== "undefined";
}

function demoToAuth(session: DemoSession): AuthSession {
  return {
    userId: session.userId,
    displayName: session.displayName,
    email: session.email,
    role: session.role,
    roles: [session.role],
    permissions: [],
    tenantId: session.tenantId,
    institutionId: session.institutionId,
    expiresAt: Date.now() + 8 * 60 * 60 * 1000,
    authMode: "demo",
  };
}

export function getSession(): AuthSession | null {
  if (!isBrowser()) return null;

  const metaRaw = window.sessionStorage.getItem(SESSION_META_KEY);
  if (metaRaw) {
    try {
      const parsed = JSON.parse(metaRaw) as AuthSession & {
        accessToken?: string;
      };
      if (parsed.expiresAt && parsed.expiresAt < Date.now()) {
        clearSession();
        return null;
      }
      if (parsed.authMode === "bearer" && parsed.accessToken) {
        if (!getAccessToken()) {
          setAccessToken(parsed.accessToken);
        }
      }
      const { accessToken: _t, ...session } = parsed;
      void _t;
      return session;
    } catch {
      /* fall through */
    }
  }

  const demoRaw = window.localStorage.getItem(DEMO_SESSION_KEY);
  if (!demoRaw) return null;
  try {
    return demoToAuth(JSON.parse(demoRaw) as DemoSession);
  } catch {
    return null;
  }
}

export function setBearerSession(
  session: AuthSession,
  accessToken: string,
): void {
  setAccessToken(accessToken);
  const payload = { ...session, accessToken, authMode: "bearer" as const };
  window.sessionStorage.setItem(SESSION_META_KEY, JSON.stringify(payload));
  window.localStorage.removeItem(DEMO_SESSION_KEY);
}

export function setDemoSession(session: DemoSession): void {
  clearAccessToken();
  window.localStorage.setItem(DEMO_SESSION_KEY, JSON.stringify(session));
  document.cookie = `eduvijna_demo_role=${session.role}; path=/; SameSite=Lax`;
  window.sessionStorage.removeItem(SESSION_META_KEY);
}

/** @deprecated use setDemoSession — kept for B0 call sites during transition */
export function setSession(session: DemoSession): void {
  setDemoSession(session);
}

export function clearSession(): void {
  clearAccessToken();
  if (!isBrowser()) return;
  window.localStorage.removeItem(DEMO_SESSION_KEY);
  window.sessionStorage.removeItem(SESSION_META_KEY);
  document.cookie =
    "eduvijna_demo_role=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT";
}

export function loginAs(role: UserRole): AuthSession {
  const session = DEMO_USERS[role];
  setDemoSession(session);
  return demoToAuth(session);
}

export function hasPermission(
  session: AuthSession | null,
  code: string,
): boolean {
  if (!session) return false;
  if (session.authMode === "demo") {
    // Demo roles: admin/teacher treated as fully permitted for CVB convenience.
    return (
      session.role === "PLATFORM_ADMIN" ||
      session.role === "TEACHER" ||
      session.permissions.includes(code)
    );
  }
  return session.permissions.includes(code);
}

export function isSessionExpired(session: AuthSession | null): boolean {
  if (!session) return true;
  return session.expiresAt < Date.now();
}
