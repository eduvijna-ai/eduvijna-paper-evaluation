# Rollback Runbook

**Product:** EduVijna Paper Evaluation  
**Last updated:** 2026-09-30  
**Related:** [DEPLOYMENT_RUNBOOK.md](./DEPLOYMENT_RUNBOOK.md), [MIGRATION_RUNBOOK.md](./MIGRATION_RUNBOOK.md), [BACKUP_RESTORE_DR.md](./BACKUP_RESTORE_DR.md)

---

## 1. Purpose

Recover from a bad release without destroying data volumes or founder MAT environments.

---

## 2. Decision order

1. **Config rollback** — if only env/feature flags are wrong.  
2. **Image rollback** — if application code/regression; DB schema compatible with previous image.  
3. **Migration forward-recovery** — if schema already upgraded; prefer new fix migration over downgrade.  
4. **Restore from backup** — last resort on the affected environment’s own backups; **never** onto founder MAT; disposable drills only for practice.

---

## 3. Image rollback

1. Identify last known-good image tag (`GIT_SHA`).  
2. Redeploy API + worker (+ web if needed) to that tag.  
3. Confirm `GET /health`, `GET /ready`, version endpoint.  
4. Confirm workers consume queues.  
5. Run abbreviated [PRODUCTION_SMOKE_CHECKLIST.md](./PRODUCTION_SMOKE_CHECKLIST.md).

**Constraint:** Previous image must be compatible with **current** DB revision. If the bad release already ran migrations that old images cannot read, do **not** roll image alone — use forward-recovery (§4).

---

## 4. Migration forward-recovery (preferred)

| Situation | Action |
|-----------|--------|
| Upgrade failed mid-way | Fix error; re-run `alembic upgrade head` on disposable/staging first, then prod when authorized |
| Upgrade succeeded but app buggy | Ship hotfix image **or** additive fix revision; keep head moving forward |
| Need older app behavior | Only if older image supports current schema; else forward-fix |

`alembic downgrade` is **not** the default production recovery path. Allowed on disposable DBs for engineering experiments only.

---

## 5. Config rollback

Revert sealed configuration to last known-good:

- Feature-related: AI provider modes, upload scanner, webhook flags  
- Fail-closed restores: `WEBHOOK_ALLOW_INSECURE_DESTINATIONS=false`, `B19_TEST_PROVIDERS_ENABLED=false`  
- Rotate compromised secrets (`AUTH_TOKEN_SECRET`, `OPENAI_API_KEY`, integration keys) rather than “rolling back” to leaked values  

Restart API/worker after config change; smoke auth + one upload path.

---

## 6. Data restore caveat

Restoring Postgres + object storage must stay paired (hashes/keys). Redis may be empty after restore — re-enqueue jobs as needed. See [BACKUP_RESTORE_DR.md](./BACKUP_RESTORE_DR.md).

**Forbidden:** `docker compose down -v` against MAT; restore scripts targeting MAT defaults without disposable isolation.

---

## 7. Post-rollback

- Record incident, correlation IDs, from/to image SHAs, Alembic revision  
- Update [SECURITY_PRIVACY_READINESS.md](./SECURITY_PRIVACY_READINESS.md) if security-related  
- Do not reopen founder MAT as validation for a production rollback  
