# Frontend contract requests

**Product:** EduVijna Paper Evaluation (CVB)  
**Author:** Implementation Engineer B  
**Updated:** 2026-09-05 (A1 merge gate — develop `2de5ebe`)  
**Status:** Partially resolved by A1; evaluation/ingestion domains still open

## Context

Adapters (`NEXT_PUBLIC_API_MODE`):

- `mock` (default, **B0 active**) → `MockEduVijnaApi`
- `http` → `HttpEduVijnaApi` (operational + **A1 platform** typed helpers under `.a1`; CVB domain methods still throw)

A1 (PR #4) published OpenAPI for auth, institution, academic years, class sections, students, student import, and guardians. Assessment / curriculum / submission / evaluation / reporting / learning remain for later backend phases.

Pages must call `api.*` only — never import fixtures directly.

---

## Request registry (reconciled)

| Request ID | Priority | Screen(s) | Resolution status | Resolved API / schema | Next backend phase |
|------------|----------|-----------|-------------------|----------------------|--------------------|
| **FCR-001** | P0 | Domain CRUD | **PARTIALLY_RESOLVED** | Students: `GET/POST /api/v1/students`, `GET/PATCH /api/v1/students/{id}`; Institution / academic-years / class-sections | Assessments, curriculum, submissions → **OPEN_FOR_A2** |
| **FCR-002** | P0 | Identity review | **OPEN_FOR_INGESTION** | — (roster candidates can use A1 students in B1) | Submission identity endpoints |
| **FCR-003** | P0 | Question mapping | **OPEN_FOR_INGESTION** | — | Mapping GET + actions |
| **FCR-004** | P0 | Evaluation | **OPEN_FOR_EVALUATION** | Ledger schema exists as JSON Schema; no HTTP paths yet | Evaluation workspace + teacher actions |
| **FCR-005** | P1 | Reports / Analytics | **OPEN_FOR_REPORTING** | — | Report & analytics DTOs |
| **FCR-006** | P1 | Adaptive learning | **OPEN_FOR_LEARNING** | — | Learning + improvement blueprint |
| **FCR-007** | P1 | Paper viewer | **OPEN_FOR_INGESTION** | — | Evidence region / page schema |
| **FCR-008** | P2 | Answer key / curriculum map | **OPEN_FOR_A2** | — | Assessment authoring paths |
| **FCR-009** | P2 | Raw upload | **OPEN_FOR_INGESTION** | — | Multipart / pre-signed upload |
| **FCR-010** | P0 | Auth (B1) | **RESOLVED_BY_A1** | `POST /api/v1/auth/login`, `GET /api/v1/auth/me`, `LoginRequest`, `TokenResponse`, `User` | B1 frontend wiring |
| **FCR-011** | P1 | Guardians / import | **RESOLVED_BY_A1** | `/api/v1/guardians`, `/api/v1/students/import/validate`, `/api/v1/students/import/commit`, `ImportValidation` | B1 UI against live API |

---

## FCR-001 — Core domain CRUD (P0)

**Resolution:** PARTIALLY_RESOLVED  

**Resolved by A1:**
- `GET/POST /api/v1/students`, `GET/PATCH /api/v1/students/{id}` — schema `Student` / `StudentInput` (`student_code`, `full_name`, `roll_number`, …)
- `GET /api/v1/institution`
- `GET/POST /api/v1/academic-years`, `GET/PATCH /api/v1/academic-years/{id}`
- `GET/POST /api/v1/class-sections`, `GET/PATCH /api/v1/class-sections/{id}`

**Still open:** assessments, curriculum trees, submissions list/detail → **OPEN_FOR_A2** / ingestion.

**B1 note:** UI `Student` DTO (`display_name`, `external_ref`, …) differs from A1 `full_name` / `student_code` — map at HTTP adapter boundary; do not rename OpenAPI fields.

---

## FCR-002 — Identity matching (P0)

**Resolution:** OPEN_FOR_INGESTION  

Roster candidates can eventually load from A1 students. Submission identity GET/confirm/unmatched paths still required.

---

## FCR-003 — Question mapping (P0)

**Resolution:** OPEN_FOR_INGESTION  

---

## FCR-004 — Evaluation ledger (P0)

**Resolution:** OPEN_FOR_EVALUATION  

JSON Schema `evaluation-ledger.schema.json` exists; HTTP workspace + action endpoints do not.

---

## FCR-005 — Reports & analytics (P1)

**Resolution:** OPEN_FOR_REPORTING  

---

## FCR-006 — Adaptive learning (P1)

**Resolution:** OPEN_FOR_LEARNING  

---

## FCR-007 — Paper / evidence geometry (P1)

**Resolution:** OPEN_FOR_INGESTION  

---

## FCR-008 — Answer key & curriculum map (P2)

**Resolution:** OPEN_FOR_A2  

---

## FCR-009 — Raw upload (P2)

**Resolution:** OPEN_FOR_INGESTION  

---

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
- Do not treat localStorage demo auth as production-safe.
