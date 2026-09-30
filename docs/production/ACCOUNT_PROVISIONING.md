# Account Provisioning (Production)

**Product:** EduVijna Paper Evaluation  
**Last updated:** 2026-09-30  
**Related:** [SECURITY_PRIVACY_READINESS.md](./SECURITY_PRIVACY_READINESS.md), [SECURITY_BASELINE.md](../architecture/SECURITY_BASELINE.md), B19 enterprise identity surfaces, `app.cli.seed_dev`

---

## 1. Purpose

Describe **supported** production account mechanisms. Do **not** invent product features (e.g. email invitation flows) that are not implemented.

---

## 2. Explicit: `seed_dev` is local/demo only

`docker compose exec api python -m app.cli.seed_dev` (or `infra/scripts/seed.*`) creates synthetic demo tenant data, including:

- Tenant slug `demo`  
- Email `admin@demo.eduvijna.local` with demo password constants in `seed_dev.py`  
- Additional demo enterprise users  

**Forbidden in production / pilot SoT environments** as the provisioning mechanism. Same for other `seed_*` E2E CLIs.

---

## 3. Supported mechanisms

### 3.1 Local password users (JWT)

| Capability | Status |
|------------|--------|
| Login | `POST /api/v1/auth/login` with email/password + tenant slug |
| Password hashing | Argon2 via `app.core.security` |
| Production admin “create password user” HTTP API | **No dedicated general-purpose invitation/admin-create-user API is documented as a product provisioning surface for production.** Do not invent one in this runbook. |
| How password users appear | Local/dev seeds and tests; SSO/SCIM-provisioned users typically have `password_hash=None` until a governed break-glass procedure attaches a password (test helper exists under gated B19 test providers — **not** for production) |

**Production guidance:** Prefer SSO/SCIM for institutional users. If a break-glass local password admin is required, define an **ops-controlled** procedure (DB/runbook under dual control) without committing passwords to git — details EXTERNAL_INPUT_REQUIRED for ownership.

### 3.2 SSO (OIDC / SAML) — B19 / PEV-054

| Capability | Notes |
|------------|-------|
| Protocols | Tenant-configured OIDC (Auth Code + PKCE) and SAML 2.0 |
| Provisioning on login | `resolve_or_provision_user` style linking — tenant-bound |
| Production IdP metadata & credentials | **EXTERNAL_INPUT_REQUIRED** |
| Formal register state | PEV-054 remains `FUTURE_ENTERPRISE` classification even when implementation exists |

### 3.3 SCIM 2.0 — B19 / PEV-054

| Capability | Notes |
|------------|-------|
| Endpoints | `/scim/v2/Users` (create/list/get/put/patch) plus discovery docs |
| Auth | Integration / machine credentials (tenant-scoped) |
| Lifecycle | Create, update, activate/deactivate; retain historical attribution |
| Password | SCIM-created users are not password-login users by default (`password_hash=None`) |

---

## 4. What not to invent

- Email invitation / magic-link onboarding product  
- Self-service signup for institutions  
- Treating demo passwords as production credentials  
- Enabling `B19_TEST_PROVIDERS_ENABLED` to “attach passwords” in production  

---

## 5. Pilot bootstrap checklist (when deploy authorized)

1. Create/configure production tenant(s) via authorized ops path (not `seed_dev`).  
2. Configure IdP (OIDC and/or SAML) **or** SCIM client — EXTERNAL_INPUT_REQUIRED credentials.  
3. Provision initial `INSTITUTION_ADMIN` (or equivalent) via SSO first login or SCIM.  
4. Verify login; verify deactivated user cannot login.  
5. Document break-glass contact.  
6. Run smoke auth items in [PRODUCTION_SMOKE_CHECKLIST.md](./PRODUCTION_SMOKE_CHECKLIST.md).

---

## 6. Sign-off

| Item | Status |
|------|--------|
| seed_dev barred from prod | Documented |
| SSO/SCIM as primary | Documented |
| Invitation feature | **Not claimed** (not invented) |
| IdP/SCIM credentials | EXTERNAL_INPUT_REQUIRED |
