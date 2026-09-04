# ADR-005: Tenant-Aware Data Model from First Migration

## Status: Accepted

## Date: 2026-09-04

## Context

EduVijna is an enterprise platform: multiple schools, coaching centers, or university departments will share the same deployment. Each institution's students, papers, rubrics, and evaluation results must be invisible to other tenants. Bolting tenancy on after tables exist leads to nullable `tenant_id` columns, missed filters, and data leaks discovered only in production.

UI-level hiding ("don't show other school's menu items") is insufficient for regulated educational data. Isolation must be enforced where data lives and where queries run — in PostgreSQL and in the API authorization layer.

CVB pilots may start with one or two tenants, but schema and application patterns must assume multi-tenancy from migration `0001` onward to avoid a costly retrofit before broader rollout.

## Decision

Implement **tenant-aware data modeling from the first Alembic migration**:

- **`tenants` table**: Root entity with UUID PK, name, slug, status, and configuration JSONB (feature flags, retention policies). Created before any tenant-scoped data.
- **`tenant_id` on every tenant-owned table**: Non-null UUID foreign key to `tenants.id` on entities including but not limited to: users/memberships, roles, assessments, submissions, source papers, answer keys, rubrics, evaluation ledger entries, review actions, pipeline jobs, ai_execution_records, and audit events.
- **Composite uniqueness where needed**: e.g., `(tenant_id, external_ref)` for institution-provided student IDs, `(tenant_id, slug)` for assessment codes — prevents cross-tenant collision without global uniqueness constraints that leak information.
- **Database-enforced isolation**:
  - Foreign keys include `tenant_id` in child tables referencing parent rows scoped to the same tenant (composite FKs or trigger checks where ORM supports).
  - Row-Level Security (RLS) policies on sensitive tables setting `tenant_id = current_setting('app.tenant_id')::uuid` for defense in depth; API sets session variable at connection checkout per request.
  - Indexes lead with `tenant_id` on all high-traffic queries: `(tenant_id, assessment_id)`, `(tenant_id, submission_id)`, etc.
- **Application-layer enforcement**: Repository base class requires `tenant_id` filter on all reads/writes. Integration tests assert cross-tenant access returns 404 (not 403) to avoid entity existence leakage.
- **Roles scoped within tenant**: Global platform admin (super-tenant) is a distinct role with explicit audit; institution roles (`INSTITUTION_ADMIN`, `TEACHER`, `REVIEWER`, `VIEWER`) are assigned via `tenant_memberships` with no cross-tenant role inheritance.
- **Request context**: Authenticated API requests resolve `tenant_id` from JWT/session membership; workers receive `tenant_id` in task kwargs and set DB session context before any query.

Shared reference data (e.g., error taxonomy enums, AI model registry metadata) may omit `tenant_id` if truly global and non-PII; anything touching student work does not.

## Consequences

**Positive**

- Pilot-to-production path does not require a "tenancy migration" fire drill.
- RLS provides a safety net if a developer forgets a filter in one query path.
- Per-tenant export, deletion (GDPR/right-to-erasure), and billing attribution become straightforward key-prefix and row-filter operations.
- Security reviewers can verify isolation at schema level, not only by reading route handlers.

**Negative**

- Every new table requires tenancy review in PR checklist — slight overhead, intentional friction.
- Composite FKs and RLS complicate SQLAlchemy models and local testing (must set session vars in fixtures).
- Super-admin cross-tenant support views need explicit bypass policies and heavy audit logging.

**Migration rule**

No Alembic revision merging to `main` that introduces tenant-scoped entities without `tenant_id NOT NULL` and appropriate index — exceptions require a new ADR.

## Alternatives Considered

| Alternative | Why rejected |
|-------------|--------------|
| **Single-tenant CVB schema, add tenancy later** | Retrofit risk is high; historical rows would lack tenant assignment; RLS cannot be enabled cleanly. |
| **Separate database per tenant** | Operationally expensive at CVB scale; complicates migrations, backups, and shared AI cost accounting. |
| **Schema-per-tenant in one Postgres** | Migration fan-out N times; connection pool multiplication; harder ORM story. |
| **UI-only isolation** | Fails security review; one missing `WHERE tenant_id` exposes all student data. |
| **Discriminator column without FK/RLS** | Application bugs can assign wrong tenant; no database backstop. |
