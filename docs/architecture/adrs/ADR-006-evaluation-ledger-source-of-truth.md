# ADR-006: Evaluation Ledger as Source of Truth for Scores

## Status: Accepted

## Date: 2026-09-04

## Context

EduVijna's product promise is defensible, explainable grading — not a black-box PDF summary. Stakeholders (teachers, students, parents, auditors) must answer: "For question 7, what mark was awarded, against which rubric criterion, with what evidence, and at what confidence?" A single LLM pass over an entire answer sheet cannot be the authoritative record; it is non-deterministic, hard to diff, and impossible to partially override.

The pipeline (per README) flows: **source evidence → structured understanding → rubric decisions → evaluation ledger → human approval → published result → learning evidence**. The ledger sits at the center as the structured, queryable record of proposed and final marks.

AI systems often expose one "confidence score." EduVijna's pipeline has distinct failure modes: wrong student identity, wrong question mapping, transcription errors, rubric misapplication, and mathematical verification failures. Collapsing these into one number misleads reviewers and erodes trust.

## Decision

The **question-level evaluation ledger** in PostgreSQL is the **source of truth (SoT) for all scores and marks**:

- **Ledger grain**: One row (or normalized row set) per `(submission_id, question_id)` with links to rubric version, criterion-level marks, evidence references (S3 keys to cropped regions, transcription text), and workflow status (`DRAFT`, `PENDING_REVIEW`, `APPROVED`, `OVERRIDDEN`, `PUBLISHED`).
- **Criterion-level detail**: Child rows or JSONB array for rubric criteria marks, supporting partial credit, all-or-nothing (AON), error carried forward (ECF), accepted alternative answers, unit requirements, and numeric precision rules — aligned with ADR-008.
- **Separate confidence dimensions** — never a single generic "AI confidence":
  - `identity_confidence` — student/roll mapping from cover page.
  - `mapping_confidence` — physical region ↔ question number alignment.
  - `transcription_confidence` — OCR/handwriting read quality.
  - `evaluation_confidence` — rubric application certainty.
  - Optional: `math_verification_confidence` when symbolic/numeric check runs.
  Each is stored explicitly on the ledger or linked stage record; UI surfaces all relevant dimensions to reviewers.
- **AI proposes, ledger records proposals**: Celery evaluation tasks write `DRAFT` ledger entries. They do not publish results.
- **Human approval gate** (ADR-010): Transition to `APPROVED`/`PUBLISHED` requires a `ReviewAction` of type `ACCEPT` or `OVERRIDE` by an authorized tenant user.
- **No unconstrained whole-PDF LLM for final reports**: Report and summary generation (student explanation, parent summary, learning plan) must consume **approved ledger rows + linked evidence**, not re-run open-ended "grade this PDF" prompts. LLMs may narrate and explain existing structured decisions; they must not silently change marks.

Published API responses and export files are **projections** of the approved ledger, version-stamped with rubric/answer-key version IDs.

## Consequences

**Positive**

- Teachers can override Q3 without re-running the entire sheet; audit trail shows before/after at criterion granularity.
- Reporting, analytics, and dispute resolution query SQL, not re-parse PDFs or re-invoke models.
- Confidence UX is honest: low mapping confidence triggers region review even when transcription confidence is high.
- Regulatory and institutional audit: "show me the decision record" is a database export, not a chat log.

**Negative**

- More schema and API surface than "store LLM JSON blob per paper."
- Pipeline must fail gracefully when upstream stages lack confidence — ledger rows may be `INCOMPLETE` with blocking reasons.
- Narrative report generators must be constrained by templates/schemas so they cannot hallucinate marks inconsistent with ledger (validation step on generate).

**Invariants**

1. No published score exists without a corresponding approved ledger row.
2. Ledger rows reference a specific `rubric_version_id` and `answer_key_version_id`.
3. Deleting or rewriting approved ledger rows is forbidden; corrections append new `OVERRIDE` actions and adjustment rows.

## Alternatives Considered

| Alternative | Why rejected |
|-------------|--------------|
| **LLM output JSON as SoT** | Non-reproducible, hard to partially edit, weak audit story. |
| **Single aggregate confidence** | Hides which stage failed; causes wrong reviewer actions. |
| **Scores in export PDF only** | Not queryable; regenerating export could drift from truth. |
| **Re-run LLM on whole PDF for reports** | Marks can drift from reviewed decisions; violates "teacher is final authority." |
| **Spreadsheet export as SoT** | Breaks multi-user concurrent review and API-first product model. |
