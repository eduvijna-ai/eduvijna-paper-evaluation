# ADR-007: Interface-Based AI Provider Abstraction

## Status: Accepted

## Date: 2026-09-04

## Context

EduVijna's CVB pipeline invokes multiple AI capabilities across vision, language, and symbolic math: reading cover pages, detecting question regions, transcribing handwriting, applying rubrics, verifying calculations, classifying error types, and generating pedagogical narratives. Providers (OpenAI, Anthropic, Google, Azure OpenAI, local models) differ in API shapes, pricing, latency, and quality per task.

Hard-coding provider SDK calls in route handlers and Celery tasks would make swapping models expensive, prevent consistent observability, and tempt the frontend to call providers directly for "faster" UX — exposing API keys and bypassing audit, tenancy, and ledger constraints.

The repository reserves an `ai` package for abstractions. CVB needs a stable internal contract that pipeline stages depend on, not on vendor specifics.

## Decision

Implement an **interface-based AI provider abstraction** with discrete, purpose-named operations:

| Operation | Responsibility |
|-----------|----------------|
| `extract_student_identity` | Cover page: name, roll, class, exam metadata |
| `analyze_page` | Layout, printed question numbers, handwriting zones |
| `map_answer_regions` | Align physical regions to rubric question IDs |
| `transcribe_answer` | Handwritten content to text/LaTeX per region |
| `evaluate_rubric` | Apply rubric criteria; propose criterion marks |
| `verify_math` | Symbolic/numeric check against expected answer |
| `classify_error` | Taxonomy label (conceptual, calculation, omission, etc.) |
| `generate_student_explanation` | Student-facing feedback from **approved** ledger |
| `generate_parent_summary` | Parent-facing summary from approved ledger |
| `generate_learning_plan` | Remediation suggestions from error patterns |
| `generate_improvement_blueprint` | Longer-horizon skill gap narrative |

**Architecture rules**

- **Python Protocol or ABC** defines each operation's input/output dataclasses, documented in `packages/contracts` JSON schemas where exposed externally.
- **Provider adapters** implement the interface for specific vendors (e.g., `OpenAIVisionProvider`, `AnthropicTextProvider`). Configuration selects default provider per operation type via environment or tenant config — not hard-coded in business logic.
- **Frontend never calls AI providers**: All invocations go API → Celery worker → `ai` module → provider adapter. Browser receives job status and structured results only.
- **`AiExecutionRecord` for every invocation**: Persisted to Postgres with `tenant_id`, `submission_id`, operation name, provider, model, input artifact references (S3 keys, ledger row IDs), output summary, token/cost metrics, latency, status, and error class. Links to pipeline stage and contributes to per-dimension confidence fields (ADR-006).
- **No god-object LLM client**: Callers request a specific operation; generic `complete(prompt)` is internal to adapters only, not exported to domain modules.
- **Deterministic replay inputs**: Store hashed prompts and input artifact references so disputes can reproduce what was sent without storing full base64 images in Postgres (reference S3).

Evaluation and narrative operations that could change marks (`evaluate_rubric`) run only in worker context and write ledger drafts. Narrative operations (`generate_*`) run only against approved ledger snapshots post-review (ADR-010).

## Consequences

**Positive**

- Vendor migration is adapter-level; rubric engine unchanged.
- Cost attribution per operation and tenant from `AiExecutionRecord` aggregates.
- Security: API keys live in worker/API secret store only.
- Testing: mock providers implement the same interface for deterministic CI.

**Negative**

- Initial adapter implementation effort for each supported vendor.
- Operation granularity may require composite calls internally — adapters may orchestrate multi-step prompts while exposing one domain operation.
- Schema evolution on operation I/O requires contract versioning in `packages/contracts`.

**Package layout (target)**

```
ai/
  protocols.py          # Operation interfaces
  types.py              # Shared input/output models
  registry.py           # Provider selection
  providers/
    openai/
    anthropic/
  mocks/                # Test doubles
```

## Alternatives Considered

| Alternative | Why rejected |
|-------------|--------------|
| **Direct SDK calls in tasks** | No swap path, duplicated retry/logging, untestable monolith. |
| **Single `ask_llm(prompt)` service** | Encourages whole-PDF grading anti-pattern (ADR-006); no operation-level metrics. |
| **Frontend-to-provider (edge AI)** | Exposes secrets, skips audit, breaks tenant policy. |
| **LangChain/LlamaIndex as core architecture** | Useful optionally inside adapters; should not own domain boundaries or ledger writes. |
| **One provider for everything** | Different tasks need vision vs. math vs. cheap classification models; no vendor wins all. |
