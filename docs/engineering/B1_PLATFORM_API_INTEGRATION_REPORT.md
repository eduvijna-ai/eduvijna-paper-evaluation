# B1 — Platform API integration report

**Product:** EduVijna Paper Evaluation (CVB)  
**Author:** Implementation Engineer B  
**Date:** 2026-09-06 (B1 corrective gate)  
**Branch:** `cursor-b/platform-api-integration`  
**Base:** `origin/develop`

## Summary

B1 replaces B0 mock-only platform behavior with **hybrid domain routing**:

| Domain | Provider |
|--------|----------|
| Auth, Institution, Academic years, Class sections, Students, Student CSV import, Guardians | **HTTP (A1)** |
| Curriculum, Assessment, Answer key, Rubric, Submissions, Evaluation, Analytics, Learning | **MOCK** (until later phases) |

Ordinary feature components call `api.*` and `getApiCapabilities()` — they do not branch on transport mode via `getApiMode()`.

## Corrective gate (2026-09-06)

- Import validation aligns with DB uniqueness (`student_code` + class/roll), structured reason codes, structured session/conflict errors.
- Frontend normalizes nested import `data` rows and maps `committed_count` → `committedCount`.
- Mock identity lookups fail closed (no `students[0]` substitution).
- `GET /api/v1/students/{id}/guardians` + UI refetch after link/unlink/reload.
- OpenAPI: guardian list, ImportCommit, RubricInput / RubricVersionInput (Issue #6 acceptance).
- Real E2E uses collision-resistant run IDs; suite run twice against same DB.

## API mode

`NEXT_PUBLIC_API_MODE`:

- `mock` — full mock (Playwright B0 suite)
- `hybrid` (or alias `http`) — platform HTTP + CVB mock

Same-origin Next rewrite preferred (`NEXT_PUBLIC_API_BASE_URL` empty / same-origin).

## Auth

- Login: `POST /api/v1/auth/login` with email/password
- Session: `GET /api/v1/auth/me`
- Access token held in memory (`token-store`) and mirrored to **sessionStorage** for CVB page-refresh survival
- **CVB technical debt:** bearer JWT without HttpOnly cookie sessions (accepted for CVB)
- 401 clears session and redirects to `/login`
- Mock mode retains demo role buttons for B0 E2E

## DTO mapping

UI view-models stay camelCase. Transport stays OpenAPI snake_case.

- Student / guardian / academic structure mappers
- `importRowApiToView` / `importValidationApiToView` / `importCommitApiToView`
- `studentGuardianLinkApiToView`

## Student import

1. Download CSV template
2. Validate — outcomes + normalized row fields
3. Commit VALID rows
4. Success: `Imported N student(s).` from `committedCount`
5. Structured 409 codes mapped to specific UX (expired / invalid / roster conflict)

## Guardians

List linked guardians via `GET /students/{id}/guardians`.  
Create/link/unlink invalidate query cache; links survive browser reload.

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
