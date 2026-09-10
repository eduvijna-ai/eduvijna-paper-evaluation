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
| 2026-09-10 | **Approve APP-013.1 corrective release promotion.** Authorizes promotion of the independently accepted APP-013.1 release-test-governance integrity remediation from `develop` to `main`. Release/governance only; restores UI-faithful B12/B14 real-E2E finalize evidence; no new product implementation; PEV-050–051 remain formally `FUTURE_ENTERPRISE`; PEV-054–057 remain deferred; no new migration (Alembic head remains `20260910_0020`); exact-tree snapshot mandatory; no direct develop→main conflict resolution; no merge-back from main to develop; no AI provider/model deployment authorization. Founder authorization: “approved. proceed”. | Founder / Product Architect | APPROVED | APP-014. Corrective follow-up to APP-013 Issue #84 / governance PR #85 / release PR #86. APP-013.1 Issue #87 / PR #88. Accepted develop: `669968e0438caf71ae13a9bdf1bf1f6a81b925f9` (tree `c1945b460ccf070c6468790877ea954c5205a123`). Expected main until promotion: `c0b084fb1db5164104ed77bd43bdc5efb8d26092` (tree `2f143e4f9a76b67e3d64d67ae02b581d1b8a0c09`). Tracking Issue #89. |
| 2026-09-10 | **Approve Answer Intelligence & Outcome Reporting release promotion.** Authorizes promotion of the independently accepted APP-012 / B18 + B18.1 + B18.2 Answer Clustering & CO/PO Reporting implementation (PEV-050–051) from `develop` to `main`. Release promotion only; no new product implementation; PEV-050–051 remain formally `FUTURE_ENTERPRISE`; PEV-054–057 remain deferred; exact-tree snapshot mandatory because main/develop histories intentionally diverge; no direct develop→main conflict resolution; no merge-back from main to develop; no AI provider/model deployment authorization. | Founder / Product Architect | APPROVED | APP-013. Milestone: Answer Intelligence & Outcome Reporting Release. Issue #84. Starting develop: `4148401549591472453f1bf7231727921352937e`. Expected main until promotion: `548960e6b35e5229595c9fd0ef17d9b375080e07`. Implementation already accepted through B18 (#78 / PR #79) + B18.1 (#80 / PR #81) + B18.2 (#82 / PR #83). |
| 2026-09-10 | **Approve third FUTURE_ENTERPRISE implementation tranche: PEV-050 and PEV-051.** Activates answer clustering from transcription embeddings and CO/PO attainment reporting as bounded B18 work from `develop` after Assessment Quality & Calibration release. Clustering supports pattern discovery and advisory rubric-refinement observations only and must never mutate approved rubrics, evaluation ledger scores, ReviewActions, or publication state; CO/PO analytics report marks-weighted attainment from current PUBLISHED human-final evidence only and must never rewrite historical evaluation results; SUPERSEDED publications must not double-count; no external vector database; no main promotion. | Founder / Product Architect | APPROVED | APP-012. Tranche: B18 — Answer Clustering & CO/PO Reporting. PEV-050–051 remain formally `FUTURE_ENTERPRISE` (release-state classification unchanged). PEV-054–057 remain deferred. PEV-048/049 already released via APP-011 — do not redesign. No `main` promotion. No new infrastructure architecture. |
| 2026-09-10 | **Approve Assessment Quality & Calibration release promotion.** Authorizes promotion of the independently accepted APP-010 / B17 + B17.1 Assessment Quality & Evaluator Calibration implementation (PEV-048–049) from `develop` to `main`. Release promotion only; no new product implementation; PEV-048–049 remain formally `FUTURE_ENTERPRISE`; PEV-050–051 and PEV-054–057 remain deferred; exact-tree snapshot mandatory because main/develop histories intentionally diverge; no direct develop→main conflict resolution; no merge-back from main to develop; no AI provider/model deployment authorization. | Founder / Product Architect | APPROVED | APP-011. Milestone: Assessment Quality & Calibration Release. Issue #73. Starting develop: `83547716a49aae8cc7ebdf24abc3a2ad839b4dfd`. Expected main until promotion: `5febe578f4f57f24c63149ae5a03be8adb5baac3`. Implementation already accepted through B17 (#69 / PR #70) + B17.1 (#71 / PR #72). |
| 2026-09-10 | **Approve second FUTURE_ENTERPRISE implementation tranche: PEV-048 and PEV-049.** Activates item difficulty/discrimination psychometrics and evaluator consistency/calibration as bounded B17 work from `develop` after Enterprise Operations release. Metrics derive only from authoritative human-final/current published ledger evidence or isolated calibration responses; quality analytics must not mutate evaluation scores, ReviewActions, PublishedResults, mastery or publication state; calibration responses are QA artifacts not a second grading ledger; evaluator metrics must not automatically change assignments, access, moderation or publication; low-sample statistics must be suppressed/marked insufficient; no cross-tenant pooled psychometrics; no PEV-050 embeddings/clustering. | Founder / Product Architect | APPROVED | APP-010. Tranche: B17 — Assessment Quality & Evaluator Calibration. PEV-048–049 remain formally `FUTURE_ENTERPRISE` (release-state classification unchanged). PEV-050–051 and PEV-054–057 remain deferred. No `main` promotion. No new infrastructure architecture. |
| 2026-09-09 | **Approve Enterprise Operations release promotion.** Authorizes promotion of the independently accepted APP-008 / B16 + B16.1 Enterprise Grading, Moderation & Grievance implementation (PEV-044–046) from `develop` to `main`. Release promotion only; no new product implementation; PEV-044–046 remain formally `FUTURE_ENTERPRISE`; PEV-048–051 and PEV-054–057 remain deferred; exact-tree snapshot mandatory because main/develop histories intentionally diverge. | Founder / Product Architect | APPROVED | APP-009. Milestone: Enterprise Operations Release. Issue #64. Starting develop: `801f1ea119d2d35b50e642518bf5da3e7d74ad0a`. Expected main until promotion: `50fc217ab54ea7c526994b98266a1914accc8d34`. |
| 2026-09-09 | **Approve first FUTURE_ENTERPRISE implementation tranche: PEV-044, PEV-045, and PEV-046.** Activates horizontal grading, configurable moderation workflows, and formal grievance/re-evaluation as bounded B16 work from `develop` after Post-CVB Phase 1 release. Evaluation ledger remains authoritative; AI never becomes final authority; publication remains blocked until required human governance completes; grievances create a new EvaluationRun version without mutating the original ledger or published artifact; analytics/mastery must not double-count superseded publications. | Founder / Product Architect | APPROVED | APP-008. Tranche: B16 — Enterprise Grading, Moderation & Grievance. PEV-044–046 remain formally `FUTURE_ENTERPRISE` (release-state classification unchanged). PEV-048–051 and PEV-054–057 remain deferred. No `main` promotion. No new infrastructure architecture (K8s/Kafka/Temporal/microservices/GraphQL/Firebase/Supabase/serverless-only). |
| 2026-09-09 | **Approve Post-CVB Phase 1 release promotion.** Authorizes promotion of the independently verified `develop` release candidate containing all eight completed `AFTER_CLIENT_APPROVAL` implementations (PEV-035–038, PEV-041, PEV-043, PEV-058–059 under APP-003–APP-006 / B12–B15.1) from `develop` to `main`. No new product scope; no FUTURE_ENTERPRISE activation; release-state classifications unchanged; release promotion only. | Founder / Product Architect | APPROVED | APP-007. Milestone name: Post-CVB Phase 1. Starting verified develop candidate before governance merge: `a3905bdce04a684af4cf2b1617a183540ed0a264`. Prior `main` must remain `30c96af951ce418eb446beb7c35b679e3697b047` until the exact-tree snapshot release PR merges. |
| 2026-09-09 | **Approve fourth/final bounded post-CVB AFTER_CLIENT_APPROVAL tranche: PEV-058 and PEV-059.** Activates gold benchmark dataset curation and AI regression testing as bounded B15 work from `develop` after B14 completion. Gold truth must be human-adjudicated from eligible immutable published evidence; benchmark execution must never mutate the evaluation ledger or published results; datasets and runs remain tenant-isolated; provider/model/prompt/template metadata must be preserved; regression thresholds must be deterministic and auditable; required CI must not depend on live third-party AI credentials; failed regression must be capable of blocking a provider/model release. | Founder / Product Architect | APPROVED | APP-006. One Cursor implementation engineer owns backend + frontend + contracts + migrations + tests + E2E + CI + PR + merge execution. PEV-058 and PEV-059 remain formally `AFTER_CLIENT_APPROVAL` (release-state classification unchanged). All FUTURE_ENTERPRISE requirements remain deferred. No feature work is promoted to `main`. |
| 2026-09-08 | **Approve third post-CVB AFTER_CLIENT_APPROVAL tranche: PEV-043.** Activates reassessment instantiation and mastery-delta tracking as bounded B14 work from `develop` after B13 completion. Reassessment must originate from an APPROVED B9 improvement-assessment blueprint, remain tenant/student/curriculum scoped, use the existing Assessment → Submission → evaluation ledger → human approval → publication pipeline, and derive mastery change only from published B8/B12 evidence rather than a second mastery algorithm. | Founder / Product Architect | APPROVED | APP-005. One Cursor implementation engineer owns backend + frontend + contracts + migration + tests + CI. PEV-058, PEV-059 and all FUTURE_ENTERPRISE requirements remain deferred. No auto-publication, no bypass of teacher/rubric/evaluation approval gates, and no feature merge to `main`. |
| 2026-09-08 | **Approve second post-CVB AFTER_CLIENT_APPROVAL tranche: PEV-041.** Activates curriculum resource assignment as bounded B13 work from `develop` after B12 completion. Assignments must reference tenant-scoped, institution-approved curriculum resources/practice materials; no open-web discovery or arbitrary external resource assignment is authorized. | Founder / Product Architect | APPROVED | APP-004. One Cursor implementation engineer owns backend + frontend + contracts + migration + tests + CI. PEV-043, PEV-058, PEV-059 and all FUTURE_ENTERPRISE requirements remain deferred. `main` remains release-only and unchanged. |
| 2026-09-07 | **Approve first post-CVB AFTER_CLIENT_APPROVAL tranche: PEV-035–038.** Activates repeated error analysis, recoverable marks analysis, longitudinal mastery tracking, and the persistent student mistake notebook as the first bounded post-CVB implementation tranche from `develop` after CVB v0.1 release completion. | Founder / Product Architect | APPROVED | APP-003. One Cursor implementation engineer owns backend + frontend + contracts + tests + CI. PEV-041, PEV-043, PEV-058, PEV-059 and all FUTURE_ENTERPRISE requirements remain deferred. `main` remains release-only. |
| 2026-09-07 | **Approve CVB v0.1 release promotion.** Authorizes the independently re-audited BUILD_NOW release candidate on `develop` after B11: 59 VERIFIED / 0 BLOCKED, B11 squash `dd6bd64faf7ddcd089c94d7c32f748ec70109840`, with promotion to `main` through the release workflow after authoritative CI succeeds. Deferred requirements remain deferred and unchanged. | Founder / Product Architect | APPROVED | Release milestone approval. Record B11 evidence in the authorized release path; do not introduce new implementation scope. Issue #1 may close only after the `main` promotion is confirmed. |
| 2026-09-04 | **Mandatory architecture contract for Day 1 bootstrap (CVB v0.1).** Approves: modular monolith; Python 3.12 + FastAPI + SQLAlchemy 2 async + Alembic + PostgreSQL 16; Redis + Celery async; S3-compatible storage (MinIO local); Next.js + React + TypeScript + Tailwind frontend stack; pnpm monorepo; SymPy + PyMuPDF; Docker Compose deployment. **Prohibits for CVB:** Kubernetes, Temporal, Kafka, microservices split, GraphQL, native mobile, Firebase, Supabase, serverless-only architecture. **Approves** core pipeline: source evidence → structured understanding → rubric decisions → evaluation ledger → human approval → published result → learning evidence. **Approves** tenant-aware data model from first migration; evaluation ledger as source of truth; immutable raw source papers; human approval required before publication; AI provider abstraction. **Approves** 30-day BUILD_NOW vertical slice per `docs/product/MASTER_PRODUCT_SCOPE.md` and requirements PEV-001 – PEV-078 in `docs/product/REQUIREMENTS_REGISTER.md`. **Approves** Cursor A/B ownership split per master scope §7. | Founder / Product Architect | APPROVED | Day 1 bootstrap foundation. ADRs ADR-001 through ADR-010 derive from this decision. Repository: `eduvijna/eduvijna-paper-evaluation`. No requirement from business context may be deleted — deferred items use AFTER_CLIENT_APPROVAL or FUTURE_ENTERPRISE only. |

---

## Detailed Entry — APP-014

### APP-014 — APP-013.1 Corrective Release Promotion

| Field | Value |
|-------|-------|
| **Date** | 2026-09-10 |
| **Decision** | Founder approves promotion of the independently accepted APP-013.1 release-test-governance integrity remediation from `develop` to `main`. Milestone: **APP-014 — APP-013.1 Corrective Release**. Release/governance only — product remediation already accepted through APP-013.1 (Issue #87 / PR #88). Founder authorization recorded in ChatGPT on 2026-09-10: **“approved. proceed”**. |
| **Approver** | Founder / Product Architect |
| **Status** | APPROVED |
| **Notes** | Issue #89. Accepted post-APP-013.1 develop before this governance merge: `669968e0438caf71ae13a9bdf1bf1f6a81b925f9` (tree `c1945b460ccf070c6468790877ea954c5205a123`). Expected unchanged `main` until promotion: `c0b084fb1db5164104ed77bd43bdc5efb8d26092` (tree `2f143e4f9a76b67e3d64d67ae02b581d1b8a0c09`). Traceability: APP-013 Issue #84 / governance PR #85 / release PR #86; APP-013.1 Issue #87 / PR #88. **Invariants:** (1) release promotion only; (2) no new product implementation / no product scope expansion beyond already-accepted APP-013.1; (3) PEV-050–051 classification remains `FUTURE_ENTERPRISE`; (4) PEV-054–057 remain deferred; (5) zero requirement activation; (6) zero new migration — Alembic head remains `20260910_0020`; (7) no AI provider/model deployment authorization; (8) exact-tree release promotion required; (9) no direct develop→main conflict resolution; (10) no merge-back from main to develop; (11) no historical Git reconciliation; (12) governance PR for APP-014 is documentation-only (must not modify executable tests/apps — lesson from APP-013 governance PR #85); (13) B12/B14 real-E2E finalize must remain UI-faithful with no success-path `POST .../transcription/finalize` rescue and no forced `page.goto` substituting for application navigation. Exact-tree release promotion is mandatory (same conflict-safe snapshot pattern as CVB PR #40 / APP-007 / APP-009 / APP-011 / APP-013). |

---

## Detailed Entry — APP-013

### APP-013 — Answer Intelligence & Outcome Reporting Release Promotion

| Field | Value |
|-------|-------|
| **Date** | 2026-09-10 |
| **Decision** | Founder approves promotion of the independently accepted APP-012 / B18 + B18.1 + B18.2 Answer Clustering & CO/PO Reporting implementation from `develop` to `main`. Scope: PEV-050, PEV-051 only. Milestone: **Answer Intelligence & Outcome Reporting Release / APP-013**. Release promotion only — implementation already accepted through B18 (Issue #78 / PR #79), B18.1 (Issue #80 / PR #81), and B18.2 (Issue #82 / PR #83). |
| **Approver** | Founder / Product Architect |
| **Status** | APPROVED |
| **Notes** | Issue #84. Starting develop before governance merge: `4148401549591472453f1bf7231727921352937e` (tree `b5049642fc0e094171da2bb6bbe662357856fa7a`). Expected unchanged `main` until promotion: `548960e6b35e5229595c9fd0ef17d9b375080e07` (tree `286897f47943bf265cf1ce3e66d0d4d49a650ada`). **Invariants:** (1) release promotion only; (2) no new product implementation / no product scope expansion; (3) PEV-050–051 classification remains `FUTURE_ENTERPRISE`; (4) PEV-054–057 remain deferred; (5) no AI provider/model deployment authorization; (6) exact-tree release promotion required; (7) no direct develop→main conflict resolution; (8) no merge-back from main to develop; (9) no historical Git reconciliation; (10) no architecture expansion; (11) no migration beyond already accepted `20260910_0019` and corrected `20260910_0020`. Exact-tree release promotion is mandatory (same conflict-safe snapshot pattern as CVB PR #40 / APP-007 PR #58 / APP-009 PR #66 / APP-011). |

---

## Detailed Entry — APP-012

### APP-012 — Answer Intelligence & Outcome Reporting

| Field | Value |
|-------|-------|
| **Date** | 2026-09-10 |
| **Decision** | Approve activation of PEV-050 (Answer Clustering) and PEV-051 (CO / PO Reporting) together as the third bounded `FUTURE_ENTERPRISE` implementation tranche following Assessment Quality & Calibration release. B18 shall deliver tenant-scoped, deterministic answer clustering from transcription embeddings with advisory human review/refinement observations, and versioned CO/PO outcome mapping with immutable activated mapping sets and marks-weighted attainment report snapshots (JSON + CSV)—without mutating the evaluation ledger/publication/rubric chain, without an external vector database, and without promoting feature work to `main`. |
| **Approver** | Founder / Product Architect |
| **Status** | APPROVED |
| **Notes** | Issue #76. Implementation starts from current post-APP-011 `develop` (`05104717514808a6141034eac15a21dbdd0c248e`, tree `286897f47943bf265cf1ce3e66d0d4d49a650ada`) with expected unchanged `main` (`548960e6b35e5229595c9fd0ef17d9b375080e07`, tree `286897f47943bf265cf1ce3e66d0d4d49a650ada`). One Cursor implementation engineer owns backend + frontend + contracts + migrations + tests + E2E + CI + PR + merge to `develop`. **Invariants:** (1) PEV-050/051 only; (2) PEV-054/055/056/057 remain deferred; (3) release-state classifications remain `FUTURE_ENTERPRISE`; (4) no `main` promotion; (5) clustering uses current effective PUBLISHED human-final transcription evidence only; (6) SUPERSEDED publications must not double-count; (7) cluster refinement observations are advisory and must not mutate approved rubrics, QuestionEvaluations, ReviewActions, or published marks; (8) CO/PO attainment uses final human-approved ledger scores only; (9) ACTIVE mapping sets are immutable (new version required for changes); (10) report runs are immutable snapshots; (11) credential-free fixed embedding provider required for CI; (12) no external vector DB / pgvector / Kubernetes / Kafka / Temporal / microservices / GraphQL / Firebase / Supabase / serverless-only; (13) PEV-048/049 already released via APP-011 — do not redesign; (14) tenant isolation and RBAC remain mandatory; (15) six authoritative CI jobs must succeed on the exact final feature head before merge. |

---

## Detailed Entry — APP-011

### APP-011 — Assessment Quality & Calibration Release Promotion

| Field | Value |
|-------|-------|
| **Date** | 2026-09-10 |
| **Decision** | Founder approves promotion of the independently accepted APP-010 / B17 + B17.1 Assessment Quality & Evaluator Calibration implementation from `develop` to `main`. Scope: PEV-048, PEV-049 only. Milestone: **Assessment Quality & Calibration Release / APP-011**. Release promotion only — implementation already accepted through B17 (Issue #69 / PR #70) and B17.1 (Issue #71 / PR #72). |
| **Approver** | Founder / Product Architect |
| **Status** | APPROVED |
| **Notes** | Issue #73. Starting develop before governance merge: `83547716a49aae8cc7ebdf24abc3a2ad839b4dfd` (tree `e27fee0972cbbbe9f1e9b9413be1f0e75a89622a`). Expected unchanged `main` until promotion: `5febe578f4f57f24c63149ae5a03be8adb5baac3` (tree `58c13212bac1ecd086d546309752bb4c69cd7acd`). **Invariants:** (1) release promotion only; (2) no new product implementation / no product scope expansion; (3) PEV-048–049 classification remains `FUTURE_ENTERPRISE`; (4) PEV-050–051 and PEV-054–057 remain deferred; (5) no AI provider/model deployment authorization; (6) exact-tree release promotion required; (7) no direct develop→main conflict resolution; (8) no merge-back from main to develop; (9) no historical Git reconciliation; (10) no architecture expansion. Exact-tree release promotion is mandatory (same conflict-safe snapshot pattern as CVB PR #40 / APP-007 PR #58 / APP-009 PR #66). |

---

## Detailed Entry — APP-010

### APP-010 — Assessment Quality & Evaluator Calibration

| Field | Value |
|-------|-------|
| **Date** | 2026-09-10 |
| **Decision** | Approve activation of PEV-048 (Item Difficulty & Discrimination) and PEV-049 (Evaluator Consistency / Calibration) together as the second bounded `FUTURE_ENTERPRISE` implementation tranche following Enterprise Operations release. B17 shall deliver tenant-scoped, auditable psychometric runs derived from current effective PUBLISHED human-final evidence, and an isolated blind calibration workflow with deterministic inter-rater reliability (ICC) and evaluator-to-reference metrics—without creating a second score source, without mutating the evaluation ledger/publication/mastery chain, and without promoting feature work to `main`. |
| **Approver** | Founder / Product Architect |
| **Status** | APPROVED |
| **Notes** | Implementation starts from current post-APP-009 `develop` (`4ae56d9649a8a7c94cb6b9a998c04f058b959637`) with expected unchanged `main` (`5febe578f4f57f24c63149ae5a03be8adb5baac3`). One Cursor implementation engineer owns backend + frontend + contracts + migrations + tests + E2E + CI + PR + merge to `develop`. **Invariants:** (1) PEV-048/049 only; (2) PEV-050/051/054/055/056/057 remain deferred; (3) release-state classifications remain `FUTURE_ENTERPRISE`; (4) no `main` promotion; (5) metrics derive only from authoritative human-final/current published ledger evidence or isolated calibration responses; (6) quality analytics must not mutate evaluation scores, ReviewActions, PublishedResults, mastery or publication state; (7) calibration responses are QA artifacts, not a second grading ledger; (8) evaluator metrics must not automatically change grading assignments, employment decisions, access, moderation outcomes or publication; (9) low-sample statistics must be explicitly suppressed/marked insufficient; (10) SUPERSEDED publications must not be treated as additional attempts; (11) locked historical benchmark/calibration evidence remains historically reproducible; (12) tenant isolation and RBAC remain mandatory; (13) no cross-tenant pooled psychometrics; (14) no student-identifying data in blind calibration work; (15) no PEV-050 embeddings/clustering; (16) no Kubernetes, Kafka, Temporal, microservices split, GraphQL, Firebase, Supabase, or serverless-only redesign. |

---

## Detailed Entry — APP-009

### APP-009 — Enterprise Operations Release Promotion

| Field | Value |
|-------|-------|
| **Date** | 2026-09-09 |
| **Decision** | Founder approves promotion of the independently accepted APP-008 / B16 + B16.1 Enterprise Grading, Moderation & Grievance implementation from `develop` to `main`. Scope: PEV-044, PEV-045, PEV-046. Milestone: **Enterprise Operations Release / APP-009**. |
| **Approver** | Founder / Product Architect |
| **Status** | APPROVED |
| **Notes** | Issue #64. Starting develop before governance merge: `801f1ea119d2d35b50e642518bf5da3e7d74ad0a`. Expected unchanged `main` until promotion: `50fc217ab54ea7c526994b98266a1914accc8d34`. **Invariants:** (1) release promotion only; (2) no new product implementation; (3) PEV-044–046 classification remains `FUTURE_ENTERPRISE`; (4) PEV-048–051 and PEV-054–057 remain deferred; (5) source evidence → structured understanding → rubric decisions → evaluation ledger → human governance → published result → learning evidence remains authoritative; (6) ReviewAction/audit history remains append-only; (7) publication governance is not weakened; (8) grievance creates versioned new evaluation evidence rather than mutating historical ledger truth; (9) `SUPERSEDED` publications remain historical but excluded from current effective analytics/mastery; (10) B15 locked historical gold evidence remains valid; (11) tenant isolation remains mandatory; (12) no automatic AI provider/model deployment; (13) no Kubernetes, Temporal, Kafka, microservices split, GraphQL, Firebase, Supabase or serverless-only architecture; (14) release content must match the approved develop tree exactly; (15) historical main/develop divergence must not be hand-resolved. Exact-tree release promotion is mandatory (same conflict-safe snapshot pattern as CVB PR #40 / APP-007 PR #58). |

---

## Detailed Entry — APP-008

### APP-008 — Enterprise Grading, Moderation & Grievance Tranche

| Field | Value |
|-------|-------|
| **Date** | 2026-09-09 |
| **Decision** | Approve activation of PEV-044 (Horizontal Grading), PEV-045 (Moderation Workflows), and PEV-046 (Re-Evaluation & Grievance) together as the first bounded `FUTURE_ENTERPRISE` implementation tranche following Post-CVB Phase 1 release. B16 shall deliver tenant-scoped horizontal question-level grading pools/work items, configurable ordered moderation stages with separation of duties, and formal post-publication grievance cases that create a new EvaluationRun version and superseding PublishedResult—without replacing the evaluation ledger, without AI final authority, and without promoting feature work to `main`. |
| **Approver** | Founder / Product Architect |
| **Status** | APPROVED |
| **Notes** | Implementation starts from current post-Phase-1 `develop` and follows `docs/engineering/DEVELOPMENT_WORKFLOW.md`: one Cursor implementation engineer owns backend, frontend, contracts, migrations, tests, E2E, CI, PR, and merge execution in one bounded feature PR to `develop`. **Invariants:** (1) immutable source evidence → structured understanding → rubric decisions → evaluation ledger → human governance → published result → learning evidence remains authoritative; (2) no second score source; (3) ReviewAction history is append-only; (4) publication blocked until required governance completes; (5) grievance re-evaluation uses a new run_number and does not mutate the original run/ledger; (6) superseded publications must not double-count in analytics/mastery; (7) locked B15 gold cases remain valid against historical results; (8) tenant isolation; (9) no `main` promotion. PEV-044–046 remain formally classified `FUTURE_ENTERPRISE` (implementation under APP-008/B16 does not change release-state classification). PEV-048, PEV-049, PEV-050, PEV-051, PEV-054, PEV-055, PEV-056, and PEV-057 remain deferred. Do not introduce Kubernetes, Temporal, Kafka, microservices split, GraphQL, Firebase, Supabase, or serverless-only architecture. |

---

## Detailed Entry — APP-007

### APP-007 — Post-CVB Phase 1 Release Promotion

| Field | Value |
|-------|-------|
| **Date** | 2026-09-09 |
| **Decision** | Founder approves release promotion of the completed post-CVB Phase 1 `AFTER_CLIENT_APPROVAL` work from the independently verified `develop` candidate to `main`. Scope includes implementation already completed under APP-003 / B12 (PEV-035–038), APP-004 / B13 (PEV-041), APP-005 / B14 + B14.1 (PEV-043), and APP-006 / B15 + B15.1 (PEV-058–059). Milestone name: **Post-CVB Phase 1**. |
| **Approver** | Founder / Product Architect |
| **Status** | APPROVED |
| **Notes** | Starting verified develop candidate before this governance merge: `a3905bdce04a684af4cf2b1617a183540ed0a264`. Expected unchanged `main` until promotion: `30c96af951ce418eb446beb7c35b679e3697b047`. **Governance invariants:** (1) no new product scope; (2) no FUTURE_ENTERPRISE activation; (3) requirement release-state classifications remain unchanged; (4) release promotion only; (5) evaluation-ledger authority unchanged; (6) human approval before publication unchanged; (7) immutable source evidence unchanged; (8) tenant isolation unchanged; (9) B15 regression/gold benchmark invariants unchanged; (10) no automatic AI provider/model deployment; (11) release content must match the approved develop release tree exactly; (12) do not hand-resolve historical main/develop divergence in a way that changes content. Deferred FUTURE_ENTERPRISE remains: PEV-044, PEV-045, PEV-046, PEV-048, PEV-049, PEV-050, PEV-051, PEV-054, PEV-055, PEV-056, PEV-057. Promotion uses the conflict-safe exact-tree snapshot pattern previously used for CVB v0.1 (PR #40). |

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
| 1.3 | 2026-09-10 | Release workflow | APP-013 approves Answer Intelligence & Outcome Reporting release promotion of APP-012 / B18 + B18.1 + B18.2 (PEV-050–051) to main |
| 1.2 | 2026-09-10 | Governance workflow | APP-012 activates FUTURE_ENTERPRISE PEV-050–051 B18 answer clustering & CO/PO outcome reporting tranche |
| 1.1 | 2026-09-10 | Release workflow | APP-011 approves Assessment Quality & Calibration release promotion of APP-010 / B17 + B17.1 (PEV-048–049) to main |
| 1.0 | 2026-09-10 | Governance workflow | APP-010 activates FUTURE_ENTERPRISE PEV-048–049 B17 assessment quality & evaluator calibration tranche |
| 0.9 | 2026-09-09 | Release workflow | APP-009 approves Enterprise Operations release promotion of APP-008 / B16 + B16.1 (PEV-044–046) to main |
| 0.8 | 2026-09-09 | Governance workflow | APP-008 activates FUTURE_ENTERPRISE PEV-044–046 B16 enterprise grading/moderation/grievance tranche |
| 0.7 | 2026-09-09 | Release workflow | APP-007 approves Post-CVB Phase 1 release promotion of AFTER_CLIENT_APPROVAL work to main |
| 0.6 | 2026-09-09 | Governance workflow | APP-006 activates final post-CVB PEV-058–059 AI quality benchmark & regression gate tranche |
| 0.5 | 2026-09-08 | Governance workflow | APP-005 activates post-B13 PEV-043 reassessment & mastery update tranche |
| 0.4 | 2026-09-08 | Governance workflow | APP-004 activates post-CVB PEV-041 curriculum resource assignment tranche |
| 0.3 | 2026-09-07 | Governance workflow | APP-003 activates first post-CVB PEV-035–038 tranche |
| 0.2 | 2026-09-07 | Release workflow | APP-002 CVB v0.1 release promotion approval |
| 0.1 | 2026-09-04 | Cursor A (bootstrap) | Initial log with APP-001 Day 1 architecture approval |
