# EduVijna Paper Evaluation — Founder Approval Log

Architecture and product scope decisions requiring founder sign-off are recorded here. Implementation engineers (Cursor A, Cursor B) **must not** substitute stacks, delete requirements, or alter release states without a new entry in this log.

---

## Approval Record Template

Copy this block for each new decision:

```markdown
### APP-NNN — [Short decision title]

| Field | Value |
|-------|-------|
| **Date** | YYYY-MM-DD |
| **Decision** | [What was decided — be specific] |
| **Approver** | [Name / role] |
| **Status** | PROPOSED \| APPROVED \| REJECTED \| SUPERSEDED |
| **Notes** | [Context, constraints, links to ADRs/requirements, expiry if applicable] |
```

---

## Decision Register

| Date | Decision | Approver | Status | Notes |
|------|----------|----------|--------|-------|
| 2026-09-09 | **Approve fourth/final bounded post-CVB AFTER_CLIENT_APPROVAL tranche: PEV-058 and PEV-059.** Activates gold benchmark dataset curation and AI regression testing as bounded B15 work from `develop` after B14 completion. Gold truth must be human-adjudicated from eligible immutable published evidence; benchmark execution must never mutate the evaluation ledger or published results; datasets and runs remain tenant-isolated; provider/model/prompt/template metadata must be preserved; regression thresholds must be deterministic and auditable; required CI must not depend on live third-party AI credentials; failed regression must be capable of blocking a provider/model release. | Founder / Product Architect | APPROVED | APP-006. One Cursor implementation engineer owns backend + frontend + contracts + migrations + tests + E2E + CI + PR + merge execution. PEV-058 and PEV-059 remain formally `AFTER_CLIENT_APPROVAL` (release-state classification unchanged). All FUTURE_ENTERPRISE requirements remain deferred. No feature work is promoted to `main`. |
| 2026-09-08 | **Approve third post-CVB AFTER_CLIENT_APPROVAL tranche: PEV-043.** Activates reassessment instantiation and mastery-delta tracking as bounded B14 work from `develop` after B13 completion. Reassessment must originate from an APPROVED B9 improvement-assessment blueprint, remain tenant/student/curriculum scoped, use the existing Assessment → Submission → evaluation ledger → human approval → publication pipeline, and derive mastery change only from published B8/B12 evidence rather than a second mastery algorithm. | Founder / Product Architect | APPROVED | APP-005. One Cursor implementation engineer owns backend + frontend + contracts + migration + tests + CI. PEV-058, PEV-059 and all FUTURE_ENTERPRISE requirements remain deferred. No auto-publication, no bypass of teacher/rubric/evaluation approval gates, and no feature merge to `main`. |
| 2026-09-08 | **Approve second post-CVB AFTER_CLIENT_APPROVAL tranche: PEV-041.** Activates curriculum resource assignment as bounded B13 work from `develop` after B12 completion. Assignments must reference tenant-scoped, institution-approved curriculum resources/practice materials; no open-web discovery or arbitrary external resource assignment is authorized. | Founder / Product Architect | APPROVED | APP-004. One Cursor implementation engineer owns backend + frontend + contracts + migration + tests + CI. PEV-043, PEV-058, PEV-059 and all FUTURE_ENTERPRISE requirements remain deferred. `main` remains release-only and unchanged. |
| 2026-09-07 | **Approve first post-CVB AFTER_CLIENT_APPROVAL tranche: PEV-035–038.** Activates repeated error analysis, recoverable marks analysis, longitudinal mastery tracking, and the persistent student mistake notebook as the first bounded post-CVB implementation tranche from `develop` after CVB v0.1 release completion. | Founder / Product Architect | APPROVED | APP-003. One Cursor implementation engineer owns backend + frontend + contracts + tests + CI. PEV-041, PEV-043, PEV-058, PEV-059 and all FUTURE_ENTERPRISE requirements remain deferred. `main` remains release-only. |
| 2026-09-07 | **Approve CVB v0.1 release promotion.** Authorizes the independently re-audited BUILD_NOW release candidate on `develop` after B11: 59 VERIFIED / 0 BLOCKED, B11 squash `dd6bd64faf7ddcd089c94d7c32f748ec70109840`, with promotion to `main` through the release workflow after authoritative CI succeeds. Deferred requirements remain deferred and unchanged. | Founder / Product Architect | APPROVED | Release milestone approval. Record B11 evidence in the authorized release path; do not introduce new implementation scope. Issue #1 may close only after the `main` promotion is confirmed. |
| 2026-09-04 | **Mandatory architecture contract for Day 1 bootstrap (CVB v0.1).** Approves: modular monolith; Python 3.12 + FastAPI + SQLAlchemy 2 async + Alembic + PostgreSQL 16; Redis + Celery async; S3-compatible storage (MinIO local); Next.js + React + TypeScript + Tailwind frontend stack; pnpm monorepo; SymPy + PyMuPDF; Docker Compose deployment. **Prohibits for CVB:** Kubernetes, Temporal, Kafka, microservices split, GraphQL, native mobile, Firebase, Supabase, serverless-only architecture. **Approves** core pipeline: source evidence → structured understanding → rubric decisions → evaluation ledger → human approval → published result → learning evidence. **Approves** tenant-aware data model from first migration; evaluation ledger as source of truth; immutable raw source papers; human approval required before publication; AI provider abstraction. **Approves** 30-day BUILD_NOW vertical slice per `docs/product/MASTER_PRODUCT_SCOPE.md` and requirements PEV-001 – PEV-078 in `docs/product/REQUIREMENTS_REGISTER.md`. **Approves** Cursor A/B ownership split per master scope §7. | Founder / Product Architect | APPROVED | Day 1 bootstrap foundation. ADRs ADR-001 through ADR-010 derive from this decision. Repository: `eduvijna/eduvijna-paper-evaluation`. No requirement from business context may be deleted — deferred items use AFTER_CLIENT_APPROVAL or FUTURE_ENTERPRISE only. |

---

## Detailed Entry — APP-006

### APP-006 — AI Quality Benchmark & Regression Gate Tranche

| Field | Value |
|-------|-------|
| **Date** | 2026-09-09 |
| **Decision** | Approve activation of PEV-058 and PEV-059 together as the fourth and final bounded post-CVB `AFTER_CLIENT_APPROVAL` implementation tranche following B14 completion. B15 shall deliver a tenant-scoped, versioned, human-adjudicated gold benchmark dataset and an isolated AI regression runner that produces deterministic, auditable pass/fail verdicts usable as a provider/model release gate—without mutating production evaluation or learning evidence, and without promoting feature work to `main`. |
| **Approver** | Founder / Product Architect |
| **Status** | APPROVED |
| **Notes** | Implementation starts from the post-B14 `develop` SHA `269ad6f976cfe789175689bb4ade5a66fb02e613` and follows `docs/engineering/DEVELOPMENT_WORKFLOW.md`: one Cursor implementation engineer owns backend, frontend, contracts, migrations, tests, E2E, CI, PR, and merge execution in one bounded feature PR to `develop`. **Invariants:** (1) gold truth is human-adjudicated; (2) benchmark source evidence is immutable; (3) benchmark execution never mutates the evaluation ledger or published results; (4) datasets and runs are tenant-isolated; (5) provider/model/prompt/template metadata is preserved; (6) regression thresholds are deterministic and auditable; (7) required CI must not depend on live third-party AI credentials; (8) failed regression must be capable of blocking a provider/model release; (9) no feature work is promoted to `main`. PEV-058 and PEV-059 remain formally classified `AFTER_CLIENT_APPROVAL` (implementation under APP-006/B15 does not change release-state classification). All FUTURE_ENTERPRISE requirements remain deferred. Do not implement model training/fine-tuning, cross-tenant pooled benchmarks, automatic provider/model deployment, or any `main` promotion in this tranche. |

---

## Detailed Entry — APP-005

### APP-005 — Reassessment & Mastery Update Tranche

| Field | Value |
|-------|-------|
| **Date** | 2026-09-08 |
| **Decision** | Approve activation of PEV-043 as the third bounded `AFTER_CLIENT_APPROVAL` implementation tranche following B13 completion. B14 shall instantiate an APPROVED B9 `ImprovementAssessment` blueprint into a real, tenant-scoped reassessment that is explicitly linked to the blueprint, student, and curriculum, and shall expose the resulting mastery change after the reassessment reaches the existing PUBLISHED result boundary. |
| **Approver** | Founder / Product Architect |
| **Status** | APPROVED |
| **Notes** | Implementation starts from the post-B13 `develop` SHA and follows `docs/engineering/DEVELOPMENT_WORKFLOW.md`: one Cursor implementation engineer, contract-first, backend + frontend + migration + tests + CI in one bounded feature PR to `develop`. Reassessment creation must be idempotent per approved blueprint and must not create a parallel grading/publication path. Generated or teacher-completed assessment content remains subject to existing authoring, answer-key, rubric, READY/ACTIVE, evaluation-ledger, human-approval, and publication gates. Mastery delta must be deterministic and auditable: capture the blueprint/reassessment baseline from existing B12 state/snapshots, then compare only against B12 state produced from immutable B8 evidence after the linked reassessment result is PUBLISHED. Do not manually rewrite `MasteryEvidence`, `MasteryState`, or historical snapshots; reuse B8/B12 materialization. Do not infer mastery from assignment completion or an unpublished reassessment. Preserve B13 resource-assignment semantics and all no-open-web constraints. PEV-058, PEV-059 and all FUTURE_ENTERPRISE requirements remain deferred. Do not merge feature work to `main`; a later founder-approved release milestone is required. |

---

## Detailed Entry — APP-004

### APP-004 — Curriculum Resource Assignment Tranche

| Field | Value |
|-------|-------|
| **Date** | 2026-09-08 |
| **Decision** | Approve activation of PEV-041 as the second bounded `AFTER_CLIENT_APPROVAL` implementation tranche following B12 completion. B13 shall support assignment of approved curriculum resources and practice materials to students, linked to curriculum nodes and learning recommendations where applicable, using only tenant-scoped resources that have been explicitly approved for institutional use. |
| **Approver** | Founder / Product Architect |
| **Status** | APPROVED |
| **Notes** | Implementation starts from the post-APP-004 `develop` SHA and follows `docs/engineering/DEVELOPMENT_WORKFLOW.md`: one Cursor implementation engineer, contract-first, backend + frontend + migration + tests + CI in one bounded feature PR to `develop`. Resource assignment must be auditable and tenant-isolated. Do not add open-web search, crawling, arbitrary URL recommendation, or unapproved external-resource assignment. Preserve B9 learning recommendations and B12 mastery/mistake intelligence semantics; resource assignment may link to those records but must not rewrite their evidence. PEV-043, PEV-058, PEV-059 and all FUTURE_ENTERPRISE requirements remain deferred. Do not merge feature work to `main`; a later founder-approved release milestone is required. |

---

## Detailed Entry — APP-003

### APP-003 — First Post-CVB Mastery & Mistake Intelligence Tranche

| Field | Value |
|-------|-------|
| **Date** | 2026-09-07 |
| **Decision** | Approve activation of PEV-035, PEV-036, PEV-037, and PEV-038 as the first bounded `AFTER_CLIENT_APPROVAL` implementation tranche following confirmed CVB v0.1 release completion. The tranche covers repeated error analysis across submissions, recoverable marks analysis by error class, longitudinal `MasteryState` tracking across published assessments, and a persistent student mistake notebook linked to source questions, error codes, corrections, and approved curriculum practice context. |
| **Approver** | Founder / Product Architect |
| **Status** | APPROVED |
| **Notes** | Implementation starts from current `develop` and follows `docs/engineering/DEVELOPMENT_WORKFLOW.md`: one Cursor implementation engineer, contract-first, backend + frontend + tests + CI in one bounded feature PR to `develop`. Preserve immutable `MasteryEvidence` as evidence history; longitudinal aggregates must be derived/auditable and tenant-scoped. Do not activate PEV-041, PEV-043, PEV-058, PEV-059, or any FUTURE_ENTERPRISE requirement in this tranche. Do not merge feature work to `main`; a later founder-approved release milestone is required. |

---

## Detailed Entry — APP-002

### APP-002 — CVB v0.1 Release Promotion

| Field | Value |
|-------|-------|
| **Date** | 2026-09-07 |
| **Decision** | Approve the CVB v0.1 release milestone for promotion from the independently re-audited `develop` release candidate to `main`, after B11 closed the post-B10 release blockers and the BUILD_NOW audit reached 59 VERIFIED / 0 BLOCKED. The approved B11 squash is `dd6bd64faf7ddcd089c94d7c32f748ec70109840`. |
| **Approver** | Founder / Product Architect |
| **Status** | APPROVED |
| **Notes** | Promotion must use the repository release workflow and authoritative CI. This approval does not activate deferred PEV-035–038, PEV-041, PEV-043, PEV-044–046, PEV-048–051, or PEV-054–059. Issue #1 closes only after `main` promotion is confirmed. |

---

## Detailed Entry — APP-001

### APP-001 — Day 1 Bootstrap Mandatory Architecture Contract

| Field | Value |
|-------|-------|
| **Date** | 2026-09-04 |
| **Decision** | Ratify the full mandatory architecture contract for EduVijna Paper Evaluation CVB v0.1 Day 1 bootstrap, including technology stack, non-goals, core evaluation pipeline, tenant isolation, evaluation ledger authority, human-in-the-loop publication gate, and parallel Cursor ownership model. |
| **Approver** | Founder / Product Architect |
| **Status** | APPROVED |
| **Notes** | Implementation Engineer A executed bootstrap under this contract. Frontend UI deferred to Cursor B; backend foundation migration covers tenants through audit_events only — evaluation tables specified in architecture docs for subsequent bounded migrations. Changes to prohibited technologies or deletion of PEV requirements require new APP entry with APPROVED status before implementation. |

---

## Rules of Use

1. **Status values:** Only `PROPOSED`, `APPROVED`, `REJECTED`, or `SUPERSEDED` are valid.
2. **Supersession:** When a decision replaces a prior one, set the old entry to `SUPERSEDED` and reference the new APP ID in both Notes fields.
3. **Linkage:** Major approvals should reference affected ADR IDs (see `docs/architecture/ADR_INDEX.md`) and PEV requirement IDs when scope or priority changes.
4. **Emergency exception:** If production incident requires temporary deviation, log `PROPOSED` immediately and obtain `APPROVED` within one business day or revert.

---

## Document Control

| Version | Date | Author | Change |
|---------|------|--------|--------|
| 0.6 | 2026-09-09 | Governance workflow | APP-006 activates final post-CVB PEV-058–059 AI quality benchmark & regression gate tranche |
| 0.5 | 2026-09-08 | Governance workflow | APP-005 activates post-B13 PEV-043 reassessment & mastery update tranche |
| 0.4 | 2026-09-08 | Governance workflow | APP-004 activates post-CVB PEV-041 curriculum resource assignment tranche |
| 0.3 | 2026-09-07 | Governance workflow | APP-003 activates first post-CVB PEV-035–038 tranche |
| 0.2 | 2026-09-07 | Release workflow | APP-002 CVB v0.1 release promotion approval |
| 0.1 | 2026-09-04 | Cursor A (bootstrap) | Initial log with APP-001 Day 1 architecture approval |
