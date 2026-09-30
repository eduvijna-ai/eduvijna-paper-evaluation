# Migration Runbook

**Product:** EduVijna Paper Evaluation  
**Last updated:** 2026-09-30  
**Alembic head (current):** `20260918_0022` (`down_revision = 20260917_0021`)  
**Related:** `database/migrations/`, `infra/scripts/migrate.sh|.ps1`, [BACKUP_RESTORE_DR.md](./BACKUP_RESTORE_DR.md), [ROLLBACK_RUNBOOK.md](./ROLLBACK_RUNBOOK.md)

---

## 1. Purpose

How to bring PostgreSQL schema from empty → head, and how to upgrade existing DBs, with failure visibility. Practice on **disposable** databases only — never against founder MAT volumes.

---

## 2. Tooling

| Path | Role |
|------|------|
| `apps/api/alembic.ini` | Alembic config (container: `/app/alembic.ini`) |
| `database/migrations/` | Versions tree (mounted read-only in Compose API/worker) |
| `infra/scripts/migrate.sh` / `migrate.ps1` | `alembic upgrade head` via running `api` container or local `apps/api` |

Helper behavior: if Compose service `api` is running, executes:

`docker compose exec -T api alembic -c /app/alembic.ini upgrade head`

---

## 3. Clean bootstrap (empty → head)

1. Provision empty disposable Postgres (name/port **not** MAT defaults).  
2. Set `DATABASE_URL` for API to that instance.  
3. Ensure application image/code includes migrations through **`20260918_0022`**.  
4. Run migrate script or equivalent `alembic upgrade head`.  
5. Verify:

```text
alembic -c alembic.ini current
# expect: 20260918_0022 (head)
```

6. Optional: application `/ready` returns ready after migrate.  
7. **Do not** run `seed_dev` as production bootstrap — [ACCOUNT_PROVISIONING.md](./ACCOUNT_PROVISIONING.md).

---

## 4. Upgrade path (existing DB → head)

1. Backup disposable/staging DB first ([BACKUP_RESTORE_DR.md](./BACKUP_RESTORE_DR.md)).  
2. Confirm current revision: `alembic current`.  
3. Review pending revisions under `database/migrations/versions/` (linear chain through `20260918_0022`).  
4. Deploy application build that **includes** the migration files for the target head **before or with** migrate (ordering per [DEPLOYMENT_RUNBOOK.md](./DEPLOYMENT_RUNBOOK.md) when authorized).  
5. `alembic upgrade head`.  
6. Re-check `alembic current` and `/ready`.  
7. Run [PRODUCTION_SMOKE_CHECKLIST.md](./PRODUCTION_SMOKE_CHECKLIST.md) items that touch schema-dependent APIs.

---

## 5. Failure visibility

| Failure | Visible as | Action |
|---------|------------|--------|
| Migrate exception | Non-zero exit; Alembic stderr | Do not ignore; fix forward or restore disposable from backup |
| Partial upgrade | `alembic current` behind head; app errors | Prefer **forward** fix migration / complete upgrade |
| App ahead of DB | API/worker errors on missing columns | Stop serving traffic; finish migrate |
| DB ahead of app | Unexpected; rare | Align image to migration set; avoid blind `downgrade` in prod-shaped envs |
| Lock / connection | Hang or OperationalError | Check DB locks; never wipe MAT |

Capture correlation/build (`GIT_SHA`) in incident notes.

---

## 6. Rollback vs forward-recovery

**Preference: forward-recovery** (fix forward with a new revision or complete the upgrade) over `alembic downgrade` on production-shaped data.

Downgrade is acceptable only on disposable DBs during development. See [ROLLBACK_RUNBOOK.md](./ROLLBACK_RUNBOOK.md).

---

## 7. Head reference

| Revision ID | File (abbrev) |
|-------------|----------------|
| `20260918_0022` | `20260918_0022_b20_multisubject_multilingual.py` |

If head advances later, update this runbook in the same change set as the migration.

---

## 8. Safety

- No `docker compose down -v` as migration “fix.”  
- No migrate/restore onto founder MAT without explicit disposable isolation.  
- No secrets in migration files.
