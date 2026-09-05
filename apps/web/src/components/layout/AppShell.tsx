"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  BookOpen,
  ClipboardList,
  FileStack,
  LayoutDashboard,
  LineChart,
  LogOut,
  Settings,
  Upload,
  Users,
  GraduationCap,
} from "lucide-react";
import { clearSession, getSession } from "@/lib/auth/session";
import { cn } from "@/lib/utils/cn";
import { useEffect, useState } from "react";
import type { DemoSession } from "@/lib/types/domain";

const navItems = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard, testId: "nav-dashboard" },
  { href: "/assessments", label: "Assessments", icon: ClipboardList, testId: "nav-assessments" },
  { href: "/submissions", label: "Submissions", icon: FileStack, testId: "nav-submissions" },
  { href: "/submissions/upload", label: "Upload", icon: Upload, testId: "nav-upload" },
  { href: "/students", label: "Students", icon: Users, testId: "nav-students" },
  { href: "/curriculum", label: "Curriculum", icon: BookOpen, testId: "nav-curriculum" },
  {
    href: "/learning/student-demo-001",
    label: "Adaptive learning",
    icon: GraduationCap,
    testId: "nav-adaptive-learning",
  },
  {
    href: "/analytics/assessments/assess-demo-001",
    label: "Analytics",
    icon: LineChart,
    testId: "nav-analytics",
  },
  { href: "/admin", label: "Admin", icon: Settings, testId: "nav-admin" },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside
      data-testid="sidebar"
      className="flex w-60 shrink-0 flex-col border-r border-slate-200 bg-slate-950 text-slate-100"
    >
      <div className="border-b border-slate-800 px-4 py-5">
        <Link href="/dashboard" className="block">
          <div className="text-lg font-semibold tracking-tight text-white">
            EduVijna
          </div>
          <div className="text-xs text-slate-400 mt-0.5">
            Paper Evaluation
          </div>
        </Link>
      </div>
      <nav className="flex-1 space-y-0.5 p-2 overflow-y-auto">
        {navItems.map((item) => {
          const active =
            pathname === item.href ||
            (item.href !== "/dashboard" && pathname.startsWith(item.href));
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              data-testid={item.testId}
              className={cn(
                "flex items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-colors",
                active
                  ? "bg-teal-700/30 text-white"
                  : "text-slate-300 hover:bg-slate-900 hover:text-white",
              )}
            >
              <Icon className="h-4 w-4 shrink-0 opacity-80" aria-hidden />
              {item.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}

export function TopBar() {
  const router = useRouter();
  const [session, setSessionState] = useState<DemoSession | null>(null);

  useEffect(() => {
    setSessionState(getSession());
  }, []);

  return (
    <header
      data-testid="topbar"
      className="flex h-14 items-center justify-between border-b border-slate-200 bg-white px-4 sm:px-6"
    >
      <div className="text-sm text-slate-500">
        Client Validation Build · Mock API
      </div>
      <div className="flex items-center gap-3">
        {session && (
          <div className="text-right hidden sm:block">
            <div className="text-sm font-medium text-slate-800">
              {session.displayName}
            </div>
            <div className="text-xs text-slate-500">{session.role}</div>
          </div>
        )}
        <button
          type="button"
          data-testid="logout-button"
          onClick={() => {
            clearSession();
            router.push("/login");
          }}
          className="inline-flex items-center gap-1.5 rounded-md border border-slate-200 px-2.5 py-1.5 text-sm text-slate-700 hover:bg-slate-50"
        >
          <LogOut className="h-3.5 w-3.5" />
          Sign out
        </button>
      </div>
    </header>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div data-testid="app-shell" className="flex min-h-screen bg-slate-50">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar />
        <main className="flex-1 overflow-auto p-4 sm:p-6">{children}</main>
      </div>
    </div>
  );
}
