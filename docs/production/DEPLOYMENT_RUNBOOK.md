# Deployment Runbook

**Product:** EduVijna Paper Evaluation  
**Last updated:** 2026-09-30  
**Status:** NEXT-stage order only — **DO NOT PERFORM NOW**  
**Related:** [PRODUCTION_READINESS.md](./PRODUCTION_READINESS.md), [ENVIRONMENT_CONFIGURATION.md](./ENVIRONMENT_CONFIGURATION.md), [MIGRATION_RUNBOOK.md](./MIGRATION_RUNBOOK.md), [ROLLBACK_RUNBOOK.md](./ROLLBACK_RUNBOOK.md), [PRODUCTION_SMOKE_CHECKLIST.md](./PRODUCTION_SMOKE_CHECKLIST.md)

---

## 1. Explicit non-action

**Do not execute this runbook as part of the pre-production documentation package.**  
No provisioning, no DNS cutover, no pilot enablement, no production secret creation from this doc alone.

Platform decision = **EXTERNAL_INPUT_REQUIRED** (no invented AWS / Azure / GCP / Kubernetes architecture).

---

## 2. Prerequisites before any future execution

- [ ] Founder authorizes deployment window  
- [ ] Platform chosen and documented (EXTERNAL_INPUT_REQUIRED today)  
- [ ] Gates in [PRODUCTION_READINESS.md](./PRODUCTION_READINESS.md) reviewed  
- [ ] Secrets path exists (not git)  
- [ ] Disposable rehearsal succeeded (migrate, backup/restore drill, smoke)  
- [ ] `AI_PRODUCTION_PROVIDER_GATE` / corpus gates addressed or explicitly waived  

---

## 3. NEXT-stage order ONLY (when authorized)

Execute **in order**. Stop on failure; prefer rollback/forward-recovery over destructive resets.

| Step | Action | Notes |
|------|--------|-------|
| 1 | **Provision infra** | Postgres, Redis, S3-compatible storage, compute for API + worker, TLS edge — **per chosen platform** (EXTERNAL_INPUT_REQUIRED) |
| 2 | **Configure secrets & env** | [ENVIRONMENT_CONFIGURATION.md](./ENVIRONMENT_CONFIGURATION.md); fail-closed flags |
| 3 | **Build & push images** | API/worker (and web) tagged with `GIT_SHA`; no secrets in layers |
| 4 | **Migrate database** | Empty→head or upgrade to **`20260918_0022`** ([MIGRATION_RUNBOOK.md](./MIGRATION_RUNBOOK.md)) on the **production** DB only after backups exist |
| 5 | **Deploy API** | Health `/health`, ready `/ready` |
| 6 | **Deploy worker** | Celery worker+beat as designed; `CELERY_TASK_ALWAYS_EAGER=false` |
| 7 | **Deploy web** | Point at API; CORS/origins match |
| 8 | **Wire observability** | Probes + alerts ([OBSERVABILITY_ALERTING.md](./OBSERVABILITY_ALERTING.md)) |
| 9 | **Account bootstrap** | [ACCOUNT_PROVISIONING.md](./ACCOUNT_PROVISIONING.md) — **not** `seed_dev` |
| 10 | **Production smoke** | [PRODUCTION_SMOKE_CHECKLIST.md](./PRODUCTION_SMOKE_CHECKLIST.md) — do not reopen founder MAT |
| 11 | **Enable pilot** | Tenant-limited traffic; monitoring watch |

---

## 4. Explicitly out of order / forbidden during docs phase

- Running steps 1–11 now  
- Inventing cloud diagrams or resource names as if decided  
- Destroying MAT volumes to “simulate prod”  
- Committing production `.env`  

---

## 5. Record (fill when a real deploy is authorized)

| Field | Value |
|-------|-------|
| Authorization ticket / date | |
| Platform | EXTERNAL_INPUT_REQUIRED |
| Image tags | |
| Alembic revision | `20260918_0022` (or newer if updated) |
| Pilot tenants | |
| Outcome | NOT EXECUTED (docs package) |
