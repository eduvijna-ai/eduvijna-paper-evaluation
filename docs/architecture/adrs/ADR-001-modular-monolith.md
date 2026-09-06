# ADR-001: Modular Monolith for Client Validation Build

## Status: Accepted

## Date: 2026-09-04

## Context

EduVijna Paper Evaluation is entering its Client Validation Build (CVB) v0.1 — a phase whose goal is to prove end-to-end value with a small number of pilot institutions, not to operate at hyperscale. The core pipeline spans ingestion of handwritten answer sheets, AI-assisted understanding, rubric-based evaluation, human approval, and publication of results and learning evidence.

Several architectural patterns were considered early: Kubernetes-orchestrated microservices, event-driven choreography via Kafka, durable workflow engines such as Temporal, and GraphQL as the primary API surface. Each of these adds operational complexity, cross-service contract management, and debugging surface area that is disproportionate to CVB scope. The team has two parallel workstreams (backend/workers/AI and frontend/UI) and needs a single deployable unit that can be stood up locally with Docker Compose and deployed to a single VM or managed container service for pilots.

The repository already reflects this direction: `apps/api` (FastAPI), `apps/web` (Next.js), `workers` (Celery), `ai` (provider abstractions), `database/migrations` (Alembic), and `packages/contracts` (OpenAPI and JSON schemas). Domain boundaries must still be enforced in code even though everything ships together.

## Decision

Adopt a **modular monolith** as the CVB architecture:

- **Single deployable backend**: one FastAPI application process (with optional horizontal replicas behind a load balancer) serving REST/OpenAPI endpoints defined in `packages/contracts`.
- **Single deployable frontend**: one Next.js application (`apps/web`) consuming the REST API; no direct AI provider calls from the browser.
- **Separate worker process pool**: Celery workers (`workers`) running async pipeline stages (identity extraction, page analysis, evaluation) against the same codebase and database, coordinated via Redis — not a separate microservice repository.
- **Module boundaries by domain**, not by network boundary. Initial modules:
  - **Ingestion** — upload, storage references, immutability guarantees for source papers.
  - **Identity** — student/roll mapping from cover pages and metadata.
  - **Structure** — page layout, question region mapping, transcription.
  - **Evaluation** — rubric application, scoring, ledger writes.
  - **Review** — human approval workflow, override and audit.
  - **Publication** — approved-result exposure, report generation inputs.
  - **Tenancy** — tenant context propagation, role enforcement.
  - **AI execution** — provider abstraction, `AiExecutionRecord` tracing.
- **Explicit non-goals for CVB**: no Kubernetes requirement, no service mesh, no Kafka, no Temporal, no GraphQL gateway. These may be revisited post-CVB if scale or compliance demands it.

Modules communicate via in-process calls and shared PostgreSQL state. Cross-module imports are allowed only through defined public interfaces (service layers or domain packages), not direct model access across boundaries.

## Consequences

**Positive**

- Local development and pilot deployment require only Docker Compose (Postgres, Redis, MinIO) plus API, web, and worker containers — no cluster operations.
- End-to-end debugging, tracing, and integration tests run against one codebase and one migration history.
- Contract evolution stays centralized in `packages/contracts`; frontend and external integrators consume a single OpenAPI document.
- Team parallelism (Cursor A on backend/workers, Cursor B on web/UI) remains viable because boundaries are package-level, not repo-level.

**Negative**

- All modules share the same deployment lifecycle; a bad migration or startup bug affects the entire API.
- Horizontal scaling applies to the whole API, not individual hot modules — acceptable at CVB scale.
- Discipline is required to prevent the monolith from becoming a ball of mud; module boundary violations must be caught in code review and lint rules.

**Operational**

- Production CVB target: single VM or managed container group (e.g., ECS task set, Azure Container Apps, Railway) with Postgres, Redis, and S3-compatible storage as managed or co-located services.
- Observability is application-level (structured logs, `AiExecutionRecord`, audit tables) rather than distributed tracing across services.

## Alternatives Considered

| Alternative | Why rejected for CVB |
|-------------|---------------------|
| **Microservices per domain** | Requires independent deploy pipelines, inter-service auth, and saga/compensation patterns before the domain model is validated. |
| **Kubernetes** | Adds cluster ops, ingress, and secrets management overhead; no CVB workload justifies it. |
| **Temporal (or similar workflow engine)** | Excellent for long-running retries, but introduces a new operational dependency and learning curve; Celery + Postgres job state suffices for CVB. |
| **Kafka / event bus** | Useful at high throughput with many consumers; CVB has a linear pipeline with a handful of stages and low concurrent volume. |
| **GraphQL** | REST + OpenAPI matches the contract-first approach in `packages/contracts` and is simpler for the Next.js client and external integrators. |
| **Serverless functions per stage** | Cold starts and PDF/vision workloads are a poor fit; workers need sustained CPU and shared model caches. |
