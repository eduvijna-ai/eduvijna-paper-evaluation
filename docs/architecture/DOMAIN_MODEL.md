# EduVijna Domain Model

**Product:** EduVijna Paper Evaluation (CVB v0.1)  
**Status:** Architecture contract — Day 1 approved  
**Last updated:** 2026-09-07  
**Related:** [ADR-005](adrs/ADR-005-tenant-aware-data-model.md), [DATABASE_SCHEMA.md](./DATABASE_SCHEMA.md), [EVALUATION_LEDGER.md](./EVALUATION_LEDGER.md)

---

## 1. Purpose

This document defines the **logical domain entities**, their fields, tenant scoping rules, and relationships for EduVijna. It is the contract between product, API, database, and AI pipeline modules.

**Conventions**

| Symbol | Meaning |
|--------|---------|
| `T` | Entity is **tenant-scoped** (`tenant_id NOT NULL`) |
| `G` | **Global** reference data (no `tenant_id`; non-PII) |
| `→` | Required FK relationship |
| `⇢` | Optional FK |
| `1—*` | One-to-many |
| `*—*` | Many-to-many via join entity |

All tenant-scoped entities inherit audit timestamps: `created_at`, `updated_at` (UTC, timestamptz). Primary keys are UUID v4 unless noted.

---

## 2. Tenancy & Organization

### 2.1 Tenant `G` (root partition)

The deployment partition. All institution data hangs under a tenant.

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | PK |
| `slug` | string | Globally unique URL identifier |
| `name` | string | Display name |
| `status` | enum | `ACTIVE`, `SUSPENDED`, `ARCHIVED` |
| `config` | JSONB | Feature flags, retention, review policies |
| `created_at` | timestamptz | |
| `updated_at` | timestamptz | |

**Relationships:** `Tenant 1—* Institution`, `Tenant 1—* User` (via membership), all `T` business aggregates.

---

### 2.2 Institution `T`

A school, college, or coaching center within a tenant. CVB may use one institution per tenant; schema supports many.

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | PK |
| `tenant_id` | UUID | FK → `tenants.id` |
| `code` | string | Unique per tenant |
| `name` | string | |
| `timezone` | string | IANA, e.g. `Asia/Kolkata` |
| `address` | JSONB | Optional structured address |
| `settings` | JSONB | Grading defaults, report templates |
| `created_at` | timestamptz | |
| `updated_at` | timestamptz | |

**Unique:** `(tenant_id, code)`

**Relationships:** `Institution 1—* AcademicYear`, `Institution 1—* ClassSection`, `Institution 1—* Student`, `Institution 1—* Assessment`

---

## 3. Identity & Access Control

### 3.1 User `T`

Human operator (teacher, admin, reviewer). Not the same as Student.

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | PK |
| `tenant_id` | UUID | FK → `tenants.id` |
| `email` | string | Unique per tenant |
| `display_name` | string | |
| `status` | enum | `ACTIVE`, `INVITED`, `DISABLED` |
| `password_hash` | string | Nullable until CVB auth placeholder replaced |
| `last_login_at` | timestamptz | Optional |
| `created_at` | timestamptz | |
| `updated_at` | timestamptz | |

**Unique:** `(tenant_id, email)`

---

### 3.2 Role `T`

Named role definition within a tenant (extensible RBAC foundation).

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | PK |
| `tenant_id` | UUID | FK → `tenants.id` |
| `code` | string | e.g. `INSTITUTION_ADMIN`, `TEACHER`, `REVIEWER`, `VIEWER` |
| `name` | string | Display label |
| `description` | string | Optional |
| `is_system` | boolean | Seed roles; non-deletable |
| `created_at` | timestamptz | |
| `updated_at` | timestamptz | |

**Unique:** `(tenant_id, code)`

**Seed roles (CVB):** `INSTITUTION_ADMIN`, `TEACHER`, `REVIEWER`, `VIEWER`

---

### 3.3 Permission `G`

Atomic capability. Global catalog; assigned to roles per tenant.

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | PK |
| `code` | string | Globally unique, e.g. `assessment:create` |
| `resource` | string | Domain resource |
| `action` | string | `create`, `read`, `update`, `delete`, `approve`, `publish` |
| `description` | string | |
| `created_at` | timestamptz | |

---

### 3.4 UserRole `T`

Join: user ↔ role within tenant. Optional institution scope for future multi-campus.

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | PK |
| `tenant_id` | UUID | FK → `tenants.id` |
| `user_id` | UUID | FK → `users.id` |
| `role_id` | UUID | FK → `roles.id` |
| `institution_id` | UUID | Optional FK → `institutions.id` |
| `granted_by` | UUID | FK → `users.id` |
| `granted_at` | timestamptz | |
| `created_at` | timestamptz | |

**Unique:** `(tenant_id, user_id, role_id, institution_id)` — null institution treated as tenant-wide.

**ER note:** `User *—* Role` via `UserRole`; permissions resolved through `role_permissions` (future join table or JSONB on Role for CVB simplification).

---

## 4. Academic Structure

### 4.1 AcademicYear `T`

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | PK |
| `tenant_id` | UUID | |
| `institution_id` | UUID | FK → `institutions.id` |
| `label` | string | e.g. `2025-26` |
| `start_date` | date | |
| `end_date` | date | |
| `is_current` | boolean | One current per institution |
| `created_at` | timestamptz | |
| `updated_at` | timestamptz | |

**Unique:** `(tenant_id, institution_id, label)`

---

### 4.2 ClassSection `T`

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | PK |
| `tenant_id` | UUID | |
| `institution_id` | UUID | |
| `academic_year_id` | UUID | FK → `academic_years.id` |
| `grade` | string | e.g. `10`, `B.Sc Sem 2` |
| `section` | string | e.g. `A` |
| `display_name` | string | e.g. `Grade 10 — Section A` |
| `created_at` | timestamptz | |
| `updated_at` | timestamptz | |

**Unique:** `(tenant_id, institution_id, academic_year_id, grade, section)`

---

### 4.3 Student `T`

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | PK |
| `tenant_id` | UUID | |
| `institution_id` | UUID | |
| `class_section_id` | UUID | Optional FK |
| `external_ref` | string | Institution roll / admission number |
| `first_name` | string | |
| `last_name` | string | |
| `date_of_birth` | date | Optional |
| `status` | enum | `ACTIVE`, `TRANSFERRED`, `WITHDRAWN` |
| `metadata` | JSONB | Optional tags |
| `created_at` | timestamptz | |
| `updated_at` | timestamptz | |

**Unique:** `(tenant_id, institution_id, external_ref)`

---

### 4.4 Guardian `T`

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | PK |
| `tenant_id` | UUID | |
| `institution_id` | UUID | |
| `first_name` | string | |
| `last_name` | string | |
| `email` | string | Optional |
| `phone` | string | Optional |
| `created_at` | timestamptz | |
| `updated_at` | timestamptz | |

---

### 4.5 StudentGuardian `T`

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | PK |
| `tenant_id` | UUID | |
| `student_id` | UUID | FK → `students.id` |
| `guardian_id` | UUID | FK → `guardians.id` |
| `relationship` | enum | `PARENT`, `GUARDIAN`, `OTHER` |
| `is_primary` | boolean | |
| `created_at` | timestamptz | |

**Unique:** `(tenant_id, student_id, guardian_id)`

**ER:** `Student *—* Guardian` via `StudentGuardian`

---

## 5. Curriculum

### 5.1 Curriculum `T`

Root curriculum document for an institution or tenant (e.g. CBSE Grade 10 Mathematics).

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | PK |
| `tenant_id` | UUID | |
| `institution_id` | UUID | Optional; null = tenant-wide template |
| `code` | string | Unique per tenant |
| `title` | string | |
| `subject` | string | e.g. `Mathematics` |
| `grade_level` | string | |
| `status` | enum | `DRAFT`, `ACTIVE`, `ARCHIVED` |
| `version` | integer | Logical version counter |
| `created_at` | timestamptz | |
| `updated_at` | timestamptz | |

See [CURRICULUM_ONTOLOGY.md](./CURRICULUM_ONTOLOGY.md) for hierarchy semantics.

---

### 5.2 CurriculumNode `T`

Generic tree node; `node_type` discriminates hierarchy level.

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | PK |
| `tenant_id` | UUID | |
| `curriculum_id` | UUID | FK → `curricula.id` |
| `parent_id` | UUID | Optional self-FK |
| `node_type` | enum | `GRADE`, `SEMESTER`, `SUBJECT`, `UNIT`, `CHAPTER`, `TOPIC`, `SUBTOPIC`, `CONCEPT`, `SKILL`, `LEARNING_OUTCOME` |
| `code` | string | Unique within curriculum |
| `title` | string | |
| `description` | text | Optional |
| `sort_order` | integer | Sibling ordering |
| `metadata` | JSONB | Bloom level, board refs |
| `created_at` | timestamptz | |
| `updated_at` | timestamptz | |

**Unique:** `(tenant_id, curriculum_id, code)`

**ER:** Self-referential tree `CurriculumNode parent 1—* children`

---

### 5.3 CurriculumPrerequisite `T`

Directed edge: prerequisite → dependent concept/skill.

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | PK |
| `tenant_id` | UUID | |
| `curriculum_id` | UUID | |
| `from_node_id` | UUID | Prerequisite |
| `to_node_id` | UUID | Dependent |
| `strength` | enum | `REQUIRED`, `RECOMMENDED` |
| `created_at` | timestamptz | |

**Unique:** `(tenant_id, from_node_id, to_node_id)`

---

## 6. Assessment Content

### 6.1 Assessment `T`

Logical exam / test instance.

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | PK |
| `tenant_id` | UUID | |
| `institution_id` | UUID | |
| `curriculum_id` | UUID | Optional FK |
| `academic_year_id` | UUID | Optional |
| `class_section_id` | UUID | Optional target cohort |
| `code` | string | Unique per tenant |
| `title` | string | |
| `subject` | string | CVB: `Mathematics` |
| `workflow_state` | enum | See [WORKFLOW_STATES.md](./WORKFLOW_STATES.md) |
| `scheduled_at` | timestamptz | Optional |
| `max_total_marks` | decimal | Denormalized sum |
| `created_by` | UUID | FK → `users.id` |
| `created_at` | timestamptz | |
| `updated_at` | timestamptz | |

---

### 6.2 AssessmentVersion `T`

Immutable snapshot of question paper structure once published for evaluation.

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | PK |
| `tenant_id` | UUID | |
| `assessment_id` | UUID | FK |
| `version_number` | integer | Monotonic |
| `status` | enum | `DRAFT`, `PUBLISHED`, `SUPERSEDED` |
| `question_paper_s3_key` | string | Object storage ref |
| `structure` | JSONB | Question tree, marks, labels |
| `published_at` | timestamptz | |
| `published_by` | UUID | |
| `created_at` | timestamptz | |

**Unique:** `(tenant_id, assessment_id, version_number)`

---

### 6.2a AssessmentArtifact `T` — **B10 live**

Immutable uploaded assessment source (question paper). Scan runs before storage write.

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | PK |
| `tenant_id` | UUID | |
| `assessment_id` | UUID | FK → `assessments.id` |
| `artifact_type` | enum | `QUESTION_PAPER` (CVB) |
| `original_filename` | string | |
| `mime_type` | string | |
| `byte_size` | bigint | |
| `content_sha256` | string | Content-addressed |
| `storage_key` | string | Write-once object key |
| `security_scan_status` | enum | `NOT_CONFIGURED`, `CLEAN`, `REJECTED`, `ERROR` |
| `uploaded_by` | UUID | Optional FK → `users.id` |
| `uploaded_at` | timestamptz | |
| `created_at` | timestamptz | |

**Unique:** `storage_key`

---

### 6.2b AuthoringAiRun `T` — **B10 live**

Durable authoring AI job. Proposals are not evaluation marks.

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | PK |
| `tenant_id` | UUID | |
| `assessment_id` / `assessment_version_id` | UUID | Required |
| `question_version_id` | UUID | Optional (propose flows) |
| `assessment_artifact_id` | UUID | Optional parse input |
| `operation` | enum | `PARSE_QUESTION_PAPER`, `PROPOSE_ANSWER_KEY`, `PROPOSE_RUBRIC`, `SUGGEST_CURRICULUM_MAPPING` |
| `status` | enum | `QUEUED`, `RUNNING`, `REVIEW_REQUIRED`, `SUCCEEDED`, `FAILED`, `UNAVAILABLE` |
| `input_hash` | string | Idempotency / staleness |
| `proposal_payload` | JSONB | Bounded tree / answer / rubric / mappings |
| `requested_by` / `requested_at` | UUID / timestamptz | |
| `celery_task_id` | string | Optional |
| `answer_key_version_id` / `rubric_version_id` | UUID | Optional created drafts |
| `correlation_id` | string | Request/worker trace (PEV-072) |
| `failure_code` / `failure_detail` | string | Optional |

---

### 6.3 Question `T`

Logical question within an assessment (may span sub-parts).

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | PK |
| `tenant_id` | UUID | |
| `assessment_id` | UUID | |
| `parent_question_id` | UUID | Optional for sub-questions |
| `label` | string | e.g. `Q7`, `Q7(a)` |
| `sort_order` | integer | |
| `max_marks` | decimal | |
| `question_type` | enum | `MCQ`, `SHORT`, `LONG`, `NUMERIC`, `PROOF` |
| `created_at` | timestamptz | |
| `updated_at` | timestamptz | |

---

### 6.4 QuestionVersion `T`

Frozen question content bound to an assessment version.

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | PK |
| `tenant_id` | UUID | |
| `question_id` | UUID | |
| `assessment_version_id` | UUID | |
| `prompt_text` | text | |
| `prompt_assets` | JSONB | S3 refs for diagrams |
| `curriculum_node_ids` | UUID[] | Mapped concepts |
| `created_at` | timestamptz | |

---

### 6.5 AnswerKey `T` / AnswerKeyVersion `T`

| Entity | Key fields |
|--------|------------|
| **AnswerKey** | `id`, `tenant_id`, `assessment_id`, `title`, `created_at` |
| **AnswerKeyVersion** | `id`, `tenant_id`, `answer_key_id`, `version_number`, `status` (`DRAFT`→`PUBLISHED`), `answers` JSONB (per question: expected, alternatives, tolerance, units), `published_at`, `published_by` |

**ER:** `Assessment 1—* AnswerKey 1—* AnswerKeyVersion`

---

### 6.6 Rubric `T` / RubricVersion `T` / RubricCriterion `T`

| Entity | Key fields |
|--------|------------|
| **Rubric** | `id`, `tenant_id`, `assessment_id`, `title`, `provenance` (`TEACHER`, `AI_PROPOSED`) |
| **RubricVersion** | `id`, `tenant_id`, `rubric_id`, `version_number`, `status`, `approved_by`, `approved_at`, `published_at` |
| **RubricCriterion** | See [RUBRIC_SCHEMA.md](./RUBRIC_SCHEMA.md) — `id`, `tenant_id`, `rubric_version_id`, `question_id`, `label`, `max_marks`, scoring rules JSONB |

**ER:** `Rubric 1—* RubricVersion 1—* RubricCriterion`; each criterion links to one `Question`.

---

## 7. Submission & Evidence

### 7.1 Submission `T`

One student's answer sheet bundle for an assessment.

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | PK |
| `tenant_id` | UUID | |
| `assessment_id` | UUID | |
| `assessment_version_id` | UUID | Bound at processing time |
| `student_id` | UUID | Optional until identity confirmed |
| `student_match_state` | enum | See WORKFLOW_STATES |
| `workflow_state` | enum | Submission lifecycle |
| `source_bundle_s3_key` | string | Immutable original upload |
| `source_content_hash` | string | SHA-256 for integrity |
| `page_count` | integer | |
| `uploaded_by` | UUID | |
| `uploaded_at` | timestamptz | |
| `created_at` | timestamptz | |
| `updated_at` | timestamptz | |

---

### 7.2 SubmissionPage `T`

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | PK |
| `tenant_id` | UUID | |
| `submission_id` | UUID | |
| `page_index` | integer | 0-based |
| `image_s3_key` | string | Normalized page image |
| `width_px` | integer | |
| `height_px` | integer | |
| `is_continuation` | boolean | Extra sheet flag |
| `created_at` | timestamptz | |

**Unique:** `(tenant_id, submission_id, page_index)`

---

### 7.3 AnswerRegion `T`

Detected bounding region containing student work.

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | PK |
| `tenant_id` | UUID | |
| `submission_page_id` | UUID | |
| `bbox` | JSONB | `{x, y, w, h}` normalized 0–1 |
| `region_type` | enum | `ANSWER`, `SCRATCH`, `DIAGRAM`, `IDENTITY` |
| `crop_s3_key` | string | Optional cropped evidence |
| `transcription` | text | Latest transcription |
| `transcription_confidence` | decimal | 0–1 |
| `created_at` | timestamptz | |
| `updated_at` | timestamptz | |

---

### 7.4 QuestionAnswerMapping `T`

Links answer regions to rubric questions.

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | PK |
| `tenant_id` | UUID | |
| `submission_id` | UUID | |
| `question_id` | UUID | |
| `answer_region_ids` | UUID[] | May span pages |
| `mapping_state` | enum | `PROPOSED`, `REVIEW_REQUIRED`, `CONFIRMED` |
| `mapping_confidence` | decimal | |
| `mapped_by` | enum | `AI`, `HUMAN` |
| `confirmed_by` | UUID | Optional |
| `created_at` | timestamptz | |
| `updated_at` | timestamptz | |

**Unique:** `(tenant_id, submission_id, question_id)`

---

## 8. Evaluation

### 8.1 EvaluationRun `T`

One async pipeline execution for a submission (or re-run).

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | PK |
| `tenant_id` | UUID | |
| `submission_id` | UUID | |
| `run_number` | integer | |
| `trigger` | enum | `INITIAL`, `REPROCESS`, `OVERRIDE_RERUN` |
| `status` | enum | `RUNNING`, `COMPLETED`, `FAILED` |
| `stages_completed` | JSONB | Pipeline checkpoint |
| `started_at` | timestamptz | |
| `completed_at` | timestamptz | |
| `created_at` | timestamptz | |

---

### 8.2 QuestionEvaluation `T`

Aggregate evaluation for one question on one submission. Canonical ledger projection — see [EVALUATION_LEDGER.md](./EVALUATION_LEDGER.md).

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | PK |
| `tenant_id` | UUID | |
| `evaluation_run_id` | UUID | |
| `submission_id` | UUID | |
| `student_id` | UUID | |
| `assessment_id` | UUID | |
| `assessment_version_id` | UUID | |
| `question_id` | UUID | |
| `question_version_id` | UUID | |
| `rubric_version_id` | UUID | |
| `answer_key_version_id` | UUID | |
| `workflow_state` | enum | Question evaluation states |
| `max_mark` | decimal | |
| `proposed_ai_score` | decimal | Sum of criterion proposals |
| `final_score` | decimal | Human-approved |
| `first_divergence_step` | integer | Optional step index |
| `ecf_applied` | boolean | |
| `alternative_method_id` | string | Optional |
| `error_codes` | string[] | Taxonomy codes |
| `identity_confidence` | decimal | |
| `mapping_confidence` | decimal | |
| `transcription_confidence` | decimal | |
| `evaluation_confidence` | decimal | |
| `transcribed_answer` | text | |
| `deduction_reasons` | JSONB | Structured reasons |
| `curriculum_concept_ids` | UUID[] | |
| `reviewer_id` | UUID | |
| `reviewed_at` | timestamptz | |
| `ledger_version` | integer | Optimistic concurrency |
| `created_at` | timestamptz | |
| `updated_at` | timestamptz | |

**Unique:** `(tenant_id, submission_id, question_id, evaluation_run_id)` — latest approved row wins for publication.

---

### 8.3 CriterionEvaluation `T`

Per-rubric-criterion mark proposal and final decision.

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | PK |
| `tenant_id` | UUID | |
| `question_evaluation_id` | UUID | |
| `rubric_criterion_id` | UUID | |
| `max_marks` | decimal | |
| `proposed_marks` | decimal | |
| `final_marks` | decimal | |
| `decision` | enum | `AWARDED`, `PARTIAL`, `DEDUCTED`, `NOT_APPLICABLE` |
| `rationale` | text | |
| `error_code` | string | Optional taxonomy |
| `created_at` | timestamptz | |
| `updated_at` | timestamptz | |

---

### 8.4 Annotation `T`

Digital mark overlay on submission evidence (separate from immutable source).

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | PK |
| `tenant_id` | UUID | |
| `submission_id` | UUID | |
| `submission_page_id` | UUID | |
| `question_evaluation_id` | UUID | Optional |
| `annotation_type` | enum | `TICK`, `CROSS`, `PARTIAL`, `MARK`, `COMMENT`, `HIGHLIGHT` |
| `geometry` | JSONB | Point or bbox |
| `payload` | JSONB | Marks awarded/deducted, short reason |
| `created_by` | UUID | AI or human |
| `created_at` | timestamptz | |

---

### 8.5 ReviewAction `T`

Immutable human decision record.

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | PK |
| `tenant_id` | UUID | |
| `submission_id` | UUID | |
| `question_evaluation_id` | UUID | Optional (whole-submission actions) |
| `actor_id` | UUID | FK → `users.id` |
| `action_type` | enum | `ACCEPT`, `OVERRIDE`, `REJECT`, `REQUEST_REPROCESS`, `ESCALATE` |
| `before_snapshot` | JSONB | Marks/state before |
| `after_snapshot` | JSONB | Marks/state after |
| `reason` | text | Required for OVERRIDE/REJECT |
| `created_at` | timestamptz | Append-only |

---

### 8.6 PublishedResult `T`

Released outputs after approval.

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | PK |
| `tenant_id` | UUID | |
| `submission_id` | UUID | |
| `assessment_id` | UUID | |
| `student_id` | UUID | |
| `total_score` | decimal | |
| `max_total_score` | decimal | |
| `annotated_pdf_s3_key` | string | |
| `student_report_s3_key` | string | |
| `parent_report_s3_key` | string | |
| `teacher_report_s3_key` | string | |
| `published_by` | UUID | |
| `published_at` | timestamptz | |
| `ledger_snapshot_id` | UUID | Hash or run ref |
| `created_at` | timestamptz | |

---

## 9. Learning Analytics

### 9.1 MasteryEvidence `T` — **B8 live (B9 / B12 source)**

Evidence row linking a **PUBLISHED** evaluation to a curriculum mastery signal.
Algorithm version `B8_V1`. Derived deterministically from final human-approved ledger
scores + taxonomy + A2 `QuestionCurriculumMapping` (exact `question_version_id`).
No AI inference. Immutable. See migration `20260907_0009`.

**B9 / B12 role:** sole evidence **source** for learning plans (`source_evidence_hash`)
and longitudinal MasteryState / mistake notebook materialization. B9/B12 never invent
mastery from unpublished ledgers or AI, and never mutate these rows.

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | PK |
| `tenant_id` | UUID | |
| `student_id` | UUID | |
| `curriculum_node_id` | UUID | Concept/skill/LO |
| `question_evaluation_id` | UUID | Source evaluation |
| `published_result_id` | UUID | B7 published source |
| `evidence_type` | enum | `CONCEPT`, `EXECUTION`, `PROCEDURE` |
| `strength` | enum | `STRONG`, `WEAK`, `INCONCLUSIVE` |
| `score_ratio` | decimal | Factual normalized score (not “mastery probability”) |
| `algorithm_version` | string | e.g. `B8_V1` |
| `created_at` | timestamptz | |

---

### 9.2 MasteryState `T` — **B12 live (APP-003 / PEV-037)**

Current longitudinal mastery aggregate per student × curriculum node, derived
deterministically from immutable B8 `MasteryEvidence` (`algorithm_version = B12_V1`).
No AI inference. Null ratio = insufficient decisive (STRONG/WEAK) evidence for that
dimension; INCONCLUSIVE is counted separately and never treated as weakness.
See migration `20260907_0012`.

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | PK |
| `tenant_id` | UUID | |
| `student_id` | UUID | |
| `curriculum_id` | UUID | |
| `curriculum_node_id` | UUID | |
| `concept_mastery` | decimal \| null | Nullable 0..1; null = no decisive concept evidence |
| `execution_accuracy` | decimal \| null | Nullable 0..1; null = no decisive execution evidence |
| `concept_decisive_count` | integer | STRONG+WEAK concept evidence count |
| `execution_decisive_count` | integer | STRONG+WEAK execution evidence count |
| `concept_inconclusive_count` | integer | INCONCLUSIVE concept evidence (not in ratio) |
| `execution_inconclusive_count` | integer | INCONCLUSIVE execution evidence (not in ratio) |
| `evidence_count` | integer | Concept + execution evidence rows contributing |
| `source_evidence_hash` | string | SHA-256 of sorted contributing evidence IDs |
| `algorithm_version` | string | `B12_V1` |
| `last_updated_at` | timestamptz | |
| `created_at` | timestamptz | |

**Unique:** `(tenant_id, student_id, curriculum_node_id, algorithm_version)`

---

### 9.2a MasteryStateSnapshot `T` — **B12 live (PEV-037 trend)**

Historical cumulative mastery state at each published-result effective time
(ordered by `published_at` / `created_at`). Same ratio/count semantics as
`MasteryState`. Grain unique:
`(tenant_id, student_id, curriculum_node_id, published_result_id, algorithm_version)`.

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | PK |
| `tenant_id` / `student_id` / `curriculum_id` / `curriculum_node_id` | UUID | |
| `published_result_id` | UUID | Snapshot as-of this published result |
| `assessment_id` | UUID | |
| `concept_mastery` / `execution_accuracy` | decimal \| null | Same null semantics as MasteryState |
| `concept_decisive_count` / `execution_decisive_count` | integer | |
| `concept_inconclusive_count` / `execution_inconclusive_count` | integer | |
| `evidence_count` | integer | |
| `source_evidence_hash` | string | |
| `algorithm_version` | string | `B12_V1` |
| `effective_at` | timestamptz | Published effective time |
| `created_at` | timestamptz | |

---

### 9.2b MistakeNotebookEntry `T` — **B12 live (PEV-038)**

Persistent per-error notebook grain from published academic errors (review/system
codes excluded). Practice kinds are curriculum-only
(`CONCEPT_CHECK` / `EXECUTION_PRACTICE` / `PROCEDURE_PRACTICE`); may link ACTIVE
B9 `LearningRecommendation` IDs when available. No open-web resources.
Institution-approved catalog assignment is **B13 live** (PEV-041 / APP-004) —
see §9.6 / §9.7; notebook practice kinds remain curriculum-constrained text only.

Grain unique: `(tenant_id, student_id, published_result_id, question_evaluation_id,
academic_error_code, algorithm_version)`.

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | PK |
| `tenant_id` / `student_id` | UUID | |
| `published_result_id` / `assessment_id` / `submission_id` | UUID | |
| `question_evaluation_id` / `question_version_id` | UUID | |
| `academic_error_code` | string | Canonical academic taxonomy code |
| `final_score` / `max_mark` | decimal | From final human-approved QE |
| `deduction_reasons` | JSONB | |
| `first_divergence_step` | text \| null | |
| `curriculum_node_ids` | JSONB | Related node UUID strings |
| `recommended_practice_kind` | enum | Curriculum-only practice kinds above |
| `linked_learning_recommendation_ids` | JSONB | Optional B9 ACTIVE links |
| `source_ledger_snapshot_hash` | string | |
| `source_mastery_evidence_ids` | JSONB | Contributing B8 evidence IDs |
| `algorithm_version` | string | `B12_V1` |
| `materialized_at` / `effective_at` / `created_at` | timestamptz | |

**Still deferred (not B12/B13):** PEV-043 reassessment instantiation, PEV-058/059
gold benchmark / AI regression. PEV-041 curriculum resource assignment is **B13 live**.

---

### 9.3 LearningPlanRun `T` — **B9 live**

Versioned, hashed generation of a curriculum-scoped learning plan (algorithm `B9_V1`).
Statuses: `QUEUED`, `RUNNING`, `READY`, `FAILED`, `SUPERSEDED`.
Does **not** reuse `PipelineJob`.

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | PK |
| `tenant_id` | UUID | |
| `student_id` | UUID | |
| `curriculum_id` | UUID | Never mixed across curricula |
| `version_number` | integer | Per student×curriculum |
| `status` | enum | See above |
| `source_evidence_hash` | string | Canonical B8 facts |
| `curriculum_graph_hash` | string | Nodes + prerequisites |
| `input_hash` | string | Algorithm + evidence + graph |
| `algorithm_version` | string | `B9_V1` |
| `generation_source` | enum | `AI`, `FIXED`, `RULES_FALLBACK` |
| `celery_task_id` | string | Optional worker id |
| `requested_by` / `requested_at` | UUID / timestamptz | |

---

### 9.4 LearningRecommendation `T` — **B9 live (curriculum-constrained)**

Curriculum-constrained remediation suggestion for one plan run. Targets and prerequisites
must stay inside the selected curriculum. No open-web URLs in recommendation payloads;
institution-approved catalog assignment is separate (**B13** `StudentResourceAssignment`).

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | PK |
| `tenant_id` | UUID | |
| `learning_plan_run_id` | UUID | Parent run |
| `student_id` | UUID | |
| `curriculum_id` | UUID | Must stay within curriculum |
| `target_node_id` | UUID | Topic/concept to study |
| `recommendation_kind` | enum | `PREREQUISITE_REPAIR`, `TARGET_CONCEPT`, `PROCEDURE_PRACTICE`, `EXECUTION_PRACTICE` |
| `priority` | integer | 1–3 |
| `rationale` | text | |
| `concept_signal` / `execution_signal` / `procedure_signal` | enum | `STRONG`/`WEAK`/`INCONCLUSIVE` |
| `evidence_count` | integer | |
| `mean_evidence_score_ratio` | decimal | Optional |
| `status` | enum | `ACTIVE`, `DISMISSED`, `COMPLETED` |
| `target_node_*_snapshot` | string | Code/title/type at generation |

Related: `LearningRecommendationPrerequisite` (ordered REQUIRED/RECOMMENDED edges),
`LearningRecommendationEvidence` (FK to `MasteryEvidence`), `LearningPathStep`
(ordered path kinds including `MASTERY_CHECK` for inconclusive required prerequisites).

---

### 9.5 ImprovementAssessment `T` / ImprovementAssessmentItem `T` — **B9 live (blueprint only)**

Teacher-reviewed **blueprint** only. Approval does **not** create Assessment / Question /
Submission reassessment entities (PEV-043 deferred). Resource catalog assignment is
**B13 live** (PEV-041 / APP-004 / Issue #45) — see §9.6 / §9.7.

| Entity | Key fields |
|--------|------------|
| **ImprovementAssessment** | `id`, `tenant_id`, `student_id`, `curriculum_id`, `learning_plan_run_id`, `version_number`, `title`, `status` (`DRAFT`…`APPROVED`/`REJECTED`/`FAILED`), hashes, `blueprint_storage_key` / `blueprint_sha256` / `blueprint_byte_size`, approve/reject metadata |
| **ImprovementAssessmentItem** | `id`, `tenant_id`, `improvement_assessment_id`, `learning_recommendation_id`, `curriculum_node_id`, `item_code`, `template_kind`, `question_template_ref`, `focus`, `difficulty`, `suggested_marks` (advisory), `sort_order` |

---

### 9.6 CurriculumResource `T` / CurriculumResourceNode `T` — **B13 live (PEV-041 / APP-004)**

Tenant-scoped, institution-approved practice catalog. `content_ref` is an opaque
internal key — open-web URLs (`http://`, `https://`, `//`) are rejected. No open-web
discovery. Lifecycle: `DRAFT` → `APPROVED` → `ACTIVE` (or `DEACTIVATED`).

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | PK |
| `tenant_id` / `curriculum_id` | UUID | Unique with `code` |
| `code` | string | Per-curriculum unique |
| `title` / `description` | string / text \| null | |
| `resource_kind` | enum | `PRACTICE_SET`, `WORKED_EXAMPLE`, `CONCEPT_NOTE`, `INTERNAL_PACKET` |
| `status` | enum | `DRAFT`, `APPROVED`, `ACTIVE`, `DEACTIVATED` |
| `content_ref` | string | Opaque internal catalog ref (not a public URL) |
| `created_by` / `approved_by` / `approved_at` | UUID / timestamptz | |
| `created_at` / `updated_at` | timestamptz | |

**CurriculumResourceNode:** unique `(resource_id, curriculum_node_id)`; nodes must belong
to the resource’s curriculum and tenant. At least one node required to create/approve.

---

### 9.7 StudentResourceAssignment `T` — **B13 live (PEV-041 / APP-004)**

Assigns an **ACTIVE** `CurriculumResource` to a student. Optional link to an ACTIVE B9
`LearningRecommendation` (same student; target node must be mapped on the resource).
Assignment does **not** mutate B9 recommendations or B12 mastery/notebook rows.

Idempotency (PostgreSQL partial unique, `NULLS NOT DISTINCT`):

`(tenant_id, student_id, resource_id, learning_recommendation_id) WHERE status='ASSIGNED'`.

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | PK |
| `tenant_id` / `student_id` / `resource_id` | UUID | |
| `learning_recommendation_id` | UUID \| null | Optional B9 link |
| `status` | enum | `ASSIGNED`, `CANCELLED` |
| `assigned_by` / `assigned_at` | UUID / timestamptz | |
| `cancelled_by` / `cancelled_at` | UUID / timestamptz \| null | |
| `created_at` | timestamptz | |

**Still deferred after B13:** PEV-043 reassessment instantiation, PEV-058/059 gold
benchmark / AI regression, all FUTURE_ENTERPRISE PEVs.

---

## 10. Platform & Audit

### 10.1 AuditEvent `T`

Append-only audit log for significant actions.

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | PK |
| `tenant_id` | UUID | Nullable only for rare system events |
| `actor_user_id` | UUID | Optional (system jobs) |
| `entity_type` | string | Entity name |
| `entity_id` | UUID | |
| `action` | string | e.g. `created`, `updated`, `uploaded` |
| `payload_json` | JSONB | Before/after, metadata |
| `correlation_id` | string | Request trace (`X-Correlation-ID`, max 100) — **B10 enforced via `add_audit_event`** |
| `created_at` | timestamptz | Immutable |

**B10 note:** Prefer `apps/api/app/services/audit.py` (`add_audit_event`) so correlation IDs attach automatically. Direct `AuditEvent(` construction is restricted by test allowlist.

---

### 10.2 AiExecutionRecord `T`

Trace for every AI provider invocation.

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | PK |
| `tenant_id` | UUID | |
| `submission_id` | UUID | Optional |
| `evaluation_run_id` | UUID | Optional |
| `operation` | string | e.g. `evaluate_rubric` |
| `provider` | string | e.g. `openai` |
| `model` | string | |
| `model_version` | string | |
| `prompt_template_version` | string | |
| `input_refs` | JSONB | S3 keys, entity IDs |
| `input_hash` | string | SHA-256 of normalized input |
| `output_summary` | JSONB | Truncated structured output |
| `status` | enum | `SUCCESS`, `FAILED`, `TIMEOUT` |
| `latency_ms` | integer | |
| `token_usage` | JSONB | |
| `error_class` | string | Optional |
| `created_at` | timestamptz | |

See [AI_PROVIDER_CONTRACT.md](./AI_PROVIDER_CONTRACT.md).

---

## 11. Entity Relationship Overview

```
Tenant
 ├── Institution
 │    ├── AcademicYear
 │    ├── ClassSection
 │    ├── Student ←──StudentGuardian──→ Guardian
 │    └── Assessment
 │         ├── AssessmentVersion
 │         ├── Question → QuestionVersion
 │         ├── AnswerKey → AnswerKeyVersion
 │         └── Rubric → RubricVersion → RubricCriterion
 ├── Curriculum
 │    ├── CurriculumNode (tree)
 │    └── CurriculumPrerequisite (edges)
 └── Submission (per Assessment)
      ├── SubmissionPage → AnswerRegion
      ├── QuestionAnswerMapping → Question
      ├── EvaluationRun
      │    └── QuestionEvaluation → CriterionEvaluation
      ├── Annotation
      ├── ReviewAction
      └── PublishedResult

Student ← MasteryEvidence / MasteryState / MasteryStateSnapshot / MistakeNotebookEntry
      └── LearningPlanRun → LearningRecommendation → LearningPathStep
      └── ImprovementAssessment (blueprint) → ImprovementAssessmentItem
User ← UserRole → Role → Permission
AuditEvent, AiExecutionRecord (cross-cutting)
```

---

## 12. Tenant Scoping Summary

| Scope | Entities |
|-------|----------|
| **Global (`G`)** | `Permission` (capability catalog); platform `Tenant` root |
| **Tenant-scoped (`T`)** | All others listed in this document |
| **Immutable after publish** | `AssessmentVersion`, `AnswerKeyVersion`, `RubricVersion`, `Submission.source_*`, `ReviewAction`, `AuditEvent`, approved ledger rows |
| **Never cross-tenant FK** | All child FKs must match parent `tenant_id` (composite FK or RLS per ADR-005) |

---

## 13. Document Control

| Version | Date | Change |
|---------|------|--------|
| 0.1 | 2026-09-04 | Initial domain model contract for CVB |
| 0.2 | 2026-09-07 | B8 MasteryEvidence live; MasteryState deferred |
| 0.3 | 2026-09-07 | B9 LearningPlanRun / LearningRecommendation / ImprovementAssessment blueprint live; MasteryState, resource assignment, reassessment still deferred |
| 0.4 | 2026-09-08 | B12 MasteryState / MasteryStateSnapshot / MistakeNotebookEntry live (APP-003 / PEV-035–038); PEV-041/043/058/059 still deferred |
| 0.5 | 2026-09-08 | B13 CurriculumResource / StudentResourceAssignment live (APP-004 / PEV-041 / Issue #45); PEV-043/058/059 still deferred |
