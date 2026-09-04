# Frontend contract requests

**Product:** EduVijna Paper Evaluation (CVB)  
**Author:** Implementation Engineer B (frontend foundation)  
**Date:** 2026-09-04  
**Status:** Open — blocking HTTP adapter cutover

## Context

The web app ships with a **typed service layer** (`apps/web/src/lib/api`) and adapters selected by `NEXT_PUBLIC_API_MODE`:

- `mock` (default) → `MockEduVijnaApi`
- `http` → `HttpEduVijnaApi` (operational `health` / `ready` / `version` only; domain methods throw)

Field names and workflow enums are aligned with architecture docs and JSON schemas under `packages/contracts`. OpenAPI currently exposes only operational endpoints, so the frontend cannot bind domain screens to a real HTTP API without inventing paths.

Pages must call `api.*` methods only — never import `@/lib/fixtures` or `mock/data` directly (fixtures re-export is for tests / adapter internals).

---

## Request registry

| Request ID | Priority | Screen(s) | Summary |
|------------|----------|-----------|---------|
| **FCR-001** | P0 | All domain | Publish tenant-scoped OpenAPI for assessments, students, curriculum, submissions |
| **FCR-002** | P0 | Identity | Identity review GET + confirm / unmatched POST |
| **FCR-003** | P0 | Mapping | Mapping payload + action POST (`ACCEPT`…`MARK_CONTINUATION`) |
| **FCR-004** | P0 | Evaluation | Evaluation workspace + teacher ledger actions |
| **FCR-005** | P1 | Reports / Analytics | Student & parent reports; assessment & student analytics |
| **FCR-006** | P1 | Adaptive learning | Learning plan + improvement blueprint approve |
| **FCR-007** | P1 | Paper viewer | Paper page / evidence region schema (normalized coords) |
| **FCR-008** | P2 | Assessment authoring | Answer-key + curriculum-map endpoints |
| **FCR-009** | P2 | Upload | Multipart / pre-signed upload for raw unmarked sheets |

---

## FCR-001 — Core domain CRUD (P0)

**Screens:** Dashboard, Assessments list/detail, Students, Curriculum, Submissions list/detail  

**Fields / shapes (frontend already models):**
- Assessment: `workflow_state` (`DRAFT`…`ARCHIVED`), `max_marks`, `question_count`, `curriculum_id`
- Student: roster refs, `status`
- Curriculum nodes: `node_type` from curriculum ontology
- Submission: pipeline `workflow_state`, identity + mapping confidence

**Limitation:** HTTP adapter throws on all domain methods.  
**Proposal:** Versioned paths consistent with `API_CONVENTIONS.md`, e.g. `GET/POST /assessments`, `GET /assessments/{id}`, `GET /students`, `GET /curricula/{id}`, `GET /submissions`.

---

## FCR-002 — Identity matching (P0)

**Screens:** `/submissions/[id]/identity`  

**Fields:** `roll_number_detected`, `name_detected`, `student_match_state` (`UNMATCHED`|`REVIEW_REQUIRED`|`AUTO_MATCHED`|`CONFIRMED`), `identity_confidence`, ranked `candidates[]`  

**Actions UI needs:** Confirm, Choose Different Student, Mark Unmatched  

**Proposal:**
- `GET /submissions/{id}/identity`
- `POST /submissions/{id}/identity/confirm` body `{ student_id }`
- `POST /submissions/{id}/identity/unmatched`

**Limitation:** Low-confidence UX is frontend-only until API returns authoritative match state.

---

## FCR-003 — Question mapping (P0)

**Screens:** `/submissions/[id]/mapping`  

**Fields:** evidence regions (`page_number`, normalized `x,y,width,height` 0–1), mapping nodes with `status` `PROPOSED`|`REVIEW_REQUIRED`|`CONFIRMED` (+ `CROSSED_OUT`), `mapping_confidence`  

**Actions:** Accept Mapping, Move Answer, Merge Continuation, Split Region, Ignore, Crossed Out, Mark Continuation  

**Proposal:** `GET /submissions/{id}/mapping`, `POST /submissions/{id}/mapping/actions`  

**Limitation:** Action side-effects are mocked; no persistence contract.

---

## FCR-004 — Evaluation ledger (P0)

**Screens:** Evaluation workspace, Annotated paper, Teacher review  

**Fields:** `proposed_ai_score`, `final_human_approved_score`, `criterion_decisions`, separate confidence dims (`identity`, `mapping`, `transcription`, `evaluation`), `error_codes`, `ecf_applied`, first-divergence / alternative notes  

**Teacher actions:** `ACCEPT`, `CHANGE_SCORE`, `EDIT_FEEDBACK`, `VALID_ALTERNATIVE`, `OCR_TRANSCRIPTION_ERROR`, `MAPPING_ERROR`, `ESCALATE`  

**Proposal:** `GET /submissions/{id}/evaluation`, `POST .../evaluation/{ledger_id}/actions`  

**Limitation:** Teacher action payloads invented in mock; need contract for score override + feedback body.

---

## FCR-005 — Reports & analytics (P1)

**Screens:** Student report, Parent report, Assessment analytics, Student analytics  

**Proposal:**
- `GET /reports/student/{studentId}/assessment/{assessmentId}`
- `GET /reports/parent/{studentId}/assessment/{assessmentId}` — plain language, no pipeline jargon
- `GET /analytics/assessments/{assessmentId}`
- `GET /analytics/students/{studentId}`

**Limitation:** Parent report DTO not in contracts package.

---

## FCR-006 — Adaptive learning (P1)

**Screens:** Adaptive learning, Improvement assessment blueprint  

**Fields:** priorities 1–3, learning path steps, blueprint `PENDING_APPROVAL`→`APPROVED`, topic outline (e.g. Second Derivatives 2q, Maxima/Minima 2q, Variance 2q, Regression 1q)  

**Proposal:** `GET /learning/{studentId}`, `GET /learning/{studentId}/improvement-assessment`, `POST /learning/improvement-assessments/{id}/approve`  

**Limitation:** Blueprint lifecycle not in WORKFLOW_STATES.md.

---

## FCR-007 — Paper / evidence geometry (P1)

**Screens:** PaperViewerShell (all review stages)  

**Fields:** `NormalizedRect` / `PaperDocument`; regions with `annotation_kind` (`FULL`|`PARTIAL`|`DEDUCTION`|`NEUTRAL`)  

**Limitation:** Paper page / evidence region schema not published; viewer uses synthetic pages (no PDF bytes).  

**Proposal:** Publish region schema aligned with AI pipeline + PDF.js viewport mapping (0–1 page-relative).

---

## FCR-008 — Answer key & curriculum map (P2)

**Screens:** `/assessments/[id]/answer-key`, `/assessments/[id]/curriculum-map`  

**Proposal:** `GET /assessments/{id}/answer-key`, `GET /assessments/{id}/curriculum-map` (question → curriculum node titles)  

**Limitation:** Currently served only via mock fixtures.

---

## FCR-009 — Raw upload (P2)

**Screens:** `/submissions/upload`  

**UI constraint:** Emphasize **RAW, UNMARKED HANDWRITTEN ANSWER SHEETS** only.  

**Proposal:** `POST /submissions/upload` multipart or pre-signed initiation; reject marked/annotated bundles at API validation layer.

---

## Contract gaps observed while building UI

| Gap | Impact | Suggested owner | Maps to |
|-----|--------|-----------------|---------|
| No domain OpenAPI paths | HTTP adapter cannot replace mock | API / contracts | FCR-001 |
| Submission identity & mapping not in JSON Schema package | Frontend duplicated enums from WORKFLOW_STATES.md | Contracts | FCR-002, FCR-003 |
| Teacher review action API not specified | Action payloads invented in mock | Product + API | FCR-004 |
| Parent report DTO not in contracts | Frontend-defined plain-language shape | Product + contracts | FCR-005 |
| Improvement assessment blueprint lifecycle not in WORKFLOW_STATES | Used `DRAFT`/`PENDING_APPROVAL`/`APPROVED`/`REJECTED` | Architecture | FCR-006 |
| Paper page / evidence region schema not published | Placeholder viewer + local region model | AI pipeline + contracts | FCR-007 |

## Interim frontend stance

- Continue shipping against **mock fixtures** for CVB demos.
- Keep `createApiClient()` as the single swap point; do not call ad-hoc `fetch` from pages.
- When OpenAPI lands, hand-write or generate HTTP adapter mapping into `src/lib/types/domain.ts` at the boundary (prefer adapting responses rather than rewriting UI).
