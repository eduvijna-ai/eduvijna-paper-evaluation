# B2 — Live A2 authoring integration

**Branch:** `b2/live-authoring-integration`  
**Base:** `develop` at `74fd4902478642d0f93fee9aa154c5669430569b`  
**Final feature SHA (pre-merge):** see commit on branch after conditional-pass fixes  
**Project gate:** `CONDITIONAL PASS — required fixes completed and all CI green`

## Scope

B2 moves the curriculum and assessment-authoring slice from mock fixtures to the live A2 HTTP API while preserving the hybrid boundary for later domains.

### Live in hybrid mode

- Auth, institution, academic years, class sections, students, import, guardians (A1/B1)
- Curriculum list/detail/tree (A2)
- Assessment list/detail/create (A2)
- Latest assessment-version question tree
- Answer-key versions
- Rubric criteria through rubric → rubric-version discovery
- Question → curriculum mappings

### Intentionally still mock

- Submissions
- Evaluation workspaces
- Reports
- Analytics
- Adaptive learning

Live A2 assessment identities are not routed into those mock downstream domains. The assessment detail page hides mock analytics for live assessments and labels submissions as not live yet.

## Backend integration seam

A2 already exposed rubric creation, rubric-version creation and criterion listing, but the client could not discover a rubric version ID from a rubric ID. B2 adds:

`GET /api/v1/rubrics/{rubric_id}/versions`

The route requires `rubric:read`, validates the rubric in the authenticated tenant, returns tenant-scoped versions ordered by `version_number`, and returns 404 for unknown/cross-tenant rubric identities.

OpenAPI documents the `200` response as an array of `RubricVersion` output objects aligned with the runtime dump and `A2RubricVersion` fields used by the live adapter.

No database migration is required. No B3 scope was added. Issue #7 (AI proposal context binding) remains out of scope and open.

## Frontend adapter

`AuthoringHttpApi` keeps A2 snake_case/version-centric DTOs behind the shared `ApiClient` view models. It resolves the latest assessment version for question-driven views and never falls back to mock data on live authoring API errors.

The existing mock provider remains source-compatible. `createAssessment` is optional on the shared client so mock mode retains its demo creation path while hybrid mode performs a real A2 POST.

## Permissions

- Curriculum reads depend on `curriculum:read`.
- Assessment reads depend on `assessment:read`.
- Live assessment creation is shown only with `assessment:manage`.
- Rubric reads depend on `rubric:read`.
- Backend authorization remains authoritative.

## Verification results (local, CI-equivalent)

| Gate | Result |
|------|--------|
| Backend Ruff / strict mypy / Alembic upgrade head / pytest | **58 passed** |
| Contracts OpenAPI + JSON schema validation | pass |
| Frontend lint / typecheck / Vitest / Next.js production build | **65 passed** |
| Docker Compose config validation | pass |
| Mock Playwright | **15 passed** |
| Real-backend Playwright (B1 platform + unauthorized + B2 authoring) | **3 passed** |

Conditional-pass completion included:

- Unambiguous Playwright assertion for curriculum node text (`getByText(..., { exact: true })`)
- Explicit foreign-tenant regression for `GET /api/v1/rubrics/{id}/versions` → **404** with no content leak
- Typed OpenAPI `RubricVersion` array response + strengthened B2 contract test

## Residual debt (acceptable for B2)

- Bearer token persistence in `sessionStorage` remains CVB-only technical debt.
- Assessment version selection is "latest version number" because A2 does not publish a current-version pointer on assessment list/get responses.
- Curriculum/assessment list hydration performs small CVB-scale fan-out requests for tree/count enrichment; pagination/batched read models are future optimization work.
- Submission/evaluation/analytics/reporting/learning remain mock until their backend phases are integrated.
- Production session hardening remains later work.
- `docs/FOUNDER_APPROVAL_LOG.md` still contains historical Cursor A/Cursor B ownership wording; treated as governance debt (not rewritten in this PR).
