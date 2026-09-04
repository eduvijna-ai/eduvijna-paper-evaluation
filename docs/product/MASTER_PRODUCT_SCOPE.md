# EduVijna Paper Evaluation — Master Product Scope

**Product:** EduVijna Enterprise Paper Evaluation  
**Release target:** Client Validation Build (CVB) v0.1  
**Timeline:** 30 days from bootstrap  
**Status:** Active — Day 1 architecture contract approved  
**Last updated:** 2026-09-04

---

## 1. Product Vision

EduVijna is an **enterprise AI-assisted handwritten assessment platform** for schools, colleges, and coaching institutions. The production input is **raw, unmarked handwritten answer sheets** — not pre-digitized responses or scantron forms.

The platform ingests physical evidence, produces structured understanding of student work, evaluates against institution-approved rubrics, and surfaces learning evidence — while preserving **teacher and institution authority** over every published result.

**Design principle:** AI proposes; institution/teacher approves. No unconstrained model output becomes a final grade or report.

**Target users (full product):**

| Persona | Primary value |
|---------|---------------|
| Teacher / Evaluator | Faster, consistent marking with override control |
| Academic coordinator | Class analytics, curriculum alignment, quality oversight |
| Student | Question-level feedback and improvement path |
| Parent / Guardian | Understandable progress summary |
| Institution admin | Multi-tenant governance, audit, integration |
| Platform operator | Model quality, regression safety, tenant isolation |

**CVB v0.1 focus:** Mathematics assessments for a single-tenant pilot institution, proving the end-to-end vertical slice from raw upload to published reports and basic adaptive-learning recommendations.

---

## 2. Core Evaluation Pipeline

All product capabilities ultimately serve this canonical pipeline. No feature may bypass it.

```
source evidence
    → structured understanding
    → rubric decisions
    → evaluation ledger
    → human approval
    → published result
    → learning evidence
```

| Stage | Meaning | Key artifacts |
|-------|---------|---------------|
| **Source evidence** | Immutable raw uploads (PDF/images), roster, question paper, approved answer key & rubric | `Submission`, `SubmissionPage`, object-storage blobs |
| **Structured understanding** | Identity resolution, page/region detection, transcription, question mapping | `AnswerRegion`, `QuestionAnswerMapping`, confidence scores |
| **Rubric decisions** | Criterion-level AI proposals against approved rubric version | `QuestionEvaluation`, `CriterionEvaluation` |
| **Evaluation ledger** | Canonical, append-only record of every decision, deduction, and confidence | Evaluation ledger rows (see architecture doc) |
| **Human approval** | Teacher review, override, escalation for low-confidence cases | `ReviewAction`, workflow states |
| **Published result** | Evaluated PDF, student/parent/teacher reports | `PublishedResult`, generated documents |
| **Learning evidence** | Mastery signals, weakness mapping, curriculum-constrained recommendations | `MasteryEvidence`, `LearningRecommendation`, `ImprovementAssessment` |

**Hard constraint:** Final reports and published scores MUST NOT be produced from a single unconstrained LLM call over an entire PDF. Every output derives from ledger-backed, rubric-scoped, auditable steps.

---

## 3. Full Product Capability Register (65 Capabilities)

Every capability below is **in scope for the EduVijna product**. CVB v0.1 implements a vertical slice; non-CVB capabilities remain documented and scheduled — none are deleted.

### 3.1 Assessment & Content Setup

| # | Capability | CVB note |
|---|------------|----------|
| 1 | Create assessments (with versioning lifecycle) | BUILD_NOW — draft → ready → active |
| 2 | Accept question paper upload and structured representation | BUILD_NOW |
| 3 | Accept teacher-provided answer keys and rubrics when available | BUILD_NOW |
| 4 | AI-propose answer key/rubric when unavailable; teacher must approve before use | BUILD_NOW — contract + approval workflow |
| 30 | Map every question to curriculum hierarchy (grade → subject → unit → chapter → topic → subtopic → concept → skill → learning outcome) | BUILD_NOW — hierarchy model + tagging |
| 31 | Maintain prerequisite concept relationships as directed edges | BUILD_NOW — prerequisite graph |
| 47 | Question, rubric, and test analytics | BUILD_NOW basic; advanced metrics deferred |

### 3.2 Institution & Identity

| # | Capability | CVB note |
|---|------------|----------|
| 5 | Import institution student database / roster | BUILD_NOW |
| 52 | Enterprise role-based access control (RBAC) | BUILD_NOW — roles foundation |
| 53 | Multi-tenancy with tenant-scoped data isolation | BUILD_NOW — tenant-aware from first migration |

### 3.3 Submission Ingestion & Understanding

| # | Capability | CVB note |
|---|------------|----------|
| 6 | Upload raw handwritten student answer sheets | BUILD_NOW — upload contract |
| 7 | Retrieve student roll number / name from handwritten paper | BUILD_NOW — identity extraction contract |
| 8 | Automatically match student to institution roster with confidence | BUILD_NOW |
| 9 | Route uncertain identity matches to human review (never silent auto-assign) | BUILD_NOW |
| 10 | Detect pages and answer regions on each sheet | BUILD_NOW — page model + regions |
| 11 | Map handwritten answer content to question / subquestion | BUILD_NOW |
| 12 | Support continuation pages and extra sheets | BUILD_NOW |
| 13 | Understand handwriting, mathematics, tables, diagrams, and structured work | BUILD_NOW — Mathematics focus |
| 23 | Preserve original source paper as immutable evidence | BUILD_NOW |

### 3.4 Evaluation & Scoring

| # | Capability | CVB note |
|---|------------|----------|
| 14 | Evaluate student work against approved answer key / rubric | BUILD_NOW |
| 15 | Award step-level partial credit | BUILD_NOW — criterion-level scoring |
| 16 | Support alternative valid solution methods | BUILD_NOW — representation in ledger |
| 17 | Support error-carried-forward (ECF) policies | BUILD_NOW — ECF representation |
| 18 | Identify first incorrect / divergent step | BUILD_NOW |
| 19 | Digitally mark original paper: ✓ correct, ✕ incorrect, △ partial, awarded/deducted marks, short reason | BUILD_NOW — annotations |
| 20 | Show final question mark beside the handwritten answer | BUILD_NOW — score reconciliation |
| 21 | Explain exactly why marks were deducted | BUILD_NOW — deduction reasons in ledger |
| 22 | Allow teacher / evaluator review and override of AI proposals | BUILD_NOW |
| 34 | Categorize errors: concept, formula, method, calculation, algebra, sign, substitution, notation, unit, diagram, interpretation, incomplete, logic/reasoning, presentation, final-answer | BUILD_NOW — error taxonomy |

### 3.5 Confidence, Review & Governance

| # | Capability | CVB note |
|---|------------|----------|
| 61 | Measure identity, mapping, transcription, and evaluation confidence **separately** | BUILD_NOW |
| 62 | Never expose a single meaningless generic "AI confidence" score | BUILD_NOW |
| 63 | Route low-confidence and unreadable cases to mandatory human review | BUILD_NOW |
| 64 | AI proposes; institution / teacher remains final authority | BUILD_NOW — governing principle |
| 65 | Prohibit final report generation from one unconstrained LLM call over an entire PDF | BUILD_NOW — architectural guardrail |
| 24 | Preserve complete evaluation and audit history | BUILD_NOW — audit-event foundation |
| 60 | Store model, provider, template, and prompt version metadata per AI invocation | BUILD_NOW — `AiExecutionRecord` |

### 3.6 Outputs & Reporting

| # | Capability | CVB note |
|---|------------|----------|
| 25 | Generate evaluated / annotated PDF output | BUILD_NOW — output contract |
| 26 | Generate student question-by-question evaluation report | BUILD_NOW |
| 27 | Generate understandable parent report | BUILD_NOW |
| 28 | Generate deeper teacher report | BUILD_NOW |
| 29 | Generate test / class analytics | BUILD_NOW — basic analytics |

### 3.7 Learning Analytics & Adaptive Path

| # | Capability | CVB note |
|---|------------|----------|
| 32 | Determine concepts / topics where student is strong or weak | BUILD_NOW |
| 33 | Separate concept mastery from execution accuracy | BUILD_NOW — mastery evidence model |
| 35 | Analyze repeated errors across submissions | AFTER_CLIENT_APPROVAL |
| 36 | Analyze potentially avoidable / recoverable marks | AFTER_CLIENT_APPROVAL |
| 37 | Maintain longitudinal mastery across assessments | AFTER_CLIENT_APPROVAL |
| 38 | Build student mistake notebook | AFTER_CLIENT_APPROVAL |
| 39 | Produce curriculum-only adaptive learning recommendations (no open-web content) | BUILD_NOW |
| 40 | Repair prerequisite gaps before advancing to dependent topics | BUILD_NOW — prerequisite-aware recommendations |
| 41 | Assign approved curriculum resources and practice materials | AFTER_CLIENT_APPROVAL |
| 42 | Generate personalized improvement assessment blueprint | BUILD_NOW — blueprint contract |
| 43 | Reassess and update mastery after improvement work | AFTER_CLIENT_APPROVAL |

### 3.8 Enterprise Operations (Deferred)

| # | Capability | Release state |
|---|------------|---------------|
| 44 | Horizontal grading (multiple evaluators, workload distribution) | FUTURE_ENTERPRISE |
| 45 | Moderation and multi-stage approval workflows | FUTURE_ENTERPRISE |
| 46 | Re-evaluation and grievance handling | FUTURE_ENTERPRISE |
| 48 | Question difficulty and discrimination analytics | FUTURE_ENTERPRISE |
| 49 | Evaluator consistency measurement and calibration | FUTURE_ENTERPRISE |
| 50 | Answer clustering for pattern discovery | FUTURE_ENTERPRISE |
| 51 | Course Outcome (CO) / Program Outcome (PO) and learning-outcome reporting | FUTURE_ENTERPRISE |
| 54 | SSO / SAML / OIDC authentication and SCIM provisioning | FUTURE_ENTERPRISE |
| 55 | LMS / SIS / LTI integrations, public API, and webhooks | FUTURE_ENTERPRISE |
| 56 | Additional subjects: Physics, Chemistry, Statistics, Accounting, structured descriptive subjects | FUTURE_ENTERPRISE (Mathematics only in CVB) |
| 57 | Multilingual handwriting support | FUTURE_ENTERPRISE |
| 58 | Gold evaluation benchmark dataset maintenance | AFTER_CLIENT_APPROVAL |
| 59 | AI evaluation regression tests before model / provider releases | AFTER_CLIENT_APPROVAL |

---

## 4. CVB v0.1 — 30-Day Vertical Slice (`BUILD_NOW`)

The Client Validation Build delivers a **demonstrable end-to-end path** for one pilot institution evaluating Mathematics handwritten papers. Scope is intentionally narrow in subject and integration surface; depth is intentionally high in evaluation correctness, auditability, and human-in-the-loop control.

### 4.1 In Scope for CVB v0.1

**Foundation & tenancy**

- Tenant-aware data model with institution, users, roles, permissions
- Roles foundation (teacher, evaluator, admin — extensible to enterprise RBAC)
- Audit-event foundation for all significant state changes

**Curriculum & assessment setup**

- Curriculum hierarchy model with prerequisite edges
- Question paper ingestion and question / subquestion hierarchy
- Answer key and rubric with versioning
- AI-proposed answer key / rubric contract with mandatory teacher approval state

**Roster & submission**

- Student roster import (CSV/API contract; CSV for CVB)
- Raw paper upload contract (PDF/images → object storage)
- Original source preservation (immutable blobs, content-addressed references)
- Page model for multi-page submissions
- Continuation page and extra-sheet support

**Understanding pipeline**

- Student identity extraction and roster matching contract
- Identity confidence scoring and review queue
- Answer region detection on pages
- Answer-to-question mapping with confidence
- Manual mapping correction workflow
- Structured understanding for Mathematics: handwriting, expressions, steps, tables, basic diagrams

**Evaluation core**

- Evaluation ledger as canonical source of truth
- Criterion-level scoring with partial credit
- Error taxonomy classification
- First-divergence step representation
- ECF (error-carried-forward) representation
- Alternative-method representation
- Separate confidence dimensions (identity, mapping, transcription, evaluation)
- Teacher review, override, and escalation
- Digital annotations on evaluated output
- Final score reconciliation per question and assessment

**Outputs**

- Evaluated-paper output contract (annotated PDF)
- Student report contract (question-by-question)
- Parent report contract (plain-language summary)
- Teacher report contract (diagnostic depth)
- Basic test / class analytics

**Learning evidence (curriculum-constrained)**

- Concept / topic weakness identification
- Mastery evidence (separating concept vs execution)
- Curriculum-only learning recommendations
- Prerequisite-aware recommendation ordering
- Improvement-assessment blueprint generation

**Platform & engineering**

- Modular monolith: FastAPI + Celery + PostgreSQL + Redis + MinIO
- AI provider abstraction with execution traceability
- Docker Compose local/dev environment
- CI: lint, typecheck, test, contract validation
- Synthetic demo data only — no real student PII in repository

### 4.2 CVB v0.1 Success Criteria

1. A teacher can create a Mathematics assessment, upload or approve a rubric, and import a roster.
2. Raw handwritten sheets upload, identity resolves (or enters review), and answers map to questions.
3. AI proposes criterion-level evaluations; teacher can accept or override each question.
4. Published outputs include annotated PDF and three report types derived from the evaluation ledger.
5. Basic class analytics and curriculum-constrained learning recommendations are generated.
6. Every published score is traceable to ledger rows, rubric version, model metadata, and reviewer action.
7. Low-confidence paths never auto-publish without human decision.

### 4.3 Explicitly Out of CVB v0.1 (Non-Goals)

These are **intentionally excluded** from the 30-day build. They are not deleted from the product roadmap.

| Category | Non-goal |
|----------|----------|
| Orchestration | Kubernetes, Temporal, Kafka |
| Architecture style | Microservices split, GraphQL API, serverless-only deployment |
| Mobile | Native iOS / Android clients |
| BaaS | Firebase, Supabase |
| Identity | SSO / SAML / OIDC / SCIM |
| Integrations | LMS / SIS / LTI / webhooks |
| Grading ops | Horizontal grading pools, moderation chains, grievance workflows |
| Advanced analytics | Item difficulty/discrimination, evaluator consistency, answer clustering, CO/PO reporting |
| Subjects | Physics, Chemistry, Statistics, Accounting, descriptive subjects |
| Language | Multilingual handwriting |
| Learning (advanced) | Mistake notebook, longitudinal mastery, resource assignment, reassessment loops |
| Quality ops | Gold benchmark dataset, pre-release AI regression suite |

---

## 5. Deferred Release Tracks

### 5.1 `AFTER_CLIENT_APPROVAL`

Capabilities scheduled immediately after CVB sign-off, before full enterprise rollout:

- Repeated-error analysis and recoverable-marks insight
- Longitudinal mastery tracking across assessments
- Student mistake notebook
- Approved curriculum resource assignment
- Reassessment and mastery update loops
- Gold evaluation benchmark dataset
- AI evaluation regression gate before model/provider upgrades

**Gate:** Pilot institution validates CVB outputs; founder + client approve expansion budget and priority order.

### 5.2 `FUTURE_ENTERPRISE`

Capabilities required for multi-institution enterprise deployment:

- Horizontal grading and evaluator workload management
- Moderation and multi-stage approval
- Re-evaluation and grievance workflows
- Advanced psychometric analytics (difficulty, discrimination)
- Evaluator consistency and calibration
- Answer clustering
- CO / PO / formal learning-outcome reporting
- Enterprise SSO (SAML / OIDC) and SCIM provisioning
- LMS / SIS / LTI / API / webhook integrations
- Subject expansion beyond Mathematics
- Multilingual handwriting

**Gate:** Enterprise contract, integration requirements, and compliance review.

---

## 6. Mandated Technology Stack (CVB)

Architecture decisions are **mandatory** for CVB. Substitutions require founder approval logged in `docs/FOUNDER_APPROVAL_LOG.md`.

### Frontend (Cursor B)

| Layer | Choice |
|-------|--------|
| Framework | Next.js, React, TypeScript |
| Styling | Tailwind CSS |
| Data fetching | TanStack Query |
| Forms / validation | React Hook Form, Zod |
| PDF viewing | PDF.js (post-CVB UI milestones) |
| Testing | Vitest, Playwright |

### Backend (Cursor A)

| Layer | Choice |
|-------|--------|
| Language | Python 3.12 |
| API | FastAPI, Pydantic v2 |
| ORM | SQLAlchemy 2.x (async) |
| Migrations | Alembic |
| Database | PostgreSQL 16 |
| Quality | pytest, Ruff, mypy |

### Async & Storage (Cursor A)

| Layer | Choice |
|-------|--------|
| Job queue | Redis + Celery |
| Object storage | S3-compatible (MinIO locally) |
| Math verification | SymPy |
| PDF / image | PyMuPDF |

### Platform

| Layer | Choice |
|-------|--------|
| Deployment | Docker, Docker Compose |
| Monorepo | pnpm workspaces (JS/TS); isolated Python envs in `apps/api`, `workers` |
| Contracts | OpenAPI + JSON Schema in `packages/contracts` |

**Pattern:** Modular monolith — one deployable API with bounded internal modules, not microservices.

---

## 7. Cursor A vs Cursor B Ownership

Parallel development requires strict path ownership to prevent merge conflicts and architectural drift.

### Cursor A — Backend, AI, Infrastructure

| Path / domain | Responsibility |
|---------------|----------------|
| `apps/api/**` | FastAPI application, business endpoints, middleware |
| `workers/**` | Celery tasks, async pipeline workers |
| `ai/**` | AI provider abstractions, prompt contracts, execution records |
| `infra/**` | Docker, Compose, bootstrap/verify scripts |
| `database/migrations/**` | Alembic migrations, schema evolution |
| Backend tests | pytest suites |
| Architecture docs | Domain model, ledger, rubric, workflow, ADRs |

### Cursor B — Frontend

| Path / domain | Responsibility |
|---------------|----------------|
| `apps/web/**` | Next.js application, pages, client logic |
| `packages/ui/**` | Shared accessible component library |
| Frontend tests | Vitest unit tests |
| Playwright E2E | End-to-end user flows |

### Shared (requires contract alignment)

| Path | Rule |
|------|------|
| `packages/contracts/**` | OpenAPI + JSON Schema — **both cursors** must align API changes here before implementation |
| `docs/product/**` | Product scope and requirements — architect/founder authority |
| Root config | Coordinated changes via PR review |

**Integration contract:** Cursor B consumes REST APIs defined in `packages/contracts/openapi.yaml`. Cursor A implements those contracts. Neither cursor modifies the other's owned paths without explicit coordination.

---

## 8. Related Documents

| Document | Purpose |
|----------|---------|
| [REQUIREMENTS_REGISTER.md](./REQUIREMENTS_REGISTER.md) | PEV-NNN requirement IDs, priorities, release states |
| [../FOUNDER_APPROVAL_LOG.md](../FOUNDER_APPROVAL_LOG.md) | Architecture decision approvals |
| [../architecture/ADR_INDEX.md](../architecture/ADR_INDEX.md) | Architecture Decision Records |
| [../architecture/DOMAIN_MODEL.md](../architecture/DOMAIN_MODEL.md) | Entity and aggregate definitions |
| [../architecture/EVALUATION_LEDGER.md](../architecture/EVALUATION_LEDGER.md) | Ledger schema and invariants |

---

## 9. Document Control

| Version | Date | Author | Change |
|---------|------|--------|--------|
| 0.1 | 2026-09-04 | Cursor A (bootstrap) | Initial master scope from architecture contract |
