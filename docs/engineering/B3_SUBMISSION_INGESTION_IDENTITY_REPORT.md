# B3 — Live submission evidence ingestion and identity review

**Branch:** `b3/live-submission-ingestion-identity`  
**Starting `develop` SHA:** `9f85b2a5ad9e224266fa4138eac29fafefdab49c` (merged B2)  
**Final feature SHA:** `57ca3a5e9514413c8d5b13d7373c6ba9fa802b3b`  
**Squash merge SHA:** `a6134656f85b7785cbe145d0397e2a2892ce9c36`  
**CI run:** `34039302994` (Infrastructure, Contracts, Backend, Frontend, Frontend E2E, Frontend E2E Real — all green)  
**Migration:** `database/migrations/versions/20260906_0004_submission_ingestion.py`

## Scope

B3 moves submission upload through identity confirmation onto the live API and MinIO-backed storage. The phase ends at the identity boundary.

### Live in hybrid mode

- A1/B1 platform domains (unchanged)
- A2/B2 curriculum and assessment authoring (unchanged)
- Submission upload (ACTIVE assessments only)
- Immutable raw source storage + authenticated source proxy
- Page normalization worker (Celery + PyMuPDF)
- Submission list/detail/pages
- Authenticated page-image proxy
- Manual identity review / confirm / unmatched

### Intentionally still mock

- Question-answer mapping
- Evaluation / ledger / annotations
- Reports / analytics / adaptive learning
- Any AI/OCR/identity-extraction provider

**Invariant:** a live submission UUID must never enter mock mapping, evaluation, annotated-paper, review-hub, report, analytics, or learning APIs.

## Migration / tables

`database/migrations/versions/20260906_0004_submission_ingestion.py`

- `submissions`
- `submission_pages`
- `pipeline_jobs`

Tenant-leading indexes and FKs follow existing A1/A2 conventions.

## Storage model

- MinIO/S3 via boto3 (`ObjectStorage`)
- Raw keys: `{tenant_id}/raw/{sha256_prefix}/{uuid}.{ext}` — write-once, never overwritten
- Derived page images under `{tenant_id}/derived/{submission_id}/pages/...` — regenerable
- SHA-256 computed while streaming the upload (bounded by `SUBMISSION_UPLOAD_MAX_BYTES`)
- Duplicate tenant+assessment+hash → `409`
- Accepted types: PDF / PNG / JPEG with signature checks
- Compose `api`/`worker` hardcode `S3_ENDPOINT_URL=http://minio:9000` so host publish-port overrides cannot break in-container MinIO access

## Worker architecture

- Celery worker service in Docker Compose (`worker`)
- Task `submissions.normalize_pages`
- Durable `pipeline_jobs` row with idempotency key
- Recomputes source hash before render; mismatch → `FAILED` + audit
- Ends at `workflow_state=IDENTITY_REVIEW`, `student_match_state=REVIEW_REQUIRED`, confidence `0.0`
- Real E2E CI starts the worker and dumps worker logs on failure

## Permissions

- `submission:read`
- `submission:upload`
- `submission:review`

CVB mapping: Institution Admin (all), Teacher (all three), Evaluator (read+review), Student/Parent (none).

## API surface

- `POST /api/v1/submissions` (multipart)
- `GET /api/v1/submissions`
- `GET /api/v1/submissions/{id}`
- `GET /api/v1/submissions/{id}/pages`
- `GET /api/v1/submissions/{id}/source`
- `GET /api/v1/submission-pages/{id}/image`
- `GET /api/v1/submissions/{id}/identity`
- `POST /api/v1/submissions/{id}/identity/confirm`
- `POST /api/v1/submissions/{id}/identity/unmatched`

## Identity semantics

- No automated extraction in B3
- Candidates = active students from assessment class section, else bounded tenant roster (cap 100)
- Confidence always `0.0` with explicit manual-roster reason
- Confirm → `CONFIRMED` + `PROCESSING` (mapping not live)
- Unmatched → `UNMATCHED` + stay in `IDENTITY_REVIEW`

## Frontend

- `SubmissionHttpApi` live adapter
- Capabilities: `submissions`/`identityReview` live; `mapping`/`evaluation` mock
- Upload page accepts real PDF/PNG/JPEG against ACTIVE assessments
- Detail polls until identity review / failure / confirmed
- Paper viewer renders live page images through authenticated blob URLs
- Live detail hides mapping/evaluation/annotated/review links

## Issue #7

Remains **OPEN**. No AI provider activation in B3.

## Local verification (pre-push)

| Gate | Result |
|------|--------|
| Ruff | pass |
| mypy (strict app) | pass |
| Alembic head | `20260906_0004` |
| Backend pytest | **66 passed** |
| Frontend lint / typecheck / build | pass |
| Frontend Vitest | **73 passed** |
| Contracts validate | pass |
| `docker compose config` | pass |
| Mock Playwright | **15 passed** |
| Real Playwright (MinIO + worker) | **4 passed** (B1 + B2 + B3 + unauthorized) |

## Residual debt

- Bearer token still in `sessionStorage` (CVB debt)
- Upload buffers up to 50 MiB in memory after streaming hash (acceptable for CVB max)
- Page-normalization fan-out and orphan object GC are future hardening
- Mapping/evaluation remain mock until B4+
- Founder approval log Cursor A/B wording left untouched

## Post-merge

Final feature SHA, squash merge SHA, and GitHub Actions run ID are recorded in the merge Cursor report after CI + squash merge.
