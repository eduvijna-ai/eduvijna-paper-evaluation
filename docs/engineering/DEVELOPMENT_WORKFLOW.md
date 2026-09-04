# Development Workflow

**Product:** EduVijna Paper Evaluation (CVB v0.1)  
**Last updated:** 2026-09-04  
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
| Cursor IDE | Latest | Parallel Cursor A / B development |

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

Key variables (defaults work for Docker Compose):

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | Async Postgres connection |
| `REDIS_URL` / `CELERY_BROKER_URL` | Celery broker |
| `S3_*` | MinIO object storage |
| `CORS_ORIGINS` | Frontend origin (`http://localhost:3000`) |

### 2.2 Bootstrap

Install dependencies, pull images, run initial migrations, seed demo tenant:

```bash
# Unix / macOS / WSL
make bootstrap

# Windows PowerShell (equivalent)
./infra/scripts/bootstrap.ps1
```

**Bootstrap performs:**

1. pnpm install (root + workspaces)
2. Python venv creation in `apps/api`, `workers`
3. Docker Compose pull
4. Alembic migration `0001_day1_foundation`
5. Seed synthetic demo tenant, institution, roles, sample students

### 2.3 Start stack

```bash
make up
# Windows: ./infra/scripts/up.ps1
```

Services (local defaults):

| Service | URL |
|---------|-----|
| API | http://localhost:8000 |
| API docs | http://localhost:8000/docs |
| Web (when built) | http://localhost:3000 |
| MinIO console | http://localhost:9001 |

### 2.4 Verify

Run the full verification suite (lint, typecheck, tests, contract validation):

```bash
make verify
# Windows: ./infra/scripts/verify.ps1
```

Exit code `0` required before opening PR to `develop`.

---

## 3. Cursor A vs Cursor B Ownership

Parallel development uses **strict path ownership** to prevent merge conflicts.

### Cursor A — Backend, AI, Infrastructure

| Path | Responsibility |
|------|----------------|
| `apps/api/**` | FastAPI application |
| `workers/**` | Celery tasks |
| `ai/**` | AI provider abstractions |
| `infra/**` | Docker, scripts, Makefile |
| `database/migrations/**` | Alembic migrations |
| `docs/architecture/**` | Domain, ledger, workflow specs |

### Cursor B — Frontend

| Path | Responsibility |
|------|----------------|
| `apps/web/**` | Next.js application |
| `packages/ui/**` | Shared UI components |
| Frontend tests | Vitest, Playwright |

### Shared (coordinate before merge)

| Path | Rule |
|------|------|
| `packages/contracts/**` | OpenAPI + JSON Schema — **both** cursors align here first |
| `docs/product/**` | Product scope — founder/architect authority |
| Root `package.json`, `pnpm-workspace.yaml` | Coordinate via PR review |

**Integration:** Cursor B consumes REST from `packages/contracts/openapi.yaml`. Cursor A implements. Neither modifies the other's owned paths without explicit coordination.

---

## 4. Branch Strategy

```
main          ← production-ready releases
develop       ← integration branch (default PR target)
cursor-a/*    ← Cursor A feature branches
cursor-b/*    ← Cursor B feature branches
```

### 4.1 Workflow

1. Branch from latest `develop`:
   ```bash
   git fetch origin
   git checkout develop
   git pull origin develop
   git checkout -b cursor-a/my-feature   # or cursor-b/my-feature
   ```

2. Implement within owned paths only.

3. Run verification locally:
   ```bash
   make verify
   ```

4. Push and open **Pull Request → `develop`** (not directly to `main`).

5. PR requirements:
   - Passing CI (lint, typecheck, test, contracts)
   - No secrets in diff
   - Architecture docs updated if schema/API contract changes
   - Reviewer from other cursor for shared contract changes

6. `main` receives merges from `develop` at release milestones (founder approval).

### 4.2 Branch naming

| Pattern | Example |
|---------|---------|
| `cursor-a/<topic>` | `cursor-a/day1-migration` |
| `cursor-b/<topic>` | `cursor-b/review-queue-ui` |
| `fix/<topic>` | Either cursor — hotfix |

---

## 5. Testing Commands

### 5.1 Full suite

```bash
make verify
```

### 5.2 Backend (Cursor A)

```bash
cd apps/api
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pytest
ruff check .
mypy .
```

```bash
cd workers
pytest
```

### 5.3 Frontend (Cursor B)

```bash
pnpm install
pnpm --filter @eduvijna/web test        # Vitest
pnpm --filter @eduvijna/web test:e2e    # Playwright (when configured)
pnpm lint:contracts                      # OpenAPI / JSON Schema validation
```

### 5.4 Contracts (shared)

```bash
pnpm lint:contracts
```

Validates `packages/contracts/openapi.yaml` and JSON schemas.

### 5.5 Database migrations

```bash
cd apps/api
alembic upgrade head
alembic revision --autogenerate -m "description"   # Cursor A only
```

---

## 6. Local Development Tips

### 6.1 API hot reload

When running API outside Docker:

```bash
cd apps/api
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Ensure `.env` points `POSTGRES_HOST=localhost` if not using Compose network.

### 6.2 Celery worker

```bash
cd workers
celery -A worker.app worker --loglevel=info
```

### 6.3 Frontend dev server

```bash
pnpm --filter @eduvijna/web dev
```

### 6.4 Docker logs

```bash
docker compose -f infra/docker-compose.yml logs -f api
```

---

## 7. Contract-First API Changes

1. Edit `packages/contracts/openapi.yaml` (+ JSON schemas if needed).
2. Run `pnpm lint:contracts`.
3. Cursor A implements FastAPI routes.
4. Cursor B updates TanStack Query hooks / types.
5. Both verify against `make verify`.

---

## 8. Documentation

| When | Update |
|------|--------|
| New entity or table | `docs/architecture/DOMAIN_MODEL.md`, `DATABASE_SCHEMA.md` |
| New API endpoint | `packages/contracts/openapi.yaml`, `API_CONVENTIONS.md` if pattern change |
| New workflow state | `WORKFLOW_STATES.md` |
| Architecture decision | New ADR in `docs/architecture/adrs/` + `ADR_INDEX.md` |

---

## 9. Getting Help

| Topic | Document |
|-------|----------|
| Product scope | [MASTER_PRODUCT_SCOPE.md](../product/MASTER_PRODUCT_SCOPE.md) |
| Requirements IDs | [REQUIREMENTS_REGISTER.md](../product/REQUIREMENTS_REGISTER.md) |
| Architecture | [ADR_INDEX.md](../architecture/ADR_INDEX.md) |
| Security | [SECURITY_BASELINE.md](../architecture/SECURITY_BASELINE.md) |

---

## 10. Document Control

| Version | Date | Change |
|---------|------|--------|
| 0.1 | 2026-09-04 | Initial development workflow |
