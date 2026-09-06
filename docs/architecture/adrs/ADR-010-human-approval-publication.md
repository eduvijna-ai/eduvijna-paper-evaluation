# ADR-010: Human Approval Required Before Publication

## Status: Accepted

## Date: 2026-09-04

## Context

EduVijna's product principle: **AI proposes; institution/teacher remains the final authority.** Automated marks and generated narratives may be wrong — identity mismatches, transcription errors, or rubric misapplication. Publishing results to students, parents, or downstream LMS systems without human review creates institutional liability and erodes trust.

CVB must implement an explicit review gate, not an implicit "auto-publish if confidence > 0.8" shortcut. Confidence dimensions (ADR-006) inform prioritization but do not replace human judgment for publication.

Reports (PDF, parent letter, learning plan) must reflect **approved** decisions, not draft AI proposals.

## Decision

**No published result without an explicit human approval path** via `ReviewAction`:

**Evaluation review states** (submission or submission-batch scope)

| State | Meaning |
|-------|---------|
| `PIPELINE_RUNNING` | Async stages in progress |
| `READY_FOR_REVIEW` | Ledger drafts complete; awaiting human |
| `IN_REVIEW` | Reviewer actively editing |
| `CHANGES_REQUESTED` | Sent back for re-run or manual fix |
| `APPROVED` | Accepted for publication |
| `PUBLISHED` | Visible to authorized student/parent roles and exports |

State transitions are recorded in Postgres with timestamps and actor; not inferred from UI alone.

**ReviewAction types**

- `ACCEPT` — reviewer confirms AI-proposed ledger as-is (per question or whole submission per UI design).
- `OVERRIDE` — reviewer changes marks, criterion notes, or identity mapping with mandatory reason text.
- `REJECT` — submission cannot be graded (blank, wrong paper, illegible); no publication.
- `REQUEST_REPROCESS` — triggers targeted pipeline re-run (e.g., remap regions only).

Publication requires at least one `ACCEPT` or `OVERRIDE` on every question slated for publication, by a user with `REVIEWER`, `TEACHER`, or `INSTITUTION_ADMIN` role in the tenant (ADR-005). Optional institution policy: dual approval for high-stakes exams — configured per tenant, not hard-coded in CVB v0.1.

**Ledger coupling**

- Draft ledger rows (`DRAFT`, `PENDING_REVIEW`) are invisible to student/parent APIs.
- On `ACCEPT`/`OVERRIDE`, ledger rows transition to `APPROVED`; `PUBLISHED` is set when institution releases results (immediate or scheduled release window).
- Overrides append audit entries with before/after marks; original AI proposal retained.

**Reports and narratives**

- `generate_student_explanation`, `generate_parent_summary`, `generate_learning_plan`, and `generate_improvement_blueprint` (ADR-007) execute only when submission status ≥ `APPROVED`, reading approved ledger snapshot IDs.
- Export jobs (`publication.prepare_exports`) fail fast if any included question lacks `APPROVED` ledger row.
- No API endpoint returns "final report" from unconstrained LLM over raw PDF.

**Auto-publish prohibition**

- No feature flag for "skip review" in production tenant configs for CVB.
- Bulk approve is allowed with explicit confirmation and per-submission summary — still records individual `ReviewAction` rows, not a silent batch SQL update.

**Frontend**

- Review UI surfaces confidence dimensions, evidence crops, transcription, and criterion marks before approve.
- Published dashboard clearly distinguishes "pending review" vs. "published" cohorts.

## Consequences

**Positive**

- Aligns product with institutional procurement and academic integrity expectations.
- Legal defensibility: human decision maker identified in audit trail.
- Narrative content cannot drift from approved marks without detection.

**Negative**

- Throughput limited by reviewer capacity — batch review UX and filtering by low confidence become important product work.
- Cannot demo "instant results to student" without reviewer in loop — correct tradeoff for enterprise positioning.
- Additional states and API endpoints for review queue management.

**API invariant**

`GET /submissions/{id}/published-result` returns 404 until publication state reached; drafts available only on reviewer endpoints.

## Alternatives Considered

| Alternative | Why rejected |
|-------------|--------------|
| **Auto-publish above confidence threshold** | Thresholds hide compound failures; no human accountability. |
| **Teacher signs off on PDF only, not ledger** | PDF not SoT; marks could diverge from structured data (ADR-006). |
| **Publish first, amend later** | Harmful to student trust; amendment workflows harder than hold-until-approved. |
| **AI as reviewer (second model approves first)** | Does not satisfy institutional final authority requirement. |
| **Implicit approval by opening export** | No audit-grade `ReviewAction`; legally weak. |
