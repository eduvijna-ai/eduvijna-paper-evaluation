# B1 — Platform API integration report

**Product:** EduVijna Paper Evaluation (CVB)  
**Author:** Implementation Engineer B  
**Date:** 2026-09-06 (independent-review corrective pass)  
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
- Guardian UI reads are permission-gated with `guardian:read`; forbidden/error states no longer render the false empty state `No guardians linked.`.
- Student PATCH now accepts the same optional academic-assignment invariant as create: both year/section may be null, or both must be a valid pair. Mixed, mismatched, and cross-tenant references remain rejected.
- Real E2E covers create-without-assignment → edit → reload persistence.
- OpenAPI: guardian list, ImportCommit, RubricInput / RubricVersionInput (Issue #6 acceptance).
- Real E2E uses collision-resistant run IDs; suite run twice against same DB.
- GitHub CI now runs both mock Playwright and the real Docker-backed Playwright gate.

## API mode

`NEXT_PUBLIC_API_MODE`:

- `mock` — full mock (Playwright B0 suite)
- `hybrid` (or alias `http`) — platform HTTP + CVB mock

Same-origin Next rewrite preferred (`NEXT_PUBLIC_API_BASE_URL` empty / same-origin).

## Auth

- Login: `POST /api/v1/auth/login` with email/password
- Session: `GET /api/v1/auth/me`
- Access token held in memory (`token-store`) and mirrored to **sessionStorage** for CVB page-refresh survival
- **CVB technical debt:** bearer JWT without HttpOnly cookie sessions (accepted for CVB only, not production-ready authentication)
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

## Students and academic assignment

Student create and PATCH share one invariant:

- `academic_year_id = null` and `class_section_id = null` is a supported unassigned state.
- Otherwise both values are required together and the class section must belong to the selected academic year inside the authenticated tenant.

The real-backend E2E suite verifies that an unassigned student can be created, edited, reloaded, and remain unassigned.

## Guardians

List linked guardians via `GET /students/{id}/guardians`.  
Create/link/unlink invalidate query cache; links survive browser reload.

Frontend behavior follows `guardian:read` independently of `student:read`:

- without `guardian:read`, the guardian query is not issued and a role-aware restricted state is shown;
- API failures show an error/retry state;
- `No guardians linked.` is shown only after an authorized successful empty response.

## E2E

- Mock: `pnpm test:e2e:mock` (existing B0 suite)
- Real: `pnpm test:e2e:real` against Docker API + seed  
  `docker compose exec -T api python -m app.cli.seed_dev`  
  Credentials: `admin@demo.eduvijna.local` / `DemoAdmin!2026` (synthetic)
- CI: dedicated **Frontend E2E Real** job builds the Docker stack, migrates, seeds, runs the real Playwright suite, captures backend logs on failure, and tears the stack down.

## Permissions

Frontend hides/disables actions using A1 permission codes (`student:write`, `student:import`, `guardian:read`, `guardian:write`, …). Backend remains authoritative.

## Known limitations

- No student list pagination (A1)
- Hybrid student detail does not show mock analytics for real UUIDs (avoids identity mixup)
- Bearer token in sessionStorage is CVB debt and must move to an HttpOnly secure cookie/session architecture before production hardening
- CORS must allow the Next origin; request change via B1_BACKEND_CHANGE_REQUESTS if needed
