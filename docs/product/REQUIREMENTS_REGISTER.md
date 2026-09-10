# EduVijna Paper Evaluation — Requirements Register

**Product:** EduVijna Enterprise Paper Evaluation  
**Release target:** CVB v0.1  
**Last updated:** 2026-09-08  
**Total requirements:** 78 (65 product capabilities + 13 architectural contract requirements)

---

## Release State Definitions

| State | Meaning |
|-------|---------|
| **BUILD_NOW** | In scope for CVB v0.1 (30-day Client Validation Build) |
| **AFTER_CLIENT_APPROVAL** | Scheduled immediately after CVB pilot sign-off |
| **FUTURE_ENTERPRISE** | Required for enterprise rollout; not in CVB or post-CVB Phase 1 |

> **Rule:** No requirement may use `DROPPED`, `TODO`, or ownerless states. Every capability from business context is retained.

---

## Priority Definitions

| Priority | Meaning |
|----------|---------|
| **P0** | Blocking for CVB demo / vertical slice; must ship in BUILD_NOW |
| **P1** | Important for product completeness; may ship BUILD_NOW or AFTER_CLIENT_APPROVAL |
| **P2** | Enterprise or enhancement tier; FUTURE_ENTERPRISE or AFTER_CLIENT_APPROVAL |

---

## Requirements Summary by Release State

| Release State | Count | PEV IDs |
|---------------|-------|---------|
| BUILD_NOW | 59 | PEV-001 – PEV-034, PEV-039, PEV-040, PEV-042, PEV-047, PEV-052, PEV-053, PEV-060 – PEV-078 |
| AFTER_CLIENT_APPROVAL | 8 | PEV-035, PEV-036, PEV-037, PEV-038, PEV-041, PEV-043, PEV-058, PEV-059 |
| FUTURE_ENTERPRISE | 11 | PEV-044, PEV-045, PEV-046, PEV-048, PEV-049, PEV-050, PEV-051, PEV-054, PEV-055, PEV-056, PEV-057 |

---

## Section A — Product Capabilities (PEV-001 – PEV-065)

Mapped 1:1 from the 65 business capabilities in the architecture contract.

| ID | Name | Description | Priority | Release State | Acceptance Intent | Owner / Domain |
|----|------|-------------|----------|---------------|-------------------|----------------|
| PEV-001 | Assessment Creation | System shall allow teachers to create assessments with versioned lifecycle (draft → rubric review → ready → active → closed → archived). | P0 | BUILD_NOW | Teacher creates assessment; version history preserved; state transitions auditable. | Assessment & Content |
| PEV-002 | Question Paper Ingestion | System shall accept question paper uploads and represent questions and subquestions in a structured hierarchy linked to the assessment version. | P0 | BUILD_NOW | Question paper parses to question/subquestion tree; linked to assessment version. | Assessment & Content |
| PEV-003 | Teacher Answer Key & Rubric | System shall accept teacher-provided answer keys and rubrics, versioned and bound to assessment versions. | P0 | BUILD_NOW | Answer key and rubric stored with version IDs; retrievable for evaluation runs. | Assessment & Content / Rubric |
| PEV-004 | AI-Proposed Answer Key & Rubric | When teacher material is unavailable, AI may propose answer key and rubric; proposals remain unusable for evaluation until teacher approval. | P0 | BUILD_NOW | AI proposal enters RUBRIC_REVIEW state; evaluation blocked until explicit approval recorded. | Assessment & Content / AI |
| PEV-005 | Student Roster Import | System shall import institution student database / class roster with tenant-scoped identifiers. | P0 | BUILD_NOW | CSV or API import creates student records scoped to tenant, class, academic year. | Tenancy & Identity |
| PEV-006 | Raw Paper Upload | System shall accept raw, unmarked handwritten answer sheet uploads (PDF/images) per submission. | P0 | BUILD_NOW | Upload stores immutable blob in object storage; submission record created with UPLOADED state. | Submission & Ingestion |
| PEV-007 | Handwritten Identity Extraction | System shall extract student roll number and/or name from handwritten paper content. | P0 | BUILD_NOW | Identity fields extracted with structured output; stored on submission with extraction metadata. | Understanding Pipeline / AI |
| PEV-008 | Roster Matching | System shall automatically match extracted identity to institution roster candidates with a confidence score. | P0 | BUILD_NOW | Match produces ranked candidates; highest-confidence match proposed with score ≥ threshold logic documented. | Understanding Pipeline |
| PEV-009 | Identity Review Routing | Uncertain identity matches shall route to human review; system shall never silently assign wrong student. | P0 | BUILD_NOW | Below-threshold matches enter IDENTITY_REVIEW; no evaluation proceeds on unconfirmed identity. | Understanding Pipeline / Governance |
| PEV-010 | Page & Region Detection | System shall detect submission pages and answer regions within each page. | P0 | BUILD_NOW | Each page modeled; answer regions bounded with coordinates and page references. | Understanding Pipeline / AI |
| PEV-011 | Answer-Question Mapping | System shall map handwritten answer regions to question and subquestion identifiers. | P0 | BUILD_NOW | Each region linked to question_id; mapping stored with PROPOSED or CONFIRMED state. | Understanding Pipeline |
| PEV-012 | Continuation Page Support | System shall support continuation pages and extra sheets beyond primary answer booklet pages. | P0 | BUILD_NOW | Continuation pages linked to parent question; ordering preserved in mapping model. | Understanding Pipeline |
| PEV-013 | Structured Work Understanding | System shall understand handwriting, mathematics, tables, diagrams, and structured student work (Mathematics focus in CVB). | P0 | BUILD_NOW | Transcription produces structured representation for math steps, expressions, tables; confidence scored separately. | Understanding Pipeline / AI |
| PEV-014 | Rubric-Based Evaluation | System shall evaluate transcribed answers against the approved rubric version for the assessment. | P0 | BUILD_NOW | Evaluation run produces criterion-level proposals bound to rubric_version_id. | Evaluation / AI |
| PEV-015 | Step-Level Partial Credit | System shall award partial credit at criterion / step level according to rubric rules. | P0 | BUILD_NOW | Criterion marks sum correctly; partial marks recorded per criterion with max mark enforced. | Evaluation / Rubric |
| PEV-016 | Alternative Valid Methods | System shall recognize and score alternative valid solution methods defined in rubric or detected as VALID_ALTERNATIVE. | P0 | BUILD_NOW | Alternative method flagged in ledger; full credit possible when rubric permits. | Evaluation / Rubric |
| PEV-017 | Error-Carried-Forward (ECF) | System shall apply institution ECF policies when later steps depend on earlier errors. | P0 | BUILD_NOW | ECF policy representation stored; downstream scoring reflects configured ECF behavior. | Evaluation / Rubric |
| PEV-018 | First Divergence Detection | System shall identify the first incorrect or divergent step in multi-step work. | P0 | BUILD_NOW | First divergence step index and reason recorded in evaluation ledger per question. | Evaluation / AI |
| PEV-019 | Digital Paper Marking | System shall digitally mark papers with ✓ correct, ✕ incorrect, △ partial, awarded marks, deducted marks, and short reason. | P0 | BUILD_NOW | Annotations render on evaluated PDF at region coordinates; symbols match ledger decisions. | Evaluation / Reporting |
| PEV-020 | Inline Final Question Marks | System shall display final question mark beside the handwritten answer on evaluated output. | P0 | BUILD_NOW | Final approved score visible per question on annotated PDF and reports. | Evaluation / Reporting |
| PEV-021 | Deduction Explanations | System shall explain exactly why marks were deducted for each criterion or step. | P0 | BUILD_NOW | Deduction reasons human-readable; sourced from ledger deduction_reasons field. | Evaluation / Reporting |
| PEV-022 | Teacher Review & Override | Teachers / evaluators shall review AI proposals and accept, override, or escalate any question evaluation. | P0 | BUILD_NOW | ReviewAction recorded; OVERRIDE updates final score; original AI proposal preserved in ledger. | Evaluation / Governance |
| PEV-023 | Immutable Source Preservation | Original uploaded papers shall remain immutable; no destructive edit of source evidence. | P0 | BUILD_NOW | Source blob content-addressed; re-upload creates new submission version, not overwrite. | Submission & Ingestion / Governance |
| PEV-024 | Complete Audit History | System shall preserve complete evaluation and audit history for all significant actions. | P0 | BUILD_NOW | AuditEvent append-only log; links to entity, actor, timestamp, payload hash. | Governance & Audit |
| PEV-025 | Evaluated Annotated PDF | System shall generate evaluated / annotated PDF from ledger and annotation data. | P0 | BUILD_NOW | PDF output contract validated; generated only after APPROVED submission state. | Reporting & Analytics |
| PEV-026 | Student Evaluation Report | System shall generate question-by-question student evaluation report from ledger (not raw LLM over PDF). | P0 | BUILD_NOW | Report sections map 1:1 to questions; scores and feedback trace to ledger rows. | Reporting & Analytics |
| PEV-027 | Parent Report | System shall generate understandable parent-facing summary report. | P0 | BUILD_NOW | Plain-language summary; no jargon; derived from ledger-backed explanations. | Reporting & Analytics / AI |
| PEV-028 | Teacher Diagnostic Report | System shall generate deeper teacher report with diagnostic detail per student and question. | P0 | BUILD_NOW | Includes error taxonomy, divergence, ECF, alternative method detail from ledger. | Reporting & Analytics |
| PEV-029 | Test & Class Analytics | System shall generate basic test and class-level analytics (score distribution, question performance). | P0 | BUILD_NOW | Class dashboard shows mean, median, question-level stats for published assessments. | Reporting & Analytics |
| PEV-030 | Curriculum Question Mapping | Every question shall map to curriculum hierarchy: grade → subject → unit → chapter → topic → subtopic → concept → skill → learning outcome. | P0 | BUILD_NOW | Question carries curriculum_node references; hierarchy navigable via generic tree model. | Curriculum |
| PEV-031 | Prerequisite Concept Graph | System shall maintain prerequisite concept relationships as directed edges in curriculum graph. | P0 | BUILD_NOW | Prerequisite edges stored; cycle detection on write; used by recommendation engine. | Curriculum |
| PEV-032 | Concept Strength & Weakness | System shall determine concepts and topics where each student is strong or weak based on evaluation evidence. | P0 | BUILD_NOW | Weakness list produced post-evaluation; tied to curriculum nodes with evidence links. | Adaptive Learning / Analytics |
| PEV-033 | Mastery vs Execution Separation | System shall separate concept mastery evidence from execution / calculation accuracy in analytics. | P0 | BUILD_NOW | MasteryEvidence distinguishes CONCEPT errors from CALCULATION/METHOD errors per taxonomy. | Adaptive Learning / Analytics |
| PEV-034 | Error Taxonomy Classification | System shall categorize errors using canonical codes: CONCEPT, FORMULA, METHOD, CALCULATION, ALGEBRA, SIGN, SUBSTITUTION, NOTATION, UNIT, DIAGRAM, INTERPRETATION, INCOMPLETE, LOGIC_REASONING, PRESENTATION, FINAL_ANSWER, plus review categories. | P0 | BUILD_NOW | Each criterion evaluation carries ≥1 taxonomy code; UNREADABLE not auto-marked wrong. | Evaluation / AI |
| PEV-035 | Repeated Error Analysis | System shall analyze repeated errors across multiple submissions for the same student. | P1 | AFTER_CLIENT_APPROVAL | Pattern report shows recurring error codes per student over time. **Implemented in B12 (APP-003 / Issue #42)** — release state unchanged. | Adaptive Learning / Analytics |
| PEV-036 | Recoverable Marks Analysis | System shall analyze potentially avoidable / recoverable marks lost to specific error types. | P1 | AFTER_CLIENT_APPROVAL | Report quantifies marks recoverable if specific error class corrected. **Implemented in B12 (APP-003 / Issue #42)** — release state unchanged. | Adaptive Learning / Analytics |
| PEV-037 | Longitudinal Mastery Tracking | System shall maintain mastery state across assessments over time. | P1 | AFTER_CLIENT_APPROVAL | MasteryState updates after each published assessment; historical trend available. **Implemented in B12 (APP-003 / Issue #42)** — release state unchanged. | Adaptive Learning |
| PEV-038 | Student Mistake Notebook | System shall build a persistent mistake notebook aggregating errors and corrections per student. | P1 | AFTER_CLIENT_APPROVAL | Notebook entries link to questions, error codes, and recommended practice. **Implemented in B12 (APP-003 / Issue #42)** — release state unchanged. | Adaptive Learning |
| PEV-039 | Curriculum-Only Recommendations | System shall produce adaptive learning recommendations constrained to approved curriculum content only (no open-web sources). | P0 | BUILD_NOW | Recommendations reference curriculum nodes only; external URLs blocked by policy. | Adaptive Learning |
| PEV-040 | Prerequisite-Aware Recommendations | Recommendations shall repair prerequisite gaps before advancing to dependent topics. | P0 | BUILD_NOW | Recommendation ordering respects prerequisite graph; gaps surfaced first. | Adaptive Learning / Curriculum |
| PEV-041 | Curriculum Resource Assignment | System shall assign approved curriculum resources and practice materials to students. | P1 | AFTER_CLIENT_APPROVAL | Teacher or system assigns resource IDs from approved catalog per recommendation. **Implemented in B13 (APP-004 / Issue #45)** — release state unchanged; no open-web discovery. | Adaptive Learning |
| PEV-042 | Improvement Assessment Blueprint | System shall generate personalized improvement assessment blueprint targeting identified weaknesses. | P0 | BUILD_NOW | Blueprint lists question templates / concept targets; contract schema validated; not full auto-generation in CVB. | Adaptive Learning / AI |
| PEV-043 | Reassessment & Mastery Update | System shall support reassessment after improvement work and update mastery accordingly. | P1 | AFTER_CLIENT_APPROVAL | Follow-up assessment links to blueprint; mastery delta computed and stored. **Implemented in B14 (APP-005 / Issue #48)** — release state unchanged. | Adaptive Learning |
| PEV-044 | Horizontal Grading | System shall support horizontal grading with multiple evaluators and workload distribution. | P2 | FUTURE_ENTERPRISE | Submissions assignable to evaluator pool; progress tracked per evaluator. **Implemented in B16 (APP-008 / Issue #60)** — release state unchanged. | Enterprise Operations |
| PEV-045 | Moderation Workflows | System shall support moderation and multi-stage approval beyond single-teacher review. | P2 | FUTURE_ENTERPRISE | Configurable approval chain; moderator role can accept/reject evaluator work. **Implemented in B16 (APP-008 / Issue #60)** — release state unchanged. | Enterprise Operations / Governance |
| PEV-046 | Re-Evaluation & Grievance | System shall support re-evaluation requests and formal grievance workflows. | P2 | FUTURE_ENTERPRISE | Grievance ticket triggers re-evaluation run; prior ledger preserved; new run versioned. **Implemented in B16 (APP-008 / Issue #60)** — release state unchanged. | Enterprise Operations / Governance |
| PEV-047 | Question & Rubric Analytics | System shall provide question, rubric, and test-level analytics beyond basic class stats. | P1 | BUILD_NOW | Basic question-level stats in CVB; advanced rubric analytics in later phases. | Reporting & Analytics |
| PEV-048 | Item Difficulty & Discrimination | System shall compute question difficulty and discrimination indices. | P2 | FUTURE_ENTERPRISE | Psychometric metrics computed on published cohorts above minimum N. **Implemented in B17 (APP-010 / Issue #67)**; **acceptance remediation B17.1 (Issue #71)** — release state unchanged. | Reporting & Analytics |
| PEV-049 | Evaluator Consistency | System shall measure and report evaluator consistency and support calibration. | P2 | FUTURE_ENTERPRISE | Inter-rater reliability metrics; calibration session support. **Implemented in B17 (APP-010 / Issue #67)**; **acceptance remediation B17.1 (Issue #71)** — release state unchanged. | Enterprise Operations / Analytics |
| PEV-050 | Answer Clustering | System shall cluster similar student answers for pattern discovery and rubric refinement. | P2 | FUTURE_ENTERPRISE | Clusters generated from transcription embeddings; reviewer can inspect clusters. | AI / Analytics |
| PEV-051 | CO / PO Reporting | System shall support Course Outcome (CO), Program Outcome (PO), and formal learning-outcome reporting. | P2 | FUTURE_ENTERPRISE | Questions map to CO/PO; aggregate attainment reports exportable. | Curriculum / Enterprise Reporting |
| PEV-052 | Enterprise RBAC | System shall support role-based access control with permissions bound to roles and tenant scope. | P0 | BUILD_NOW | Roles (admin, teacher, evaluator) enforced on API; permission checks not UI-only. | Tenancy & Identity / Governance |
| PEV-053 | Multi-Tenancy | System shall isolate data by tenant; all business records tenant-scoped with enforced query filters. | P0 | BUILD_NOW | Cross-tenant access impossible via API; tenant_id on all business tables. | Tenancy & Identity |
| PEV-054 | Enterprise SSO & SCIM | System shall support SSO via SAML/OIDC and user provisioning via SCIM. | P2 | FUTURE_ENTERPRISE | IdP-initiated login; SCIM sync creates/deactivates users per tenant. | Enterprise Integration / Identity |
| PEV-055 | LMS / SIS / LTI Integration | System shall integrate with LMS, SIS, LTI, public API, and outbound webhooks. | P2 | FUTURE_ENTERPRISE | LTI launch, grade passback, roster sync, webhook delivery with retry. | Enterprise Integration |
| PEV-056 | Multi-Subject Expansion | System shall support subjects beyond Mathematics: Physics, Chemistry, Statistics, Accounting, structured descriptive subjects. | P2 | FUTURE_ENTERPRISE | Subject-specific understanding modules pluggable via AI provider contract. | Understanding Pipeline / AI |
| PEV-057 | Multilingual Handwriting | System shall support multilingual handwriting recognition and evaluation. | P2 | FUTURE_ENTERPRISE | Language tag on submission; transcription model selected per language. | Understanding Pipeline / AI |
| PEV-058 | Gold Benchmark Dataset | System shall maintain a gold evaluation benchmark dataset for quality measurement. | P1 | AFTER_CLIENT_APPROVAL | Curated papers with human-adjudicated scores; versioned dataset in secure storage. **Implemented in B15 (APP-006 / Issue #53)** — release state unchanged. | Platform & AI / Quality |
| PEV-059 | AI Regression Testing | System shall run AI evaluation regression tests against gold dataset before model/provider releases. | P1 | AFTER_CLIENT_APPROVAL | CI gate blocks provider upgrade if regression metrics exceed threshold. **Implemented in B15 (APP-006 / Issue #53)** — release state unchanged. | Platform & AI / Quality |
| PEV-060 | AI Execution Metadata | Every AI invocation shall store model, provider, template, and prompt version metadata. | P0 | BUILD_NOW | AiExecutionRecord created per call; linked from evaluation and understanding artifacts. | Platform & AI |
| PEV-061 | Separate Confidence Dimensions | System shall measure identity, mapping, transcription, and evaluation confidence as separate dimensions. | P0 | BUILD_NOW | Four confidence fields on relevant records; no aggregation into single score for decisions. | Understanding Pipeline / Evaluation / Governance |
| PEV-062 | No Generic AI Confidence | System shall not expose a single meaningless generic "AI confidence" to users or downstream logic. | P0 | BUILD_NOW | UI and API document per-dimension confidence only; code review gate on confidence fields. | Platform & AI / Governance |
| PEV-063 | Mandatory Human Review for Low Confidence | Low-confidence and unreadable cases shall require human review before publication. | P0 | BUILD_NOW | UNREADABLE and below-threshold paths block PUBLISHED state until human action. | Governance & Audit |
| PEV-064 | Teacher Final Authority | AI proposes evaluations; institution / teacher remains final authority on all published results. | P0 | BUILD_NOW | No auto-publish path; APPROVED state requires human actor ID. | Governance & Audit |
| PEV-065 | No Whole-PDF LLM Reports | Final reports shall not be generated from one unconstrained LLM call over an entire PDF. | P0 | BUILD_NOW | Report generation reads ledger + structured artifacts only; architecture test verifies no bypass. | Platform & AI / Governance |

---

## Section B — Architectural Contract Requirements (PEV-066 – PEV-078)

Explicit BUILD_NOW vertical-slice contracts supplementing the 65 capabilities. Each maps to a named deliverable in the 30-day scope.

| ID | Name | Description | Priority | Release State | Acceptance Intent | Owner / Domain |
|----|------|-------------|----------|---------------|-------------------|----------------|
| PEV-066 | Evaluation Ledger | Canonical question-level evaluation ledger shall be the source of truth for all scores, deductions, confidences, and review actions. | P0 | BUILD_NOW | Ledger schema validates against `evaluation-ledger.schema.json`; no score published without ledger row. | Evaluation / Architecture |
| PEV-067 | Question Subquestion Hierarchy | Assessment content shall model explicit question and subquestion hierarchy with stable IDs across versions where applicable. | P0 | BUILD_NOW | Tree structure supports nested subquestions; mapping references subquestion IDs. | Assessment & Content |
| PEV-068 | Submission Page Model | Each submission shall decompose into ordered pages with metadata (page number, source file reference, dimensions). | P0 | BUILD_NOW | SubmissionPage records created per detected page; ordering deterministic. | Submission & Ingestion |
| PEV-069 | Raw Upload Contract | Raw paper upload shall conform to OpenAPI/contract spec: accepted formats, max size, virus-scan hook point, storage layout. | P0 | BUILD_NOW | Contract test passes; invalid uploads rejected with standard error envelope. | Submission & Ingestion / Contracts |
| PEV-070 | Answer Region Model | Detected answer regions shall store bounding geometry, page reference, and link to transcription artifacts. | P0 | BUILD_NOW | AnswerRegion entity populated after analyze_page; coordinates usable for annotation overlay. | Understanding Pipeline |
| PEV-071 | Mapping Manual Correction | Evaluators shall manually correct answer-question mappings when mapping confidence is insufficient. | P0 | BUILD_NOW | UI/API allows remap; REVIEW_REQUIRED → CONFIRMED transition audited. | Understanding Pipeline / Governance |
| PEV-072 | Audit Event Foundation | Foundation audit event stream shall capture create/update/delete on all governed entities from day one. | P0 | BUILD_NOW | audit_events table populated; correlation ID links API request to events. | Governance & Audit |
| PEV-073 | AI Provider Abstraction | All AI capabilities shall invoke through provider abstraction interfaces, never direct vendor SDK from API handlers. | P0 | BUILD_NOW | `ai/` module exposes documented interfaces; AiExecutionRecord for every call. | Platform & AI |
| PEV-074 | Core Pipeline Enforcement | System architecture shall enforce the pipeline: source evidence → structured understanding → rubric decisions → evaluation ledger → human approval → published result → learning evidence. | P0 | BUILD_NOW | Workflow states prevent stage skipping; ADR-006 and integration tests verify ordering. | Architecture / Governance |
| PEV-075 | Annotation Contract | Digital annotations shall conform to schema specifying symbol type, coordinates, text, linked criterion, and ledger reference. | P0 | BUILD_NOW | Annotation records validate; PDF renderer consumes annotation list. | Evaluation / Reporting |
| PEV-076 | Final Score Reconciliation | Final per-question and assessment totals shall reconcile AI proposed scores with human-approved final scores. | P0 | BUILD_NOW | Sum(criterion marks) = question score; sum(questions) = assessment score; override delta logged. | Evaluation |
| PEV-077 | Evaluated Paper Output Contract | Evaluated paper output shall conform to documented contract (format, layers, metadata, immutability after publish). | P0 | BUILD_NOW | Output artifact stored in object storage with content hash; contract schema validated. | Reporting & Analytics / Contracts |
| PEV-078 | Report Output Contracts | Student, parent, and teacher reports shall each conform to separate documented output contracts derived from ledger. | P0 | BUILD_NOW | Three contract schemas defined; generated reports validate; no free-form LLM-only body. | Reporting & Analytics / Contracts |

---

## Section C — BUILD_NOW Vertical Slice Checklist

Cross-reference of mandated 30-day deliverables to requirement IDs.

| Vertical slice item | Requirement ID(s) |
|---------------------|-------------------|
| Tenant-aware data model | PEV-053 |
| Roles foundation | PEV-052 |
| Curriculum hierarchy | PEV-030, PEV-031 |
| Question paper | PEV-002, PEV-067 |
| Answer key | PEV-003 |
| Rubric | PEV-003 |
| AI-proposed answer/rubric contract | PEV-004 |
| Teacher approval state | PEV-004, PEV-022, PEV-064 |
| Student roster | PEV-005 |
| Raw paper upload contract | PEV-006, PEV-069 |
| Original source preservation | PEV-023 |
| Page model | PEV-068, PEV-010 |
| Student identity extraction/matching contract | PEV-007, PEV-008 |
| Identity confidence/review | PEV-009, PEV-061, PEV-063 |
| Question/subquestion hierarchy | PEV-067, PEV-002 |
| Answer regions | PEV-010, PEV-070 |
| Answer-question mapping | PEV-011 |
| Mapping confidence/manual correction | PEV-061, PEV-071 |
| Continuation support | PEV-012 |
| Evaluation ledger | PEV-066, PEV-014 |
| Criterion-level scoring | PEV-015, PEV-014 |
| Partial credit | PEV-015 |
| Error taxonomy | PEV-034 |
| First-divergence representation | PEV-018 |
| ECF representation | PEV-017 |
| Alternative-method representation | PEV-016 |
| Evaluation confidence | PEV-061, PEV-062 |
| Teacher review/override | PEV-022 |
| Annotations | PEV-019, PEV-075 |
| Final score reconciliation | PEV-076, PEV-020 |
| Audit-event foundation | PEV-024, PEV-072 |
| Evaluated-paper output contract | PEV-025, PEV-077 |
| Student report contract | PEV-026, PEV-078 |
| Parent report contract | PEV-027, PEV-078 |
| Teacher report contract | PEV-028, PEV-078 |
| Basic test analytics | PEV-029, PEV-047 |
| Concept/topic weakness | PEV-032 |
| Mastery evidence | PEV-033 |
| Repeated error / recoverable marks / longitudinal mastery / mistake notebook | PEV-035 – PEV-038 (B12 / APP-003) |
| Curriculum-only learning recommendation | PEV-039 |
| Prerequisite-aware recommendation | PEV-040, PEV-031 |
| Improvement-assessment blueprint | PEV-042 |

---

## Section D — Domain Ownership Matrix

| Domain | Cursor | Primary PEV range |
|--------|--------|-------------------|
| Tenancy & Identity | A | PEV-005, PEV-052, PEV-053, PEV-054 |
| Assessment & Content | A | PEV-001 – PEV-004, PEV-067 |
| Curriculum | A | PEV-030, PEV-031, PEV-051 |
| Submission & Ingestion | A | PEV-006, PEV-023, PEV-068, PEV-069 |
| Understanding Pipeline | A (+ AI module) | PEV-007 – PEV-013, PEV-070, PEV-071, PEV-056, PEV-057 |
| Evaluation | A (+ AI module) | PEV-014 – PEV-022, PEV-034, PEV-066, PEV-075, PEV-076 |
| Reporting & Analytics | A (generation), B (display) | PEV-025 – PEV-029, PEV-047, PEV-048, PEV-077, PEV-078 |
| Adaptive Learning | A (+ AI module) | PEV-032, PEV-033, PEV-035 – PEV-043, PEV-039, PEV-040 |
| Platform & AI | A | PEV-060 – PEV-065, PEV-058, PEV-059, PEV-073, PEV-074 |
| Governance & Audit | A | PEV-024, PEV-063, PEV-064, PEV-072 |
| Enterprise Operations | A (future) | PEV-044 – PEV-046, PEV-049 |
| Enterprise Integration | A (future) | PEV-054, PEV-055 |
| Frontend presentation | B | Consumes all published outputs; no direct AI calls |

---

## Section E — Traceability Notes

1. **No dropped requirements:** All 65 business capabilities map to PEV-001 – PEV-065. Architectural contracts PEV-066 – PEV-078 ensure BUILD_NOW deliverables are explicitly testable.
2. **CVB subject scope:** PEV-013 and PEV-056 — only Mathematics is implemented in BUILD_NOW; Physics/Chemistry/etc. remain FUTURE_ENTERPRISE.
3. **Report generation guardrail:** PEV-065 applies to PEV-026, PEV-027, PEV-028 — reports use ledger + structured generation; LLM may assist phrasing per-section, not replace ledger.
4. **Confidence model:** PEV-061 and PEV-062 together satisfy the business rule that confidence is meaningful and dimensional (business items 61–62).
5. **Change control:** Altering release state or priority requires entry in `docs/FOUNDER_APPROVAL_LOG.md`.
6. **APP-003 / B12 implementation:** PEV-035–038 remain `AFTER_CLIENT_APPROVAL` in Release State (planning gate). They are implemented on `develop` under B12 / Issue #42 per APP-003. The register has no separate implementation-status column; B8/B9 BUILD_NOW PEVs likewise were not re-labeled when shipped.
7. **APP-004 / B13 implementation:** PEV-041 remains `AFTER_CLIENT_APPROVAL` in Release State (planning gate). It is implemented on `develop` under B13 / Issue #45 per APP-004 (tenant-scoped approved catalog + assignment; no open-web discovery). PEV-058, PEV-059 remain deferred.
8. **APP-005 / B14 implementation:** PEV-043 remains `AFTER_CLIENT_APPROVAL` in Release State (planning gate). It is implemented on `develop` under B14 / Issue #48 per APP-005 (blueprint → Assessment instantiation + B12-derived mastery deltas; no new AI / no open-web). PEV-058, PEV-059 remain deferred.
9. **APP-006 / B15 implementation:** PEV-058 and PEV-059 remain `AFTER_CLIENT_APPROVAL` in Release State (planning gate). They are implemented on `develop` under B15 / Issue #53 per APP-006 (tenant-scoped human-adjudicated gold datasets + isolated AI regression gate; credential-free CI; no ledger/published mutation; no `main` promotion). All eight `AFTER_CLIENT_APPROVAL` requirements are now implemented under APP-003–APP-006 while retaining their release-state classification. FUTURE_ENTERPRISE PEVs remain deferred.
10. **APP-008 / B16 implementation:** PEV-044–046 remain `FUTURE_ENTERPRISE` in Release State (planning gate). They are implemented on `develop` under B16 / Issue #60 per APP-008 (horizontal question grading pools, configurable moderation, formal grievance re-evaluation with versioned runs/results; no double-count of superseded publications; no `main` promotion).
11. **APP-010 / B17 implementation:** PEV-048–049 remain `FUTURE_ENTERPRISE` in Release State (planning gate). They are implemented on `develop` under B17 / Issue #67 per APP-010 (tenant-scoped psychometric runs from PUBLISHED human-final evidence; isolated blind calibration with ICC + evaluator metrics; no ledger/publication/mastery mutation; no `main` promotion). **B17.1 (Issue #71)** corrects acceptance blockers (participant freeze at ACTIVE, bounded psychometric source loading, deterministic real E2E) without changing release-state classification. PEV-050/051/054–057 remain deferred.

---

## Document Control

| Version | Date | Author | Change |
|---------|------|--------|--------|
| 0.1 | 2026-09-04 | Cursor A (bootstrap) | Initial register — 78 requirements, zero dropped |
| 0.2 | 2026-09-08 | Cursor | Annotate PEV-035–038 Acceptance Intent as B12/APP-003 implemented; release state unchanged |
| 0.3 | 2026-09-08 | Cursor | Annotate PEV-041 Acceptance Intent as B13/APP-004 / Issue #45 implemented; release state unchanged; PEV-043/058/059 still deferred |
| 0.4 | 2026-09-08 | Cursor | Annotate PEV-043 Acceptance Intent as B14/APP-005 / Issue #48 implemented; release state unchanged; PEV-058/059 still deferred |
| 0.5 | 2026-09-09 | Cursor | Annotate PEV-058–059 Acceptance Intent as B15/APP-006 / Issue #53 implemented; release state unchanged; all AFTER_CLIENT_APPROVAL PEVs now implemented |
| 0.6 | 2026-09-09 | Cursor | Annotate PEV-044–046 Acceptance Intent as B16/APP-008 / Issue #60 implemented; release state unchanged FUTURE_ENTERPRISE; PEV-048+ still deferred |
| 0.7 | 2026-09-10 | Cursor | Annotate PEV-048–049 Acceptance Intent as B17/APP-010 / Issue #67 implemented; release state unchanged FUTURE_ENTERPRISE; PEV-050+ still deferred |
| 0.8 | 2026-09-10 | Cursor | Annotate PEV-048–049 with B17.1 / Issue #71 acceptance remediation; release state unchanged FUTURE_ENTERPRISE |
