# Architecture Decision Records — Index

EduVijna Paper Evaluation (CVB v0.1) architecture decisions. Each ADR is **Accepted** as of 2026-09-04 unless superseded by a later record.

| ADR | Title | Summary |
|-----|-------|---------|
| [ADR-001](adrs/ADR-001-modular-monolith.md) | Modular Monolith for Client Validation Build | Single deployable FastAPI + Next.js + Celery modular monolith; explicitly not k8s, microservices, Temporal, Kafka, or GraphQL for CVB. |
| [ADR-002](adrs/ADR-002-postgresql-system-of-record.md) | PostgreSQL 16 as System of Record | Postgres with SQLAlchemy 2 async, Alembic, UUID PKs, tenant-scoped tables; evaluation ledger lives in SQL not blob storage. |
| [ADR-003](adrs/ADR-003-s3-compatible-object-storage.md) | S3-Compatible Object Storage for Paper Artifacts | MinIO locally, S3 in production; raw papers, annotated PDFs, and exports in object storage with write-once originals; never in git. |
| [ADR-004](adrs/ADR-004-redis-celery-async-jobs.md) | Redis and Celery for Asynchronous Pipeline Jobs | Redis-backed Celery workers for identity, structure, and evaluation stages; traced via AiExecutionRecord and audit, not Temporal yet. |
| [ADR-005](adrs/ADR-005-tenant-aware-data-model.md) | Tenant-Aware Data Model from First Migration | `tenant_id` from migration 0001 with DB-enforced isolation (RLS, composite FKs) and roles scoped within tenant. |
| [ADR-006](adrs/ADR-006-evaluation-ledger-source-of-truth.md) | Evaluation Ledger as Source of Truth for Scores | Question-level ledger is SoT for marks with separate confidences; human approval before publish; no whole-PDF LLM for final scores. |
| [ADR-007](adrs/ADR-007-ai-provider-abstraction.md) | Interface-Based AI Provider Abstraction | Named AI operations behind protocols; frontend never calls providers; every invocation logged in AiExecutionRecord. |
| [ADR-008](adrs/ADR-008-rubric-answer-key-versioning.md) | Versioned Answer Keys and Rubrics with Teacher Approval | Immutable published AnswerKey/Rubric versions; teacher approves AI-proposed rubrics; criteria support partial, AON, ECF, alternatives, units, precision. |
| [ADR-009](adrs/ADR-009-immutable-raw-source-papers.md) | Immutable Raw Source Papers with Overlay Annotations | Original uploads write-once and content-addressed; annotations as separate overlays; audit on access and mutation attempts. |
| [ADR-010](adrs/ADR-010-human-approval-publication.md) | Human Approval Required Before Publication | AI proposes only; publication requires ReviewAction ACCEPT or OVERRIDE; reports generated solely from approved ledger. |

## Reading order

For new engineers, read ADR-001 (shape of the system), then ADR-005 (tenancy), ADR-002 and ADR-003 (data placement), ADR-004 (async pipeline), ADR-006 through ADR-010 (evaluation trust model).

## Pipeline alignment

These ADRs collectively implement the CVB pipeline:

**source evidence → structured understanding → rubric decisions → evaluation ledger → human approval → published result → learning evidence**

## Supersession

When an ADR is replaced, set its status to **Superseded by ADR-NNN** in the original file and add a row here. Do not delete historical ADRs.
