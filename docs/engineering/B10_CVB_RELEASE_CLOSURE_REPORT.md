# B10 — CVB release closure

> **Post-audit note (B11):** Independent review found PEV-002 parse was not source-evidence-driven, curriculum AI suggestions auto-wrote canonical mappings, and PEV-060 authoring metadata was incomplete. Those blockers are fixed in `b11/cvb-release-blocker-fixes` — see `docs/engineering/B11_CVB_RELEASE_AUDIT_FIX_REPORT.md`. This B10 report remains historical; do not treat its pre-B11 59/59 claim as final without the B11 audit.

**Branch:** `b10/cvb-release-closure`  
**PR base:** `develop` (never `main`)  
**Starting `develop` SHA:** `9f4f8f9fb3ece34fad08dd824e4052f47598c53d`  
**Starting `main` SHA:** `be5f10aef3cf536420adcffdb9302b6b3b6c0955`  
**Migration:** `database/migrations/versions/20260907_0011_cvb_release_closure.py`  
**Final feature SHA:** `09a0eae2907ea7a43bbb889af15bf65c95c359da`  
**CI run ID:** `34121730685`  
**Squash SHA:** `be73cc3bcf91b4078b3fea63b3788403129a1419`  
**Final develop:** `be73cc3bcf91b4078b3fea63b3788403129a1419`  
**Final main:** `be5f10aef3cf536420adcffdb9302b6b3b6c0955` (unchanged)

```text
CI: Infrastructure / Contracts / Backend / Frontend /
Frontend E2E / Frontend E2E Real = _TBD_

Feature branch: _TBD_
Post-merge develop commit: none
Do not push a post-merge docs commit to develop.
```

## Scope (implemented)

* **PEV-002** Question paper ingestion — upload → `assessment_artifacts` → AI parse → teacher edit → apply question tree  
* **PEV-004** AI-proposed answer key & rubric — durable `authoring_ai_runs`; proposals unusable until teacher approval  
* **PEV-013** Structured work understanding — MATH / TABLE / DIAGRAM transcription segments (Mathematics focus)  
* **PEV-069** Raw upload contract — malware scan hook on submission + question-paper uploads  
* **PEV-072** Audit event foundation — centralized writer + request `correlation_id` propagation  

**Also closed in B10:**

* `AuthoringAIProvider` (`parse_question_paper`, `propose_answer_key`, `propose_rubric`, `suggest_curriculum_mapping`)  
* OpenAPI / JSON Schema for assessment artifacts, authoring runs, and question-paper parse bounds  
* Full BUILD_NOW release audit → `docs/engineering/CVB_BUILD_NOW_RELEASE_AUDIT.md`

**Not complete (remain deferred):**

| Ticket | Topic |
|--------|--------|
| PEV-035 / 036 / 037 / 038 | Longitudinal MasteryState / repeated-error / recoverable marks |
| PEV-041 | Curriculum resource / URL assignment |
| PEV-043 | Instantiate approved blueprint as live reassessment |
| PEV-044 – 046, 048 – 051, 054 – 057 | FUTURE_ENTERPRISE |
| PEV-058 / 059 | Gold dataset / AI regression gates |

## Persistence

Migration `20260907_0011` creates:

| Table | Role |
|-------|------|
| `assessment_artifacts` | Immutable question-paper uploads (hash, storage key, scan status) |
| `authoring_ai_runs` | Versioned authoring AI jobs + `proposal_payload` + correlation |

Also:

* `assessment_versions.question_paper_artifact_id` → `assessment_artifacts`  
* `authoring_ai_runs.answer_key_version_id` / `rubric_version_id` (nullable FKs to created drafts)  
* `ai_execution_records.authoring_ai_run_id` (+ optional assessment/artifact/key/rubric refs)  
* Scan status enum: `NOT_CONFIGURED` | `CLEAN` | `REJECTED` | `ERROR`

**Explicitly not created:**

* No real AV product integration (hook only — `UPLOAD_SCANNER=none|fixed`)  
* No reassessment / MasteryState tables  

## Permissions

| Code | Used by |
|------|---------|
| `assessment:manage` | Question-paper upload, parse, edit/apply tree, propose answer key |
| `assessment:read` | GET authoring AI run |
| `rubric:manage` | Propose rubric |
| `curriculum:manage` | Suggest curriculum mapping |

Role map unchanged from A2: `INSTITUTION_ADMIN` / `TEACHER` manage; evaluators remain read-scoped where already defined.

## Question paper ingestion (PEV-002)

Flow:

1. `POST /api/v1/assessment-versions/{id}/question-paper` — multipart upload (DRAFT version only)  
2. Scan hook → reject before storage on `REJECTED` / `ERROR`  
3. Write-once MinIO key + `assessment_artifacts` row (`artifact_type=QUESTION_PAPER`)  
4. `POST …/question-paper/parse` → `AuthoringAiRun` (`PARSE_QUESTION_PAPER`)  
5. Teacher may `PUT …/authoring-ai-runs/{id}/question-tree-proposal`  
6. `POST …/apply-question-tree` materializes `Question` / `QuestionVersion` tree  

Bounds (server + contract): max depth **6**, max nodes **200**, unique `stable_code`, leaf marks reconcile to assessment max.

Storage layout:

```text
{tenant}/assessments/{assessment}/sources/{sha256}/{filename}
```

Code paths:

* `apps/api/app/services/assessment_artifacts.py`  
* `apps/api/app/api/v1/authoring.py`  
* `apps/api/app/services/authoring_ai.py`  
* `apps/api/app/db/models/authoring.py`

## AI-proposed answer key & rubric (PEV-004)

When `AI_PROVIDER_AUTHORING` is configured (`fixed` | `openai`):

| Endpoint | Operation | Outcome |
|----------|-----------|---------|
| `POST /api/v1/ai/proposals/answer-key` | `PROPOSE_ANSWER_KEY` | Draft `AnswerKeyVersion` `source_type=AI_PROPOSED` → teacher approve still required |
| `POST /api/v1/ai/proposals/rubric` | `PROPOSE_RUBRIC` | Draft `RubricVersion` `AI_PROPOSED` → rubric review / approve |
| `POST /api/v1/ai/proposals/curriculum-mapping` | `SUGGEST_CURRICULUM_MAPPING` | Proposal payload only (apply remains teacher-driven) |

When provider is `none` / unset → `503 AI_PROVIDER_UNAVAILABLE` (no fabricated content).  
Teacher-authored material is **not** overwritten (`AUTHORING_MATERIAL_ALREADY_EXISTS`).  
Evaluation remains blocked until answer key + rubric are teacher-approved (A2 readiness gates unchanged).

Provider: `apps/api/app/ai/providers/authoring.py` + `FixedAuthoringProvider` / OpenAI adapter via registry.  
Tracing: `AiExecutionRecord` with `authoring_ai_run_id`.

## Structured transcription (PEV-013)

Extends B5 transcription with typed segments:

* Kinds: `TEXT` | `MATH` | `TABLE` | `DIAGRAM`  
* Stage confidence stays on `transcription_confidence` (not a generic AI score)  
* Contract: `packages/contracts/schemas/structured-transcription.schema.json`  
* Tests: `apps/api/tests/test_b10_structured_transcription.py`

CVB subject scope remains **Mathematics** (register §E); multi-subject → PEV-056 FUTURE_ENTERPRISE.

## Upload scan hook (PEV-069)

`apps/api/app/services/upload_scanner.py`:

| `UPLOAD_SCANNER` | Behavior |
|------------------|----------|
| `none` (default) | Always `NOT_CONFIGURED` — never reports `CLEAN` |
| `fixed` | Deterministic reject on malware markers (non-production only) |

Wired on:

* Submission raw upload (`apps/api/app/api/v1/submissions.py`)  
* Question-paper upload (`assessment_artifacts.enforce_upload_scan`)

Invalid MIME / size still rejected via existing upload validation + OpenAPI contract.

## Audit correlation (PEV-072)

* Middleware: `apps/api/app/middleware/correlation.py` — echo / generate `X-Correlation-ID`  
* Writer: `apps/api/app/services/audit.py` (`add_audit_event`) auto-attaches correlation  
* Guard: tests forbid direct `AuditEvent(` construction outside allowlist  
* Authoring runs persist `correlation_id` for API → worker linkage  

## Provider abstraction

| Config | Behavior |
|--------|----------|
| `AI_PROVIDER_AUTHORING=fixed` | Deterministic FixedAuthoringProvider (non-prod) |
| `AI_PROVIDER_AUTHORING=openai` | OpenAI adapter |
| `AI_PROVIDER_AUTHORING=none` | 503 unavailable path |

Structure/evaluation/narrative/learning providers unchanged from B5–B9.

## Workers

| Celery task | Pipeline |
|-------------|----------|
| `authoring.parse_question_paper` | Parse → `REVIEW_REQUIRED` proposal |
| `authoring.propose_answer_key` | Answer-key draft proposal |
| `authoring.propose_rubric` | Rubric draft proposal |
| `authoring.suggest_curriculum_mapping` | Mapping suggestions |

Enqueue after prepare commit; broker failure surfaces `enqueue_error` without rolling back the QUEUED row.

## APIs

| Method | Path | Permission |
|--------|------|------------|
| POST | `/api/v1/assessment-versions/{id}/question-paper` | `assessment:manage` |
| POST | `/api/v1/assessment-versions/{id}/question-paper/parse` | `assessment:manage` |
| GET | `/api/v1/authoring-ai-runs/{id}` | `assessment:read` |
| PUT | `/api/v1/authoring-ai-runs/{id}/question-tree-proposal` | `assessment:manage` |
| POST | `/api/v1/authoring-ai-runs/{id}/apply-question-tree` | `assessment:manage` |
| POST | `/api/v1/ai/proposals/answer-key` | `assessment:manage` |
| POST | `/api/v1/ai/proposals/rubric` | `rubric:manage` |
| POST | `/api/v1/ai/proposals/curriculum-mapping` | `curriculum:manage` |

Contracts:

* `packages/contracts/schemas/question-paper-parse.schema.json`  
* `packages/contracts/schemas/structured-transcription.schema.json`  
* OpenAPI: `AssessmentArtifact`, `AuthoringAiRun`, `ProposedQuestionNode`

## Frontend capability

Backend authoring closure is live. Hybrid web capability boundary for B7–B9 **must not regress**:

```
analytics = live
learning = live
```

Authoring UI wiring against B10 paths is recorded in `FRONTEND_CONTRACT_REQUESTS.md` (FCR-008 / FCR-012). No silent live→mock fallback.

## Test counts

| Suite | Count |
|-------|-------|
| Backend pytest | 154 (local) |
| Frontend Vitest | 152 |
| Mock Playwright | 15 |
| Real Playwright | 11 (includes `zz-b10-authoring`) |

B10-focused suites:

* `apps/api/tests/test_b10_assessment_artifacts.py`  
* `apps/api/tests/test_b10_authoring_ai.py`  
* `apps/api/tests/test_b10_structured_transcription.py`  
* `apps/api/tests/test_b10_audit_correlation.py`  
* `apps/web/src/lib/api/b10-authoring.test.ts`  
* `apps/web/e2e/real/zz-b10-authoring.spec.ts`

## Residual debt

* Production malware scanner adapter (beyond `none` / `fixed` hook)  
* PEV-035–038, 041, 043 and FUTURE_ENTERPRISE items (unchanged)  
* Class-section cohort filters on analytics (B8 carry-over)

## Verification

| Check | Status |
|-------|--------|
| Backend pytest | 154 passed (local) |
| Frontend Vitest | 152 passed |
| Mock Playwright | 15 (CI) |
| Real Playwright | 11 including B10 (CI) |
| Contracts validate | 15 schemas + openapi |
| Ruff / mypy --strict | passed |
| docker compose config | passed |
| GitHub Actions (six jobs) | `_TBD_` |
| Squash-merge to develop | `_TBD_` |
| `main` unchanged | required `be5f10aef3cf536420adcffdb9302b6b3b6c0955` |
| Issue #1 | remains OPEN |
| BUILD_NOW audit | `docs/engineering/CVB_BUILD_NOW_RELEASE_AUDIT.md` |
