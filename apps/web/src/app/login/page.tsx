"use client";

import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { api, getApiMode, isApiError } from "@/lib/api";
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

const credentialsSchema = z.object({
  email: z.string().email("Enter a valid email"),
  password: z.string().min(1, "Password is required"),
});

const SSO_ERROR_COPY: Record<string, string> = {
  provider_not_configured: "Enterprise sign-in is not configured for this institution.",
  sso_rejected: "Enterprise authentication was rejected.",
  replay_detected: "That sign-in request was already used.",
  invalid_state: "The sign-in session expired. Try again.",
  user_inactive: "This account is deactivated.",
  identity_unlinked: "This identity is not linked to an EduVijna account.",
};

type Credentials = z.infer<typeof credentialsSchema>;

export default function LoginPage() {
  const [hydrated, setHydrated] = useState(false);
  const [mode, setMode] = useState<"mock" | "hybrid">("mock");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [tenantSlug, setTenantSlug] = useState("demo");
  const [ssoProviders, setSsoProviders] = useState<
    Array<{ id: string; name: string; protocol: string }>
  >([]);
  const [ssoBusy, setSsoBusy] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<Credentials>({
    resolver: zodResolver(credentialsSchema),
    defaultValues: { email: "", password: "" },
  });

  useEffect(() => {
    setHydrated(true);
    setMode(getApiMode());
  }, []);

  function handleDemoLogin(role: UserRole) {
    loginAs(role);
    window.location.assign("/dashboard");
  }

  async function onCredentials(values: Credentials) {
    setFormError(null);
    setSubmitting(true);
    try {
      await api.login(values.email.trim(), values.password);
      window.location.assign("/dashboard");
    } catch (err) {
      if (isApiError(err)) {
        if (err.kind === "unauthorized") {
          setFormError("Invalid credentials.");
        } else if (err.kind === "network" || err.kind === "server") {
          setFormError("Server unavailable. Try again later.");
        } else {
          setFormError(err.userMessage());
        }
      } else {
        setFormError("Unable to sign in. Try again.");
      }
      setSubmitting(false);
    }
  }

  async function discoverEnterprise() {
    setFormError(null);
    setSsoBusy(true);
    try {
      const result = await api.listPublicSsoProviders!(tenantSlug.trim() || "demo");
      setSsoProviders(result.items);
      if (result.items.length === 0) {
        setFormError(SSO_ERROR_COPY.provider_not_configured);
      }
    } catch (err) {
      setSsoProviders([]);
      setFormError(
        isApiError(err) ? err.userMessage() : SSO_ERROR_COPY.provider_not_configured,
      );
    } finally {
      setSsoBusy(false);
    }
  }

  function startEnterprise(providerId: string, protocol: string) {
    const slug = encodeURIComponent(tenantSlug.trim() || "demo");
    const path =
      protocol === "SAML"
        ? `/api/v1/sso/saml/start?tenant_slug=${slug}&provider_id=${providerId}`
        : `/api/v1/sso/oidc/start?tenant_slug=${slug}&provider_id=${providerId}`;
    window.location.assign(path);
  }

  const showDemo = mode === "mock";
  const showCredentials = mode === "hybrid" || mode === "mock";

  return (
    <div
      data-testid="login-page"
      data-hydrated={hydrated ? "true" : "false"}
      data-api-mode={mode}
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
            Evidence-backed marking with teacher control.
            {mode === "hybrid" ? (
              <> Sign in with your institution account.</>
            ) : (
              <>
                {" "}
                <strong className="font-medium text-amber-200/90">
                  Demo mode
                </strong>{" "}
                — mock domains active for CVB screens.
              </>
            )}
          </p>
        </div>

        {showCredentials && (
          <form
            data-testid="login-credentials-form"
            className="mt-10 max-w-md space-y-4 rounded-lg border border-slate-700 bg-slate-900/70 p-5"
            onSubmit={handleSubmit(onCredentials)}
          >
            <label className="block text-sm">
              <span className="font-medium text-slate-200">Email</span>
              <input
                data-testid="login-email"
                type="email"
                autoComplete="username"
                className="mt-1 w-full rounded-md border border-slate-600 bg-slate-950 px-3 py-2 text-white"
                {...register("email")}
              />
              {errors.email && (
                <span className="mt-1 block text-xs text-rose-300">
                  {errors.email.message}
                </span>
              )}
            </label>
            <label className="block text-sm">
              <span className="font-medium text-slate-200">Password</span>
              <input
                data-testid="login-password"
                type="password"
                autoComplete="current-password"
                className="mt-1 w-full rounded-md border border-slate-600 bg-slate-950 px-3 py-2 text-white"
                {...register("password")}
              />
              {errors.password && (
                <span className="mt-1 block text-xs text-rose-300">
                  {errors.password.message}
                </span>
              )}
            </label>
            {formError && (
              <p
                data-testid="login-error"
                className="rounded-md bg-rose-950/60 px-3 py-2 text-sm text-rose-200 ring-1 ring-rose-800"
              >
                {formError}
              </p>
            )}
            <button
              type="submit"
              data-testid="login-submit"
              disabled={submitting}
              className="w-full rounded-md bg-teal-700 px-3 py-2 text-sm font-medium text-white hover:bg-teal-600 disabled:opacity-60"
            >
              {submitting ? "Signing in…" : "Sign in"}
            </button>
            <div className="border-t border-slate-700 pt-4">
              <label className="block text-sm">
                <span className="font-medium text-slate-200">Institution slug</span>
                <input
                  data-testid="login-tenant-slug"
                  value={tenantSlug}
                  onChange={(event) => setTenantSlug(event.target.value)}
                  className="mt-1 w-full rounded-md border border-slate-600 bg-slate-950 px-3 py-2 text-white"
                />
              </label>
              <button
                type="button"
                data-testid="login-enterprise-discover"
                disabled={ssoBusy}
                onClick={() => void discoverEnterprise()}
                className="mt-3 w-full rounded-md border border-teal-700 px-3 py-2 text-sm font-medium text-teal-200 hover:bg-teal-950 disabled:opacity-60"
              >
                {ssoBusy ? "Looking up…" : "Enterprise SSO"}
              </button>
              <div data-testid="login-enterprise-providers" className="mt-3 space-y-2">
                {ssoProviders.map((provider) => (
                  <button
                    key={provider.id}
                    type="button"
                    data-testid={`login-sso-${provider.protocol.toLowerCase()}`}
                    onClick={() => startEnterprise(provider.id, provider.protocol)}
                    className="w-full rounded-md bg-slate-800 px-3 py-2 text-left text-sm text-white"
                  >
                    Continue with {provider.name}
                  </button>
                ))}
              </div>
            </div>
          </form>
        )}

        {showDemo && (
          <div className="mt-10 grid gap-3 sm:grid-cols-2">
            <p className="sm:col-span-2 text-xs uppercase tracking-wide text-slate-500">
              Or continue with demo role (mock only)
            </p>
            {ROLES.map((item) => (
              <button
                key={item.role}
                type="button"
                data-testid={`login-as-${item.role}`}
                onClick={() => handleDemoLogin(item.role)}
                className="rounded-lg border border-slate-700 bg-slate-900/70 p-4 text-left transition-colors hover:border-teal-600 hover:bg-slate-900"
              >
                <div className="text-sm font-semibold text-white">
                  {item.label}
                </div>
                <p className="mt-1 text-sm text-slate-400">{item.blurb}</p>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
