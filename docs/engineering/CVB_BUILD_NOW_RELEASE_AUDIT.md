# CVB BUILD_NOW Release Audit

**Product:** EduVijna Enterprise Paper Evaluation — CVB v0.1  
**Current corrective branch:** `b11/cvb-release-blocker-fixes`  
**PR base:** `develop`  
**B10 squash on `develop`:** `be73cc3bcf91b4078b3fea63b3788403129a1419`  
**Starting `main` SHA:** `be5f10aef3cf536420adcffdb9302b6b3b6c0955`  
**Authoritative register:** `docs/product/REQUIREMENTS_REGISTER.md`  
**Audit date:** 2026-09-07 (re-audited after B11)  
**Evidence basis:** Live code after A1–A2 + B1–B11

---

## Independent post-B10 audit findings

An independent post-merge audit of B10 superseded the earlier **59/59 VERIFIED** claim. Confirmed defects:

| Finding | Requirement impact | Status after B11 |
|---------|-------------------|------------------|
| Question-paper parse did not consume uploaded source evidence (metadata-only input; tests parsed without upload) | **PEV-002** | Closed — artifact required + evidence extraction + evidence-dependent fixed parse + regressions |
| Curriculum AI suggestions auto-wrote canonical `QuestionCurriculumMapping` rows | Authoring human-gate (PEV-004 / curriculum proposal path) | Closed — proposal-only worker + `apply-curriculum-mappings` + allowlist |
| Authoring (and other) AI invocations omitted `model` / `model_version` / `prompt_template_version` | **PEV-060** | Closed — `AIExecutionMetadata` + call-site population |

Do not treat the pre-B11 B10 matrix as final release evidence. See `docs/engineering/B11_CVB_RELEASE_AUDIT_FIX_REPORT.md`.

---

## Method

* Scope = all **59 BUILD_NOW** requirements from the register (§ Summary).  
* **VERIFIED** = concrete runtime implementation + test evidence meeting acceptance intent (not contract-only stubs).  
* **BLOCKED** = genuine BUILD_NOW gap remaining after B11.  
* AFTER_CLIENT_APPROVAL / FUTURE_ENTERPRISE IDs are **out of scope** and listed only under Deferred (must not be marked VERIFIED as live).  
* CVB-bounded deliverables (e.g. PEV-013 Mathematics focus, PEV-042 blueprint-only, PEV-047 basic question analytics, PEV-069 scan **hook**) are VERIFIED when the register’s CVB acceptance intent is met.

---

## Executive rollup

| Status | Count | Notes |
|--------|------:|-------|
| **VERIFIED** | **59** | Re-verified after B11 blocker fixes (evidence-driven parse, curriculum human-gate, PEV-060 metadata) |
| **BLOCKED** | **0** | No remaining BUILD_NOW implementation gaps found after B11 |

**Deferred (not BUILD_NOW — do not treat as live):**  
PEV-035, 036, 037, 038, 041, 043, 044–046, 048–051, 054–059.

**CVB scope notes (still VERIFIED):**

| ID | Bound |
|----|--------|
| PEV-013 | Mathematics structured transcription (TEXT/MATH/TABLE/DIAGRAM); multi-subject = PEV-056 |
| PEV-042 | Improvement **blueprint** + teacher approve; no Assessment creation (PEV-043) |
| PEV-047 | Basic question-level analytics; advanced rubric psychometrics = PEV-048 |
| PEV-069 | Provider-neutral scan **hook** (`none`/`fixed`); not a production AV product |

---

## Phase map

| Phase | Primary deliverables |
|-------|----------------------|
| A1 | Tenancy, RBAC, roster, audit foundation |
| A2 | Curriculum, assessments, keys, rubrics, hierarchy |
| B1 | Hybrid platform API |
| B3 | Submissions, identity review, immutable raw storage, pages |
| B4 | Answer regions, mapping, continuation, manual correction |
| B5 | Structure AI, identity extraction, transcription |
| B6 | Evaluation ledger, review/override, taxonomy, ECF/alt/divergence |
| B7 | Publication, annotated paper, student/parent/teacher reports |
| B8 | Analytics, mastery evidence |
| B9 | Curriculum learning plans, prerequisite path, improvement blueprint |
| B10 | Question-paper artifacts, authoring AI, structured segments, upload scan, audit correlation |

---

## BUILD_NOW matrix (59)

### Assessment & content

| PEV | Name | Phase | Code evidence | Test evidence | Status |
|-----|------|-------|---------------|---------------|--------|
| PEV-001 | Assessment Creation | A2 | `apps/api/app/db/models/curriculum_assessment.py` (`Assessment`/`AssessmentVersion`); `apps/api/app/api/v1/curriculum_assessment.py` | `apps/api/tests/test_a2_gate_matrix.py` | **VERIFIED** |
| PEV-002 | Question Paper Ingestion | B10+B11 | `assessment_artifacts.py`; evidence `question_paper_evidence.py`; parse/apply in `authoring_ai.py`; mig `20260907_0011` | `test_b11_release_blockers.py` (no-source blocked; evidence-dependent parse); `test_b10_authoring_ai.py` | **VERIFIED** |
| PEV-003 | Teacher Answer Key & Rubric | A2 | `AnswerKeyVersion` / `RubricVersion` / `RubricCriterion` models + A2 approve routes | `test_a2_gate_matrix.py` (`test_a2_answer_key_rubric_mapping_and_readiness`) | **VERIFIED** |
| PEV-004 | AI-Proposed Answer Key & Rubric | B10+B11 | Authoring runs; curriculum suggest proposal-only + human apply; answer/rubric REVIEW_REQUIRED | `test_b10_authoring_ai.py`; `test_b11_release_blockers.py` (curriculum gate) | **VERIFIED** |

### Tenancy, roster, RBAC

| PEV | Name | Phase | Code evidence | Test evidence | Status |
|-----|------|-------|---------------|---------------|--------|
| PEV-005 | Student Roster Import | A1 | `apps/api/app/api/v1/platform.py` (CSV validate/commit) | `test_a1_gate_matrix.py`; `test_b1_import_guardian_fixes.py` | **VERIFIED** |
| PEV-052 | Enterprise RBAC | A1 | `apps/api/app/core/authorization.py` (`require_permissions`, role→permission map) | `test_a1_gate_matrix.py`; `test_platform_integration.py` | **VERIFIED** |
| PEV-053 | Multi-Tenancy | A1 | Tenant-bound JWT + `tenant_id` predicates on queries/storage keys | `test_a1_gate_matrix.py` (`test_a1_tenancy_isolation_matrix`); cross-suite isolation tests | **VERIFIED** |

### Submission, identity, pages, upload

| PEV | Name | Phase | Code evidence | Test evidence | Status |
|-----|------|-------|---------------|---------------|--------|
| PEV-006 | Raw Paper Upload | B3 | `apps/api/app/api/v1/submissions.py`; `services/storage.py`; mig `20260906_0004` | `test_b3_submission_ingestion.py` | **VERIFIED** |
| PEV-007 | Handwritten Identity Extraction | B5 | `services/identity_ai.py`; `ai` `extract_student_identity`; structure models | `test_b5_ai_structure_transcription.py` | **VERIFIED** |
| PEV-008 | Roster Matching | B3/B5 | Identity candidates + confidence on submission identity APIs | `test_b3_submission_ingestion.py`; `test_b5_ai_structure_transcription.py` | **VERIFIED** |
| PEV-009 | Identity Review Routing | B3 | `IDENTITY_REVIEW` / below-threshold → human confirm; no silent assign | `test_b3_submission_ingestion.py` | **VERIFIED** |
| PEV-023 | Immutable Source Preservation | B3 | Write-once raw keys + content hash; overwrite denied | `test_b3_submission_ingestion.py` (`test_raw_storage_immutability_and_hash_mismatch`) | **VERIFIED** |
| PEV-068 | Submission Page Model | B3 | `db/models/submission.py` (`SubmissionPage`); page normalization | `test_b3_submission_ingestion.py` | **VERIFIED** |
| PEV-069 | Raw Upload Contract | B3+B10 | `services/upload_scanner.py`; wired in `submissions.py` + `assessment_artifacts.py`; OpenAPI upload constraints | `test_b10_assessment_artifacts.py` (malware reject, scan-before-storage, `none`≠CLEAN) | **VERIFIED** |

### Mapping & structured understanding

| PEV | Name | Phase | Code evidence | Test evidence | Status |
|-----|------|-------|---------------|---------------|--------|
| PEV-010 | Page & Region Detection | B4/B5 | `AnswerRegion` model; B5 `analyze_page` | `test_b4_answer_region_mapping.py`; `test_b5_ai_structure_transcription.py` | **VERIFIED** |
| PEV-011 | Answer-Question Mapping | B4 | `QuestionAnswerMapping*`; `api/v1/mapping.py` | `test_b4_answer_region_mapping.py` | **VERIFIED** |
| PEV-012 | Continuation Page Support | B4 | Continuation regions / ordering in mapping workspace | `test_b4_answer_region_mapping.py` | **VERIFIED** |
| PEV-013 | Structured Work Understanding | B5+B10 | `packages/contracts/schemas/structured-transcription.schema.json`; `ai/types.py` segments; `services/transcription.py` | `test_b10_structured_transcription.py`; `test_b5_ai_structure_transcription.py` | **VERIFIED** (Math CVB scope) |
| PEV-070 | Answer Region Model | B4 | `AnswerRegion` bbox, page FK, crop/transcription links | `test_b4_answer_region_mapping.py` | **VERIFIED** |
| PEV-071 | Mapping Manual Correction | B4 | Manual region CRUD + confirm/finalize APIs | `test_b4_answer_region_mapping.py` | **VERIFIED** |

### Evaluation, ledger, review

| PEV | Name | Phase | Code evidence | Test evidence | Status |
|-----|------|-------|---------------|---------------|--------|
| PEV-014 | Rubric-Based Evaluation | B6 | `services/evaluation.py`; evaluation models; mig `20260906_0007` | `test_b6_evaluation_ledger.py` | **VERIFIED** |
| PEV-015 | Step-Level Partial Credit | B6 | Criterion-level marks + max enforcement | `test_b6_evaluation_ledger.py` | **VERIFIED** |
| PEV-016 | Alternative Valid Methods | B6 | `VALID_ALTERNATIVE` / alt-method fields on ledger | `test_b6_evaluation_ledger.py` | **VERIFIED** |
| PEV-017 | Error-Carried-Forward (ECF) | B6 | `ecf_applied` + rubric `ecf_policy` | `test_b6_evaluation_ledger.py` | **VERIFIED** |
| PEV-018 | First Divergence Detection | B6 | `QuestionEvaluation.first_divergence_step` | `test_b6_evaluation_ledger.py` | **VERIFIED** |
| PEV-019 | Digital Paper Marking | B7 | `db/models/publication.py` (`Annotation`); `services/publication.py` | `test_b7_publication_reports.py` | **VERIFIED** |
| PEV-020 | Inline Final Question Marks | B7 | Annotations use `final_human_approved_score` only | `test_b7_publication_reports.py` | **VERIFIED** |
| PEV-021 | Deduction Explanations | B6/B7 | Ledger `deduction_reasons` → report builders | `test_b6_evaluation_ledger.py`; `test_b7_publication_reports.py` | **VERIFIED** |
| PEV-022 | Teacher Review & Override | B6 | Accept / override / escalate + `ReviewAction` | `test_b6_evaluation_ledger.py` | **VERIFIED** |
| PEV-034 | Error Taxonomy Classification | B6 | Canonical taxonomy codes on criterion evaluations | `test_b6_evaluation_ledger.py` (`test_b6_types_forbid_unknown_error_code`) | **VERIFIED** |
| PEV-063 | Mandatory Human Review (low conf) | B6 | UNREADABLE / low-confidence blocks accept/publish paths | `test_b6_evaluation_ledger.py` | **VERIFIED** |
| PEV-064 | Teacher Final Authority | B6/B7 | No auto-publish; explicit human publish gate | `test_b6_evaluation_ledger.py`; `test_b7_publication_reports.py` | **VERIFIED** |
| PEV-066 | Evaluation Ledger | B6 | `packages/contracts/schemas/evaluation-ledger.schema.json`; ledger models | `test_b6_evaluation_ledger.py` | **VERIFIED** |
| PEV-076 | Final Score Reconciliation | B6 | Criterion → question → assessment reconciliation on finalize | `test_b6_evaluation_ledger.py` | **VERIFIED** |

### Curriculum, analytics, learning

| PEV | Name | Phase | Code evidence | Test evidence | Status |
|-----|------|-------|---------------|---------------|--------|
| PEV-029 | Test & Class Analytics | B8 | `services/analytics.py`; mig `20260907_0009` | `test_b8_analytics_mastery.py` | **VERIFIED** |
| PEV-030 | Curriculum Question Mapping | A2 | `Curriculum` / `CurriculumNode`; `QuestionCurriculumMapping` | `test_a2_gate_matrix.py` | **VERIFIED** |
| PEV-031 | Prerequisite Concept Graph | A2 | `CurriculumPrerequisite` + cycle detection | `test_a2_gate_matrix.py` | **VERIFIED** |
| PEV-032 | Concept Strength & Weakness | B8 | `MasteryEvidence` derivation from published results | `test_b8_mastery_derivation.py`; `test_b8_analytics_mastery.py` | **VERIFIED** |
| PEV-033 | Mastery vs Execution Separation | B8 | Taxonomy → concept / execution / procedure signals | `test_b8_mastery_derivation.py` | **VERIFIED** |
| PEV-039 | Curriculum-Only Recommendations | B9 | `services/learning_algorithm.py` + URL reject guard | `test_b9_learning_algorithm.py`; `test_b9_learning_blueprint.py` | **VERIFIED** |
| PEV-040 | Prerequisite-Aware Recommendations | B9 | Prerequisite ordering / repair-before-target | `test_b9_learning_algorithm.py`; `test_b9_learning_blueprint.py` | **VERIFIED** |
| PEV-042 | Improvement Assessment Blueprint | B9 | `improvement_assessments` + blueprint schema; approve **without** Assessment create | `test_b9_learning_blueprint.py` | **VERIFIED** (blueprint only) |
| PEV-047 | Question & Rubric Analytics | B8 | Question performance stats on assessment analytics | `test_b8_analytics_mastery.py` | **VERIFIED** (basic CVB) |

### Governance, AI platform, pipeline, hierarchy

| PEV | Name | Phase | Code evidence | Test evidence | Status |
|-----|------|-------|---------------|---------------|--------|
| PEV-024 | Complete Audit History | A1+B10 | `db/models/audit.py`; `services/audit.py` | A1 suite; `test_b10_audit_correlation.py` | **VERIFIED** |
| PEV-060 | AI Execution Metadata | A2/B5+B11 | `AiExecutionRecord`; `ai/tracing.py`; `ai/execution_metadata.py` | A2/B5/B6/B9/B10/B11 AI tests (`test_b11_fixed_authoring_metadata_shape`) | **VERIFIED** |
| PEV-061 | Separate Confidence Dimensions | B3–B6 | `identity` / `mapping` / `transcription` / `evaluation` confidence fields | B3–B6 tests; publication dimensional dump | **VERIFIED** |
| PEV-062 | No Generic AI Confidence | B5–B7 | APIs/reports expose dimensional confidence only | B5–B7 suites / report builders | **VERIFIED** |
| PEV-065 | No Whole-PDF LLM Reports | B7 | Ledger-backed `publication.py` builders; narrative from structured context | `test_b7_publication_reports.py` | **VERIFIED** |
| PEV-067 | Question Subquestion Hierarchy | A2+B10 | `Question`/`QuestionVersion` tree; B10 apply from parse | `test_a2_gate_matrix.py`; `test_b10_authoring_ai.py` | **VERIFIED** |
| PEV-072 | Audit Event Foundation | A1+B10 | `services/audit.py`; `middleware/correlation.py`; `correlation_id` on events/runs | `test_b10_audit_correlation.py` | **VERIFIED** |
| PEV-073 | AI Provider Abstraction | B5–B10 | `apps/api/app/ai/protocols.py`, `registry.py`, providers | B5/B6/B9/B10 provider tests | **VERIFIED** |
| PEV-074 | Core Pipeline Enforcement | B3→B7 | Workflow gates: mapping → eval → approve → publish → learning evidence | Cross-suite prepare/finalize/publish gates | **VERIFIED** |

### Publication & report contracts

| PEV | Name | Phase | Code evidence | Test evidence | Status |
|-----|------|-------|---------------|---------------|--------|
| PEV-025 | Evaluated Annotated PDF | B7 | `publication.py` + `evaluated-paper.schema.json` | `test_b7_publication_reports.py` | **VERIFIED** |
| PEV-026 | Student Evaluation Report | B7 | `student-report.schema.json`; student report builder | `test_b7_publication_reports.py` | **VERIFIED** |
| PEV-027 | Parent Report | B7 | `parent-report.schema.json` | `test_b7_publication_reports.py` | **VERIFIED** |
| PEV-028 | Teacher Diagnostic Report | B7 | `teacher-report.schema.json` | `test_b7_publication_reports.py` | **VERIFIED** |
| PEV-075 | Annotation Contract | B7 | `Annotation` model + ledger-linked generation | `test_b7_publication_reports.py` | **VERIFIED** |
| PEV-077 | Evaluated Paper Output Contract | B7 | Evaluated-paper schema + write-once export storage | `test_b7_publication_reports.py` | **VERIFIED** |
| PEV-078 | Report Output Contracts | B7 | student / parent / teacher schemas under `packages/contracts/schemas/` | `test_b7_publication_reports.py` | **VERIFIED** |

---

## B10 closure deep-dive

| PEV | Verdict | Concrete proof |
|-----|---------|----------------|
| **PEV-002** | VERIFIED | Upload → `assessment_artifacts` → parse run → edit → apply question tree (`authoring.py`, `authoring_ai.py`, mig `0011`) |
| **PEV-004** | VERIFIED | Live `/ai/proposals/answer-key|rubric` enqueue `AuthoringAiRun` when `AI_PROVIDER_AUTHORING` set; AI_PROPOSED drafts require teacher approve; A2 503-only stub superseded |
| **PEV-013** | VERIFIED | Structured segment schema + Pydantic kinds + fixed-provider emission; Math-only CVB bound documented |
| **PEV-069** | VERIFIED | `UploadScanner` protocol; scan-before-storage; rejection codes `MALWARE_DETECTED` / `UPLOAD_SCAN_FAILED` |
| **PEV-072** | VERIFIED | Central `add_audit_event` + correlation middleware + ctor allowlist test |

**Not VERIFIED as live (deferred):** PEV-035–038, 041, 043, and all FUTURE_ENTERPRISE IDs.

---

## Explicitly deferred (not BUILD_NOW)

| Release state | PEV IDs | Must remain |
|---------------|---------|-------------|
| AFTER_CLIENT_APPROVAL | 035, 036, 037, 038, 041, 043, 058, 059 | Deferred — no live MasteryState / resource assignment / reassessment / gold gates |
| FUTURE_ENTERPRISE | 044–046, 048–051, 054–057 | Deferred — horizontal grading, SSO, multi-subject, etc. |

Do **not** mark these VERIFIED in CVB release notes.

---

## Residual non-blocking hygiene

These are **not** BUILD_NOW BLOCKED items, but should be tracked:

1. Production AV adapter beyond `UPLOAD_SCANNER=none|fixed`  
2. Frontend authoring UI for question-paper parse / proposal review (FCR recorded)  
3. Analytics class-section cohort filter stub (B8 carry-over)  
4. Fill B10 report placeholders: feature SHA, CI run, squash SHA, test counts  

---

## Sign-off checklist

| Check | Status |
|-------|--------|
| 59/59 BUILD_NOW audited against code | Complete |
| Deferred IDs kept deferred | Yes |
| No contract-only stub marked VERIFIED for PEV-004 | Yes (B10 live provider path) |
| Genuine BLOCKED gaps | **None** |
| `main` unchanged requirement | `be5f10aef3cf536420adcffdb9302b6b3b6c0955` |
| Related report | `docs/engineering/B10_CVB_RELEASE_CLOSURE_REPORT.md` |

---

## Document control

| Version | Date | Change |
|---------|------|--------|
| 0.1 | 2026-09-07 | Initial CVB BUILD_NOW release audit at B10 closure |
