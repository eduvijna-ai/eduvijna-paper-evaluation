# Rubric Schema Specification

**Product:** EduVijna Paper Evaluation (CVB v0.1)  
**Status:** Architecture contract (ADR-008)  
**Last updated:** 2026-09-04  
**Related:** [DOMAIN_MODEL.md](./DOMAIN_MODEL.md), [EVALUATION_LEDGER.md](./EVALUATION_LEDGER.md)

---

## 1. Purpose

Rubrics define **how marks are awarded** for each question. `RubricCriterion` is the atomic scoring unit. Rubrics are **versioned and immutable after publish**; evaluation binds to a specific `RubricVersion`.

**Hierarchy:**

```
Rubric (logical)
 └── RubricVersion (immutable snapshot)
      └── RubricCriterion[] (per question / sub-part)
```

---

## 2. Rubric & Version Entities

### 2.1 Rubric

| Field | Description |
|-------|-------------|
| `assessment_id` | Parent assessment |
| `title` | e.g. "Midterm Mathematics — Marking Scheme" |
| `provenance` | `TEACHER`, `AI_PROPOSED`, `IMPORTED` |

### 2.2 RubricVersion lifecycle

| State | Meaning |
|-------|---------|
| `DRAFT` | Editable; not usable for evaluation |
| `PENDING_TEACHER_REVIEW` | AI-proposed; awaiting teacher |
| `APPROVED` | Teacher signed off; not yet frozen |
| `PUBLISHED` | Immutable; bound to evaluations |
| `SUPERSEDED` | Replaced by newer version |

**Rule:** Batch evaluation requires `PUBLISHED` version with teacher approval recorded.

---

## 3. RubricCriterion Schema

Each criterion row (or JSONB element) supports the following fields.

### 3.1 Core identity

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | UUID | Yes | Criterion PK |
| `rubric_version_id` | UUID | Yes | Parent version |
| `question_id` | UUID | Yes | Target question |
| `label` | string | Yes | e.g. `M1`, `Step 2 — simplification` |
| `sort_order` | integer | Yes | Display/evaluation order |
| `description` | text | No | Teacher-facing criterion text |

### 3.2 Marks & scoring mode

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `max_marks` | decimal | Yes | Maximum awardable for this criterion |
| `scoring_mode` | enum | Yes | See §4 |
| `partial_marks_allowed` | boolean | Yes | Enable fractional awards |
| `partial_mark_schedule` | JSONB | No | Explicit partial tiers, e.g. `[{"condition":"method correct, arithmetic error","marks":1}]` |
| `min_award` | decimal | No | Floor when partial (default 0) |

### 3.3 Scoring modes (`scoring_mode`)

| Mode | Behavior |
|------|----------|
| `PARTIAL` | Award 0..max_marks continuously or via schedule |
| `ALL_OR_NOTHING` | Full `max_marks` or zero |
| `ADDITIVE` | Marks add toward question total from independent checks |
| `DEDUCTIVE` | Start from max; deduct per error (common for presentation/final answer) |

**Combined example:** Question total = sum of `ADDITIVE` method marks minus `DEDUCTIVE` presentation penalties (bounded at 0).

### 3.4 Dependencies

| Field | Type | Description |
|-------|------|-------------|
| `depends_on_criterion_ids` | UUID[] | Criteria that must be evaluated first |
| `dependency_policy` | enum | `BLOCK_IF_PARENT_ZERO` — skip dependent if parent fails; `EVALUATE_ANYWAY` — still attempt |
| `required_for_full_credit` | boolean | If true, failure caps question score |

**Evaluator rule:** Topological sort criteria by dependency graph before scoring.

### 3.5 Alternative methods

| Field | Type | Description |
|-------|------|-------------|
| `alternative_methods` | JSONB[] | Each: `{ "id", "label", "description", "criteria_override_ids?", "max_marks?" }` |
| `default_method_id` | string | Model solution path |
| `accept_any_valid_method` | boolean | If true, AI may classify method then apply matching branch |

Ledger stores `alternative_method_id` when a non-default path is accepted ([EVALUATION_LEDGER.md](./EVALUATION_LEDGER.md)).

### 3.6 Error carried forward (ECF)

| Field | Type | Description |
|-------|------|-------------|
| `ecf_enabled` | boolean | Whether ECF applies to this criterion |
| `ecf_policy` | enum | `FOLLOW_THROUGH`, `CAP_AT_ZERO`, `STOP_CHAIN` |
| `ecf_origin_allowed` | boolean | Can this criterion be the first error source |
| `ecf_max_follow_on` | decimal | Max marks awardable downstream after ECF |

**Graph:** `ecf_graph` JSONB on `RubricVersion` defines propagation edges between criteria across questions for multi-part items.

### 3.7 Units & precision

| Field | Type | Description |
|-------|------|-------------|
| `unit_required` | boolean | Answer must include unit |
| `expected_unit` | string | e.g. `m/s²` |
| `unit_marks` | decimal | Separate marks for correct unit (may be 0 = gate only) |
| `unit_separate_criterion` | boolean | Split unit into child criterion |
| `precision_rule` | JSONB | `{ "type": "SIG_FIGS"|"DECIMAL_PLACES", "value": 3, "rounding": "HALF_UP" }` |
| `numeric_tolerance` | JSONB | `{ "absolute": 0.01, "relative": 0.001 }` |

Deterministic checks run in rules engine; ambiguous cases defer to `evaluate_rubric` AI with `evaluation_confidence`.

### 3.8 Reasoning & expression

| Field | Type | Description |
|-------|------|-------------|
| `required_reasoning` | boolean | Must show working |
| `reasoning_min_steps` | integer | Minimum visible steps |
| `accepted_equivalent_expressions` | string[] | LaTeX/SymPy-normalized equivalents |
| `symbolic_verify_enabled` | boolean | Run SymPy verify against equivalents |

### 3.9 Pedagogical metadata

| Field | Type | Description |
|-------|------|-------------|
| `explanation` | text | Student-facing rubric explanation (post-approval) |
| `teacher_comment` | text | Internal marking notes |
| `error_hints` | JSONB | Map error taxonomy codes to feedback snippets |
| `curriculum_node_ids` | UUID[] | Linked concepts/skills |

### 3.10 Versioning metadata

| Field | Type | Description |
|-------|------|-------------|
| `criterion_version` | integer | Increment within rubric version (for diff) |
| `supersedes_criterion_id` | UUID | Lineage from prior rubric version |

---

## 4. Example Criterion (JSON)

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "question_id": "...",
  "label": "M2 — Quadratic formula application",
  "max_marks": 3,
  "scoring_mode": "PARTIAL",
  "partial_marks_allowed": true,
  "partial_mark_schedule": [
    { "condition": "Correct formula, wrong arithmetic", "marks": 2 },
    { "condition": "Correct setup only", "marks": 1 }
  ],
  "depends_on_criterion_ids": ["..."],
  "dependency_policy": "BLOCK_IF_PARENT_ZERO",
  "alternative_methods": [
    { "id": "factoring", "label": "Factorisation method", "max_marks": 3 }
  ],
  "ecf_enabled": true,
  "ecf_policy": "FOLLOW_THROUGH",
  "unit_required": false,
  "precision_rule": { "type": "DECIMAL_PLACES", "value": 2, "rounding": "HALF_UP" },
  "required_reasoning": true,
  "accepted_equivalent_expressions": ["x = (-b ± sqrt(b^2-4ac))/(2a)"],
  "explanation": "Apply the quadratic formula correctly and simplify.",
  "teacher_comment": "Allow ECF from wrong discriminant if formula applied correctly."
}
```

---

## 5. Evaluation Algorithm (Summary)

1. Load frozen `RubricVersion` + `AnswerKeyVersion`.
2. Sort criteria by `sort_order` and dependency graph.
3. For each criterion:
   - If `UNREADABLE` transcription → decision `UNREADABLE`, route to review (not auto-zero).
   - Run deterministic checks: units, precision, numeric tolerance, AON gates.
   - If ambiguous → `evaluate_rubric` AI proposes marks with `evaluation_confidence`.
   - Apply ECF propagation per `ecf_policy`.
4. Sum criterion `final_marks` (post-review) to question score; write ledger.

---

## 6. AI-Proposed Rubrics

When `provenance = AI_PROPOSED`:

- Enter `PENDING_TEACHER_REVIEW`.
- UI diff: teacher edits marks, toggles AON/ECF, adds alternatives.
- `ReviewAction` or dedicated approval record required before `PUBLISHED`.

---

## 7. Validation Rules

| Rule | Enforcement |
|------|-------------|
| Sum of question criteria ≤ question `max_marks` | Schema validation on publish |
| Published version immutable | DB trigger / application guard |
| At least one criterion per scored question | Publish blocker |
| `ALL_OR_NOTHING` ⇒ `partial_marks_allowed = false` | Schema constraint |

---

## 8. Document Control

| Version | Date | Change |
|---------|------|--------|
| 0.1 | 2026-09-04 | Initial rubric schema specification |
