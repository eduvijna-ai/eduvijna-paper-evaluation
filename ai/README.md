# EduVijna AI abstraction

Runtime B5 structure providers live under `apps/api/app/ai/` (typed contracts,
registry, tracing, fixed/openai adapters). The repository-root `ai/` package
remains the architecture stub; do not call a generic `complete(prompt)` domain API.

## Provider modes (`AI_PROVIDER_VISION`)

| Mode | Behavior |
|------|----------|
| `none` | Manual B3/B4 workflows; no fabricated AI output |
| `fixed` | Deterministic local/CI provider (non-production) |
| `openai` | Optional real adapter; credentials from env only |

CI real E2E uses `AI_PROVIDER_VISION=fixed`. Never silently fall back to `fixed`
in production when configuration is missing.

## B5 operations

- `extract_student_identity`
- `analyze_page`
- `map_answer_regions`
- `transcribe_answer`

Later (B6+): `evaluate_rubric`, scoring, reporting/learning operations.

## Config

```
AI_PROVIDER_VISION
AI_MODEL_IDENTITY
AI_MODEL_PAGE_ANALYSIS
AI_MODEL_MAPPING
AI_MODEL_TRANSCRIPTION
AI_REQUEST_TIMEOUT_SECONDS
OPENAI_API_KEY   # openai mode only
```

Frontend never holds provider credentials. All paths: API → Celery → provider.
