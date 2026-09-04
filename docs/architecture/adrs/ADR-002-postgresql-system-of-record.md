# ADR-002: PostgreSQL 16 as System of Record

## Status: Accepted

## Date: 2026-09-04

## Context

EduVijna manages relational entities with strong consistency requirements: tenants, users, roles, assessments, answer keys, rubrics, per-question evaluation ledger entries, review actions, audit events, and AI execution traces. Pilot institutions expect queryable history ("what score did Q3 receive and who approved it?"), transactional integrity when a teacher overrides a mark, and the ability to export structured results without re-parsing PDFs.

Blob storage (S3/MinIO) is appropriate for multi-megabyte scanned pages but is the wrong place for authoritative scores, approval state, or rubric criteria. Storing evaluation outcomes only in JSON files on object storage would make reporting, tenancy isolation, and concurrent review workflows fragile.

The `.env.example` already targets PostgreSQL with `postgresql+asyncpg` and Alembic migrations under `database/migrations`. CVB needs a single, well-understood OLTP database with mature tooling.

## Decision

Use **PostgreSQL 16** as the system of record (SoR) for all structured domain data:

- **ORM and access layer**: SQLAlchemy 2.x with async sessions (`asyncpg` driver). All API and worker database access goes through the shared session factory and repository/service layers — no raw SQL in route handlers except where explicitly justified (e.g., complex reporting views).
- **Schema migrations**: Alembic, version-controlled under `database/migrations`, applied in CI and on deploy before API/worker startup.
- **Primary keys**: UUID v4 (or UUID v7 where time-ordering helps indexing) on all domain tables. External APIs expose UUIDs, not sequential integers, to avoid enumeration and simplify future sharding if ever needed.
- **Tenant scoping**: Every tenant-owned table includes a non-null `tenant_id` column with foreign key to `tenants`. See ADR-005 for isolation enforcement.
- **Evaluation ledger in Postgres**: Question-level scores, criterion marks, confidence breakdowns, reviewer overrides, and publication state live in normalized (and selectively denormalized) tables — not in S3 objects. Object storage holds evidence (images, annotated PDFs, export artifacts); Postgres holds decisions.
- **JSONB where appropriate**: Semi-structured payloads (e.g., AI raw responses, rubric criterion metadata, bounding boxes) may use JSONB columns with schema validation at the application layer and documented contracts in `packages/contracts`.
- **Audit and AI trace tables**: `audit_events` and `ai_execution_records` are first-class Postgres tables, queryable and joinable to ledger and review entities.

Connection pooling via PgBouncer or SQLAlchemy pool settings is acceptable at CVB scale; read replicas are out of scope for v0.1.

## Consequences

**Positive**

- ACID transactions for review workflows: accepting an evaluation, writing ledger rows, and recording `ReviewAction` happen atomically.
- Standard backup, point-in-time recovery, and SQL-based reporting for institutions and internal ops.
- Alembic gives reproducible schema history aligned with the modular monolith's single deploy unit.
- UUID PKs simplify merging data from exports and avoid leaking enrollment counts via sequential IDs.

**Negative**

- Postgres must be sized for write volume during batch evaluation runs; large JSONB blobs in-row should be avoided — store references to S3 keys instead.
- Async SQLAlchemy adds complexity versus sync ORM; team must consistently use `async with session` patterns and avoid blocking calls in the event loop.
- Cross-tenant analytics require careful indexing on `(tenant_id, ...)` on every hot query path.

**Data placement rule**

| Data type | Location |
|-----------|----------|
| Scores, rubrics, approvals, users, tenants | PostgreSQL |
| Raw page images, annotated PDFs, bulk export ZIPs | S3-compatible storage (ADR-003) |
| Celery task metadata / ephemeral locks | Redis (ADR-004) |

## Alternatives Considered

| Alternative | Why rejected |
|-------------|--------------|
| **MongoDB / document store** | Evaluation and review workflows benefit from relational integrity, joins, and constraints; document-only storage pushes that burden to application code. |
| **Evaluation ledger in S3/JSON files** | No transactional updates, poor query ergonomics, difficult tenant isolation, and no straightforward audit trail joins. |
| **SQLite for CVB** | Insufficient for concurrent workers, multi-tenant pilot deployments, and managed backup expectations. |
| **MySQL / MariaDB** | PostgreSQL's JSONB, partial indexes, and ecosystem fit (asyncpg, Alembic) are stronger for this stack; team standardizes on PG 16. |
| **Event sourcing as sole store** | Valuable as a supplement later; CVB needs straightforward CRUD and reporting on current state without replay infrastructure. |
