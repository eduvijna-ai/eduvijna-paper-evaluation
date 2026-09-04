"use client";

import { useEffect, useState } from "react";
import { loginAs } from "@/lib/auth/session";
import type { UserRole } from "@/lib/types/enums";

const ROLES: Array<{ role: UserRole; label: string; blurb: string }> = [
  {
    role: "TEACHER",
    label: "Teacher / Evaluator",
    blurb: "Review identity, mapping, and evaluation decisions.",
  },
  {
    role: "PLATFORM_ADMIN",
    label: "Platform Admin",
    blurb: "Configure curriculum, users, and institutional settings.",
  },
  {
    role: "STUDENT",
    label: "Student (viewer)",
    blurb: "View reports and adaptive learning paths.",
  },
  {
    role: "PARENT",
    label: "Parent (viewer)",
    blurb: "View plain-language progress summaries.",
  },
];

export default function LoginPage() {
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    setHydrated(true);
  }, []);

  function handleLogin(role: UserRole) {
    loginAs(role);
    // Hard navigation so AuthenticatedShell always reads a committed session.
    window.location.assign("/dashboard");
  }

  return (
    <div
      data-testid="login-page"
      data-hydrated={hydrated ? "true" : "false"}
      className="relative min-h-screen overflow-hidden bg-slate-950"
    >
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_top,_#134e4a_0%,_transparent_55%),linear-gradient(180deg,#0f172a_0%,#020617_100%)]"
      />
      <div className="relative mx-auto flex min-h-screen max-w-5xl flex-col justify-center px-6 py-16">
        <div className="max-w-xl">
          <p className="text-sm font-medium uppercase tracking-[0.2em] text-teal-300/90">
            EduVijna
          </p>
          <h1 className="mt-3 font-display text-4xl font-semibold tracking-tight text-white sm:text-5xl">
            Paper Evaluation
          </h1>
          <p className="mt-4 text-base text-slate-300 leading-relaxed">
            Evidence-backed marking with teacher control. Demo login stores a
            local session only — no production credentials.
          </p>
        </div>

        <div className="mt-10 grid gap-3 sm:grid-cols-2">
          {ROLES.map((item) => (
            <button
              key={item.role}
              type="button"
              data-testid={`login-as-${item.role}`}
              onClick={() => handleLogin(item.role)}
              className="rounded-lg border border-slate-700 bg-slate-900/70 p-4 text-left transition-colors hover:border-teal-600 hover:bg-slate-900"
            >
              <div className="text-sm font-semibold text-white">
                {item.label}
              </div>
              <p className="mt-1 text-sm text-slate-400">{item.blurb}</p>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
