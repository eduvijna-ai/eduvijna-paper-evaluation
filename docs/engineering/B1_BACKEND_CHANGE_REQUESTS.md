# B1 — Backend change requests

**From:** Implementation Engineer  
**To:** Chief Architect  
**Updated:** 2026-09-06  
**Status:** B1 corrective gate classifications

## BCR-B1-001 — Student guardian link listing

**Need:** `GET /api/v1/students/{id}/guardians` returning linked guardians (+ relationship_type).

**Classification:** **RESOLVED**

Implemented as `GET /api/v1/students/{student_id}/guardians` with `StudentGuardianLinkOut`
(`student_id`, `guardian_id`, `display_name`, `email`, `phone`, `relationship_type`).
Permission: `guardian:read`. Tenant-scoped; cross-tenant student → 404.

## BCR-B1-002 — HttpOnly cookie session (or BFF)

**Need:** Prefer secure cookie-based session over browser-persisted bearer JWT.

**Classification:** **PRODUCTION_HARDENING**

CVB currently mirrors access tokens into `sessionStorage` as accepted technical debt (F08).

## BCR-B1-003 — CORS (optional if using Next rewrites)

**Need:** Allow browser origins only if the frontend calls the API cross-origin directly.

**Classification:** **NOT REQUIRED FOR CVB**

Next.js same-origin rewrites (`API_UPSTREAM_URL`) verified for login/`/auth/*` in real E2E.

## BCR-B1-004 — Student list pagination

**Need:** Cursor/limit pagination on `GET /api/v1/students`.

**Classification:** **AFTER_CLIENT_APPROVAL**

## AbortSignal broad adoption

**Classification:** **LOW / later**

`AbortSignal` exists on the HTTP client but is not widely wired through every call site.
