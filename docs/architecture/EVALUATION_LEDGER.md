# Evaluation Ledger Specification

**Product:** EduVijna Paper Evaluation (CVB v0.1)  
**Status:** Canonical source of truth for scores (ADR-006)  
**Last updated:** 2026-09-06  
**Related:** [DOMAIN_MODEL.md](./DOMAIN_MODEL.md), [RUBRIC_SCHEMA.md](./RUBRIC_SCHEMA.md), [ERROR_TAXONOMY.md](./ERROR_TAXONOMY.md), [WORKFLOW_STATES.md](./WORKFLOW_STATES.md)

---

## 1. Purpose

The **evaluation ledger** is the authoritative, queryable record of every proposed and final mark at **question grain**. Published scores, reports, analytics, and learning evidence are **projections** of approved ledger rows — never unconstrained LLM output over raw PDFs.

**Grain:** One primary ledger row per `(tenant_id, submission_id, question_id)` per active evaluation run. Criterion-level detail lives in child `criterion_evaluations` rows or embedded JSONB arrays with identical semantics.

---

## 2. Invariants

1. No published score without an approved ledger row and corresponding `ReviewAction`.
2. Every ledger row references immutable `assessment_version_id`, `question_version_id`, `rubric_version_id`, and `answer_key_version_id`.
3. Approved rows are **never deleted or silently overwritten**; corrections append `OVERRIDE` review actions and new ledger versions.
4. **Separate confidence dimensions** — never a single generic "AI confidence" field (ADR-006).
5. `UNREADABLE` transcription does not imply incorrect work — it triggers review, not automatic zero marks. `proposed_ai_score` and criterion `proposed_marks` remain **null** until a human override supplies a score.

---

## 3. Canonical Ledger Fields

### 3.1 Identity & scope

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | UUID | Yes | Ledger row PK |
| `tenant_id` | UUID | Yes | Tenant partition |
| `evaluation_run_id` | UUID | Yes | Pipeline run that produced this row |
| `submission_id` | UUID | Yes | Student paper bundle |
| `student_id` | UUID | Yes* | Resolved student; nullable only during identity review |
| `assessment_id` | UUID | Yes | Logical assessment |
| `assessment_version_id` | UUID | Yes | Frozen question paper version |
| `question_id` | UUID | Yes | Logical question |
| `question_version_id` | UUID | Yes | Frozen question content |
| `rubric_version_id` | UUID | Yes | Rubric version used at evaluation time |
| `answer_key_version_id` | UUID | Yes | Answer key version used at evaluation time |

### 3.2 Evidence references

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `answer_region_ids` | UUID[] | Yes | Linked `AnswerRegion` rows |
| `evidence_refs` | JSONB | Yes | Structured evidence: `{ "crops": ["s3://..."], "pages": [0,1], "bboxes": [...] }` |
| `transcribed_answer` | text | No | Latest transcription (LaTeX/plain) |
| `transcription_segments` | JSONB | No | Step-indexed transcription for divergence analysis |
| `source_page_indices` | integer[] | No | Denormalized page refs |

### 3.3 Scoring

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `max_mark` | decimal | Yes | Question maximum from rubric |
| `criterion_decisions` | JSONB | Yes | Array of per-criterion decisions (see §4) |
| `proposed_ai_score` | decimal \| null | Yes | Sum of AI-proposed criterion marks; **null when unreadable / no proposal** (never coerce to 0) |
| `final_human_approved_score` | decimal | No | Set on ACCEPT/OVERRIDE; null while pending |
| `deduction_reasons` | JSONB | No | Structured list: `{ "criterion_id", "reason", "error_code", "marks_deducted" }` |
| `error_codes` | string[] | No | Top-level taxonomy codes — see [ERROR_TAXONOMY.md](./ERROR_TAXONOMY.md) |
| `first_divergence_step` | integer | No | 0-based step index where work first deviates from model solution |
| `ecf_applied` | boolean | Yes | Error-carried-forward policy applied |
| `ecf_chain` | JSONB | No | `{ "origin_criterion_id", "affected_criterion_ids", "policy" }` |
| `alternative_method_id` | string | No | Identifier of accepted alternative solution path |
| `alternative_method_label` | string | No | Human-readable method name |

### 3.4 Curriculum linkage

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `curriculum_concept_ids` | UUID[] | No | Mapped `CurriculumNode` IDs (concept/skill/LO) |
| `mastery_evidence_ids` | UUID[] | No | B8: materialised after **PUBLISHED** (not merely APPROVED); no MasteryState in B8 |

### 3.5 Confidence dimensions (SEPARATE — mandatory)

| Field | Type | Range | Description |
|-------|------|-------|-------------|
| `identity_confidence` | decimal | 0–1 | Student/roll match confidence |
| `mapping_confidence` | decimal | 0–1 | Region ↔ question alignment |
| `transcription_confidence` | decimal | 0–1 | OCR/handwriting read quality |
| `evaluation_confidence` | decimal | 0–1 | Rubric application certainty |
| `math_verification_confidence` | decimal | 0–1 | Optional; SymPy/numeric verify result |

**Prohibited:** `ai_confidence`, `overall_confidence`, or any collapsed aggregate used for routing or UI display as a single score.

**Routing rule:** Review required if **any** dimension < tenant threshold OR any dimension is null with blocking `error_codes` containing review-class codes.

### 3.6 AI provenance

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `ai_execution_record_ids` | UUID[] | Yes | Links to `AiExecutionRecord` rows per stage |
| `model_provider` | string | Yes | e.g. `openai`, `anthropic` |
| `model_name` | string | Yes | e.g. `gpt-4o` |
| `model_version` | string | No | Provider version string |
| `prompt_template_version` | string | Yes | Internal template semver |
| `rules_engine_version` | string | No | Deterministic evaluator version |

### 3.7 Human review

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `workflow_state` | enum | Yes | See [WORKFLOW_STATES.md](./WORKFLOW_STATES.md) — question evaluation states |
| `reviewer_id` | UUID | No | User who approved/overrode |
| `review_action_id` | UUID | No | FK → `review_actions.id` |
| `review_action_type` | enum | No | `ACCEPT`, `OVERRIDE`, `ESCALATED` |
| `reviewed_at` | timestamptz | No | Approval timestamp |
| `review_notes` | text | No | Optional reviewer comment |

### 3.8 Audit & immutability

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `ledger_version` | integer | Yes | Incremented on each override |
| `supersedes_ledger_id` | UUID | No | Previous row this replaces |
| `audit_event_ids` | UUID[] | Yes | Immutable audit refs for create/approve/override |
| `created_at` | timestamptz | Yes | Row creation |
| `updated_at` | timestamptz | Yes | Last metadata touch (not score after approval) |
| `approved_snapshot_hash` | string | No | SHA-256 of canonical JSON at approval |

---

## 4. Criterion Decisions Structure

Each element in `criterion_decisions`:

```json
{
  "rubric_criterion_id": "uuid",
  "criterion_label": "Set up equation",
  "max_marks": 2.0,
  "scoring_mode": "PARTIAL",
  "proposed_marks": 1.0,
  "final_marks": 1.0,
  "decision": "PARTIAL",
  "error_code": "SUBSTITUTION",
  "deduction_reason": "Incorrect substitution in step 2",
  "step_index": 2,
  "ecf_source_criterion_id": null,
  "unit_check_passed": true,
  "precision_check_passed": false,
  "accepted_alternative_id": null,
  "ai_execution_record_id": "uuid"
}
```

**Decision values:** `AWARDED`, `PARTIAL`, `DEDUCTED`, `NOT_APPLICABLE`, `UNREADABLE`

---

## 5. Lifecycle

```
[Pipeline creates row]
    workflow_state = PENDING | PROPOSED | REVIEW_REQUIRED
    proposed_ai_score populated **or null** (unreadable / provider unavailable / review-only)
    final_human_approved_score = null

[Low confidence or review policy]
    workflow_state = REVIEW_REQUIRED

[Reviewer ACCEPT] (requires non-null proposed_ai_score)
    final_human_approved_score = proposed_ai_score (or confirmed)
    workflow_state = ACCEPTED
    review_action recorded

[Reviewer OVERRIDE]
    final_human_approved_score = reviewer value
    criterion_decisions.final_marks updated
    workflow_state = OVERRIDDEN
    original AI proposal preserved in before_snapshot

[Reviewer ESCALATE]
    workflow_state = ESCALATED
    review_action recorded

[Publication gate]
    All questions ACCEPTED | OVERRIDDEN
    Submission transitions to APPROVED (B6); PUBLISHED / reports later
    Ledger rows become read-only
```

Re-evaluation creates a **new** `evaluation_run_id` and new ledger rows; prior approved rows retained for audit.

---

## 6. Storage Mapping

| Logical ledger | Physical tables |
|----------------|-----------------|
| Question-level aggregate | `question_evaluations` |
| Criterion detail | `criterion_evaluations` + `criterion_decisions` JSONB denormalized for export |
| Evidence | `answer_regions`, `question_answer_mappings` |
| AI trace | `ai_execution_records` |
| Human decisions | `review_actions`, `audit_events` |

Export/API serializers produce a single **LedgerEntry** DTO merging these sources with stable field names from §3.

---

## 7. Query Patterns

| Use case | Query |
|----------|-------|
| Submission review queue | `WHERE tenant_id = ? AND workflow_state IN ('PROPOSED','REVIEW_REQUIRED')` |
| Low mapping confidence | `WHERE mapping_confidence < ? ORDER BY mapping_confidence ASC` |
| Published class results | Join `published_results` WHERE all question rows `ACCEPTED|OVERRIDDEN` |
| Audit trail | `review_actions` + `audit_event_ids` on ledger row |
| Model regression | Join `ai_execution_records` on `ai_execution_record_ids` |

---

## 8. Anti-Patterns (Forbidden)

- Storing final marks only in generated PDF without ledger rows.
- Updating `final_human_approved_score` without `ReviewAction`.
- Computing published totals from LLM re-read of submission images.
- Exposing `(identity + mapping + transcription + evaluation) / 4` as "confidence".

---

## 9. Document Control

| Version | Date | Change |
|---------|------|--------|
| 0.1 | 2026-09-04 | Initial ledger specification |
