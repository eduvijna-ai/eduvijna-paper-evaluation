# Production Readiness Gate

**Product:** EduVijna Paper Evaluation  
**Scope:** Pre-production documentation package (vendor-neutral)  
**Last updated:** 2026-09-30  
**Related:** [SECURITY_PRIVACY_READINESS.md](./SECURITY_PRIVACY_READINESS.md), [AI_PROVIDER_READINESS.md](./AI_PROVIDER_READINESS.md), [PERFORMANCE_RELIABILITY.md](./PERFORMANCE_RELIABILITY.md), [BACKUP_RESTORE_DR.md](./BACKUP_RESTORE_DR.md), [OBSERVABILITY_ALERTING.md](./OBSERVABILITY_ALERTING.md), [ENVIRONMENT_CONFIGURATION.md](./ENVIRONMENT_CONFIGURATION.md), [MIGRATION_RUNBOOK.md](./MIGRATION_RUNBOOK.md), [DEPLOYMENT_RUNBOOK.md](./DEPLOYMENT_RUNBOOK.md), [ROLLBACK_RUNBOOK.md](./ROLLBACK_RUNBOOK.md), [PRODUCTION_SMOKE_CHECKLIST.md](./PRODUCTION_SMOKE_CHECKLIST.md), [ACCOUNT_PROVISIONING.md](./ACCOUNT_PROVISIONING.md), [SECURITY_BASELINE.md](../architecture/SECURITY_BASELINE.md)

---

## 1. Purpose

This document is the **gate criteria** for declaring a pilot/production environment ready. It does **not** authorize deployment. Platform choice, cloud credentials, production AI keys, and real paper corpora remain **EXTERNAL_INPUT_REQUIRED** until supplied by founder/ops.

**Do not deploy from this package alone.** See [DEPLOYMENT_RUNBOOK.md](./DEPLOYMENT_RUNBOOK.md) (NEXT-stage only).

---

## 2. Gate summary (current status)

| Gate area | Status | Notes |
|-----------|--------|-------|
| Founder MAT (MAT-001..017) | **PASS BY FOUNDER** | Recorded founder pass; do not reopen founder MAT as a precondition for docs |
| Founder MAT (MAT-018..055) | **DEFERRED** | Not blocking this docs package |
| Founder E2E | **NOT EXECUTED** | Must not be claimed as executed |
| Security / privacy readiness | Template open | [SECURITY_PRIVACY_READINESS.md](./SECURITY_PRIVACY_READINESS.md) |
| AI production provider | **EXTERNAL_INPUT_REQUIRED** | [AI_PROVIDER_READINESS.md](./AI_PROVIDER_READINESS.md) |
| Real paper corpus | **EXTERNAL_INPUT_REQUIRED** | Gate `REAL_PAPER_CORPUS_GATE` |
| Performance / reliability proof | Provisional | [PERFORMANCE_RELIABILITY.md](./PERFORMANCE_RELIABILITY.md) |
| Backup / restore / DR drill | Isolated disposable only | [BACKUP_RESTORE_DR.md](./BACKUP_RESTORE_DR.md) |
| Observability / alerting | Design documented | [OBSERVABILITY_ALERTING.md](./OBSERVABILITY_ALERTING.md) |
| Environment configuration | Fail-closed production | [ENVIRONMENT_CONFIGURATION.md](./ENVIRONMENT_CONFIGURATION.md) |
| Migrations to head `20260918_0022` | Documented | [MIGRATION_RUNBOOK.md](./MIGRATION_RUNBOOK.md) |
| Deployment platform decision | **EXTERNAL_INPUT_REQUIRED** | No invented AWS/Azure/GCP architecture |
| Account provisioning plan | Documented | [ACCOUNT_PROVISIONING.md](./ACCOUNT_PROVISIONING.md) |
| Post-deploy smoke | Checklist ready | [PRODUCTION_SMOKE_CHECKLIST.md](./PRODUCTION_SMOKE_CHECKLIST.md) |

---

## 3. MAT founder status

| Range | Status | Implication |
|-------|--------|-------------|
| **MAT-001 … MAT-017** | **PASS BY FOUNDER** | Treated as founder-accepted for readiness tracking; do not re-run founder MAT to “prove” this docs package |
| **MAT-018 … MAT-055** | **DEFERRED** | Explicitly out of scope for this readiness gate until founder reopens |
| **Founder E2E** | **NOT EXECUTED** | Must remain labeled NOT EXECUTED; no substitution with CI/local E2E |

Never destroy founder MAT Compose volumes or known MAT database/object-storage defaults when practicing backup/restore. See [BACKUP_RESTORE_DR.md](./BACKUP_RESTORE_DR.md) and `infra/scripts/*backup*`, `*restore*`, `dr-restore-drill*`.

---

## 4. External input policy

Items marked **EXTERNAL_INPUT_REQUIRED** must be supplied by founder/ops (or an authorized platform owner) before the corresponding gate can flip to PASS. Engineering must **not**:

- Invent cloud platform topology (AWS / Azure / GCP / Kubernetes specifics)
- Commit real secrets, API keys, IdP metadata containing secrets, or production connection strings
- Claim production AI provider readiness without a real provider credential path and model/prompt versioning plan
- Treat synthetic `seed_dev` data or demo passwords as production provisioning
- Treat founder MAT as disposable for DR drills

Until inputs arrive, keep the gate label and block go-live for that area only.

Known **EXTERNAL_INPUT_REQUIRED** flags in this package:

1. `AI_PRODUCTION_PROVIDER_GATE` — production AI provider, models, keys, timeouts/retry policy sign-off  
2. `REAL_PAPER_CORPUS_GATE` — authorized real (or licensed) paper corpus for production-like validation  
3. Deployment **platform decision** — where and how infra is provisioned  
4. Production RPO/RTO targets (TBD in DR doc until ops supplies)  
5. Production CORS allow-list origins, public base URLs, and secret-manager wiring  
6. Production IdP / SCIM / break-glass account ownership (tenant-specific)

---

## 5. Hard safety rules (pre-production work)

- **Do not** run `docker compose down -v` against founder MAT stacks.
- **Do not** restore backups onto MAT default ports/DB names without explicit `OVERRIDE_MAT_SAFETY=1` **and** disposable naming preference (scripts still refuse unsafe defaults by design).
- **Do not** set `AI_PROVIDER_*` to `fixed` in production (local/CI only).
- **Do not** set `UPLOAD_SCANNER=fixed` in production.
- **Do not** enable `B19_TEST_PROVIDERS_ENABLED` or `WEBHOOK_ALLOW_INSECURE_DESTINATIONS` outside controlled test environments.
- **Do not** run `python -m app.cli.seed_dev` as production account provisioning ([ACCOUNT_PROVISIONING.md](./ACCOUNT_PROVISIONING.md)).

---

## 6. Readiness checklist (link-out)

Complete each linked artifact before declaring pilot go-live:

- [ ] [SECURITY_PRIVACY_READINESS.md](./SECURITY_PRIVACY_READINESS.md) — findings reviewed; criticals closed or accepted  
- [ ] [AI_PROVIDER_READINESS.md](./AI_PROVIDER_READINESS.md) — `AI_PRODUCTION_PROVIDER_GATE` satisfied with real input  
- [ ] [PERFORMANCE_RELIABILITY.md](./PERFORMANCE_RELIABILITY.md) — provisional SLOs accepted; load scenarios executed on non-MAT targets  
- [ ] [BACKUP_RESTORE_DR.md](./BACKUP_RESTORE_DR.md) — disposable drill evidence recorded; RPO/RTO agreed  
- [ ] [OBSERVABILITY_ALERTING.md](./OBSERVABILITY_ALERTING.md) — health/ready, logs, alerts wired  
- [ ] [ENVIRONMENT_CONFIGURATION.md](./ENVIRONMENT_CONFIGURATION.md) — production env fail-closed; no secrets in git  
- [ ] [MIGRATION_RUNBOOK.md](./MIGRATION_RUNBOOK.md) — empty→head and upgrade path proven on disposable DB  
- [ ] [DEPLOYMENT_RUNBOOK.md](./DEPLOYMENT_RUNBOOK.md) — platform decided (**EXTERNAL_INPUT_REQUIRED** today); order followed when authorized  
- [ ] [ROLLBACK_RUNBOOK.md](./ROLLBACK_RUNBOOK.md) — image/config rollback understood; migration forward-recovery preference  
- [ ] [PRODUCTION_SMOKE_CHECKLIST.md](./PRODUCTION_SMOKE_CHECKLIST.md) — post-deploy smoke without founder MAT reopen  
- [ ] [ACCOUNT_PROVISIONING.md](./ACCOUNT_PROVISIONING.md) — production users via supported mechanisms only  

---

## 7. Document control

| Field | Value |
|-------|-------|
| Owner | Founder / Product Architect + engineering lead |
| Change rule | Update status tables when gates change; do not invent platform architecture |
| Non-goals | Deploying, destroying MAT volumes, committing secrets |
