# B2 — Live A2 authoring integration

**Branch:** `b2/live-authoring-integration`  
**Base:** `develop` at `74fd4902478642d0f93fee9aa154c5669430569b`

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

No database migration is required.

## Frontend adapter

`AuthoringHttpApi` keeps A2 snake_case/version-centric DTOs behind the shared `ApiClient` view models. It resolves the latest assessment version for question-driven views and never falls back to mock data on live authoring API errors.

The existing mock provider remains source-compatible. `createAssessment` is optional on the shared client so mock mode retains its demo creation path while hybrid mode performs a real A2 POST.

## Permissions

- Curriculum reads depend on `curriculum:read`.
- Assessment reads depend on `assessment:read`.
- Live assessment creation is shown only with `assessment:manage`.
- Backend authorization remains authoritative.

## Verification additions

- Backend tests for rubric-version discovery/authentication/scoping.
- Frontend mapper tests for curricula, assessments, questions, answer keys, rubrics and curriculum mappings.
- Real-backend Playwright flow creates a curriculum, creates an assessment through the browser, adds a question/answer/rubric/mapping through A2, and verifies all live browser read views.
- Existing B1 real-backend and mock Playwright suites remain in CI.

## Residual debt

- Bearer token persistence in `sessionStorage` remains CVB-only technical debt.
- Assessment version selection is "latest version number" because A2 does not publish a current-version pointer on assessment list/get responses.
- Curriculum/assessment list hydration performs small CVB-scale fan-out requests for tree/count enrichment; pagination/batched read models are future optimization work.
- Submission/evaluation/analytics/reporting/learning remain mock until their backend phases are integrated.
