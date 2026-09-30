# Backup, Restore & Disaster Recovery

**Product:** EduVijna Paper Evaluation  
**Last updated:** 2026-09-30  
**Related:** [PRODUCTION_READINESS.md](./PRODUCTION_READINESS.md), [MIGRATION_RUNBOOK.md](./MIGRATION_RUNBOOK.md), `infra/scripts/backup-*.sh|.ps1`, `restore-*.sh|.ps1`, `dr-restore-drill.sh|.ps1`

---

## 1. Purpose

Define how to back up and restore **PostgreSQL** and **S3-compatible object storage** for pre-production drills. All restore practice uses **ISOLATED disposable copies only**.

---

## 2. Hard safety rules

1. **NEVER destroy founder MAT volumes** (`docker compose down -v` against MAT, volume wipes, or restore-over-MAT).  
2. **NEVER** point restore scripts at known MAT Compose defaults without `OVERRIDE_MAT_SAFETY=1`, and even then **prefer disposable names**.  
3. Scripts require explicit `DISPOSABLE_*` environment variables (see §5).  
4. Redis is **not** system of record — do not treat Redis dumps as academic truth. Rebuild queues by re-enqueue / operator replay after DB+object restore if needed.  
5. Do not commit backup artifacts containing real PII to git.

Known MAT / local Compose defaults that scripts treat as unsafe targets (non-exhaustive):

| Kind | Default / pattern |
|------|-------------------|
| DB name | `eduvijna` |
| DB user | `eduvijna` |
| Published Postgres port | `15432` |
| Published MinIO API port | `19000` |
| Bucket | `eduvijna-papers` |
| Compose volume names | project `pgdata` / `miniodata` / `redisdata` |

---

## 3. What to back up

| Store | SoT? | Backup content |
|-------|------|----------------|
| PostgreSQL | **Yes** — domain SoT | Logical dump (schema + data) at known Alembic revision |
| Object storage (S3-compatible) | **Yes** — immutable raw papers + artifacts | Bucket/prefix sync or versioned copy |
| Redis | **No** | Optional operational convenience only; expect empty/rebuild after DR |
| Application images / config | Ops | Image tags + sealed config (no secrets in git) |

---

## 4. RPO / RTO

| Metric | Status |
|--------|--------|
| RPO (max acceptable data loss) | **TBD** — EXTERNAL_INPUT_REQUIRED |
| RTO (max acceptable restore time) | **TBD** — EXTERNAL_INPUT_REQUIRED |

Document agreed numbers here once founder/ops supply them. Until then, drills measure **observed** restore duration only.

---

## 5. Script contract (stubs)

Location: `infra/scripts/`

| Script | Purpose |
|--------|---------|
| `backup-postgres.sh` / `.ps1` | Dump disposable Postgres to a file path |
| `restore-postgres.sh` / `.ps1` | Restore dump into disposable Postgres only |
| `backup-object-storage.sh` / `.ps1` | Sync/copy disposable bucket/prefix |
| `restore-object-storage.sh` / `.ps1` | Restore into disposable bucket only |
| `dr-restore-drill.sh` / `.ps1` | Orchestrate synthetic backup→restore on disposable resources |

Required pattern (all scripts):

- Demand `DISPOSABLE_DATABASE_URL` or `DISPOSABLE_POSTGRES_*` / `DISPOSABLE_S3_*` as applicable.  
- Refuse MAT-like defaults unless `OVERRIDE_MAT_SAFETY=1`.  
- Prefer names containing `disposable`, `drill`, or `tmp`.  
- Print refusal reasons; exit non-zero rather than “best effort” against MAT.

Stubs may call `pg_dump` / `pg_restore` / `aws s3 sync` (or compatible) **only** when disposable env is validated; otherwise they exit with instructions.

---

## 6. Drill procedure (synthetic)

1. Provision **new** disposable Postgres + object storage (separate ports, DB name, bucket).  
2. Run migrations to head (`20260918_0022`) — [MIGRATION_RUNBOOK.md](./MIGRATION_RUNBOOK.md).  
3. Load synthetic data (not founder MAT).  
4. `backup-postgres` + `backup-object-storage`.  
5. Destroy **only** the disposable instance (never MAT).  
6. Recreate disposable instance; `restore-postgres` + `restore-object-storage`.  
7. Verify: `/ready`, row counts smoke, sample object GET, Alembic current = expected.  
8. Record duration → feeds future RTO discussion.

Or use `dr-restore-drill.*` once disposable env vars are set.

**Preferred Windows/local executed drill (real, not stub):**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File infra/scripts/run-disposable-dr-drill.ps1
```

This spins **temporary** Postgres (`25432`) + MinIO (`29000`) only, seeds synthetic rows/objects, `pg_dump`/`pg_restore`, `aws s3 sync` backup/restore, verifies row counts + FK join + object payload, confirms MAT containers on `15432`/`19000` remain healthy, then tears down disposable resources only.

---

## 7. Migration recovery after restore

- Prefer restore of DB taken at a known revision, then `alembic upgrade head` if the dump is behind application images.  
- Prefer **forward recovery** (upgrade) over downgrade for production-shaped systems — [ROLLBACK_RUNBOOK.md](./ROLLBACK_RUNBOOK.md), [MIGRATION_RUNBOOK.md](./MIGRATION_RUNBOOK.md).  
- Object storage restore must match DB foreign keys to content hashes / keys; mismatch is a failed drill.

---

## 8. Evidence log

| Date | Drill ID | Disposable targets | Duration | Result | Notes |
|------|----------|--------------------|----------|--------|-------|
| 2026-09-30 | `DR_DRILL_20260930111437` | PG `25432` / MinIO `29000`; DB `eduvijna_disposable_drill`; bucket `eduvijna-disposable-drill` | ~23s | **PASS** | Evidence: [evidence/DR_DRILL_20260930111437.txt](./evidence/DR_DRILL_20260930111437.txt). MAT postgres+minio remained healthy. |

---

## 9. Sign-off

| Role | Date | Decision |
|------|------|----------|
| Engineering | 2026-09-30 | Disposable DR drill **PASS**; scripts + evidence recorded |
| Founder / ops | | RPO/RTO TBD (EXTERNAL_INPUT_REQUIRED); MAT volumes untouched |
