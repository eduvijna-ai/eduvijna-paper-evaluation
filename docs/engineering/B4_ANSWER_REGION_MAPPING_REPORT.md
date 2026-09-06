# B4 — Live answer-region and question mapping review

**Branch:** `b4/live-answer-region-question-mapping`  
**Starting `develop` SHA:** `a6134656f85b7785cbe145d0397e2a2892ce9c36` (merged B3)  
**Migration:** `database/migrations/versions/20260906_0005_answer_region_mapping.py`  
**Project gate:** CI green + squash merge (final SHAs filled after merge)

## Scope

B4 moves answer-region geometry and question↔region mapping onto the live API, ending at `READY_FOR_EVALUATION`. Evaluation remains mock / not live.

### Live in hybrid mode

- Submissions + identity review (B3)
- Mapping preparation (`PROCESSING` → `MAPPING_REVIEW`)
- Manual answer regions (HUMAN, confidence 0.0)
- Question hierarchy from **submission-bound** `assessment_version_id`
- ANSWERED / BLANK dispositions with confirm
- Continuation pages + multi-region mappings
- Finalize → `READY_FOR_EVALUATION`

### Intentionally still mock / not implemented

- OCR / transcription
- Automated region detection or question mapping
- Live AI providers (Issue #7 remains OPEN)
- Evaluation ledger, teacher review, annotations, reports, analytics, learning

## Tables

- `answer_regions`
- `question_answer_mappings`
- `question_answer_mapping_regions`

## Permissions

- `mapping:read`
- `mapping:review`

CVB: Institution Admin / Teacher / Evaluator get both; Student / Parent none.

## API paths

- `POST /api/v1/submissions/{id}/mapping/prepare`
- `GET /api/v1/submissions/{id}/mapping`
- `POST /api/v1/submissions/{id}/mapping/finalize`
- `POST /api/v1/submission-pages/{id}/answer-regions`
- `PATCH|DELETE /api/v1/answer-regions/{id}`
- `PATCH /api/v1/submission-pages/{id}`
- `PUT /api/v1/submissions/{id}/question-mappings/{questionVersionId}`
- `POST /api/v1/submissions/{id}/question-mappings/{questionVersionId}/confirm`

Identity confirm auto-enqueues mapping preparation (`PipelineJob.stage=MAPPING`).

## Geometry / mapping semantics

- Normalized bbox 0–1 with SQL + API validation
- Manual regions: `source_type=HUMAN`, `detection_confidence=0.0`
- Manual mappings: `mapped_by=HUMAN`, `mapping_confidence=0.0`
- Editing evidence after confirm reopens `REVIEW_REQUIRED`
- Mapped region delete → 409 until unmapped
- Finalize requires every `LEAF_SCORABLE` leaf CONFIRMED ANSWERED or BLANK

## Capability boundary

```
submissions / identityReview / mapping = live
evaluation / reports / analytics / learning = mock
```

Live UUIDs must not enter mock evaluation.

## Local verification (pre-push)

| Gate | Result |
|------|--------|
| Ruff / mypy | pass |
| Alembic head | `20260906_0005` |
| Backend pytest | **70 passed** |
| Frontend lint / typecheck / build | pass |
| Frontend Vitest | **85 passed** |
| Contracts validate | pass |
| `docker compose config` | pass |
| Mock Playwright | **15 passed** |
| Real Playwright | **5 passed** (B1×2 + B2 + B3 + B4) |

## Residual debt

- Region crop generation deferred
- Draw UX is assistant to explicit add-region for E2E reliability
- No automated detection (correctly gated behind Issue #7)
- Evaluation remains the next live phase
