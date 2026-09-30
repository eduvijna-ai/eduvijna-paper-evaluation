# Production Smoke Checklist

**Product:** EduVijna Paper Evaluation  
**Last updated:** 2026-09-30  
**Related:** [DEPLOYMENT_RUNBOOK.md](./DEPLOYMENT_RUNBOOK.md), [OBSERVABILITY_ALERTING.md](./OBSERVABILITY_ALERTING.md), [PRODUCTION_READINESS.md](./PRODUCTION_READINESS.md)

---

## 1. Purpose

Post-deploy (or post-rollback) smoke checks for a pilot/production-shaped environment.

**Do not** reopen or re-run founder MAT (MAT-001..017 already PASS BY FOUNDER; MAT-018..055 DEFERRED; founder E2E NOT EXECUTED). Use the deployed environment’s own synthetic or authorized pilot tenant.

---

## 2. Preconditions

- [ ] Deploy authorized (or staging smoke explicitly requested)  
- [ ] Migrations at expected head (`20260918_0022` or documented newer)  
- [ ] Secrets present via secure channel  
- [ ] Operator has a **non-MAT** test account (SSO/SCIM/password per [ACCOUNT_PROVISIONING.md](./ACCOUNT_PROVISIONING.md))  

---

## 3. Checklist

| # | Check | Command / action | Pass criteria | Done |
|---|-------|------------------|---------------|------|
| 1 | Liveness | `GET /health` | `200` + `status=ok` | [ ] |
| 2 | Readiness | `GET /ready` | `200` + `status=ready` (not 503) | [ ] |
| 3 | Version | `GET /api/v1/system/version` (if exposed) | Expected `GIT_SHA` / version | [ ] |
| 4 | Login | `POST /api/v1/auth/login` **or** SSO happy path | Token / session established | [ ] |
| 5 | Me / RBAC | `GET /api/v1/auth/me` (or equivalent) | User + tenant context; no `password_hash` in body | [ ] |
| 6 | Tenant isolation spot-check | Foreign tenant ID on a known resource | `404` | [ ] |
| 7 | Upload path | Initiate submission (or assessment paper) upload within size limits | Accept or explicit validation error; object stored under tenant prefix | [ ] |
| 8 | Worker | Confirm Celery worker process healthy; enqueue a lightweight job if available | Job progresses or fails visibly (not silent) | [ ] |
| 9 | Redis dependency | Broker reachable from worker | No continuous connection errors in logs | [ ] |
| 10 | Object storage | GET/HEAD of uploaded object via app path | Success | [ ] |
| 11 | Correlation | Send `X-Correlation-ID` on a request | Echoed on response; appears in logs/audit if applicable | [ ] |
| 12 | AI fail-visible (if provider configured) | Trigger or observe one AI-backed stage | `AiExecutionRecord` or explicit job failure — no invented marks | [ ] |
| 13 | AI gate honesty | If provider not production-ready | Confirm `AI_PRODUCTION_PROVIDER_GATE` still EXTERNAL_INPUT_REQUIRED; do not fake PASS | [ ] |
| 14 | Webhook fail-closed | Confirm insecure destinations disabled | `WEBHOOK_ALLOW_INSECURE_DESTINATIONS` false | [ ] |
| 15 | No seed_dev in prod | Confirm production was not bootstrapped via `seed_dev` | Accounts via supported provisioning | [ ] |

---

## 4. Abort criteria

Stop and follow [ROLLBACK_RUNBOOK.md](./ROLLBACK_RUNBOOK.md) if:

- `/ready` remains 503 after migrate  
- Auth completely broken  
- Cross-tenant data returned  
- Uploads write outside tenant isolation  
- Workers cannot start and backlog is critical for pilot  

---

## 5. Evidence

| Field | Value |
|-------|-------|
| Environment | |
| Image / `GIT_SHA` | |
| Alembic revision | |
| Operator | |
| Date | |
| Result | PASS / FAIL |
| Notes | |
