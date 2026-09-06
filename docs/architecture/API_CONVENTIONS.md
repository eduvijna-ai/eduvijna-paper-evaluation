# API Conventions

**Product:** EduVijna Paper Evaluation (CVB v0.1)  
**Base URL:** `/api/v1`  
**Contract source:** `packages/contracts/openapi.yaml`  
**Last updated:** 2026-09-04  
**Related:** [ADR-001](adrs/ADR-001-modular-monolith.md) (no GraphQL)

---

## 1. Design Principles

1. **REST over HTTP/JSON** — Resource-oriented endpoints; no GraphQL in CVB.
2. **Contract-first** — OpenAPI spec in `packages/contracts` is authoritative; implement in FastAPI, consume in Next.js.
3. **Tenant-scoped** — Every business endpoint requires tenant context (ADR-005).
4. **Versioned** — `/api/v1` prefix; breaking changes → `/api/v2`.
5. **Auditable** — Mutations emit `AuditEvent`; correlation ID on every request.

---

## 2. URL Structure

```
/api/v1/{resource}
/api/v1/{resource}/{id}
/api/v1/{resource}/{id}/{sub-resource}
```

**Examples:**

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/assessments` | List assessments |
| `POST` | `/api/v1/assessments` | Create assessment |
| `GET` | `/api/v1/submissions/{id}/ledger` | Question-level ledger |
| `POST` | `/api/v1/submissions/{id}/review-actions` | Human approval |
| `GET` | `/api/v1/health` | Liveness (no auth) |

**Naming:** Plural nouns, kebab-case for multi-word resources (`review-actions`, `class-sections`).

---

## 3. Authentication (CVB Placeholder)

CVB implements a **placeholder auth** layer extensible to SSO (future enterprise).

| Header | Purpose |
|--------|---------|
| `Authorization` | `Bearer <token>` — JWT or session token |
| `X-Tenant-ID` | Tenant UUID (required when token is multi-tenant) |
| `X-Request-ID` | Client-supplied correlation ID (optional; server generates if absent) |

**Placeholder behavior (CVB local):**

- Demo tenant + demo user seeded at bootstrap.
- Token validation middleware stub returns fixed demo principal in `APP_ENV=local`.
- Production path: JWT with `tenant_id`, `user_id`, `roles[]` claims — documented in OpenAPI security schemes.

**Rule:** Frontend never sends AI provider keys; all AI via backend workers.

---

## 4. Tenant Context

Resolution order:

1. JWT claim `tenant_id` (preferred)
2. `X-Tenant-ID` header (must match JWT membership)
3. Reject with `403 TENANT_MISMATCH` if user not member

**Database:** API middleware sets `app.tenant_id` session variable for RLS.

**Cross-tenant access:** Returns `404 Not Found` (not `403`) for entity ID outside tenant to prevent existence leakage.

---

## 5. Request & Response Envelope

### 5.1 Success responses

**Single resource:**

```json
{
  "data": { "id": "...", "type": "assessment", "...": "..." },
  "meta": {
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "api_version": "v1"
  }
}
```

**Collection (paginated):**

```json
{
  "data": [ "...items..." ],
  "meta": {
    "request_id": "...",
    "api_version": "v1",
    "pagination": {
      "page": 1,
      "page_size": 25,
      "total_items": 142,
      "total_pages": 6
    }
  }
}
```

### 5.2 Error envelope

All non-2xx responses use:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Human-readable summary",
    "details": [
      { "field": "email", "issue": "invalid_format" }
    ],
    "request_id": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```

| HTTP | Typical `error.code` |
|------|----------------------|
| 400 | `VALIDATION_ERROR`, `INVALID_STATE_TRANSITION` |
| 401 | `UNAUTHENTICATED` |
| 403 | `FORBIDDEN`, `TENANT_MISMATCH` |
| 404 | `NOT_FOUND` |
| 409 | `CONFLICT`, `VERSION_CONFLICT` |
| 422 | `UNPROCESSABLE_ENTITY` |
| 429 | `RATE_LIMITED` |
| 500 | `INTERNAL_ERROR` |

**Rule:** Never expose stack traces or internal paths in production responses.

---

## 6. Correlation ID

- Accept `X-Request-ID` or generate UUID v4.
- Echo in response `meta.request_id` and error envelope.
- Propagate to logs, `AuditEvent.correlation_id`, Celery task kwargs, `AiExecutionRecord` context.

---

## 7. Pagination

**Query parameters:**

| Param | Default | Max |
|-------|---------|-----|
| `page` | 1 | — |
| `page_size` | 25 | 100 |

**Alternative (cursor — future):** `cursor`, `limit` for large ledger exports.

**Sorting:** `sort=created_at`, `order=desc` (whitelist fields per resource).

**Filtering:** Resource-specific, e.g. `workflow_state=REVIEW_REQUIRED`, `assessment_id=uuid`.

---

## 8. Versioning

| Mechanism | Usage |
|-----------|-------|
| URL prefix | `/api/v1` — primary |
| `meta.api_version` | Echo in responses |
| `Accept-Version` header | Optional future negotiation |
| OpenAPI `info.version` | Contract semver in `packages/contracts` |

Breaking changes require new major URL prefix and ADR note.

---

## 9. Idempotency

Mutations that enqueue work (`POST /submissions`, `POST /submissions/{id}/reprocess`):

- Support optional `Idempotency-Key` header.
- Server stores `(tenant_id, key, route)` → response for 24h replay.

---

## 10. Async Operations

Long-running pipeline endpoints return `202 Accepted`:

```json
{
  "data": {
    "job_id": "...",
    "status": "QUEUED",
    "poll_url": "/api/v1/jobs/{job_id}"
  },
  "meta": { "request_id": "..." }
}
```

---

## 11. Content Types

| Type | Usage |
|------|-------|
| `application/json` | Default |
| `multipart/form-data` | Paper uploads |
| `application/pdf` | Report downloads (published only) |

---

## 12. Explicit Non-Goals (CVB)

- **No GraphQL** — REST + OpenAPI only (ADR-001).
- **No frontend-direct AI endpoints.**
- **No unversioned `/api/` routes** in production.

---

## 13. Document Control

| Version | Date | Change |
|---------|------|--------|
| 0.1 | 2026-09-04 | Initial API conventions |
