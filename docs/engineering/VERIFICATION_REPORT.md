# Verification Report — Day 1 Bootstrap

**Date/time:** 2026-09-04 (IST / UTC+5:30)  
**Operator:** Cursor A (Implementation Engineer)  
**Task:** Day 1 Bootstrap / Architecture Contract / Infrastructure Foundation

## Environment

| Item | Value |
|------|-------|
| OS | Windows 10 (build 26200) |
| Git | 2.39.1.windows.1 |
| gh | 2.73.0 |
| Docker | 29.2.1 |
| Docker Compose | v5.0.2 |
| Host Python (`py`) | 3.11.9 (launcher) |
| API runtime / venv | Python 3.12 (apps/api/.venv + Docker `python:3.12-slim`) |
| Node | v22.13.0 |
| pnpm | 11.24.0 |
| GitHub account | `eduvijna` (User) |

## Repository

| Item | Value |
|------|-------|
| URL | https://github.com/eduvijna/eduvijna-paper-evaluation |
| Visibility | **PRIVATE** |
| Branches | `main`, `develop`, `cursor-a/bootstrap-foundation` |
| Working branch | `cursor-a/bootstrap-foundation` |
| PR | See section below after open |

## Commands executed

1. `git --version` / `gh --version` / `gh auth status`
2. `gh repo create eduvijna/eduvijna-paper-evaluation --private ...`
3. Branch create/push: `main` → `develop` → `cursor-a/bootstrap-foundation`
4. Repo settings: squash merge preferred, delete head on merge
5. Branch protection on `main` (PR required, no force push)
6. `docker compose config`
7. `docker compose up -d --build`
8. Health checks: Postgres, Redis, MinIO, API
9. `alembic upgrade head` / `downgrade base` / `upgrade head`
10. HTTP: `/health`, `/ready`, `/api/v1/system/version`
11. `ruff check`, `mypy app`, `pytest` (5 passed)
12. Contracts validation (`npm run validate`)
13. Secret pattern scan / `.env` gitignore check
14. Labels + CVB tracking issue via `gh`

## Verification results

| # | Check | Result |
|---|-------|--------|
| 1 | `git status` clean after commit | PASS (post-commit) |
| 2 | No secrets tracked (`.env` ignored) | PASS |
| 3 | `docker compose config` | PASS |
| 4 | Start local infrastructure | PASS |
| 5 | Postgres healthy | PASS |
| 6 | Redis healthy | PASS |
| 7 | MinIO healthy | PASS |
| 8 | Alembic migrations upgrade | PASS (`20260904_0001`) |
| 9 | API running | PASS (healthy) |
| 10 | `GET /health` | PASS `{"status":"ok"}` |
| 11 | `GET /ready` | PASS `{"status":"ready"}` |
| 12 | `GET /api/v1/system/version` | PASS |
| 13 | pytest | PASS (5 tests) |
| 14 | Ruff | PASS |
| 15 | mypy | PASS |
| 16 | Schema / OpenAPI validation | PASS |
| 17 | CI-equivalent local verify | PASS |
| 18 | Migration upgrade inspect | PASS (12 domain tables + alembic_version) |
| 19 | Migration downgrade + re-upgrade | PASS |
| 20 | Secret / private-key grep | PASS (no matches) |
| 21 | Repository PRIVATE | PASS |
| 22 | Remote branches exist | PASS |
| 23 | PR opened to `develop` | PASS (see PR URL) |

## Known limitations

1. Host publish ports remapped from common defaults to avoid Windows/Hyper-V reserved port binding (`6379` blocked): Postgres `15432`, Redis `16379`, MinIO `19000`/`19001`, API `18000`. Documented in `.env.example`.
2. Host launcher Python is 3.11; CVB API uses **Python 3.12** via Docker and `apps/api/.venv`.
3. Evaluation/curriculum/submission tables are specified in docs only; not in Day-1 migration (by design).
4. Frontend is placeholder only (Cursor B).
5. Celery/AI providers are stubs only for this bootstrap.
6. No CODEOWNERS (GitHub usernames for ownership teams not confirmed).

## External permission blockers

None for repository creation under `eduvijna`.  
Branch protection on `main` **succeeded** (PR required, force pushes disabled).

## GitHub settings

| Setting | Status |
|---------|--------|
| Private repository | Configured |
| Squash merge preferred | Configured |
| Merge commit / rebase disabled | Configured |
| Delete head branch on merge | Configured |
| `main` branch protection (PR + no force push) | Configured |
| Labels | Configured |
| CODEOWNERS | Not created (owners unknown) |

## Next-step recommendation

1. Merge PR into `develop` after review (do not merge to `main` without release process).
2. Cursor B starts from `cursor-a/bootstrap-foundation` (or `develop` after merge) to scaffold Next.js app under `apps/web` / `packages/ui`.
3. Cursor A Day 2+: assessment/rubric migrations, object-storage upload contract, Celery job skeleton.
