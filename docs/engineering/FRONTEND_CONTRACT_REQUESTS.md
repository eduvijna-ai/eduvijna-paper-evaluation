# Frontend contract requests

**Product:** EduVijna Paper Evaluation (CVB)  
**Author:** Implementation Engineer B (frontend foundation)  
**Date:** 2026-09-04  
**Status:** Open — blocking HTTP adapter cutover

## Context

The web app ships with a **typed service layer** (`apps/web/src/lib/api`) and a **mock adapter** selected by `NEXT_PUBLIC_API_MODE=mock` (default). Field names and workflow enums are aligned with architecture docs and JSON schemas under `packages/contracts`.

OpenAPI currently exposes only operational endpoints (`health` / `ready` / `version`). **Domain entities are not yet in OpenAPI**, so the frontend cannot bind to a real HTTP API without inventing paths.

## Requested OpenAPI / API additions

Please publish versioned OpenAPI paths (tenant-scoped, consistent with `API_CONVENTIONS.md`) for:

### Assessments
- `GET /assessments` — list with workflow_state filter
- `POST /assessments` — create DRAFT
- `GET /assessments/{id}`
- `GET /assessments/{id}/questions` — hierarchical question tree
- `GET /assessments/{id}/rubric` — rubric criteria + answer-key versions
- Assessment lifecycle transitions (`DRAFT` → `RUBRIC_REVIEW` → `READY` → `ACTIVE` → `CLOSED` → `ARCHIVED`)

### Students / roster
- `GET /students`, `GET /students/{id}`
- `POST /students/import` — roster CSV/XLSX ingest job

### Curriculum
- `GET /curricula`, `GET /curricula/{id}` — nodes with `node_type` enum from curriculum ontology

### Submissions
- `GET /submissions`, `GET /submissions/{id}`
- `POST /submissions/upload` — multipart / pre-signed upload initiation
- Workflow states: `UPLOADED` … `PUBLISHED` / `FAILED`

### Identity matching
- `GET /submissions/{id}/identity`
- `POST /submissions/{id}/identity/confirm` — body: `{ student_id }`
- States: `UNMATCHED` | `REVIEW_REQUIRED` | `AUTO_MATCHED` | `CONFIRMED`
- Include `identity_confidence` and ranked roster candidates

### Question mapping
- `GET /submissions/{id}/mapping` — evidence regions + hierarchy mapping
- `POST /submissions/{id}/mapping/actions` — `ACCEPT` | `MOVE` | `MERGE` | `SPLIT` | `IGNORE` | `MARK_CROSSED_OUT`
- Include `mapping_confidence` per node/region

### Evaluation ledger
- `GET /submissions/{id}/evaluation` — workspace payload (paper refs, questions, ledgers)
- `POST /submissions/{id}/evaluation/{ledger_id}/actions` — teacher actions:
  - `ACCEPT`, `CHANGE_SCORE`, `EDIT_FEEDBACK`, `VALID_ALTERNATIVE`, `OCR_TRANSCRIPTION_ERROR`, `MAPPING_ERROR`, `ESCALATE`
- Ledger fields (already in schema): `proposed_ai_score`, `final_human_approved_score`, `criterion_decisions`, `workflow_state` (`PENDING`|`PROPOSED`|`REVIEW_REQUIRED`|`ACCEPTED`|`OVERRIDDEN`), confidence fields, `error_codes` from ERROR_TAXONOMY

### Reports & analytics
- `GET /reports/student/{studentId}/assessment/{assessmentId}`
- `GET /reports/parent/{studentId}/assessment/{assessmentId}` — plain language, no pipeline jargon
- `GET /analytics/assessments/{assessmentId}`
- `GET /analytics/students/{studentId}`

### Adaptive learning
- `GET /learning/{studentId}` — priorities 1–3 + learning path steps
- `GET /learning/{studentId}/improvement-assessment`
- `POST /learning/improvement-assessments/{id}/approve`

## Contract gaps observed while building UI

| Gap | Impact | Suggested owner |
|-----|--------|-----------------|
| No domain OpenAPI paths | HTTP adapter cannot replace mock | API / contracts |
| Submission identity & mapping not in JSON Schema package | Frontend duplicated enums from WORKFLOW_STATES.md | Contracts |
| Teacher review action API not specified | Action payloads invented in mock | Product + API |
| Parent report DTO not in contracts | Frontend-defined plain-language shape | Product + contracts |
| Improvement assessment blueprint lifecycle not in WORKFLOW_STATES | Used `DRAFT`/`PENDING_APPROVAL`/`APPROVED`/`REJECTED` | Architecture |
| Paper page / evidence region schema not published | Placeholder viewer + local region model | AI pipeline + contracts |

## Interim frontend stance

- Continue shipping against **mock fixtures** for CVB demos.
- Keep `createApiClient()` as the single swap point; do not call ad-hoc `fetch` from pages.
- When OpenAPI lands, generate or hand-write an `http` adapter that maps responses into existing `src/lib/types/domain.ts` shapes (prefer adapting at the boundary rather than rewriting UI).
