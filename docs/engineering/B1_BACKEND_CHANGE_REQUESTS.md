# B1 — Backend change requests

**From:** Implementation Engineer B  
**To:** Implementation Engineer A  
**Date:** 2026-09-05  
**Status:** Optional / nice-to-have for B1 (frontend works without these)

## BCR-B1-001 — Student guardian link listing

**Need:** `GET /api/v1/students/{id}/guardians` returning linked guardians (+ relationship_type).

**Why:** Student detail cannot reliably show existing links after reload; A1 only exposes link/unlink.

**Priority:** P1 for B1 polish / B2.

## BCR-B1-002 — HttpOnly cookie session (or BFF)

**Need:** Prefer secure cookie-based session over browser-persisted bearer JWT.

**Why:** CVB currently mirrors access tokens into `sessionStorage` as technical debt.

**Priority:** P0 for production; acceptable debt for CVB.

## BCR-B1-003 — CORS (optional if using Next rewrites)

**Need:** Allow `http://localhost:3000` / `http://127.0.0.1:3001` only if the frontend calls the API **cross-origin** directly.

**CVB default:** Frontend uses Next.js same-origin rewrites (`API_UPSTREAM_URL`) so browser CORS is not required for local hybrid.

**Priority:** Optional.

## BCR-B1-004 — Student list pagination

**Need:** Cursor/limit pagination on `GET /api/v1/students`.

**Why:** Documented A1 limitation; UI intentionally has no fake pagination.

**Priority:** Later.
