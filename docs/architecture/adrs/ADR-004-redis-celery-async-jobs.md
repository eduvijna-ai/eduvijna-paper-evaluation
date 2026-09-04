# ADR-004: Redis and Celery for Asynchronous Pipeline Jobs

## Status: Accepted

## Date: 2026-09-04

## Context

The EduVijna CVB pipeline includes CPU- and IO-intensive stages that must not block HTTP request threads: student identity extraction from cover pages, per-page layout analysis, answer region mapping, transcription, rubric evaluation, and report generation inputs. A single answer sheet batch may enqueue dozens of tasks with retries, timeouts, and partial failure handling.

Synchronous execution in FastAPI would degrade API latency and make upload endpoints fragile under load. Temporal, AWS Step Functions, or Kafka-driven worker fleets were considered (see ADR-001) but add infrastructure and operational learning curves inappropriate for CVB v0.1.

The repository already defines `workers` (Celery) and `.env.example` configures `REDIS_URL`, `CELERY_BROKER_URL`, and `CELERY_RESULT_BACKEND`. Redis is already required for local Compose stacks.

## Decision

Use **Redis + Celery** as the async job system for CVB:

- **Broker and result backend**: Redis — broker on DB 0, result backend on DB 1 (as in `.env.example`). Task results store lightweight status and result IDs; large payloads remain in Postgres or S3.
- **Worker process**: Celery workers in the `workers` package, sharing domain logic with `apps/api` via common Python modules. Workers run the same Alembic-managed schema and respect tenant context passed in task kwargs.
- **Task categories** (initial CVB):
  - `identity.extract` — cover page / metadata student identification.
  - `structure.analyze_page` — layout, question boundaries.
  - `structure.map_regions` — link physical regions to rubric questions.
  - `transcription.transcribe_answer` — handwritten text extraction per region.
  - `evaluation.evaluate_submission` — apply rubric, write ledger proposals.
  - `publication.prepare_exports` — build export artifacts after approval.
- **Job state and idempotency**: Durable progress and outcomes recorded in Postgres (`pipeline_jobs`, `ai_execution_records`, evaluation ledger draft rows). Celery task ID is correlated but not the sole source of truth — workers must be safe to retry without duplicate ledger commits (idempotency keys on `(submission_id, stage, attempt)`).
- **Tracing**: Every AI-invoking task creates or updates an `AiExecutionRecord` with provider, model, input references (S3 keys, not raw bytes in Redis), output summary, latency, token usage, and error classification. Audit events capture human-visible state transitions.
- **Not Temporal (yet)**: Complex sagas (e.g., compensate on partial batch failure) are handled with explicit job status enums and manual retry endpoints in CVB. Revisit Temporal if workflow complexity or guaranteed execution semantics become a blocker post-pilot.

API enqueues tasks; workers never expose public HTTP except health checks. Frontend polls or subscribes (via API SSE/WebSocket if added) for job status — never Redis directly.

## Consequences

**Positive**

- Familiar Python ecosystem; same virtualenv/package as FastAPI.
- Redis is already deployed for CVB infra; no additional broker to operate.
- Horizontal scaling: add worker containers independently of API replicas.
- `AiExecutionRecord` gives AI cost and quality observability without a separate tracing product.

**Negative**

- Celery lacks Temporal's built-in workflow history and deterministic replay — complex multi-step compensation must be coded explicitly.
- Redis as broker is less durable than RabbitMQ or SQS; acceptable for CVB with Postgres-backed job state and retry policies; production may enable Redis persistence or migrate broker later.
- Task routing and queue naming discipline required to avoid one slow stage blocking identity extraction.

**Operational defaults**

- Task soft time limits per stage (e.g., 120s page analysis, 300s full submission evaluation).
- Dead-letter handling: failed tasks after max retries mark `pipeline_jobs.status = FAILED` with error detail; UI surfaces retry to teachers/admins.
- Separate queues recommended: `identity`, `structure`, `evaluation`, `low` — so evaluation backlog does not starve uploads.

## Alternatives Considered

| Alternative | Why rejected for CVB |
|-------------|---------------------|
| **Temporal** | Strong fit long-term; deferred until workflow complexity and ops capacity justify another stateful service. |
| **Kafka consumers** | Overkill for CVB task volume; requires topic design and consumer group ops without current need. |
| **FastAPI BackgroundTasks only** | No persistence, retry, or horizontal worker scaling; lost on process restart. |
| **RabbitMQ as broker** | Additional container and ops; Redis already present and sufficient at pilot scale. |
| **AWS SQS / Lambda** | Couples CVB to cloud-specific deployment; conflicts with modular monolith on single VM and MinIO-local dev parity. |
| **Arq / RQ** | Smaller ecosystems than Celery for multi-queue, monitoring, and team familiarity. |
