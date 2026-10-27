# Development Workflow

**Product:** EduVijna Paper Evaluation (CVB v0.1)  
**Last updated:** 2026-09-06  
**Related:** [README.md](../../README.md), [MASTER_PRODUCT_SCOPE.md](../product/MASTER_PRODUCT_SCOPE.md)

---

## 1. Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Git | 2.40+ | Version control |
| Docker Desktop | Latest | Postgres, Redis, MinIO, API containers |
| Make | GNU Make or `make` via WSL | Task runner (Windows: see §2) |
| Node.js | ≥ 20 | Frontend, contracts, pnpm |
| pnpm | 9.x | JS/TS monorepo |
| Python | 3.12 | API, workers, AI package |
| Cursor IDE | Latest | Bounded-phase implementation |

---

## 2. Clone & Initial Setup

```bash
git clone <repository-url> eduvijna-paper-evaluation
cd eduvijna-paper-evaluation
```

### 2.1 Environment file

```bash
cp .env.example .env
```

Edit `.env` for local overrides. **Never commit `.env`.** See [SECURITY_BASELINE.md](../architecture/SECURITY_BASELINE.md).

### 2.2 Bootstrap

```bash
# Unix / macOS / WSL
make bootstrap

# Windows PowerShell (equivalent)
./infra/scripts/bootstrap.ps1
```

### 2.3 Start stack

```bash
make up
# Windows: ./infra/scripts/up.ps1
```

### 2.4 Verify

```bash
make verify
# Windows: ./infra/scripts/verify.ps1
```

Exit code `0` required before opening PR to `develop`.

---

## 3. Implementation model

**One Cursor implementation engineer** handles backend + frontend + contracts +
tests + CI for each bounded phase (for example B3–B6).

Do not split a phase into parallel “Cursor A / Cursor B” ownership streams.

Contract-first remains mandatory: update `packages/contracts/**` when APIs or
schemas change, then implement API and UI against those contracts.

---

## 4. Branch Strategy

```
main          ← release branch (founder-approved milestones only)
develop       ← integration branch (default PR target)
bN/<topic>    ← feature branches from develop
```

### 4.1 Workflow

1. Branch from latest `develop`:
   ```bash
   git fetch origin
   git checkout develop
   git pull --ff-only origin develop
   git checkout -b b6/my-feature
   ```

2. Implement the bounded phase end-to-end.

3. Run verification locally (`make verify` / equivalent).

4. Push and open a PR **explicitly** against `develop`:

   ```bash
   gh pr create \
     --base develop \
     --head b6/my-feature \
     --title "B6: …"
   ```

   **Never rely on the repository default branch to choose PR base.**

   Immediately verify:

   ```bash
   gh pr view <PR> --json baseRefName,headRefName
   ```

   Required: `baseRefName = develop`.

5. PR requirements:
   - Passing CI (Infrastructure, Contracts, Backend, Frontend, Frontend E2E, Frontend E2E Real)
   - No secrets in diff
   - Architecture/docs updated when schema/API contracts change
   - Merge only with `--base develop` confirmed again immediately before merge

6. `main` receives merges from `develop` only at release milestones (founder approval).
   Feature PRs must not retarget or merge into `main`.

### 4.3 No direct post-merge pushes to `develop`

After a feature PR is squash-merged into `develop`:

* verify `origin/develop` equals the squash SHA and `main` is unchanged
* return those SHAs in the Cursor report
* **do not** push a follow-up documentation or “fill in CI SHA” commit directly to `develop`

If post-merge evidence must be recorded in-repo, reconcile it in the **next** normal feature PR or a separately authorized docs PR.

B7 used a docs-only direct follow-up on `develop` (`8d6f5814…`); that pattern is retired.

### 4.4 Branch naming

| Pattern | Example |
|---------|---------|
| `bN/<topic>` | `b8/live-analytics-mastery-evidence` |
| `fix/<topic>` | Hotfix from develop |

---

## 5. Testing Commands

### 5.1 Full suite

```bash
make verify
```

### 5.2 Backend

```bash
cd apps/api
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pytest
ruff check .
mypy .
```

### 5.3 Frontend

```bash
cd apps/web
pnpm lint
pnpm exec tsc --noEmit
pnpm test
pnpm test:e2e
pnpm test:e2e:real
```

### 5.4 Contracts

```bash
cd packages/contracts
pnpm validate
```

---

## 6. CI before merge

All authoritative jobs must be `completed` + `success` on the exact feature SHA:

- Infrastructure
- Contracts
- Backend
- Frontend
- Frontend E2E
- Frontend E2E Real

Do not merge with pending, cancelled, unexpected skip, or stale-head CI.

---

## 7. Founder / local MAT startup (F5 + npm)

Everyday path after one-time prep (Docker Desktop, `apps/api/.venv`, `pnpm install`):

### Backend

1. Ensure **Docker Desktop** is running (postgres / redis / minio).
2. Open this repository in Cursor / VS Code.
3. Select launch configuration **EduVijna Backend + Worker — Local MAT**.
4. Press **F5**.

F5 runs `infra/scripts/local-api-prepare` (idempotent): starts postgres/redis/minio if needed, stops compose `api`/`worker` if they hold port 18000 (volumes kept), applies committed Alembic migrations only (no seed/reset), then starts host FastAPI on `http://127.0.0.1:18000`, a Celery worker, and a separate Celery beat process (Windows cannot embed beat in the worker). Env comes from `apps/api/.env.local` (created from `.env.local.example` on first prepare if missing).

### Frontend

```bash
cd apps/web
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). Dev defaults in `apps/web/.env.development`: `NEXT_PUBLIC_API_MODE=hybrid` and rewrite to `http://127.0.0.1:18000`.

### Safe shutdown

- Stop the debugger (Stop / Shift+F5) — stops API + worker; Docker volumes stay.
- Stop the frontend terminal with Ctrl+C.
- Do **not** run `docker compose down -v` or `make reset` unless you intentionally wipe MAT data.

### Known limitation

Celery beat task `webhooks.deliver_due` may repeatedly log asyncio connection teardown errors on Windows host workers (often `AttributeError: 'NoneType' object has no attribute 'send'`, historically also `RuntimeError: Event loop is closed`). Do not hide these; they are a known worker asyncio lifecycle issue and are not fixed by this DX work. Tasks still report `succeeded` afterward in local MAT.

---

## 8. Local tips

- API: `uvicorn app.main:app --reload` (host MAT port: `18000` with `apps/api/.env.local`)
- Worker: `celery -A app.tasks.celery_app.celery_app worker --beat -l INFO`
- Web: `cd apps/web && npm run dev` (or `pnpm --filter web dev`)
- Compose hardcodes in-container `S3_ENDPOINT_URL=http://minio:9000`

---

## 9. Version history

| Date | Change |
|------|--------|
| 2026-09-04 | Initial two-cursor workflow |
| 2026-09-06 | Single implementation engineer; mandatory `--base develop` |
| 2026-09-20 | Local MAT F5 + `npm run dev` founder startup |
