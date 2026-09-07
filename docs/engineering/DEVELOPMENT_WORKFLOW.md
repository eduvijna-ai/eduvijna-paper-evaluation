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

## 7. Local tips

- API: `uvicorn app.main:app --reload`
- Worker: `celery -A app.tasks.celery_app.celery_app worker -l INFO`
- Web: `pnpm --filter web dev`
- Compose hardcodes in-container `S3_ENDPOINT_URL=http://minio:9000`

---

## 8. Version history

| Date | Change |
|------|--------|
| 2026-09-04 | Initial two-cursor workflow |
| 2026-09-06 | Single implementation engineer; mandatory `--base develop` |
