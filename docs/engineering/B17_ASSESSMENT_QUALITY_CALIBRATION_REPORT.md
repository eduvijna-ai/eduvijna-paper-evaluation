# B17 — Assessment Quality & Evaluator Calibration

**Branch:** `b17/assessment-quality-calibration`  
**PR base:** `develop` (never `main`)  
**Starting `develop` SHA:** `4ae56d9649a8a7c94cb6b9a998c04f058b959637`  
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
* RBAC: `calibration:participate`; `quality:read`/`quality:manage` extended to EXAM_CONTROLLER, ACADEMIC_COORDINATOR, HOD; `quality:read` for MODERATOR.
* Pure stats module `quality_stats.py` (Pearson, corrected item-total discrimination, difficulty, ICC(A,1)).
* Service `quality.py` + `/api/v1/quality/psychometrics/*` and `/api/v1/quality/calibration/*`.
* Psychometrics: PUBLISHED-only cohort (SUPERSEDED excluded), human-final ACCEPTED/OVERRIDDEN QEs, min N=20, idempotent on source-set hash, interpretation bands as heuristics.
* Calibration: DRAFT→ACTIVE→CLOSED; frozen cases; blind view without reference/student/source evaluator; immutable responses; ICC + evaluator-to-reference metrics on close.
* Invariant: does not mutate QuestionEvaluation, ReviewAction, PublishedResult, mastery, or grading work items.

### Contracts

* JSON schemas: psychometric-run, item-psychometric-metric, calibration-session, calibration-case-blind, calibration-response, calibration-session-metric, calibration-evaluator-metric.
* OpenAPI paths for all new endpoints; `validate.mjs` required paths updated; request models `extra="forbid"`.

### Frontend / E2E

* Not shipped in this backend-first pass (gap for follow-up).

### Tests

* `apps/api/tests/test_b17_quality_stats.py` — pure math fixtures including hand-checkable ICC.
* `apps/api/tests/test_b17_psychometrics.py` — insufficient sample, completed cohort + idempotency, SUPERSEDED exclusion, non-mutation, tenant/RBAC.
* `apps/api/tests/test_b17_calibration.py` — lifecycle + blind + immutable responses + ICC complete + activate gates + non-mutation + isolation/permissions.

### Governance notes

* REQUIREMENTS_REGISTER PEV-048/049 annotated **Implemented in B17 (APP-010 / Issue #67)** — release state unchanged FUTURE_ENTERPRISE.

## Deferred (not in APP-010)

PEV-050, PEV-051, PEV-054, PEV-055, PEV-056, PEV-057.
