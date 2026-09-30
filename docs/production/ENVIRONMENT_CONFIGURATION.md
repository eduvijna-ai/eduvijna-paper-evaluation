# Environment Configuration

**Product:** EduVijna Paper Evaluation  
**Last updated:** 2026-09-30  
**Related:** `.env.example`, `apps/api/app/core/config.py`, `docker-compose.yml`, [SECURITY_BASELINE.md](../architecture/SECURITY_BASELINE.md), [AI_PROVIDER_READINESS.md](./AI_PROVIDER_READINESS.md)

---

## 1. Purpose

Authoritative **variable names** for production-shaped environments. Examples use placeholders only — **never commit real secrets**.

Production must be **fail-closed**: missing auth secret outside `local`/`test` raises; insecure webhook/test provider flags off; AI `fixed` / upload scanner `fixed` forbidden.

---

## 2. Core application

| Variable | Example (non-secret) | Notes |
|----------|----------------------|-------|
| `APP_NAME` | `eduvijna-paper-evaluation` | |
| `APP_ENV` | `production` (or `staging`) | Not `local`/`test` in pilot |
| `API_VERSION` | `0.1.0` | Build metadata |
| `GIT_SHA` | `<git-sha>` | Inject at build |
| `LOG_LEVEL` | `INFO` | |
| `API_HOST` / `API_PORT` | `0.0.0.0` / `8000` | Container-internal |

---

## 3. Database

| Variable | Example (non-secret) | Notes |
|----------|----------------------|-------|
| `DATABASE_URL` | `postgresql+asyncpg://APP_USER:***@db-host:5432/eduvijna_prod` | Async SQLAlchemy URL |
| `POSTGRES_HOST` / `POSTGRES_PORT` / `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` | Compose-oriented; prefer URL in non-Compose | Password via secret manager |
| `POSTGRES_PUBLISH_PORT` | Local only (`15432` MAT/local default) | Do not expose casually in production |

**Pool / timeout:** Configurable via Settings / env:

| Knob | Env | Default |
|------|-----|---------|
| Pool size | `DATABASE_POOL_SIZE` | 5 |
| Max overflow | `DATABASE_MAX_OVERFLOW` | 10 |
| Pool timeout (s) | `DATABASE_POOL_TIMEOUT_SECONDS` | 30 |
| Recycle (s) | `DATABASE_POOL_RECYCLE_SECONDS` | 1800 |

Auth login rate limits (Redis):

| Knob | Env | Default |
|------|-----|---------|
| Failed logins / email / min | `AUTH_LOGIN_FAIL_LIMIT_PER_EMAIL_PER_MINUTE` | 10 (`0` disables) |
| Failed logins / IP / min | `AUTH_LOGIN_FAIL_LIMIT_PER_IP_PER_MINUTE` | 30 (`0` disables) |
| Integration API / min | `INTEGRATION_RATE_LIMIT_PER_MINUTE` | 120 |

Production platform connection ceilings remain **EXTERNAL_INPUT_REQUIRED**. Record chosen platform max_connections / proxy RL here when known.

| Knob | Current code default | Production plan |
|------|----------------------|-----------------|
| `pool_pre_ping` | `True` | Keep |
| Pool size / overflow | See env table above | Ops-tuned |
| Statement / lock timeout | DB/server setting | TBD |

---

## 4. Redis & Celery

| Variable | Example | Notes |
|----------|---------|-------|
| `REDIS_URL` | `redis://redis-host:6379/0` | Not SoT |
| `CELERY_BROKER_URL` | `redis://redis-host:6379/0` | |
| `CELERY_RESULT_BACKEND` | `redis://redis-host:6379/1` | |
| `CELERY_TASK_ALWAYS_EAGER` | `false` | Must be false in real workers |
| `REDIS_PUBLISH_PORT` | Local only (`16379`) | |

---

## 5. Object storage (S3-compatible)

| Variable | Example | Notes |
|----------|---------|-------|
| `S3_ENDPOINT_URL` | `https://objects.example.invalid` | Vendor-neutral endpoint |
| `S3_ACCESS_KEY` / `S3_SECRET_KEY` | secrets | Never commit |
| `S3_BUCKET` | `eduvijna-papers-prod` | Avoid MAT default bucket for drills |
| `S3_REGION` | `us-east-1` (or provider region string) | |
| `SUBMISSION_UPLOAD_MAX_BYTES` | `52428800` | |
| `SUBMISSION_MAX_PAGES` | `100` | |
| `ASSESSMENT_PAPER_UPLOAD_MAX_BYTES` | `20971520` | |
| `UPLOAD_SCANNER` | production AV adapter **or** `none` | `fixed` forbidden; `none` never claims CLEAN |

---

## 6. Auth & integrations

| Variable | Example | Notes |
|----------|---------|-------|
| `AUTH_TOKEN_SECRET` | secret | **Required** when `APP_ENV` not `local`/`test` |
| `AUTH_TOKEN_TTL_MINUTES` | `60` | |
| `AUTH_ALGORITHM` | `HS256` | |
| `STUDENT_IMPORT_MAX_BYTES` / `STUDENT_IMPORT_MAX_ROWS` | `2000000` / `5000` | |
| `PUBLIC_BASE_URL` | `https://api.example.invalid` | EXTERNAL_INPUT_REQUIRED |
| `FRONTEND_BASE_URL` | `https://app.example.invalid` | EXTERNAL_INPUT_REQUIRED |
| `CORS_ORIGINS` | `https://app.example.invalid` | Documented in `.env.example` / SECURITY_BASELINE; production origins EXTERNAL_INPUT_REQUIRED |
| `INTEGRATION_SECRET_ENCRYPTION_KEY` | Fernet key | When B19 secrets at rest |
| `INTEGRATION_RATE_LIMIT_PER_MINUTE` | `120` | |
| `B19_TEST_PROVIDERS_ENABLED` | `false` | Production fail-closed |
| `WEBHOOK_ALLOW_INSECURE_DESTINATIONS` | `false` | Production fail-closed |
| `B19_TEST_INTERNAL_BASE_URL` / `B19_TEST_WEBHOOK_SIGNING_SECRET` | unset / unused | Test-only |

---

## 7. AI

See [AI_PROVIDER_READINESS.md](./AI_PROVIDER_READINESS.md). Summary:

- Set real `AI_PROVIDER_VISION` / `AI_PROVIDER_TEXT` / `AI_PROVIDER_AUTHORING` (never `fixed`).  
- Pin `AI_MODEL_*` strings.  
- `AI_REQUEST_TIMEOUT_SECONDS` (default `60`).  
- `OPENAI_API_KEY` via secret manager only when using OpenAI adapter.  
- Gates `AI_PRODUCTION_PROVIDER_GATE` and `REAL_PAPER_CORPUS_GATE` remain EXTERNAL_INPUT_REQUIRED until supplied.

---

## 8. Production fail-closed checklist

- [ ] `APP_ENV` not `local`/`test`  
- [ ] Strong unique `AUTH_TOKEN_SECRET`  
- [ ] `B19_TEST_PROVIDERS_ENABLED=false`  
- [ ] `WEBHOOK_ALLOW_INSECURE_DESTINATIONS=false`  
- [ ] `CELERY_TASK_ALWAYS_EAGER=false`  
- [ ] No `AI_PROVIDER_*=fixed`  
- [ ] No `UPLOAD_SCANNER=fixed`  
- [ ] No demo passwords from `seed_dev`  
- [ ] Secrets not in image layers or git  
- [ ] CORS / public URLs restricted to known fronts  

---

## 9. Example skeleton (placeholders only)

```bash
APP_ENV=production
GIT_SHA=REPLACE_AT_BUILD
DATABASE_URL=postgresql+asyncpg://APP_USER:REPLACE@db-host:5432/eduvijna_prod
REDIS_URL=redis://redis-host:6379/0
CELERY_BROKER_URL=redis://redis-host:6379/0
CELERY_RESULT_BACKEND=redis://redis-host:6379/1
CELERY_TASK_ALWAYS_EAGER=false
S3_ENDPOINT_URL=https://objects.example.invalid
S3_BUCKET=eduvijna-papers-prod
AUTH_TOKEN_SECRET=REPLACE_VIA_SECRET_MANAGER
CORS_ORIGINS=https://app.example.invalid
PUBLIC_BASE_URL=https://api.example.invalid
FRONTEND_BASE_URL=https://app.example.invalid
B19_TEST_PROVIDERS_ENABLED=false
WEBHOOK_ALLOW_INSECURE_DESTINATIONS=false
AI_PROVIDER_VISION=openai
AI_PROVIDER_TEXT=openai
AI_PROVIDER_AUTHORING=openai
AI_REQUEST_TIMEOUT_SECONDS=60
# OPENAI_API_KEY=REPLACE_VIA_SECRET_MANAGER
UPLOAD_SCANNER=none
```
