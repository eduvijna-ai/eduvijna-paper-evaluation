# Security & Privacy Readiness

**Product:** EduVijna Paper Evaluation  
**Status:** Pre-production findings filled from code reality (2026-09-30)  
**Last updated:** 2026-09-30  
**Related:** [SECURITY_BASELINE.md](../architecture/SECURITY_BASELINE.md), [PRODUCTION_READINESS.md](./PRODUCTION_READINESS.md), [ACCOUNT_PROVISIONING.md](./ACCOUNT_PROVISIONING.md), [ENVIRONMENT_CONFIGURATION.md](./ENVIRONMENT_CONFIGURATION.md)

---

## 1. Purpose

Vendor-neutral security and privacy readiness for pilot/production. Aligns with the existing [SECURITY_BASELINE.md](../architecture/SECURITY_BASELINE.md). This file tracks **findings**; it is not a penetration-test report substitute.

---

## 2. Scope & non-goals

**In scope:** Auth, tenant isolation, webhooks (SSRF/HMAC), file upload, CORS, secrets handling, audit/correlation, AI key placement, seed vs production provisioning.

**Out of scope (for this template):** Invented cloud WAF/KMS product names; claiming seed_dev as production IAM; destroying MAT volumes for “security resets.”

---

## 3. Known focus areas (checklist)

### 3.1 Authentication & sessions

| Item | Expected control | Status | Findings / notes |
|------|------------------|--------|------------------|
| Password/JWT login | `POST /api/v1/auth/login`; `AUTH_TOKEN_SECRET` required outside `local`/`test` | **VERIFIED** | `apps/api/app/core/config.py` `require_auth_secret` fail-closed outside local/test; production also guarded by `production_fail_closed` |
| Token TTL / algorithm | `AUTH_TOKEN_TTL_MINUTES`, `AUTH_ALGORITHM` (default HS256) | VERIFIED | Settings fields present; defaults documented in `.env.example` |
| SSO (OIDC/SAML) | Tenant-configured B19 surfaces; production IdP metadata | OPEN | IdP credentials = EXTERNAL_INPUT_REQUIRED |
| Break-glass / local admin | Documented ownership; no demo passwords in prod | OPEN | See [ACCOUNT_PROVISIONING.md](./ACCOUNT_PROVISIONING.md) |
| Deactivated users | SCIM/local deactivation denies login; history retained | VERIFIED | Covered under B19 SCIM/enterprise suite |

### 3.2 Tenant isolation

| Item | Expected control | Status | Findings / notes |
|------|------------------|--------|------------------|
| DB tenant predicate / RLS | ADR-005; `tenant_id` on tenant data | VERIFIED | Domain models + query filters; regression coverage across suites |
| API cross-tenant IDs | Return `404`, not data leakage | **VERIFIED** | Regression: `test_a2_gate_matrix`, `test_b3_*`, `test_b7_*`, `test_b12_*`, `test_b13_*`, `test_b15_*`, `test_b17_*`, `test_b18_*`, `test_b19_*`, `test_b20_*`, and related |
| Object storage prefixes | `/{tenant_id}/...` | VERIFIED | `app/services/storage.py` key helpers |
| Workers | `tenant_id` in Celery task kwargs | VERIFIED | Task payloads carry tenant scope |
| AI records | `AiExecutionRecord.tenant_id`; no cross-tenant batching | VERIFIED | Provider registry + execution metadata |

### 3.3 Webhooks (SSRF / HMAC)

| Item | Expected control | Status | Findings / notes |
|------|------------------|--------|------------------|
| Destination allow / SSRF | `WEBHOOK_ALLOW_INSECURE_DESTINATIONS=false` in production (fail-closed) | **VERIFIED** | Runtime SSRF checks + production Settings reject `true`; suite `test_b19_enterprise` |
| Signing | HMAC (or equivalent) verification on inbound/outbound as implemented | **VERIFIED** | `test_b19_enterprise` webhook HMAC paths |
| Secrets at rest | `INTEGRATION_SECRET_ENCRYPTION_KEY` (Fernet) when integrations enabled | VERIFIED | Integration crypto module; never commit key |
| Test providers | `B19_TEST_PROVIDERS_ENABLED=false` in production | **VERIFIED** | Production Settings fail-closed rejects `true` |

### 3.4 File upload

| Item | Expected control | Status | Findings / notes |
|------|------------------|--------|------------------|
| Size / page limits | `SUBMISSION_UPLOAD_MAX_BYTES`, `SUBMISSION_MAX_PAGES`, `ASSESSMENT_PAPER_UPLOAD_MAX_BYTES` | **VERIFIED** | Enforced via Settings + upload handlers |
| Malware scan hook | `UPLOAD_SCANNER`; `none` never claims CLEAN; `fixed` forbidden in production | **VERIFIED** | Settings reject `UPLOAD_SCANNER=fixed` in production; registry/scanner docs |
| Immutable raw papers | ADR-009 write-once; hash recorded | VERIFIED | `ObjectStorage.put_raw_bytes` immutability |
| Student import bounds | `STUDENT_IMPORT_MAX_BYTES`, `STUDENT_IMPORT_MAX_ROWS` | VERIFIED | Settings defaults |

### 3.5 CORS & transport

| Item | Expected control | Status | Findings / notes |
|------|------------------|--------|------------------|
| Allowed origins | Explicit production frontend origins (see `CORS_ORIGINS` in `.env.example`) | **EXTERNAL_INPUT_REQUIRED** | Production allow-list must be supplied by ops; default hybrid Next rewrites avoid browser CORS for same-origin `/api` |
| HTTPS | Mandatory outside localhost | OPEN | TLS termination = platform decision |
| Correlation ID | `X-Correlation-ID` accepted/generated (PEV-072) | VERIFIED | Middleware + `/health` tests |

### 3.6 Secrets

| Item | Expected control | Status | Findings / notes |
|------|------------------|--------|------------------|
| No secrets in git | `.env` gitignored; only `.env.example` placeholders | **VERIFIED** | `.gitignore` includes `.env`; `.env` not committed when scan clean |
| Runtime injection | Secret manager / sealed env — platform-specific | OPEN | EXTERNAL_INPUT_REQUIRED |
| AI keys | `OPENAI_API_KEY` (or successor) only on API/worker; never in frontend | VERIFIED | Settings on API/worker only |
| Local JWT default | Never use `eduvijna_local_jwt_dev_only_change_me` outside local/test | VERIFIED | Injected only for local/test when secret missing |

### 3.7 Additional pre-production controls

| Item | Expected control | Status | Findings / notes |
|------|------------------|--------|------------------|
| Fixed AI forbidden in production | `AI_PROVIDER_*=fixed` refused | **VERIFIED** | Runtime refuse in `app/ai/registry.py`; Settings `production_fail_closed` |
| Celery webhook asyncio lifecycle | Task-local NullPool sessions; no shared-engine dispose across loops | **FIXED** | `apps/api/app/db/celery_session.py` (preprod branch) |
| List pagination bounds | Clamp limit/offset | **FIXED** | `apps/api/app/api/pagination.py` + list endpoints |
| `seed_dev` not production | Demo seed forbidden as prod IAM | **DOCUMENTED** | [ACCOUNT_PROVISIONING.md](./ACCOUNT_PROVISIONING.md) |
| General API rate limiting | Broad authenticated/public rate limits | **ACCEPTED RISK / gap** | Only integration credential rate limit (`integration_rate_limit_per_minute`) today |

---

## 4. Seed / demo vs production provisioning

**`python -m app.cli.seed_dev` is NOT production provisioning.**

| Mechanism | Allowed in production? | Notes |
|-----------|------------------------|-------|
| `app.cli.seed_dev` | **No** | Local/demo/CI synthetic tenant (`demo`), fixed demo emails/passwords |
| Other `seed_*` E2E CLIs | **No** | Test fixtures only |
| Password users via supported admin/ops path | Only if an authorized production procedure exists | See [ACCOUNT_PROVISIONING.md](./ACCOUNT_PROVISIONING.md) — do not invent invitation flows |
| SSO (OIDC/SAML) | Yes when IdP configured | Tenant-scoped |
| SCIM 2.0 | Yes when integration credentials configured | Create/update/deactivate |

---

## 5. Findings log

| ID | Date | Area | Severity | Finding | Owner | Resolution |
|----|------|------|----------|---------|-------|------------|
| SPR-001 | 2026-09-30 | Rate limiting | MEDIUM | No general API rate limit; only B19 integration RL | Eng | **ACCEPTED RISK / gap** until product decides |
| SPR-002 | 2026-09-30 | CORS | INFO | Production `CORS_ORIGINS` allow-list not yet supplied | Ops | **EXTERNAL_INPUT_REQUIRED**; hybrid Next rewrites mitigate default browser CORS |
| SPR-003 | 2026-09-30 | Celery/DB | HIGH | Asyncio loop + pooled engine lifecycle for webhook tasks | Eng | **FIXED** via `celery_session` NullPool |
| SPR-004 | 2026-09-30 | Pagination | MEDIUM | Unbounded list limit/offset risk | Eng | **FIXED** via shared clamps |
| SPR-005 | 2026-09-30 | Prod config | HIGH | Local escapes (`fixed` AI/scanner, insecure webhooks, B19 test) must not boot in prod | Eng | **FIXED** Settings `production_fail_closed` |

Severity guide: **CRITICAL** (blocks go-live) · **HIGH** · **MEDIUM** · **LOW** · **INFO**.

---

## 6. Privacy notes

- Synthetic demo data only in repo fixtures (SECURITY_BASELINE §7).
- Real pilot student PII lives only in the deployed environment DB + object storage.
- AI prompts must not become an uncontrolled PII export path; prefer S3 references and redacted `AiExecutionRecord` metadata.
- Retention minima (audit ≥ 1 year for pilot) remain per SECURITY_BASELINE unless legal overrides are supplied (**EXTERNAL_INPUT_REQUIRED** for jurisdiction-specific DPA).

---

## 7. Verification commands

Run from repo root / `apps/api` with a disposable or local test environment (never destroy MAT volumes).

```bash
# Auth secret fail-closed + production Settings guards
cd apps/api
python -m pytest tests/test_production_settings_guards.py -q

# Readiness dependency checks (mocked deps in unit tests)
python -m pytest tests/test_health.py -q

# Pagination clamps
python -m pytest tests/test_preprod_list_pagination.py -q

# Celery webhook asyncio / NullPool lifecycle
python -m pytest tests/test_preprod_webhooks_celery_lifecycle.py -q

# Tenant isolation + webhook SSRF/HMAC (subset; full suite is larger)
python -m pytest tests/test_b19_enterprise.py -q -k "tenant or webhook or cross_tenant or ssrf or hmac" 

# Broader tenant isolation regressions (examples)
python -m pytest tests/test_a2_gate_matrix.py tests/test_b3_submission_ingestion.py \
  tests/test_b7_publication_reports.py -q -k "tenant or cross_tenant"

# Confirm .env is not tracked
git check-ignore -v .env
git ls-files .env  # expect empty

# Optional: placeholder/secret pattern scan on tracked files (adjust tooling)
git grep -nE 'sk-live|BEGIN RSA PRIVATE KEY|eduvijna_local_jwt_dev_only_change_me' -- ':!.env.example' ':!**/seed*.py' || true
```

---

## 8. Sign-off

| Role | Name | Date | Decision |
|------|------|------|----------|
| Security reviewer | | | PENDING |
| Founder / Product | | | PENDING |
