# B6 — Evaluation ledger review

**Branch:** `b6/live-evaluation-ledger-review`  
**PR base:** `develop` (never `main`)  
**Starting `develop` SHA:** `6df588914706e8415629260e86e809bd1dfa5c0f`  
**Starting `main` SHA:** `be5f10aef3cf536420adcffdb9302b6b3b6c0955`  
**Trees at start:** identical (B5 tip on develop = main tree)  
**Migration:** `database/migrations/versions/20260906_0007_evaluation_ledger.py`  
**Final feature SHA:** `bdbf45c419b968abcd2daf95990ba6bc529c1463`  
**Squash SHA on develop:** `e726bae2ac4745670ddea956273a09f553141048`  
**CI run ID:** `34050518906`  
**Final develop:** `e726bae2ac4745670ddea956273a09f553141048`  
**Final main:** `be5f10aef3cf536420adcffdb9302b6b3b6c0955`

## Scope

B6 activates live evaluation ledger + teacher review. Ends at `workflow_state=APPROVED`.

**Not in B6:** `PUBLISHED`, student/parent reports, analytics, adaptive learning, annotated PDF, OCR/mapping correction workflows.

## Persistence

Tables: `evaluation_runs`, `question_evaluations`, `criterion_evaluations`, `review_actions`  
Also: `ai_execution_records.question_evaluation_id` + FK for `evaluation_run_id`.

## Semantics

* Frozen versions: `submission.assessment_version_id` + mapped `question_version_id` + approved AKV/RV
* BLANK → deterministic `proposed_ai_score=0` + `INCOMPLETE` (rules), human accept still required
* UNREADABLE → `proposed_ai_score=null`, `REVIEW_REQUIRED`; accept blocked; override allowed
* ECF validated against rubric `ecf_policy`; `NONE` rejects AI `ecf_applied`
* Alternatives: provider may propose; teacher `VALID_ALTERNATIVE` appends ReviewAction
* ACCEPT / OVERRIDE / EDIT_FEEDBACK / ESCALATE append-only ReviewAction
* Finalize: all leaf rows ACCEPTED|OVERRIDDEN → APPROVED + run COMPLETED (never PUBLISHED)
* ESCALATED blocks finalize

## Permissions

`evaluation:read|run|review|approve` — TEACHER/INSTITUTION_ADMIN all four; EVALUATOR read+review

## API

* `POST /api/v1/submissions/{id}/evaluation/prepare`
* `GET /api/v1/submissions/{id}/evaluation`
* `GET /api/v1/evaluation-runs/{id}`
* `GET /api/v1/question-evaluations/{id}`
* `POST .../accept|override|feedback|escalate`
* `POST /api/v1/submissions/{id}/evaluation/finalize`

## Frontend capability boundary

```
evaluation = live (hybrid)
reports / analytics / learning = mock
```

Live UUIDs never enter mock reports/analytics/learning.

## Residual debt

* Structured math-verification summary field on workspace DTO (client currently derives from confidence)
* Annotated paper / review hub remain mock for live submissions (addressed in B7)
* Broad public re-evaluation UI deferred (data semantics support new EvaluationRun)
* FCR-005 reports/analytics OPEN; FCR-006 learning OPEN (reports portion resolved in B7)

## Verification

| Check | Status |
|-------|--------|
| Backend pytest (clean `AI_PROVIDER_VISION=none`) | green |
| Frontend Vitest | 115 passed |
| Ruff / mypy (evaluation modules) | green |
| TypeScript `tsc --noEmit` | green |
| GitHub Actions run `34050518906` | Infrastructure / Contracts / Backend / Frontend / Frontend E2E / Frontend E2E Real = SUCCESS |

Post-merge confirmation: `origin/main` remained `be5f10aef3cf536420adcffdb9302b6b3b6c0955`.
