# B17 — Assessment Quality & Evaluator Calibration

**Branch:** `b17/assessment-quality-calibration`  
**PR base:** `develop` (never `main`)  
**Starting `develop` SHA:** `aefd1f00a4fd3fb37d06057633e4bf85a56009e8` (APP-010 merge)  
**Starting `main` SHA:** `5febe578f4f57f24c63149ae5a03be8adb5baac3`  
**Approval:** APP-010 / Issue #67  
**Migration:** `database/migrations/versions/20260910_0018_b17_assessment_quality_calibration.py`  
**Final feature SHA:** `_TBD_`  
**CI run ID:** `_TBD_`  
**Squash SHA:** `_TBD_`  
**Final develop:** `_TBD_`  
**Final main:** `5febe578f4f57f24c63149ae5a03be8adb5baac3` (must remain unchanged)

## Scope

* **PEV-048** Item Difficulty & Discrimination (psychometric runs)
* **PEV-049** Evaluator Consistency / Calibration (blind sessions + ICC)

Release state remains **FUTURE_ENTERPRISE** (unchanged).

## Implemented surfaces

### Backend

* Migration `20260910_0018` — psychometric runs/item metrics; calibration sessions/cases/participants/responses/session metrics/evaluator metrics.
* ORM models aligned to migration (`cohort_definition` JSONB dict; calibration column names `published_result_id` / `participant_id` / `mae` / `nmae`).
* RBAC: `calibration:participate`; `quality:read`/`quality:manage` for enterprise quality roles.
* Pure stats module `quality_stats.py` (Pearson, corrected item-total discrimination, difficulty, ICC(A,1)).
* Service `quality.py` + `/api/v1/quality/psychometrics/*` and `/api/v1/quality/calibration/*`.
* Psychometrics: PUBLISHED-only cohort (SUPERSEDED excluded), human-final ACCEPTED/OVERRIDDEN QEs, min N=20, idempotent on source-set hash, interpretation bands as heuristics.
* Calibration: DRAFT→ACTIVE→CLOSED; frozen cases; blind view without reference/student/source evaluator; immutable responses; ICC + evaluator-to-reference metrics on close.
* Invariant: does not mutate QuestionEvaluation, ReviewAction, PublishedResult, mastery, or grading work items.

### Contracts

* JSON schemas: psychometric-run, item-psychometric-metric, calibration-session, calibration-case-blind, calibration-response, calibration-session-metric, calibration-evaluator-metric.
* OpenAPI paths for all new endpoints; `validate.mjs` required paths updated; request models `extra="forbid"`.

### Frontend

* AppShell nav → `/quality/psychometrics`, `/quality/calibration`
* Pages with B17 testIds for runs/items and calibration sessions/blind scoring
* HTTP `QualityHttpApi` + mock fixtures + hybrid `quality` capability routing
* Vitest `b17-quality.test.ts`
* Playwright `e2e/b17-quality.spec.ts` (mock) and `e2e/real/zz-b17-quality.spec.ts` (API + UI smoke)

### Tests

* `apps/api/tests/test_b17_quality_stats.py` — pure math fixtures including hand-checkable ICC.
* `apps/api/tests/test_b17_psychometrics.py` — insufficient sample, completed cohort + idempotency, SUPERSEDED exclusion, non-mutation, tenant/RBAC.
* `apps/api/tests/test_b17_calibration.py` — lifecycle + blind + immutable responses + ICC complete + activate gates + non-mutation + isolation/permissions.

### Governance notes

* REQUIREMENTS_REGISTER PEV-048/049 annotated **Implemented in B17 (APP-010 / Issue #67)** — release state unchanged FUTURE_ENTERPRISE.

## B17.1 acceptance remediation (Issue #71)

Corrective follow-up to PR #70 / Issues #67/#69 (no new product scope; no `main` promotion):

1. **Participant freeze** — `add_calibration_participant` permitted only while `DRAFT`; ACTIVE/CLOSED return `CALIBRATION_SESSION_NOT_DRAFT` (409).
2. **Bounded psychometric source loading** — bulk QE + question metadata queries; explicit per-result×question matrix; query-count regression test.
3. **Deterministic real E2E** — `seed_b17_e2e_quality` CI fixture (`B17-E2E-QUALITY`, ≥20 published); `zz-b17-quality.spec.ts` never skips; asserts COMPLETED psychometrics + ICC COMPLETED calibration + post-activate 409s.

## Deferred (not in APP-010)

PEV-050, PEV-051, PEV-054, PEV-055, PEV-056, PEV-057.
