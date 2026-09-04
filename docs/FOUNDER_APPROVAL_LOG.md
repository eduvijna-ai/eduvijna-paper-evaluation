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
| 2026-09-04 | **Mandatory architecture contract for Day 1 bootstrap (CVB v0.1).** Approves: modular monolith; Python 3.12 + FastAPI + SQLAlchemy 2 async + Alembic + PostgreSQL 16; Redis + Celery async; S3-compatible storage (MinIO local); Next.js + React + TypeScript + Tailwind frontend stack; pnpm monorepo; SymPy + PyMuPDF; Docker Compose deployment. **Prohibits for CVB:** Kubernetes, Temporal, Kafka, microservices split, GraphQL, native mobile, Firebase, Supabase, serverless-only architecture. **Approves** core pipeline: source evidence → structured understanding → rubric decisions → evaluation ledger → human approval → published result → learning evidence. **Approves** tenant-aware data model from first migration; evaluation ledger as source of truth; immutable raw source papers; human approval required before publication; AI provider abstraction. **Approves** 30-day BUILD_NOW vertical slice per `docs/product/MASTER_PRODUCT_SCOPE.md` and requirements PEV-001 – PEV-078 in `docs/product/REQUIREMENTS_REGISTER.md`. **Approves** Cursor A/B ownership split per master scope §7. | Founder / Product Architect | APPROVED | Day 1 bootstrap foundation. ADRs ADR-001 through ADR-010 derive from this decision. Repository: `eduvijna/eduvijna-paper-evaluation`. No requirement from business context may be deleted — deferred items use AFTER_CLIENT_APPROVAL or FUTURE_ENTERPRISE only. |

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
| 0.1 | 2026-09-04 | Cursor A (bootstrap) | Initial log with APP-001 Day 1 architecture approval |
