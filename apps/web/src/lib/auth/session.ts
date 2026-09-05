"use client";

/**
 * DEMO / MOCK authentication only (B0).
 * Not production-safe. B1 will integrate A1 backend auth
 * (`POST /api/v1/auth/login`, `GET /api/v1/auth/me` + bearer token).
 * Do not invent refresh-token behavior here.
 */
import type { DemoSession } from "@/lib/types/domain";
import type { UserRole } from "@/lib/types/enums";

const SESSION_KEY = "eduvijna_demo_session";

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

export function getSession(): DemoSession | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(SESSION_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as DemoSession;
  } catch {
    return null;
  }
}

export function setSession(session: DemoSession): void {
  window.localStorage.setItem(SESSION_KEY, JSON.stringify(session));
  document.cookie = `eduvijna_demo_role=${session.role}; path=/; SameSite=Lax`;
}

export function clearSession(): void {
  window.localStorage.removeItem(SESSION_KEY);
  document.cookie =
    "eduvijna_demo_role=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT";
}

export function loginAs(role: UserRole): DemoSession {
  const session = DEMO_USERS[role];
  setSession(session);
  return session;
}
