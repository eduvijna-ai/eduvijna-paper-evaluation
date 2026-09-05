# B1 — Platform API integration report

**Product:** EduVijna Paper Evaluation (CVB)  
**Author:** Implementation Engineer B  
**Date:** 2026-09-05  
**Branch:** `cursor-b/platform-api-integration`  
**Base:** `origin/develop` (includes A2 merge)

## Summary

B1 replaces B0 mock-only platform behavior with **hybrid domain routing**:

| Domain | Provider |
|--------|----------|
| Auth, Institution, Academic years, Class sections, Students, Student CSV import, Guardians | **HTTP (A1)** |
| Curriculum, Assessment, Answer key, Rubric, Submissions, Evaluation, Analytics, Learning | **MOCK** (until later phases) |

Components call `api.*` only. They do not branch on mock vs HTTP.

## API mode

`NEXT_PUBLIC_API_MODE`:

- `mock` — full mock (Playwright B0 suite)
- `hybrid` (or alias `http`) — platform HTTP + CVB mock

`NEXT_PUBLIC_API_BASE_URL` — default local compose publish port `http://localhost:18000` (maps to container `:8000`)

## Auth

- Login: `POST /api/v1/auth/login` with email/password
- Session: `GET /api/v1/auth/me`
- Access token held in memory (`token-store`) and mirrored to **sessionStorage** for CVB page-refresh survival
- **CVB technical debt:** A1 returns bearer JWT without HttpOnly cookie sessions. Prefer cookie sessions when backend supports them. Never store passwords. Never log tokens.
- 401 clears session and redirects to `/login`
- Expired `expiresAt` forces re-login
- Mock mode retains demo role buttons for B0 E2E

## DTO mapping

UI view-models stay camelCase / CVB-friendly. Transport stays A1 OpenAPI snake_case.

- `studentApiToViewModel` / `studentFormToApi`
- `guardianApiToViewModel` / `guardianFormToApi`
- Academic year / class section mappers
- Import validation summarizer

Known intentional difference: UI `Student.display_name` maps from A1 `full_name`; `external_ref` prefers `roll_number` then `student_code`.

## Student import

1. Download client-generated CSV template (headers match backend)
2. `POST /students/import/validate` — show outcomes
3. `POST /students/import/commit` only after validation (VALID rows only)
4. Summary with created count when returned

## Guardians

Create/update/list + link/unlink on student detail.  
**Limitation:** A1 has no “list guardians for student” endpoint; linked state after create is session-optimistic. See `B1_BACKEND_CHANGE_REQUESTS.md`.

## E2E

- Mock: `pnpm test:e2e:mock` (existing ≥15 flows)
- Real: `pnpm test:e2e:real` against Docker API + seed  
  `docker compose exec api python -m app.cli.seed_dev`  
  Credentials: `admin@demo.eduvijna.local` / `DemoAdmin!2026` (synthetic)

## Permissions

Frontend hides/disables actions using A1 permission codes (`student:write`, `student:import`, `guardian:write`, …). Backend remains authoritative.

## Known limitations

- No student list pagination (A1)
- No GET student↔guardian links listing
- Hybrid student detail does not show mock analytics for real UUIDs (avoids identity mixup)
- Bearer token in sessionStorage is CVB debt
- CORS must allow the Next origin; request change via B1_BACKEND_CHANGE_REQUESTS if needed
