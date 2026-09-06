# EduVijna Domain Model

**Product:** EduVijna Paper Evaluation (CVB v0.1)  
**Status:** Architecture contract — Day 1 approved  
**Last updated:** 2026-09-04  
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

### 9.1 MasteryEvidence `T`

Evidence row linking evaluation to curriculum mastery signal.

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | PK |
| `tenant_id` | UUID | |
| `student_id` | UUID | |
| `curriculum_node_id` | UUID | Concept/skill/LO |
| `question_evaluation_id` | UUID | Source evaluation |
| `evidence_type` | enum | `CONCEPT`, `EXECUTION`, `PROCEDURE` |
| `strength` | enum | `STRONG`, `WEAK`, `INCONCLUSIVE` |
| `score_ratio` | decimal | Normalized performance |
| `created_at` | timestamptz | |

---

### 9.2 MasteryState `T`

Aggregated mastery per student × curriculum node.

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | PK |
| `tenant_id` | UUID | |
| `student_id` | UUID | |
| `curriculum_node_id` | UUID | |
| `concept_mastery` | decimal | 0–1 |
| `execution_accuracy` | decimal | 0–1 |
| `evidence_count` | integer | |
| `last_updated_at` | timestamptz | |
| `created_at` | timestamptz | |

**Unique:** `(tenant_id, student_id, curriculum_node_id)`

---

### 9.3 LearningRecommendation `T`

Curriculum-constrained remediation suggestion.

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | PK |
| `tenant_id` | UUID | |
| `student_id` | UUID | |
| `curriculum_id` | UUID | Must stay within curriculum |
| `target_node_id` | UUID | Topic/concept to study |
| `prerequisite_node_ids` | UUID[] | Ordered repair path |
| `rationale` | text | |
| `source_submission_ids` | UUID[] | |
| `priority` | integer | |
| `status` | enum | `ACTIVE`, `DISMISSED`, `COMPLETED` |
| `created_at` | timestamptz | |

---

### 9.4 ImprovementAssessment `T` / ImprovementAssessmentItem `T`

| Entity | Key fields |
|--------|------------|
| **ImprovementAssessment** | `id`, `tenant_id`, `student_id`, `curriculum_id`, `blueprint_s3_key`, `generated_from_submission_id`, `status`, `created_at` |
| **ImprovementAssessmentItem** | `id`, `tenant_id`, `improvement_assessment_id`, `curriculum_node_id`, `question_template_ref`, `difficulty`, `sort_order` |

---

## 10. Platform & Audit

### 10.1 AuditEvent `T`

Append-only audit log for significant actions.

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | PK |
| `tenant_id` | UUID | |
| `actor_id` | UUID | Optional (system jobs) |
| `actor_type` | enum | `USER`, `SYSTEM`, `WORKER` |
| `event_type` | string | e.g. `submission.uploaded`, `ledger.override` |
| `resource_type` | string | Entity name |
| `resource_id` | UUID | |
| `correlation_id` | UUID | Request trace |
| `payload` | JSONB | Before/after, metadata |
| `ip_address` | inet | Optional |
| `created_at` | timestamptz | Immutable |

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

Student ← MasteryEvidence / MasteryState / LearningRecommendation
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
