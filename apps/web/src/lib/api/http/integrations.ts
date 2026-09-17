import { httpRequest } from "./client";
import type { TokenResponse } from "../a1-types";
import type { AuthSession } from "@/lib/types/domain";
import { setBearerSession } from "@/lib/auth/session";
import { PlatformHttpApi } from "./platform";
import type {
  GradePassbackList,
  IdentityProvider,
  IdentityProviderList,
  IntegrationCredential,
  IntegrationCredentialList,
  IntegrationCredentialSecretResponse,
  LtiPlatformList,
  PublicSsoProviderList,
  WebhookDelivery,
  WebhookDeliveryList,
  WebhookEndpointList,
  WebhookEndpointSecretResponse,
} from "@/lib/types/domain";

function asCredentialSecret(
  raw: Record<string, unknown>,
): IntegrationCredentialSecretResponse {
  const secret = String(raw.secret ?? "");
  return {
    credential: raw as unknown as IntegrationCredential,
    secret,
  };
}

export const IntegrationsHttpApi = {
  listIdentityProviders() {
    return httpRequest<IdentityProviderList>("/api/v1/integrations/identity-providers");
  },
  createIdentityProvider(input: Record<string, unknown>) {
    return httpRequest<IdentityProvider>("/api/v1/integrations/identity-providers", {
      method: "POST",
      body: input,
    });
  },
  listPublicSsoProviders(tenantSlug: string) {
    return httpRequest<PublicSsoProviderList>(
      `/api/v1/sso/providers?tenant_slug=${encodeURIComponent(tenantSlug)}`,
      { anonymous: true },
    );
  },
  async exchangeSsoCode(exchangeCode: string): Promise<AuthSession> {
    const token = await httpRequest<TokenResponse>("/api/v1/sso/exchange", {
      method: "POST",
      body: { exchange_code: exchangeCode },
      anonymous: true,
    });
    setBearerSession(
      {
        userId: token.user.id,
        displayName: token.user.display_name,
        email: token.user.email,
        role: (token.user.roles?.[0] as AuthSession["role"]) ?? "TEACHER",
        roles: token.user.roles ?? [],
        permissions: token.user.permissions ?? [],
        tenantId: token.user.tenant_id,
        institutionId: "",
        expiresAt: Date.now() + token.expires_in * 1000,
        authMode: "bearer",
      },
      token.access_token,
    );
    return PlatformHttpApi.getCurrentUser();
  },
  listLtiPlatforms() {
    return httpRequest<LtiPlatformList>("/api/v1/integrations/lti-platforms");
  },
  listIntegrationCredentials() {
    return httpRequest<IntegrationCredentialList>("/api/v1/integrations/credentials");
  },
  async createIntegrationCredential(input: { name: string; scopes: string[] }) {
    const raw = await httpRequest<Record<string, unknown>>(
      "/api/v1/integrations/credentials",
      { method: "POST", body: input },
    );
    return asCredentialSecret(raw);
  },
  async rotateIntegrationCredential(id: string) {
    const raw = await httpRequest<Record<string, unknown>>(
      `/api/v1/integrations/credentials/${id}/rotate`,
      { method: "POST" },
    );
    return asCredentialSecret(raw);
  },
  revokeIntegrationCredential(id: string) {
    return httpRequest<IntegrationCredential>(
      `/api/v1/integrations/credentials/${id}/revoke`,
      { method: "POST" },
    );
  },
  listWebhookEndpoints() {
    return httpRequest<WebhookEndpointList>("/api/v1/integrations/webhooks");
  },
  async createWebhookEndpoint(input: {
    name: string;
    destination_url: string;
    event_types: string[];
  }) {
    const raw = await httpRequest<Record<string, unknown>>(
      "/api/v1/integrations/webhooks",
      { method: "POST", body: input },
    );
    return {
      endpoint: raw as unknown as WebhookEndpointSecretResponse["endpoint"],
      signing_secret: String(raw.signing_secret ?? ""),
    };
  },
  listWebhookDeliveries(endpointId: string) {
    return httpRequest<WebhookDeliveryList>(
      `/api/v1/integrations/webhooks/${endpointId}/deliveries`,
    );
  },
  retryWebhookDelivery(deliveryId: string) {
    return httpRequest<WebhookDelivery>(
      `/api/v1/integrations/webhook-deliveries/${deliveryId}/retry`,
      { method: "POST" },
    );
  },
  listGradePassbacks() {
    return httpRequest<GradePassbackList>("/api/v1/integrations/grade-passbacks");
  },
};
