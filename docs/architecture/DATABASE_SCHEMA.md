# EduVijna Database Schema (PostgreSQL 16)

**Product:** EduVijna Paper Evaluation (CVB v0.1)  
**ORM:** SQLAlchemy 2.x (async)  
**Migrations:** Alembic (`database/migrations/`)  
**Last updated:** 2026-09-04  
**Related:** [ADR-002](adrs/ADR-002-postgresql-system-of-record.md), [ADR-005](adrs/ADR-005-tenant-aware-data-model.md), [DOMAIN_MODEL.md](./DOMAIN_MODEL.md)

---

## 1. Design Principles

1. **UUID primary keys** — `gen_random_uuid()` default on all tables.
2. **Timestamps** — `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`, `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()` on mutable entities; trigger or ORM hook updates `updated_at`.
3. **Tenant isolation** — `tenant_id UUID NOT NULL REFERENCES tenants(id)` on every tenant-owned table; indexes lead with `tenant_id`.
4. **Composite uniqueness** — Business keys unique per tenant, e.g. `(tenant_id, code)`.
5. **RLS (defense in depth)** — Session variable `app.tenant_id` set per request; policies on sensitive tables (ADR-005).
6. **Append-only audit** — `audit_events` and post-approval ledger rows are not updated in place.
7. **Future tables documented now** — Full intended schema for CVB; Day-1 migration implements foundation only.

---

## 2. Migration Strategy

| Migration | Scope |
|-----------|-------|
| **`0001_day1_foundation`** | Tenancy, institution, identity, roster, audit — **implemented Day 1** |
| `0002_rbac_permissions` | `permissions`, `role_permissions` join |
| `0003_curriculum` | Curriculum tables |
| `0004_assessment_content` | Assessment, questions, keys, rubrics |
| `0005_submissions` | Submission pipeline tables |
| `0006_evaluation` | Evaluation run, ledger, annotations |
| `0007_publication_learning` | Published results, mastery, recommendations |
| `0008_ai_execution` | `ai_execution_records` |

Each migration is forward-only; destructive changes require explicit data migration scripts.

---

## 3. Day-1 Foundation Schema (`0001_day1_foundation`)

> **Implemented in CVB bootstrap.** All other tables in §4 are **documented for future migrations** — not created on Day 1.

### 3.1 `tenants`

```sql
CREATE TABLE tenants (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug            VARCHAR(64) NOT NULL,
    name            VARCHAR(255) NOT NULL,
    status          VARCHAR(32) NOT NULL DEFAULT 'ACTIVE'
                    CHECK (status IN ('ACTIVE', 'SUSPENDED', 'ARCHIVED')),
    config          JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_tenants_slug UNIQUE (slug)
);

CREATE INDEX idx_tenants_status ON tenants (status);
```

### 3.2 `institutions`

```sql
CREATE TABLE institutions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    code            VARCHAR(64) NOT NULL,
    name            VARCHAR(255) NOT NULL,
    timezone        VARCHAR(64) NOT NULL DEFAULT 'UTC',
    address         JSONB,
    settings        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_institutions_tenant_code UNIQUE (tenant_id, code)
);

CREATE INDEX idx_institutions_tenant ON institutions (tenant_id);
```

### 3.3 `users`

```sql
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    email           VARCHAR(320) NOT NULL,
    display_name    VARCHAR(255) NOT NULL,
    status          VARCHAR(32) NOT NULL DEFAULT 'ACTIVE'
                    CHECK (status IN ('ACTIVE', 'INVITED', 'DISABLED')),
    password_hash   VARCHAR(255),
    last_login_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_users_tenant_email UNIQUE (tenant_id, email)
);

CREATE INDEX idx_users_tenant ON users (tenant_id);
CREATE INDEX idx_users_tenant_status ON users (tenant_id, status);
```

### 3.4 `roles`

```sql
CREATE TABLE roles (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    code            VARCHAR(64) NOT NULL,
    name            VARCHAR(128) NOT NULL,
    description     TEXT,
    is_system       BOOLEAN NOT NULL DEFAULT false,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_roles_tenant_code UNIQUE (tenant_id, code)
);

CREATE INDEX idx_roles_tenant ON roles (tenant_id);
```

### 3.5 `permissions` (global catalog — seeded)

```sql
CREATE TABLE permissions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code            VARCHAR(128) NOT NULL,
    resource        VARCHAR(64) NOT NULL,
    action          VARCHAR(32) NOT NULL,
    description     TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_permissions_code UNIQUE (code)
);
```

> Day-1 seeds permissions; `role_permissions` join arrives in migration `0002`.

### 3.6 `user_roles`

```sql
CREATE TABLE user_roles (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id         UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    institution_id  UUID REFERENCES institutions(id) ON DELETE CASCADE,
    granted_by      UUID REFERENCES users(id) ON DELETE SET NULL,
    granted_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_user_roles_assignment
        UNIQUE NULLS NOT DISTINCT (tenant_id, user_id, role_id, institution_id)
);

CREATE INDEX idx_user_roles_tenant_user ON user_roles (tenant_id, user_id);
CREATE INDEX idx_user_roles_tenant_role ON user_roles (tenant_id, role_id);
```

### 3.7 `academic_years`

```sql
CREATE TABLE academic_years (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    institution_id  UUID NOT NULL REFERENCES institutions(id) ON DELETE CASCADE,
    label           VARCHAR(32) NOT NULL,
    start_date      DATE NOT NULL,
    end_date        DATE NOT NULL,
    is_current      BOOLEAN NOT NULL DEFAULT false,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_academic_years_institution_label
        UNIQUE (tenant_id, institution_id, label),
    CONSTRAINT chk_academic_years_dates CHECK (end_date >= start_date)
);

CREATE INDEX idx_academic_years_tenant_institution
    ON academic_years (tenant_id, institution_id);
```

### 3.8 `class_sections`

```sql
CREATE TABLE class_sections (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    institution_id      UUID NOT NULL REFERENCES institutions(id) ON DELETE CASCADE,
    academic_year_id    UUID NOT NULL REFERENCES academic_years(id) ON DELETE CASCADE,
    grade               VARCHAR(32) NOT NULL,
    section             VARCHAR(32) NOT NULL,
    display_name        VARCHAR(128) NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_class_sections UNIQUE (tenant_id, institution_id, academic_year_id, grade, section)
);

CREATE INDEX idx_class_sections_tenant_year
    ON class_sections (tenant_id, academic_year_id);
```

### 3.9 `students`

```sql
CREATE TABLE students (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    institution_id      UUID NOT NULL REFERENCES institutions(id) ON DELETE CASCADE,
    class_section_id    UUID REFERENCES class_sections(id) ON DELETE SET NULL,
    external_ref        VARCHAR(64) NOT NULL,
    first_name          VARCHAR(128) NOT NULL,
    last_name           VARCHAR(128) NOT NULL,
    date_of_birth       DATE,
    status              VARCHAR(32) NOT NULL DEFAULT 'ACTIVE'
                        CHECK (status IN ('ACTIVE', 'TRANSFERRED', 'WITHDRAWN')),
    metadata            JSONB NOT NULL DEFAULT '{}',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_students_external_ref
        UNIQUE (tenant_id, institution_id, external_ref)
);

CREATE INDEX idx_students_tenant_institution ON students (tenant_id, institution_id);
CREATE INDEX idx_students_tenant_section ON students (tenant_id, class_section_id);
CREATE INDEX idx_students_tenant_name ON students (tenant_id, last_name, first_name);
```

### 3.10 `guardians`

```sql
CREATE TABLE guardians (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    institution_id  UUID NOT NULL REFERENCES institutions(id) ON DELETE CASCADE,
    first_name      VARCHAR(128) NOT NULL,
    last_name       VARCHAR(128) NOT NULL,
    email           VARCHAR(320),
    phone           VARCHAR(32),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_guardians_tenant_institution ON guardians (tenant_id, institution_id);
CREATE INDEX idx_guardians_tenant_email ON guardians (tenant_id, email) WHERE email IS NOT NULL;
```

### 3.11 `student_guardians`

```sql
CREATE TABLE student_guardians (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    student_id      UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    guardian_id     UUID NOT NULL REFERENCES guardians(id) ON DELETE CASCADE,
    relationship    VARCHAR(32) NOT NULL DEFAULT 'PARENT'
                    CHECK (relationship IN ('PARENT', 'GUARDIAN', 'OTHER')),
    is_primary      BOOLEAN NOT NULL DEFAULT false,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_student_guardians UNIQUE (tenant_id, student_id, guardian_id)
);

CREATE INDEX idx_student_guardians_student ON student_guardians (tenant_id, student_id);
```

### 3.12 `audit_events`

```sql
CREATE TABLE audit_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
    actor_id        UUID REFERENCES users(id) ON DELETE SET NULL,
    actor_type      VARCHAR(16) NOT NULL DEFAULT 'USER'
                    CHECK (actor_type IN ('USER', 'SYSTEM', 'WORKER')),
    event_type      VARCHAR(128) NOT NULL,
    resource_type   VARCHAR(64) NOT NULL,
    resource_id     UUID NOT NULL,
    correlation_id  UUID,
    payload         JSONB NOT NULL DEFAULT '{}',
    ip_address      INET,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_audit_events_tenant_created ON audit_events (tenant_id, created_at DESC);
CREATE INDEX idx_audit_events_tenant_resource ON audit_events (tenant_id, resource_type, resource_id);
CREATE INDEX idx_audit_events_correlation ON audit_events (correlation_id) WHERE correlation_id IS NOT NULL;
```

> `audit_events` has no `updated_at` — append-only.

### 3.13 Day-1 RLS Template

```sql
ALTER TABLE students ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation_students ON students
    USING (tenant_id = current_setting('app.tenant_id', true)::uuid);
```

Apply equivalent policies to all Day-1 tenant tables except `tenants` itself.

### 3.14 Day-1 Seed Data

- One demo `tenant` (`slug = demo-pilot`)
- One `institution`, current `academic_year`, sample `class_section`
- System `roles` per tenant: `INSTITUTION_ADMIN`, `TEACHER`, `REVIEWER`, `VIEWER`
- Synthetic students only — no real PII

---

## 4. Future Schema (Documented — Not Day 1)

### 4.1 RBAC extension

```sql
-- migration 0002
CREATE TABLE role_permissions (
    role_id         UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    permission_id   UUID NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);
```

### 4.2 Curriculum (`0003`)

| Table | Key columns |
|-------|-------------|
| `curricula` | `tenant_id`, `institution_id`, `code`, `title`, `subject`, `grade_level`, `status`, `version` |
| `curriculum_nodes` | `tenant_id`, `curriculum_id`, `parent_id`, `node_type`, `code`, `title`, `sort_order`, `metadata` |
| `curriculum_prerequisites` | `tenant_id`, `curriculum_id`, `from_node_id`, `to_node_id`, `strength` |

**Indexes:** `(tenant_id, curriculum_id, node_type)`, `(tenant_id, curriculum_id, parent_id)`

### 4.3 Assessment content (`0004`)

| Table | Key columns |
|-------|-------------|
| `assessments` | `tenant_id`, `institution_id`, `code`, `title`, `workflow_state`, `max_total_marks` |
| `assessment_versions` | `tenant_id`, `assessment_id`, `version_number`, `status`, `question_paper_s3_key`, `structure` |
| `questions` | `tenant_id`, `assessment_id`, `parent_question_id`, `label`, `max_marks` |
| `question_versions` | `tenant_id`, `question_id`, `assessment_version_id`, `prompt_text`, `curriculum_node_ids` |
| `answer_keys` | `tenant_id`, `assessment_id`, `title` |
| `answer_key_versions` | `tenant_id`, `answer_key_id`, `version_number`, `status`, `answers` JSONB |
| `rubrics` | `tenant_id`, `assessment_id`, `provenance` |
| `rubric_versions` | `tenant_id`, `rubric_id`, `version_number`, `status`, `approved_by`, `published_at` |
| `rubric_criteria` | `tenant_id`, `rubric_version_id`, `question_id`, `label`, `max_marks`, `scoring_rules` JSONB |

**Unique constraints:**

- `(tenant_id, assessment_id, version_number)` on version tables
- `(tenant_id, assessment_id, label)` on `questions`
- `(tenant_id, rubric_version_id, question_id, label)` on `rubric_criteria`

### 4.4 Submissions (`0005`)

| Table | Key columns |
|-------|-------------|
| `submissions` | `tenant_id`, `assessment_id`, `student_id`, `workflow_state`, `student_match_state`, `source_bundle_s3_key`, `source_content_hash` |
| `submission_pages` | `tenant_id`, `submission_id`, `page_index`, `image_s3_key`, `is_continuation` |
| `answer_regions` | `tenant_id`, `submission_page_id`, `bbox`, `region_type`, `crop_s3_key`, `transcription`, `transcription_confidence` |
| `question_answer_mappings` | `tenant_id`, `submission_id`, `question_id`, `answer_region_ids`, `mapping_state`, `mapping_confidence` |

**Indexes:** `(tenant_id, assessment_id, workflow_state)`, `(tenant_id, submission_id, page_index)`

### 4.5 Evaluation (`0006`)

| Table | Key columns |
|-------|-------------|
| `evaluation_runs` | `tenant_id`, `submission_id`, `run_number`, `status`, `stages_completed` |
| `question_evaluations` | Full ledger projection — see [EVALUATION_LEDGER.md](./EVALUATION_LEDGER.md) |
| `criterion_evaluations` | `tenant_id`, `question_evaluation_id`, `rubric_criterion_id`, `proposed_marks`, `final_marks` |
| `annotations` | `tenant_id`, `submission_id`, `annotation_type`, `geometry`, `payload` |
| `review_actions` | Append-only — `action_type`, `before_snapshot`, `after_snapshot`, `reason` |

**Critical index:** `(tenant_id, submission_id, question_id)` on `question_evaluations`

### 4.6 Publication & learning (`0007`)

| Table | Key columns |
|-------|-------------|
| `published_results` | `tenant_id`, `submission_id`, `total_score`, report S3 keys, `ledger_snapshot_id` |
| `mastery_evidence` | `tenant_id`, `student_id`, `curriculum_node_id`, `question_evaluation_id`, `evidence_type` |
| `mastery_states` | `tenant_id`, `student_id`, `curriculum_node_id`, `concept_mastery`, `execution_accuracy` |
| `learning_recommendations` | `tenant_id`, `student_id`, `curriculum_id`, `target_node_id`, `priority` |
| `improvement_assessments` | `tenant_id`, `student_id`, `blueprint_s3_key` |
| `improvement_assessment_items` | `tenant_id`, `improvement_assessment_id`, `curriculum_node_id` |

### 4.7 AI tracing (`0008`)

```sql
CREATE TABLE ai_execution_records (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id               UUID NOT NULL REFERENCES tenants(id),
    submission_id           UUID,
    evaluation_run_id       UUID,
    operation               VARCHAR(64) NOT NULL,
    provider                VARCHAR(64) NOT NULL,
    model                   VARCHAR(128) NOT NULL,
    model_version           VARCHAR(64),
    prompt_template_version VARCHAR(64),
    input_refs              JSONB NOT NULL DEFAULT '{}',
    input_hash              VARCHAR(64),
    output_summary          JSONB,
    status                  VARCHAR(16) NOT NULL,
    latency_ms              INTEGER,
    token_usage             JSONB,
    error_class             VARCHAR(64),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_ai_exec_tenant_submission ON ai_execution_records (tenant_id, submission_id);
CREATE INDEX idx_ai_exec_tenant_operation ON ai_execution_records (tenant_id, operation, created_at DESC);
```

---

## 5. Cross-Cutting Constraints

### 5.1 Composite tenant FK pattern

When child references parent, enforce same tenant:

```sql
-- Example pattern for submissions → assessments
ALTER TABLE submissions ADD CONSTRAINT fk_submissions_assessment
    FOREIGN KEY (tenant_id, assessment_id)
    REFERENCES assessments (tenant_id, id);
```

Requires unique `(tenant_id, id)` on parent — implicit from PK + tenant_id column.

### 5.2 Numeric types

- Marks/scores: `NUMERIC(8, 2)` — never float.
- Confidence: `NUMERIC(5, 4)` — range 0.0000–1.0000.

### 5.3 Object storage references

Store S3 keys as `VARCHAR(512)`; never blob content in Postgres except small JSONB metadata.

### 5.4 Deletion policy

- **Hard delete prohibited** for submissions, ledger, audit, published results.
- Institution offboarding: soft-archive (`status = ARCHIVED`) + export workflow.

---

## 6. Document Control

| Version | Date | Change |
|---------|------|--------|
| 0.1 | 2026-09-04 | Initial schema contract; Day-1 foundation defined |
