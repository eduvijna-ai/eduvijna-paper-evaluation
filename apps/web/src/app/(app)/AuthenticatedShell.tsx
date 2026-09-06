"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { AppShell } from "@/components/layout/AppShell";
import { clearSession, getSession, isSessionExpired } from "@/lib/auth/session";
import { setUnauthorizedHandler } from "@/lib/api/http/client";
import { LoadingState } from "@/components/ui/FeedbackStates";

export function AuthenticatedShell({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const [ready, setReady] = useState(false);
  const [expired, setExpired] = useState(false);

  useEffect(() => {
    setUnauthorizedHandler(() => {
      clearSession();
      router.replace("/login?reason=session");
    });
    return () => setUnauthorizedHandler(null);
  }, [router]);

  useEffect(() => {
    const session = getSession();
    if (!session || isSessionExpired(session)) {
      setReady(false);
      setExpired(Boolean(session));
      clearSession();
      router.replace(session ? "/login?reason=expired" : "/login");
      return;
    }
    setExpired(false);
    setReady(true);
  }, [router, pathname]);

  if (!ready) {
    return (
      <div className="min-h-screen bg-slate-50" data-testid="auth-checking">
        <LoadingState
          label={expired ? "Session expired…" : "Checking session…"}
        />
      </div>
    );
  }

  return <AppShell>{children}</AppShell>;
}
