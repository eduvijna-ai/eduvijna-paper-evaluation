# B19 — Enterprise Identity & Interoperability

Implementation of APP-015 / Issue #100 for PEV-054 and PEV-055. Release-state
classifications in `REQUIREMENTS_REGISTER.md` remain `FUTURE_ENTERPRISE`.
PEV-056 and PEV-057 remain deferred.

## Architecture

B19 extends the existing modular monolith. Enterprise SSO resolves into the
current `User` / `UserRole` / `Permission` / JWT `AuthContext` path. Machine
APIs use hashed `IntegrationCredential` rows, not fake user accounts. Outbound
webhooks use a transactional outbox (`OutboundEvent` + `WebhookDelivery`).

No Kubernetes, Temporal, Kafka, microservice split, GraphQL, Firebase,
Supabase, or separate auth/SCIM/LTI/webhook services were introduced.

## Migration

- File: `database/migrations/versions/20260917_0021_b19_enterprise_identity_interoperability.py`
- `down_revision = "20260910_0020"`
- Adds `users.auth_version` and B19 identity / LTI / roster / passback / webhook tables
- One Alembic head: `20260917_0021`

## Identity model

External accounts bind on `(tenant, provider, immutable subject)`. Email linking
requires `VERIFIED_EMAIL_EXPLICIT` plus a verified email claim. JIT is opt-in.
SSO/LTI role mapping may assign only existing non-admin `ROLE_CODES`.

SCIM create never silently attaches a new `externalId` to an existing local
User solely because `userName` matches that user's email. With the SCIM binding
provider's `account_linking_policy=NONE`, that collision returns HTTP `409`
(`identity_link_required` / SCIM `uniqueness`) and requires explicit governed
identity linking. Already-bound external subjects remain authoritative and
immutable when `userName`/email changes.

## OIDC / SAML / SCIM

OIDC Authorization Code + PKCE, state/nonce, JWKS signature verification, replay
markers, and a one-time `exchange_code` browser handoff (no access token in the
URL). SAML 2.0 uses `signxml` for XML signature verification (assertion-level
signature required). SCIM 2.0 Users create/list/get/PUT/PATCH with
deactivation incrementing `auth_version` so existing JWTs fail.

## LTI 1.3 / AGS / NRPS

LTI Advantage login + launch JWT validation, resource-link persistence, AGS
score POST derived only from current `PublishedResult.status == "PUBLISHED"`,
and NRPS membership ingest through the shared roster upsert. Launch requires a
persisted `LtiResourceLink` with a non-null EduVijna `assessment_id`; a matching
platform/context/resource row with `assessment_id=None` is rejected as
`unbound_resource`. Launch never auto-creates or auto-binds assessments from
claims.

## SIS / public machine API

Versioned surface: `/api/integration/v1/*` authenticated by
`Authorization: Bearer <integration-secret>`. Scopes implemented:
`roster:read`, `roster:write`, `results:read`, plus `scim` for SCIM.

## Webhooks / outbox / SSRF

HMAC-SHA256 (`v1=` + `timestamp.raw_body`). Destinations are validated against
loopback/private/link-local/multicast unless an explicit local/test escape
hatch is enabled. Delivery rows are written in the same DB transaction as the
`OutboundEvent`; Celery task `webhooks.deliver_due` (worker `--beat` every 2s)
performs network POST after commit. Multi-endpoint events use `PARTIAL` until
every delivery is terminal. Retries persist attempts and reach terminal failure
after five attempts. Manual retry is permissioned and audited. The deterministic
receiver verifies HMAC with `B19_TEST_WEBHOOK_SIGNING_SECRET` and never with a
null secret.

SAML ACS checks Response `Destination` and `SubjectConfirmationData.Recipient`
against the configured ACS, plus SP-initiated `InResponseTo`. LTI launch binds
the signed `target_link_uri` to the initiated transaction and requires a
pre-associated assessment resource link. AGS passback derives the learner from
`ExternalRosterIdentity` for the PublishedResult student. SCIM requires a
non-email `externalId` as the immutable subject and does not email-link local
accounts.

## Secret storage

`INTEGRATION_SECRET_ENCRYPTION_KEY` (Fernet). Local/test may derive from
`AUTH_TOKEN_SECRET`. Machine/SCIM secrets are SHA-256 hashed with
constant-time compare. OIDC client secrets, SAML certs, webhook secrets, and
LTI private keys are encrypted at rest. Secrets are never listed or logged.

## Frontend

- Existing email/password login preserved
- Institution slug + Enterprise SSO discovery
- `/sso/complete` exchanges a one-time code into the normal bearer session
- `/admin/integrations` for providers, LTI, credentials, webhooks

## Deterministic fake providers

`/api/v1/b19-test/*` is available only when `B19_TEST_PROVIDERS_ENABLED` or
`APP_ENV` is `local`/`test`. It emulates OIDC, SAML, LTI, NRPS, AGS, and a
webhook receiver. Disabled by default in production configuration. The gated
`POST /api/v1/b19-test/users/{id}/local-password` fixture attaches a local
password to a SCIM-provisioned user for Real E2E revocation proofs without
implicit email linking.

## Tests / CI

Backend pytest covers OIDC, SCIM (including no silent email binding), machine
credentials, LTI (including assessment-unbound rejection), roster, AGS, and
webhooks. Real E2E: `apps/web/e2e/real/zz-b19-enterprise-integrations.spec.ts`
(never skipped) after `python -m app.cli.seed_b19_e2e_enterprise`.

Final remediation head and authoritative CI run are recorded after the six-job
SUCCESS workflow completes; independent ChatGPT audit acceptance is not claimed
here.

## Deferred

PEV-056 Multi-Subject Expansion and PEV-057 Multilingual Handwriting.
SCIM Groups / complex group-to-role sync is out of scope.
Legacy LTI 1.1 is not implemented.
