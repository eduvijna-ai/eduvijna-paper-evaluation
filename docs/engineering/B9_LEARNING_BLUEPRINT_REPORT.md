# B9 — Live curriculum learning and improvement blueprint

**Branch:** `b9/live-curriculum-learning-blueprint`  
**PR base:** `develop` (never `main`)  
**Starting `develop` SHA:** `b960ca1af24f5b7c137cf5724e9126c25a553815`  
**Starting `main` SHA:** `be5f10aef3cf536420adcffdb9302b6b3b6c0955`  
**Migration:** `database/migrations/versions/20260907_0010_learning_recommendations_blueprint.py`  
**Final feature SHA:** `484155350af5942410a0308b9f9889d3b79aa8bd`  
**CI run ID:** `34107860817`  
**Squash SHA:** `9f4f8f9fb3ece34fad08dd824e4052f47598c53d`  
**Final develop:** `9f4f8f9fb3ece34fad08dd824e4052f47598c53d`  
**Final main:** `be5f10aef3cf536420adcffdb9302b6b3b6c0955` (must remain unchanged)

```text
CI: Infrastructure / Contracts / Backend / Frontend /
Frontend E2E / Frontend E2E Real = SUCCESS

Feature branch: deleted
Post-merge develop commit: none
Do not push a post-merge docs commit to develop.
```

## Scope (implemented)

* **PEV-039** Adaptive learning recommendations (curriculum-constrained)  
* **PEV-040** Prerequisite-aware learning path  
* **PEV-042** Improvement-assessment **blueprint** + teacher approve/reject  

**Not complete (deferred):**

| Ticket | Topic |
|--------|--------|
| PEV-035 / 036 / 037 / 038 | Longitudinal mastery / MasteryState (and related) |
| PEV-041 | Resource assignment |
| PEV-043 | Actual reassessment creation (Assessment / Question entities) |
| PEV-048 | Psychometrics |

## Persistence

Migration `20260907_0010` creates:

| Table | Role |
|-------|------|
| `learning_plan_runs` | Versioned plan generation job (status, hashes, algorithm) |
| `learning_recommendations` | Curriculum-node remediation rows for a run |
| `learning_recommendation_prerequisites` | Ordered REQUIRED/RECOMMENDED edges per recommendation |
| `learning_recommendation_evidence` | Links to B8 `mastery_evidence` rows |
| `learning_path_steps` | Ordered path (PREREQUISITE / LEARN / GUIDED / INDEPENDENT / MASTERY_CHECK) |
| `improvement_assessments` | Blueprint header + approval metadata + artifact refs |
| `improvement_assessment_items` | Template-bound blueprint items (no Assessment entities) |

Also: `ai_execution_records.learning_plan_run_id`, `ai_execution_records.improvement_assessment_id`.

**Explicitly not created / not reused:**

* No `mastery_states` table (MasteryState remains AFTER_CLIENT_APPROVAL)  
* No `PipelineJob` stage for learning (B9 uses dedicated run/blueprint rows + `celery_task_id`)  
* No reassessment / Assessment / Question creation on approve  

## Permissions

| Code | Used by |
|------|---------|
| `learning:read` | Workspace, plan-run GET, blueprint GET |
| `learning:generate` | Prepare plan, prepare blueprint |
| `learning:review` | Reject blueprint |
| `learning:approve` | Approve blueprint |

Role map: `INSTITUTION_ADMIN` / `TEACHER` get all four; `EVALUATOR` gets `learning:read` only.

## B8 evidence dependency & readiness gate

**Source of truth for gaps:** immutable `MasteryEvidence` (`algorithm_version = B8_V1`) from **PUBLISHED** results only.

Before prepare/generate:

1. Student must be tenant-scoped  
2. Selected curriculum must exist in-tenant (never mix curricula)  
3. B8 materialization for the student must be **`READY`**  
4. Otherwise → `409 LEARNING_EVIDENCE_NOT_READY` (no silent partial plan)

Curriculum selection:

* Workspace exposes `available_curricula` + `selected_curriculum_id`  
* Prepare requires explicit `curriculum_id`  
* Auto-select only when exactly one evidenced curriculum exists  

## B9_V1 recommendation algorithm

Server-authoritative module: `apps/api/app/services/learning_algorithm.py` (`ALGORITHM_VERSION = B9_V1`).

### Candidate targets

A node is a direct remediation target only when at least one aggregate dimension is **WEAK** (CONCEPT / EXECUTION / PROCEDURE from B8 evidence).  
No recommendation from INCONCLUSIVE-only, no evidence, BLANK-only, or UNREADABLE-only. AI cannot override.

### Priority policy (direct targets)

| Condition | Kind | Priority |
|-----------|------|----------|
| concept = WEAK | `TARGET_CONCEPT` | 1 |
| else procedure = WEAK | `PROCEDURE_PRACTICE` | 2 |
| else execution = WEAK and concept ≠ WEAK | `EXECUTION_PRACTICE` | 3 |

**Concept vs execution gate:**  
`concept=STRONG`, `execution=WEAK` → `EXECUTION_PRACTICE` (not “relearn the concept”).

### Prerequisite traversal

* REQUIRED: transitive, dependency-first order; WEAK → `PREREQUISITE_REPAIR` (priority 1) + path `PREREQUISITE`; STRONG → omit; INCONCLUSIVE / no evidence → path `MASTERY_CHECK` (no repair recommendation)  
* RECOMMENDED: WEAK support only; does not block target; priority 2 repair; path after required, before target  
* REQUIRED cycles → `CURRICULUM_PREREQUISITE_CYCLE`  
* Edges referencing nodes outside curriculum → `CURRICULUM_PREREQUISITE_INVALID`  

Path step kinds for targets: LEARN / GUIDED / INDEPENDENT mapped from recommendation kind.

### Hashes & versioning

Persisted on each `LearningPlanRun` / blueprint:

* `source_evidence_hash` — canonical hash of sorted B8 facts  
* `curriculum_graph_hash` — nodes + prerequisite edges  
* `input_hash` — `{algorithm_version, source_evidence_hash, curriculum_graph_hash}`  

Uniques:

* `(tenant, student, curriculum, version_number)`  
* `(tenant, student, curriculum, input_hash, algorithm_version)` — idempotent retry  

Statuses: `QUEUED` → `RUNNING` → `READY` | `FAILED`; prior READY may become `SUPERSEDED`.

**Staleness:** GET compares current `input_hash` to persisted; `is_stale=true` when evidence or graph changed.  
**No-gap:** READY with empty recommendations + `no_gap_message` when no WEAK targets.

## Provider abstraction

Typed `LearningAIProvider` (`generate_learning_plan`, `generate_improvement_blueprint`).  
**Structure is server-owned**; providers return bounded prose only (rationale / focus / title).

| `AI_PROVIDER_TEXT` | Behavior |
|--------------------|----------|
| `fixed` | Deterministic FixedLearningProvider (non-prod) → `FIXED` |
| `openai` | OpenAI adapter → `AI` |
| `none` / empty | No provider → `RULES_FALLBACK` (default structure prose) |

URL guardrail: any `http://`, `https://`, or `www.` in provider text → `LEARNING_PROVIDER_URL_REJECTED`.  
Curriculum-only validator: target/item nodes must belong to selected curriculum.

Tracing: `AiExecutionRecord` with `learning_plan_run_id` and/or `improvement_assessment_id`.

## Workers

| Celery task | Pipeline |
|-------------|----------|
| `learning.generate_plan` | `run_learning_plan_pipeline` |
| `learning.generate_improvement_blueprint` | `run_blueprint_pipeline` |

Enqueue after prepare commit; broker failure does not roll back the QUEUED/DRAFT row (`enqueue_error` surfaced on prepare response).

## APIs

| Method | Path | Permission |
|--------|------|------------|
| GET | `/api/v1/learning/students/{student_id}` | `learning:read` |
| POST | `/api/v1/learning/students/{student_id}/prepare` | `learning:generate` |
| GET | `/api/v1/learning/plan-runs/{run_id}` | `learning:read` |
| POST | `/api/v1/learning/plan-runs/{run_id}/improvement-blueprints/prepare` | `learning:generate` |
| GET | `/api/v1/improvement-assessments/{id}` | `learning:read` |
| POST | `/api/v1/improvement-assessments/{id}/approve` | `learning:approve` |
| POST | `/api/v1/improvement-assessments/{id}/reject` | `learning:review` |

## Improvement blueprint (PEV-042)

* Generated only from a **READY** learning plan with actionable recommendations  
* Status: `DRAFT` → `GENERATING` → `PENDING_APPROVAL` → `APPROVED` | `REJECTED` | `FAILED`  
* Items: `CONCEPT_CHECK` / `PREREQUISITE_CHECK` / `PROCEDURE_PRACTICE` / `EXECUTION_PRACTICE` / `TRANSFER_CHECK`; `question_template_ref` pattern `CVB:…:vN`  
* `suggested_marks` are advisory only (not ledger scores)  
* Artifact (write-once export):

```text
{tenant}/exports/students/{student}/learning/{curriculum}/blueprints/{version}/blueprint.json
```

Persisted: `blueprint_storage_key`, `blueprint_sha256`, `blueprint_byte_size`.

**Approve:** re-checks plan READY, input hash freshness, artifact hash/size, foreign-node guard — then marks APPROVED.  
**Does not** create Assessment, Question, Submission, or PipelineJob reassessment artifacts.  
**Reject:** requires reason; `learning:review`.

Contracts:

* `packages/contracts/schemas/learning-plan.schema.json`  
* `packages/contracts/schemas/improvement-assessment-blueprint.schema.json`  

## Frontend capability

```
analytics = live
learning = live
```

* Hybrid: `LearningHttpApi` via live capability; **no silent live→mock fallback**  
* Pages: `/learning/[studentId]`, `/learning/[studentId]/improvement-assessment`  
* Live UUID mock adaptive learning is refused when `learning === "live"`  

## Test counts

| Suite | Count |
|-------|-------|
| Backend pytest | 128 (local; confirm on CI) |
| Frontend Vitest | 147 |
| Mock Playwright | 15 |
| Real Playwright | 10 (includes `zz-b9-learning`) |

## Residual debt

* PEV-035/036/037/038 — longitudinal MasteryState  
* PEV-041 — resource / URL assignment (still forbidden in CVB outputs)  
* PEV-043 — instantiate approved blueprint as a real reassessment  
* PEV-048 — psychometrics  
* Class-section cohort filters (carry-over from B8 analytics)  

## Verification

| Check | Status |
|-------|--------|
| Backend pytest | 128 passed (local) |
| Frontend Vitest | 147 passed |
| Mock Playwright | 15 (CI) |
| Real Playwright | 10 including B9 (CI) |
| Contracts validate | 13 schemas + openapi |
| Ruff / mypy --strict | passed |
| docker compose config | passed |
| GitHub Actions (six jobs) | `_TBD_` |
| Squash-merge to develop | `_TBD_` |
| `main` unchanged | required `be5f10aef3cf536420adcffdb9302b6b3b6c0955` |
| Issue #1 | remains OPEN |
