# Observability & Alerting

**Product:** EduVijna Paper Evaluation  
**Last updated:** 2026-09-30  
**Related:** [PRODUCTION_READINESS.md](./PRODUCTION_READINESS.md), [PERFORMANCE_RELIABILITY.md](./PERFORMANCE_RELIABILITY.md), [SECURITY_BASELINE.md](../architecture/SECURITY_BASELINE.md)

---

## 1. Purpose

Vendor-neutral expectations for health probes, logs, correlation, and an alert response matrix. Concrete SaaS/agent choices remain **EXTERNAL_INPUT_REQUIRED** (platform decision).

---

## 2. Health & readiness

| Endpoint | Meaning | Probe use |
|----------|---------|-----------|
| `GET /health` | Process liveness (`{"status":"ok"}`) | Restart unhealthy tasks/containers |
| `GET /ready` | Dependency readiness: postgres + redis + object storage; `503` with per-check detail | Remove from load until ready |

Frontend may proxy these (`/health`, `/ready` → API). Also useful: `GET /api/v1/system/version` (when deployed) for build identity (`API_VERSION`, `GIT_SHA`).

---

## 3. Structured logs

| Setting | Variable | Notes |
|---------|----------|-------|
| Level | `LOG_LEVEL` (default `INFO`) | Avoid `DEBUG` with PII in production |
| Correlation | `X-Correlation-ID` | Middleware accepts or generates; echo on responses (PEV-072) |
| Audit | `audit_events` table | Privileged mutations; attach correlation when available |
| AI | `ai_execution_records` | Provider/model/prompt metadata; redacted routing — not raw sheets |

**Do not** log secrets, raw JWT, `OPENAI_API_KEY`, webhook signing secrets, or full auth assertions.

Preferred log fields (application): timestamp, level, service (`api` \| `worker`), `correlation_id`, `tenant_id` (when in request/task context), event name, error code.

---

## 4. Alert matrix & response

Severity: **P1** page immediately · **P2** business hours urgent · **P3** ticket · **P4** backlog.

| Signal | Suggested severity | Condition (tune after baseline) | First response |
|--------|-------------------|----------------------------------|----------------|
| API `/health` failing | P1 | Continuous fail across instances | Check process/deploy; rollback image if bad release ([ROLLBACK_RUNBOOK.md](./ROLLBACK_RUNBOOK.md)) |
| API `/ready` failing | P1 | DB/Redis/object-storage check fail | Inspect dependency named in JSON `checks`; restore disposable/prod dependency — do not destroy MAT |
| Redis unavailable | P1/P2 | `/ready` redis=`fail`; workers cannot consume | Restore Redis; expect empty broker (not SoT); re-enqueue if needed |
| Object storage unavailable | P1 | `/ready` object_storage=`fail`; uploads error/timeout | Restore MinIO/S3; verify no false AVAILABLE without object |
| Auth login rate-limited | P2/P3 | Log event `auth_login_rate_limited`; HTTP 429 | Confirm not a bug (burst); check IP/email abuse; do not log passwords |
| Elevated 5xx rate | P1/P2 | Sustained above baseline | Correlate by `X-Correlation-ID`; check recent deploy/config |
| Celery worker down | P1 | No heartbeats / consumer missing | Restart worker; inspect broker `REDIS_URL` / `CELERY_BROKER_URL` |
| AI provider timeouts | P2 | Rising `ProviderUnavailable` / REVIEW_REQUIRED | Check provider status; do not force marks; use fixed provider only in non-prod |
| Queue depth growth | P2 | Backlog exceeds provisional threshold | Scale workers **only if platform allows**; check stuck tasks / AI timeouts |
| Task failure spike | P2 | `pipeline_jobs` FAILED surge | Inspect error detail; AI vs storage vs code regression |
| Redis unavailable | P1 | Broker ping fail | Restore Redis; note jobs may need re-enqueue — DB remains SoT |
| Object storage errors | P1/P2 | Upload/GET failures | Check `S3_ENDPOINT_URL`, credentials, bucket; fail closed on ingest |
| DB pressure | P1/P2 | Connection errors, slow queries, `/ready` flaps | Connection limits, long transactions, vacuum/ops runbook (platform) |
| AI timeout / provider errors | P2 | Timeout or provider 5xx spike | Verify `AI_REQUEST_TIMEOUT_SECONDS`, provider status; ensure fail-visible human review — do not bypass ledger |
| Auth failure surge | P2 | Login 401 spike | Possible attack or IdP outage; check audit events |
| Webhook delivery failures | P3 | SSRF blocks or HMAC failures | Confirm `WEBHOOK_ALLOW_INSECURE_DESTINATIONS=false`; fix destination allow-list |

Exact thresholds and paging tools = **EXTERNAL_INPUT_REQUIRED**.

---

## 5. On-call response outline

1. Confirm blast radius (single tenant vs global).  
2. Capture correlation IDs and approximate time window.  
3. Check last deploy tag (`GIT_SHA`) and config change.  
4. Prefer forward fix or image rollback; migrations → forward-recovery preference.  
5. Never `compose down -v` or restore onto founder MAT as “mitigation.”  
6. Record incident notes for SECURITY_PRIVACY findings if security-related.

---

## 6. Sign-off

| Item | Status |
|------|--------|
| Probe paths documented | Done |
| Alert tooling wired | EXTERNAL_INPUT_REQUIRED |
| Thresholds baselined | PENDING (after disposable load runs) |
