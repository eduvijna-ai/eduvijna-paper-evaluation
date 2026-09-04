# ADR-008: Versioned Answer Keys and Rubrics with Teacher Approval

## Status: Accepted

## Date: 2026-09-04

## Context

Assessment quality depends on correct answer keys and fair, explicit rubrics. In EduVijna, AI can **propose** rubrics and mapping from an official marking scheme PDF or teacher notes, but institutions require control: criteria weights, acceptable alternatives, error-carried-forward (ECF) rules, unit marks, and significant-figure policies vary by board and subject.

If rubrics mutate in place after evaluations run, historical scores become incomparable and audit fails ("which rubric version produced this mark?"). Teachers also need to review AI-generated rubrics before any automated evaluation runs at scale — publishing a bad rubric at batch scale is costly to unwind.

The evaluation ledger (ADR-006) must reference immutable rubric and answer-key versions at evaluation time.

## Decision

Implement **versioned AnswerKey and Rubric entities** with teacher approval workflow:

**Answer keys**

- `AnswerKey` — logical exam key (tenant, assessment, subject metadata).
- `AnswerKeyVersion` — immutable once `PUBLISHED`: expected answers per question, acceptable alternatives, numeric tolerances, units, precision rules.
- Version monotonic integer or UUID; only one `PUBLISHED` current version per AnswerKey for new evaluations; older versions remain for historical ledger joins.

**Rubrics**

- `Rubric` — logical rubric attached to an assessment or question set.
- `RubricVersion` — immutable once `PUBLISHED`: criteria list with marks, types, and rule flags.
- **Criterion capabilities** (first-class in schema and evaluator):
  - **Partial credit** — fractional marks per sub-part.
  - **All-or-nothing (AON)** — full marks only if entire criterion satisfied.
  - **Error carried forward (ECF)** — follow-through marking when early error propagates; evaluator reads ECF graph from version metadata.
  - **Alternative answers** — linked to answer key alternatives or rubric-specific accepts.
  - **Units** — separate unit mark or unit-required gate.
  - **Precision** — sig figs, decimal places, rounding mode.
- **Lifecycle states**: `DRAFT` → `PENDING_TEACHER_REVIEW` → `APPROVED` → `PUBLISHED`. AI-proposed rubrics enter as `DRAFT` or `PENDING_TEACHER_REVIEW` with `provenance = AI_PROPOSED`.
- **Teacher approval required**: No batch evaluation against a rubric until a tenant `TEACHER` or `INSTITUTION_ADMIN` records approval on that `RubricVersion`. Approval is auditable (`ReviewAction` or dedicated `RubricApproval` record).
- **Immutability after publish**: `PUBLISHED` versions cannot be edited. Changes create a new version; re-evaluation of past submissions is explicit opt-in migration, not silent overwrite.

**Evaluation binding**

- Each ledger row stores `rubric_version_id` and `answer_key_version_id` at evaluation time.
- `evaluate_rubric` AI operation receives frozen version payload, not live editable rubric.

**AI proposal path**

- AI ingests marking scheme / sample solutions → proposes `RubricVersion` draft with criteria breakdown.
- UI diff view for teacher: edit marks, toggle AON/ECF, add alternatives, then approve and publish.

## Consequences

**Positive**

- Audit and appeals cite exact rubric text and rules at time of marking.
- Institutions trust AI assistance without surrendering pedagogical control.
- Evaluator engine tests against fixed version fixtures — reproducible CI.
- Board-specific marking conventions encoded in data, not prompt hacks.

**Negative**

- Schema and UI complexity for versioning and approval flows.
- Storage of multiple versions per assessment; acceptable and necessary.
- ECF and partial credit logic requires dedicated evaluator code paths, not generic LLM rubric application alone — `evaluate_rubric` combines rules engine + AI judgment where rules cannot decide.

**Rules engine vs. LLM**

Deterministic criteria (numeric tolerance, unit check, AON) run in code against transcribed answers. Ambiguous handwritten reasoning may invoke `evaluate_rubric` LLM with rubric version context; result still lands in ledger as proposal with `evaluation_confidence`.

## Alternatives Considered

| Alternative | Why rejected |
|-------------|--------------|
| **Single mutable rubric document** | Breaks ledger audit trail; accidental edits change past scores' meaning. |
| **Rubric only in prompt text** | Not queryable, not approvable structurally, not testable. |
| **AI-published rubrics without teacher gate** | Institutional rejection risk; one bad criterion affects entire cohort. |
| **Version only answer key, not rubric** | Half the marking policy missing; partial credit lives in rubric. |
| **Spreadsheet upload without version entity** | No approval workflow integration or API consistency. |
