# Frontend contract requests

**Product:** EduVijna Paper Evaluation (CVB)  
**Author:** Implementation Engineer B (registry); A2 backend reconciliation by Implementation Engineer A  
**Updated:** 2026-09-08 (B14 reassessment mastery update — PEV-043 / APP-005)  
**Status:** A1+A2+B1–B10 live through analytics, curriculum learning, and authoring AI proposals; B12 longitudinal MasteryState, B13 resource assignment, and B14 reassessment instantiation are live on `develop` (AFTER_CLIENT_APPROVAL release state unchanged)

## Context

Adapters (`NEXT_PUBLIC_API_MODE`):

- `mock` — all domains mock + demo role login (Playwright B0)
- `hybrid` (alias `http`) — Auth/Institution/Years/Sections/Students/Import/Guardians (B1), Curriculum/Assessments (B2), Submissions/Identity (B3), Mapping (B4), Transcription (B5), Evaluation (B6), Publication + Reports (B7), Analytics (B8), Learning (B9) via HTTP; mock mode keeps all domains on fixtures. **B10 authoring paths are published for hybrid wiring** (question-paper upload/parse + AI proposals) — do not regress B7–B9 live capabilities.

A1 (PR #4) published OpenAPI for auth, institution, academic years, class sections, students, student import, and guardians.  
A2 (PR #5) publishes curriculum trees, prerequisites, assessments/versions, question trees, mark reconciliation, answer keys, rubrics/criteria, curriculum mappings, readiness transitions, and controlled AI-proposal unavailability.  
B10 closes live authoring AI (`AI_PROVIDER_AUTHORING`) and question-paper artifact upload with scan hook.

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
| AI proposals | `POST /api/v1/ai/proposals/answer-key\|rubric\|curriculum-mapping` → **B10 live** `AuthoringAiRun` when `AI_PROVIDER_AUTHORING` configured; else 503 |
| Question paper | `POST /api/v1/assessment-versions/{id}/question-paper`, `POST …/question-paper/parse`, `GET/PUT/POST /api/v1/authoring-ai-runs/{id}…` |

---

## Request registry (reconciled)

| Request ID | Priority | Screen(s) | Resolution status | Resolved API / schema | Next backend phase |
|------------|----------|-----------|-------------------|----------------------|--------------------|
| **FCR-001** | P0 | Domain CRUD | **IMPLEMENTED_IN_FRONTEND** (A1/B1/B2); submissions list/detail **RESOLVED_BY_B3** | A1 students/institution/years/sections; A2 curricula/assessments; B3 submissions | Mapping/evaluation later |
| **FCR-002** | P0 | Identity review | **RESOLVED_BY_B3** | `GET …/identity`, confirm, unmatched | — |
| **FCR-003** | P0 | Question mapping | **RESOLVED_BY_B4**; B5 adds AI-assisted region/mapping proposals (human confirm still mandatory) | Mapping workspace + region CRUD + confirm/finalize | — |
| **FCR-004** | P0 | Evaluation | **RESOLVED_BY_B6** | Evaluation prepare/workspace/finalize + accept/override/feedback/escalate | — |
| **FCR-005** | P1 | Reports / Analytics | **RESOLVED_BY_B7** (reporting); **RESOLVED_BY_B8** (analytics) | Student/parent/teacher published reports + annotated paper; assessment/student analytics | — |
| **FCR-006** | P1 | Adaptive learning | **RESOLVED_BY_B9**; **B12/B13/B14 extend** | Learning workspace + plan prepare/run + improvement blueprint approve/reject; B12 mastery; B13 resources; B14 reassessment | PEV-058/059 + FUTURE_ENTERPRISE remain deferred |
| **FCR-007** | P1 | Paper viewer / structure AI | **RESOLVED_BY_B5** for CVB structure pipeline (page analysis, crops, transcription review) | Page images + overlays + transcription workspace | — |
| **FCR-008** | P2 | Answer key / curriculum map / authoring AI | **RESOLVED_BY_A2** (CRUD/approve); **RESOLVED_BY_B10** (live AI proposals + question-paper parse) | Answer-key/rubric/mapping + `AuthoringAiRun` / `AssessmentArtifact` | Wire hybrid UI if not already |
| **FCR-009** | P2 | Raw upload | **RESOLVED_BY_B3**; scan hook **RESOLVED_BY_B10** | Multipart `POST /api/v1/submissions` + immutable MinIO storage + `UPLOAD_SCANNER` | — |
| **FCR-010** | P0 | Auth (B1) | **IMPLEMENTED_IN_FRONTEND** | Live `login`/`me` + hybrid session | Cookie sessions preferred (BCR) |
| **FCR-011** | P1 | Guardians / import | **IMPLEMENTED_IN_FRONTEND** | Live guardians + CSV validate/commit + GET student guardians | — |
| **FCR-012** | P1 | Question-paper authoring | **RESOLVED_BY_B10** (API); frontend hybrid wiring optional follow-up | Upload / parse / edit / apply tree | Do not regress analytics/learning live |

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

**Resolution:** **RESOLVED_BY_B7** for reporting; **RESOLVED_BY_B8** for analytics  

**Resolved by B7:**
- Publication prepare / workspace / regenerate / publish
- Annotated evaluated paper (final scores only)
- `GET /api/v1/reports/student|parent|teacher/{student_id}/assessments/{assessment_id}` — PUBLISHED only
- Reviewer report previews while GENERATED
- Schemas: `student-report`, `parent-report`, `teacher-report`, `evaluated-paper`

**Resolved by B8:**
- Assessment analytics (published attempts, mean/median %, optional pass threshold, score distribution)
- Question performance (not psychometric difficulty)
- Academic vs review-condition error distribution
- Curriculum-node performance + mastery coverage
- Student current MasteryEvidence projection (concept / execution / procedure)
- `analytics` capability live; live UUIDs never enter mock analytics

---

## FCR-006 — Adaptive learning (P1)

**Resolution:** **RESOLVED_BY_B9** (base); extended by **B12** (MasteryState / mistake intelligence), **B13** (resource assignment), **B14** (reassessment instantiate + mastery delta)

B9 resolves live curriculum-constrained recommendations, prerequisite-aware learning path, and improvement-assessment **blueprint** generation with teacher approve/reject.

**Resolved by B9:**
- `GET /api/v1/learning/students/{student_id}` — workspace (`available_curricula`, plan, path, materialization)
- `POST /api/v1/learning/students/{student_id}/prepare` — enqueue `learning.generate_plan`
- `GET /api/v1/learning/plan-runs/{run_id}` — versioned plan + staleness
- `POST /api/v1/learning/plan-runs/{run_id}/improvement-blueprints/prepare`
- `GET /api/v1/improvement-assessments/{id}` + `POST …/approve` + `POST …/reject`
- Schemas: `learning-plan`, `improvement-assessment-blueprint`
- Capability: `learning = live` in hybrid; live errors never fall back to mock

**Extended by B12 / B13 / B14 (AFTER_CLIENT_APPROVAL; live on develop):**
- B12: longitudinal mastery / repeated errors / recoverable marks / mistake notebook + `POST …/b12/rebuild`
- B13: curriculum resource catalog + student assignment (no open-web); workspace embeds `resource_assignments`
- B14: `POST /api/v1/improvement-assessments/{id}/reassessment` (`assessment:manage`); `GET /api/v1/reassessments/{id}` (`learning:read`); `POST …/b14/rebuild` (`analytics:materialize`); workspace embeds `reassessments`

**Still deferred:**
- Gold benchmark / AI regression (PEV-058 / PEV-059)
- All FUTURE_ENTERPRISE PEVs
- Open-web discovery / arbitrary external URL assignment (permanently out of policy)

---

## FCR-007 — Paper / evidence geometry (P1)

**Resolution:** **RESOLVED_BY_B4** for manual geometry/review; **RESOLVED_BY_B5** for structure AI / transcription  

Live page images plus answer-region overlays, mapping controls, and transcription workspace. B10 does not change this surface.

---

## FCR-008 — Answer key & curriculum map (P2)

**Resolution:** **RESOLVED_BY_A2** for CRUD/approve; **RESOLVED_BY_B10** for live AI proposals  

**Resolved API / schema (A2):**
- Answer keys: `GET/POST /api/v1/assessments/{id}/answer-key-versions`, `PATCH /api/v1/answer-key-versions/{id}`, `POST /api/v1/answer-key-versions/{id}/approve` — `AnswerKeyVersionInput` (`source_type` TEACHER|AI_PROPOSED|IMPORTED, `status`, `answer_text`, approval metadata on response)
- Rubrics: `POST /api/v1/assessments/{id}/rubrics`, versions/criteria/reconcile/approve — `RubricCriterionInput` (scoring_mode ADDITIVE|DEDUCTIVE|ALL_OR_NOTHING, partial_credit_allowed, ecf_policy, max_marks)
- Curriculum map: `POST/GET /api/v1/question-versions/{id}/curriculum-mappings`, `DELETE /api/v1/question-curriculum-mappings/{id}` — mapping_type PRIMARY|SECONDARY|LEARNING_OUTCOME|SKILL, optional weight
- Mark reconcile: `GET /api/v1/assessment-versions/{id}/marks/reconcile`, `GET /api/v1/rubric-versions/{id}/reconcile`

**Resolved by B10 (authoring AI):**
- `POST /api/v1/ai/proposals/answer-key|rubric|curriculum-mapping` → `AuthoringAiRun` when `AI_PROVIDER_AUTHORING` is set; else 503 `AI_PROVIDER_UNAVAILABLE`
- AI_PROPOSED drafts still require teacher approve before READY / evaluation
- Schemas: `AuthoringAiRun`, `ProposedQuestionNode`, `question-paper-parse.schema.json`

**CVB policy note:** Question↔curriculum mapping is **not** required for assessment READY in A2; READY requires leaf mark reconciliation + approved answer key + approved reconciled rubric per scorable leaf.

---

## FCR-009 — Raw upload (P2)

**Resolution:** **RESOLVED_BY_B3**; scan hook **RESOLVED_BY_B10**  

Multipart `POST /api/v1/submissions` with immutable MinIO raw storage and page-normalization worker.  
B10 adds `UPLOAD_SCANNER` hook (`none` | `fixed`) before storage write; UI should surface `MALWARE_DETECTED` / `UPLOAD_SCAN_FAILED` error codes.

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

## FCR-012 — Question-paper authoring (B10)

**Resolution:** **RESOLVED_BY_B10** (backend API + contracts)

**Resolved API / schema:**
- `POST /api/v1/assessment-versions/{id}/question-paper` → `AssessmentArtifact`
- `POST /api/v1/assessment-versions/{id}/question-paper/parse` → `AuthoringAiRun` (`PARSE_QUESTION_PAPER`)
- `GET /api/v1/authoring-ai-runs/{id}`
- `PUT /api/v1/authoring-ai-runs/{id}/question-tree-proposal`
- `POST /api/v1/authoring-ai-runs/{id}/apply-question-tree`
- Schemas: `AssessmentArtifact`, `AuthoringAiRun`, `QuestionTreeProposalInput`, `question-paper-parse.schema.json`

**Frontend note:** Hybrid screens may wire these paths without changing B7–B9 capability flags (`analytics = live`, `learning = live`). Live UUID errors must never fall back to mock authoring fixtures.

---

## Interim frontend stance

- B0 continues on **MockEduVijnaApi**.
- `HttpEduVijnaApi.a1.*` is typed against A1 OpenAPI for B1 readiness.
- A2–B10 OpenAPI is published; B should add typed helpers / adapters before switching authoring pages off mock.
- Do not treat localStorage demo auth as production-safe.
- **Do not regress** B7 publication/reports, B8 analytics, or B9 learning live hybrid modes.
