# Workflow States

**Product:** EduVijna Paper Evaluation (CVB v0.1)  
**Last updated:** 2026-09-04  
**Related:** [DOMAIN_MODEL.md](./DOMAIN_MODEL.md), [EVALUATION_LEDGER.md](./EVALUATION_LEDGER.md), [ADR-010](adrs/ADR-010-human-approval-publication.md)

---

## 1. Purpose

State machines govern lifecycle transitions for assessments, submissions, identity matching, question mapping, per-question evaluation, and report publication. Transitions are **explicit**, persisted in Postgres with timestamp and actor — never inferred from UI alone.

---

## 2. Assessment Lifecycle

### 2.1 States

| State | Description |
|-------|-------------|
| `DRAFT` | Assessment created; content editable |
| `RUBRIC_REVIEW` | Answer key / rubric awaiting teacher approval |
| `READY` | Rubric and question paper published; ready to activate |
| `ACTIVE` | Accepting submissions and evaluation |
| `CLOSED` | No new submissions; evaluation may continue |
| `ARCHIVED` | Read-only historical record |

### 2.2 Allowed transitions

```
DRAFT ──publish draft content──▶ RUBRIC_REVIEW
RUBRIC_REVIEW ──teacher approves rubric/key──▶ READY
RUBRIC_REVIEW ──reject / revise──▶ DRAFT
READY ──open for submissions──▶ ACTIVE
ACTIVE ──close intake──▶ CLOSED
CLOSED ──all work complete──▶ ARCHIVED
ACTIVE ──emergency close──▶ CLOSED
DRAFT ──cancel──▶ ARCHIVED
```

| From | To | Trigger | Actor |
|------|-----|---------|-------|
| `DRAFT` | `RUBRIC_REVIEW` | Submit for rubric review | Teacher |
| `RUBRIC_REVIEW` | `READY` | Approve `RubricVersion` + `AnswerKeyVersion` | Teacher / Admin |
| `RUBRIC_REVIEW` | `DRAFT` | Send back for edits | Teacher |
| `READY` | `ACTIVE` | Activate assessment | Admin / Teacher |
| `ACTIVE` | `CLOSED` | Close submission window | Admin / Teacher |
| `CLOSED` | `ARCHIVED` | Archive assessment | Admin |
| `*` | `ARCHIVED` | Admin archive (from DRAFT/CLOSED) | Admin |

**Invariant:** Evaluation runs only when assessment ≥ `READY` and submission intake allowed in `ACTIVE`.

---

## 3. Submission Lifecycle

### 3.1 States

| State | Description |
|-------|-------------|
| `UPLOADED` | Raw bundle stored; job queued |
| `PROCESSING` | Pipeline stages running |
| `IDENTITY_REVIEW` | Student match uncertain |
| `MAPPING_REVIEW` | Question mapping uncertain |
| `READY_FOR_EVALUATION` | Structure complete; eval queued |
| `EVALUATING` | Rubric evaluation in progress |
| `EVALUATION_REVIEW` | Human review of proposed marks |
| `APPROVED` | All questions approved; reports may generate |
| `PUBLISHED` | Results released to authorized viewers |
| `FAILED` | Unrecoverable pipeline failure |

### 3.2 Allowed transitions

```
UPLOADED ──start pipeline──▶ PROCESSING

PROCESSING ──identity low confidence──▶ IDENTITY_REVIEW
PROCESSING ──mapping low confidence──▶ MAPPING_REVIEW
PROCESSING ──success──▶ READY_FOR_EVALUATION
PROCESSING ──fatal error──▶ FAILED

IDENTITY_REVIEW ──confirmed──▶ PROCESSING | READY_FOR_EVALUATION
MAPPING_REVIEW ──confirmed──▶ READY_FOR_EVALUATION

READY_FOR_EVALUATION ──start eval──▶ EVALUATING

EVALUATING ──drafts complete──▶ EVALUATION_REVIEW
EVALUATING ──error──▶ FAILED

EVALUATION_REVIEW ──all accepted/overridden──▶ APPROVED
EVALUATION_REVIEW ──reprocess request──▶ PROCESSING | EVALUATING

APPROVED ──publish──▶ PUBLISHED

FAILED ──manual retry──▶ UPLOADED | PROCESSING
```

| From | To | Trigger |
|------|-----|---------|
| `UPLOADED` | `PROCESSING` | Celery job start |
| `PROCESSING` | `IDENTITY_REVIEW` | `identity_confidence` < threshold |
| `PROCESSING` | `MAPPING_REVIEW` | `mapping_confidence` < threshold |
| `PROCESSING` | `READY_FOR_EVALUATION` | Structure stages pass |
| `IDENTITY_REVIEW` | `PROCESSING` | Identity confirmed; resume pipeline |
| `MAPPING_REVIEW` | `READY_FOR_EVALUATION` | Mapping confirmed |
| `READY_FOR_EVALUATION` | `EVALUATING` | Evaluation job start |
| `EVALUATING` | `EVALUATION_REVIEW` | Ledger drafts written |
| `EVALUATION_REVIEW` | `APPROVED` | All questions ACCEPTED/OVERRIDDEN |
| `EVALUATION_REVIEW` | `EVALUATING` | Targeted re-eval |
| `APPROVED` | `PUBLISHED` | Publication action |
| `*` | `FAILED` | Unrecoverable error |

**Note:** `IDENTITY_REVIEW` and `MAPPING_REVIEW` may be visited sequentially.

---

## 4. Student Match Lifecycle

Field: `Submission.student_match_state`

### 4.1 States

| State | Description |
|-------|-------------|
| `UNMATCHED` | No roster candidate |
| `REVIEW_REQUIRED` | Candidates exist but confidence insufficient |
| `AUTO_MATCHED` | High-confidence match (still confirmable) |
| `CONFIRMED` | Human or policy-confirmed match |

### 4.2 Allowed transitions

```
UNMATCHED ──AI extract + no match──▶ UNMATCHED (stay)
UNMATCHED ──candidates low conf──▶ REVIEW_REQUIRED
UNMATCHED ──high confidence match──▶ AUTO_MATCHED

REVIEW_REQUIRED ──human selects student──▶ CONFIRMED
REVIEW_REQUIRED ──reject / no match──▶ UNMATCHED

AUTO_MATCHED ──human confirms──▶ CONFIRMED
AUTO_MATCHED ──human rejects──▶ REVIEW_REQUIRED

CONFIRMED ──override identity──▶ REVIEW_REQUIRED (via ReviewAction)
```

**Rule:** Never silent auto-assign to `CONFIRMED` without tenant policy explicitly allowing high-threshold auto-confirm (CVB default: human confirm required).

---

## 5. Question Mapping Lifecycle

Entity: `QuestionAnswerMapping.mapping_state`

### 5.1 States

| State | Description |
|-------|-------------|
| `PROPOSED` | AI proposed region ↔ question link |
| `REVIEW_REQUIRED` | Low confidence or conflict |
| `CONFIRMED` | Approved for evaluation |

### 5.2 Allowed transitions

```
PROPOSED ──confidence OK + policy──▶ CONFIRMED
PROPOSED ──low confidence──▶ REVIEW_REQUIRED

REVIEW_REQUIRED ──human confirms──▶ CONFIRMED
REVIEW_REQUIRED ──human remaps──▶ CONFIRMED

CONFIRMED ──correction──▶ REVIEW_REQUIRED (via ReviewAction)
```

**Gate:** Submission cannot enter `EVALUATING` until all mapped questions are `CONFIRMED` or explicitly marked N/A (blank).

---

## 6. Question Evaluation Lifecycle

Field: `QuestionEvaluation.workflow_state` (ledger)

### 6.1 States

| State | Description |
|-------|-------------|
| `PENDING` | Awaiting evaluation job |
| `PROPOSED` | AI proposal written |
| `REVIEW_REQUIRED` | Mandatory human review |
| `ACCEPTED` | Reviewer accepted proposal |
| `OVERRIDDEN` | Reviewer changed marks |
| `ESCALATED` | Sent to senior reviewer / admin |

### 6.2 Allowed transitions

```
PENDING ──eval complete──▶ PROPOSED
PENDING ──eval incomplete──▶ REVIEW_REQUIRED

PROPOSED ──confidence/policy OK──▶ ACCEPTED (bulk allow with audit)
PROPOSED ──low confidence──▶ REVIEW_REQUIRED

REVIEW_REQUIRED ──accept──▶ ACCEPTED
REVIEW_REQUIRED ──override──▶ OVERRIDDEN
REVIEW_REQUIRED ──escalate──▶ ESCALATED

ESCALATED ──resolve──▶ ACCEPTED | OVERRIDDEN

ACCEPTED ──late override──▶ OVERRIDDEN (before publication only)
OVERRIDDEN ──further override──▶ OVERRIDDEN (new ReviewAction, ledger_version++)
```

**Publication gate:** Submission `APPROVED` requires every scored question ∈ {`ACCEPTED`, `OVERRIDDEN`}.

---

## 7. Report Lifecycle

Logical state for generated outputs (may live on `PublishedResult` or job metadata).

### 7.1 States

| State | Description |
|-------|-------------|
| `NOT_READY` | Submission not approved |
| `READY` | Approved; generation queued |
| `GENERATED` | Reports and annotated PDF produced |
| `PUBLISHED` | Released to student/parent endpoints |

### 7.2 Allowed transitions

```
NOT_READY ──submission APPROVED──▶ READY
READY ──generate job success──▶ GENERATED
GENERATED ──release──▶ PUBLISHED

GENERATED ──regenerate──▶ READY (same approved ledger snapshot)
```

**Invariant:** `generate_*` AI operations run only when report state ≥ `READY` (submission `APPROVED`).

---

## 8. Cross-Machine Dependencies

```mermaid
stateDiagram-v2
    direction LR
    state Assessment {
        DRAFT --> RUBRIC_REVIEW --> READY --> ACTIVE
    }
    state Submission {
        UPLOADED --> PROCESSING --> EVALUATION_REVIEW --> APPROVED --> PUBLISHED
    }
    ACTIVE --> UPLOADED: upload allowed
    APPROVED --> GENERATED: reports
```

---

## 9. Audit Requirements

Every transition records:

- `from_state`, `to_state`
- `actor_id` (user or system)
- `timestamp`
- `correlation_id`
- Optional `reason` (required for overrides and failures)

Persist via `AuditEvent` + entity `workflow_state` update in single transaction.

---

## 10. Document Control

| Version | Date | Change |
|---------|------|--------|
| 0.1 | 2026-09-04 | Initial workflow state specification |
