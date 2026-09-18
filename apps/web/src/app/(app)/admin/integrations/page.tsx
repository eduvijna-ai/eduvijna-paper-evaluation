"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { PageHeader } from "@/components/layout/PageHeader";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/FeedbackStates";
import { api, isApiError } from "@/lib/api";
import { A1_PERMISSIONS } from "@/lib/api/a1-types";
import { getSession, hasPermission } from "@/lib/auth/session";

type Tab = "identity" | "lti" | "credentials" | "webhooks";

export default function AdminIntegrationsPage() {
  const session = useMemo(() => getSession(), []);
  const canRead = hasPermission(session, A1_PERMISSIONS.integrationRead);
  const canManageCreds = hasPermission(
    session,
    A1_PERMISSIONS.integrationCredentialsManage,
  );
  const canManageHooks = hasPermission(
    session,
    A1_PERMISSIONS.integrationWebhookManage,
  );
  const [tab, setTab] = useState<Tab>("identity");
  const [secretNotice, setSecretNotice] = useState<string | null>(null);
  const queryClient = useQueryClient();

  const providers = useQuery({
    queryKey: ["b19-providers"],
    queryFn: () => api.listIdentityProviders!(),
    enabled: canRead,
  });
  const platforms = useQuery({
    queryKey: ["b19-lti"],
    queryFn: () => api.listLtiPlatforms!(),
    enabled: canRead,
  });
  const credentials = useQuery({
    queryKey: ["b19-credentials"],
    queryFn: () => api.listIntegrationCredentials!(),
    enabled: canRead,
  });
  const webhooks = useQuery({
    queryKey: ["b19-webhooks"],
    queryFn: () => api.listWebhookEndpoints!(),
    enabled: canRead,
  });
  const passbacks = useQuery({
    queryKey: ["b19-passbacks"],
    queryFn: () => api.listGradePassbacks!(),
    enabled: canRead,
  });

  const createCred = useMutation({
    mutationFn: () =>
      api.createIntegrationCredential!({
        name: "E2E credential",
        scopes: ["roster:read", "results:read"],
      }),
    onSuccess: (result) => {
      setSecretNotice(result.secret);
      void queryClient.invalidateQueries({ queryKey: ["b19-credentials"] });
    },
  });

  if (!canRead) {
    return (
      <ErrorState
        title="Permission denied"
        message="You do not have integration:read permission."
      />
    );
  }

  return (
    <div data-testid="b19-integrations-workspace" className="space-y-6">
      <PageHeader
        title="Enterprise integrations"
        description="SSO, LTI, machine credentials, and outbound webhooks."
      />
      <div className="flex flex-wrap gap-2">
        {(
          [
            ["identity", "Enterprise identity"],
            ["lti", "LMS / LTI"],
            ["credentials", "API credentials"],
            ["webhooks", "Webhooks"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            data-testid={`b19-tab-${id}`}
            onClick={() => setTab(id)}
            className={`rounded-md px-3 py-1.5 text-sm ${
              tab === id ? "bg-teal-700 text-white" : "border border-slate-200"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {secretNotice && (
        <p
          data-testid="b19-one-time-secret"
          className="rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-900"
        >
          One-time secret: {secretNotice}
        </p>
      )}

      {tab === "identity" && (
        <section data-testid="b19-identity-section">
          {providers.isLoading && <LoadingState />}
          {providers.isError && (
            <ErrorState
              title="Unable to load providers"
              message={
                isApiError(providers.error)
                  ? providers.error.userMessage()
                  : "Request failed"
              }
            />
          )}
          {providers.data && providers.data.items.length === 0 && (
            <EmptyState title="No identity providers" />
          )}
          <ul className="space-y-2">
            {providers.data?.items.map((item) => (
              <li
                key={item.id}
                data-testid={`b19-provider-${item.protocol.toLowerCase()}`}
                className="rounded-lg border border-slate-200 bg-white p-4"
              >
                <div className="font-medium">{item.name}</div>
                <div className="text-sm text-slate-500">
                  {item.protocol} · {item.enabled ? "enabled" : "disabled"} · JIT{" "}
                  {item.jit_enabled ? "on" : "off"}
                </div>
              </li>
            ))}
          </ul>
        </section>
      )}

      {tab === "lti" && (
        <section data-testid="b19-lti-section">
          {platforms.isLoading && <LoadingState />}
          {platforms.data?.items.length === 0 && (
            <EmptyState title="No LTI platforms" />
          )}
          <ul className="space-y-2">
            {platforms.data?.items.map((item) => (
              <li
                key={item.id}
                data-testid="b19-lti-platform"
                className="rounded-lg border border-slate-200 bg-white p-4"
              >
                <div className="font-medium">{item.name}</div>
                <div className="text-sm text-slate-500">{item.issuer}</div>
              </li>
            ))}
          </ul>
          <h3 className="mt-6 text-sm font-semibold">Grade passbacks</h3>
          <ul className="mt-2 space-y-2">
            {passbacks.data?.items.map((item) => (
              <li
                key={item.id}
                data-testid="b19-passback-row"
                className="rounded-lg border border-slate-200 bg-white p-3 text-sm"
              >
                {item.state} · {item.score}/{item.max_score}
              </li>
            ))}
          </ul>
        </section>
      )}

      {tab === "credentials" && (
        <section data-testid="b19-credentials-section">
          {canManageCreds && (
            <button
              type="button"
              data-testid="b19-create-credential"
              onClick={() => createCred.mutate()}
              className="mb-4 rounded-md bg-teal-700 px-3 py-2 text-sm text-white"
            >
              Create credential
            </button>
          )}
          {credentials.data?.items.length === 0 && (
            <EmptyState title="No API credentials" />
          )}
          <ul className="space-y-2">
            {credentials.data?.items.map((item) => (
              <li
                key={item.id}
                data-testid="b19-credential-row"
                className="rounded-lg border border-slate-200 bg-white p-4 text-sm"
              >
                {item.name} · {item.key_prefix} · {item.scopes.join(", ")}
              </li>
            ))}
          </ul>
        </section>
      )}

      {tab === "webhooks" && (
        <section data-testid="b19-webhooks-section">
          {webhooks.data?.items.length === 0 && (
            <EmptyState title="No webhook endpoints" />
          )}
          <ul className="space-y-2">
            {webhooks.data?.items.map((item) => (
              <li
                key={item.id}
                data-testid="b19-webhook-row"
                className="rounded-lg border border-slate-200 bg-white p-4 text-sm"
              >
                {item.name} · {item.destination_url}
                {canManageHooks ? "" : ""}
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
