# Frontend contract requests

**Product:** EduVijna Paper Evaluation (CVB)  
**Author:** Implementation Engineer B (registry); A2 backend reconciliation by Implementation Engineer A  
**Updated:** 2026-09-07 (B7 publication / reports / annotated paper)  
**Status:** A1+A2+B1–B7 live through publication + published reports; analytics/learning remain open

## Context

Adapters (`NEXT_PUBLIC_API_MODE`):

- `mock` — all domains mock + demo role login (Playwright B0)
- `hybrid` (alias `http`) — Auth/Institution/Years/Sections/Students/Import/Guardians (B1), Curriculum/Assessments (B2), Submissions/Identity (B3), Mapping (B4), Transcription (B5), Evaluation (B6), Publication + Reports (B7) via HTTP; Analytics/Learning remain mock

A1 (PR #4) published OpenAPI for auth, institution, academic years, class sections, students, student import, and guardians.  
A2 (PR #5) publishes curriculum trees, prerequisites, assessments/versions, question trees, mark reconciliation, answer keys, rubrics/criteria, curriculum mappings, readiness transitions, and controlled AI-proposal unavailability.

Pages must call `api.*` only — never import fixtures directly.

### A2 path adapter note (canonical accepted)

B should map mock/http adapters to these **canonical** paths (no duplicate aliases):

| Topic | Canonical path |
|-------|----------------|
| Curriculum tree | `GET /api/v1/curricula/{id}/tree` |
| Curriculum nodes | `POST /api/v1/curricula/{id}/nodes`, `PATCH /api/v1/curriculum-nodes/{id}` |
| Prerequisites | `POST /api/v1/curricula/{id}/prerequisites`, `DELETE /api/v1/curriculum-prerequisites/{id}` |
| Mark reconciliation | `GET /api/v1/assessment-versions/{id}/marks/reconcile` |
| Answer keys | `GET/POST /api/v1/assessments/{id}/answer-key-versions`, `PATCH …/answer-key-versions/{id}`, `POST …/approve` |
| Rubrics | under `/api/v1/assessments/{id}/rubrics`, `/api/v1/rubrics/{id}/versions`, `/api/v1/rubric-versions/{id}/…` |
| Curriculum mapping | `POST/GET /api/v1/question-versions/{id}/curriculum-mappings` |
| AI proposals | `POST /api/v1/ai/proposals/answer-key\|rubric\|curriculum-mapping` (503 when unconfigured) |

---

## Request registry (reconciled)

| Request ID | Priority | Screen(s) | Resolution status | Resolved API / schema | Next backend phase |
|------------|----------|-----------|-------------------|----------------------|--------------------|
| **FCR-001** | P0 | Domain CRUD | **IMPLEMENTED_IN_FRONTEND** (A1/B1/B2); submissions list/detail **RESOLVED_BY_B3** | A1 students/institution/years/sections; A2 curricula/assessments; B3 submissions | Mapping/evaluation later |
| **FCR-002** | P0 | Identity review | **RESOLVED_BY_B3** | `GET …/identity`, confirm, unmatched | — |
| **FCR-003** | P0 | Question mapping | **RESOLVED_BY_B4**; B5 adds AI-assisted region/mapping proposals (human confirm still mandatory) | Mapping workspace + region CRUD + confirm/finalize | — |
| **FCR-004** | P0 | Evaluation | **RESOLVED_BY_B6** | Evaluation prepare/workspace/finalize + accept/override/feedback/escalate | — |
| **FCR-005** | P1 | Reports / Analytics | **RESOLVED_BY_B7** (reporting); **OPEN_FOR_B8** (analytics) | Student/parent/teacher published reports + annotated paper | Analytics aggregations |
| **FCR-006** | P1 | Adaptive learning | **OPEN** | — | Learning + improvement blueprint |
| **FCR-007** | P1 | Paper viewer / structure AI | **RESOLVED_BY_B5** for CVB structure pipeline (page analysis, crops, transcription review) | Page images + overlays + transcription workspace | — |
| **FCR-008** | P2 | Answer key / curriculum map | **RESOLVED_BY_A2** | Answer-key versions + approve; question curriculum mappings; rubrics/criteria | — |
| **FCR-009** | P2 | Raw upload | **RESOLVED_BY_B3** | Multipart `POST /api/v1/submissions` + immutable MinIO storage | — |
| **FCR-010** | P0 | Auth (B1) | **IMPLEMENTED_IN_FRONTEND** | Live `login`/`me` + hybrid session | Cookie sessions preferred (BCR) |
| **FCR-011** | P1 | Guardians / import | **IMPLEMENTED_IN_FRONTEND** | Live guardians + CSV validate/commit + GET student guardians | — |

---

## FCR-001 — Core domain CRUD (P0)

**Resolution:** PARTIALLY_RESOLVED  

**Resolved by A1:**
- `GET/POST /api/v1/students`, `GET/PATCH /api/v1/students/{id}` — schema `Student` / `StudentInput` (`student_code`, `full_name`, `roll_number`, …)
- `GET /api/v1/institution`
- `GET/POST /api/v1/academic-years`, `GET/PATCH /api/v1/academic-years/{id}`
- `GET/POST /api/v1/class-sections`, `GET/PATCH /api/v1/class-sections/{id}`

**Resolved by A2:**
- Curricula: `GET/POST /api/v1/curricula`, `GET/PATCH /api/v1/curricula/{id}`, `GET /api/v1/curricula/{id}/tree` — schemas `Curriculum`, `CurriculumInput`, `CurriculumNode`
- Assessments: `GET/POST /api/v1/assessments`, `GET/PATCH /api/v1/assessments/{id}`, versions + `POST …/transition` — schemas `Assessment`, `AssessmentInput`, `AssessmentVersionInput`
- Questions: `GET/POST /api/v1/assessment-versions/{id}/questions`, `PATCH/DELETE /api/v1/question-versions/{id}` — schema `QuestionInput` / question tree payload

**Still open for later phases:** ingestion paper/region mapping and evaluation (not B3).

**B1 note:** UI `Student` DTO (`display_name`, `external_ref`, …) differs from A1 `full_name` / `student_code` — map at HTTP adapter boundary; do not rename OpenAPI fields.  
**B2 note:** Assessment create returns `initial_version_id`; list/get assessment does not embed `current_version` — clients should use `GET …/versions` or create response.  
**B3 note:** Submissions list/detail/upload + identity review are live in hybrid mode.

---

## FCR-002 — Identity matching (P0)

**Resolution:** RESOLVED_BY_B3  

Live `GET /api/v1/submissions/{id}/identity`, confirm, and unmatched with manual roster candidates (confidence 0.0; no automated extraction).

---

## FCR-003 — Question mapping (P0)

**Resolution:** RESOLVED_BY_B4  

Live mapping workspace binds to `submission.assessment_version_id`, supports manual answer regions, ANSWERED/BLANK confirmations, continuation regions, and finalize → `READY_FOR_EVALUATION`. Automated region detection / OCR / AI mapping are **not** part of B4.

---

## FCR-004 — Evaluation ledger (P0)

**Resolution:** RESOLVED_BY_B6  

Live evaluation prepare, workspace, accept / override / feedback / escalate, and finalize → `APPROVED`.  
`proposed_ai_score` may be null (unreadable / no proposal) — UI must not display as zero.  
OCR/mapping correction workflows and result publication / reports remain out of scope.

---

## FCR-005 — Reports & analytics (P1)

**Resolution:** **RESOLVED_BY_B7** for reporting; **OPEN_FOR_B8** for analytics  

**Resolved by B7:**
- Publication prepare / workspace / regenerate / publish
- Annotated evaluated paper (final scores only)
- `GET /api/v1/reports/student|parent|teacher/{student_id}/assessments/{assessment_id}` — PUBLISHED only
- Reviewer report previews while GENERATED
- Schemas: `student-report`, `parent-report`, `teacher-report`, `evaluated-paper`

**Still open (B8):** assessment/student analytics aggregations, score bands, class means — remain mock; live UUIDs refuse mock analytics.

---

## FCR-006 — Adaptive learning (P1)

**Resolution:** **OPEN**  

Adaptive learning plans, mastery topics, and improvement blueprints remain mock. Live UUIDs refuse mock learning.

---

## FCR-007 — Paper / evidence geometry (P1)

**Resolution:** RESOLVED_BY_B4 for manual geometry/review  

Live page images plus manual answer-region overlays and mapping controls. Automated handwriting understanding / region detection / transcription remain open.

---

## FCR-008 — Answer key & curriculum map (P2)

**Resolution:** RESOLVED_BY_A2  

**Resolved API / schema:**
- Answer keys: `GET/POST /api/v1/assessments/{id}/answer-key-versions`, `PATCH /api/v1/answer-key-versions/{id}`, `POST /api/v1/answer-key-versions/{id}/approve` — `AnswerKeyVersionInput` (`source_type` TEACHER|AI_PROPOSED|IMPORTED, `status`, `answer_text`, approval metadata on response)
- Rubrics: `POST /api/v1/assessments/{id}/rubrics`, versions/criteria/reconcile/approve — `RubricCriterionInput` (scoring_mode ADDITIVE|DEDUCTIVE|ALL_OR_NOTHING, partial_credit_allowed, ecf_policy, max_marks)
- Curriculum map: `POST/GET /api/v1/question-versions/{id}/curriculum-mappings`, `DELETE /api/v1/question-curriculum-mappings/{id}` — mapping_type PRIMARY|SECONDARY|LEARNING_OUTCOME|SKILL, optional weight
- Mark reconcile: `GET /api/v1/assessment-versions/{id}/marks/reconcile`, `GET /api/v1/rubric-versions/{id}/reconcile`
- AI (controlled failure): `POST /api/v1/ai/proposals/answer-key|rubric|curriculum-mapping` → 503 `AI_PROVIDER_UNAVAILABLE` when unconfigured

**CVB policy note:** Question↔curriculum mapping is **not** required for assessment READY in A2; READY requires leaf mark reconciliation + approved answer key + approved reconciled rubric per scorable leaf.

**Next:** B adapter wiring against canonical paths above.

---

## FCR-009 — Raw upload (P2)

**Resolution:** RESOLVED_BY_B3  

Multipart `POST /api/v1/submissions` with immutable MinIO raw storage and page-normalization worker.

## FCR-010 — Auth (added at A1 merge gate)

**Resolution:** RESOLVED_BY_A1  

**Resolved API:** `POST /api/v1/auth/login`, `GET /api/v1/auth/me`  

**Next:** B1 — replace demo localStorage login with bearer token flow. B0 remains **DEMO/MOCK ONLY**.

---

## FCR-011 — Guardians & student import (added at A1 merge gate)

**Resolution:** RESOLVED_BY_A1  

**Resolved API:** guardians CRUD; `students/import/validate` + `commit`  

**Next:** B1 — wire import UI to multipart validate/commit.

---

## Interim frontend stance

- B0 continues on **MockEduVijnaApi**.
- `HttpEduVijnaApi.a1.*` is typed against A1 OpenAPI for B1 readiness.
- A2 OpenAPI is published; B should add typed helpers / adapters before switching pages off mock.
- Do not treat localStorage demo auth as production-safe.
