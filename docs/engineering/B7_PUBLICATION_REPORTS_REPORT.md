# B7 — Publication, reports, annotated paper

**Branch:** `b7/publication-reports-annotated-paper`  
**PR base:** `develop` (never `main`)  
**Starting `develop` SHA:** `e726bae2ac4745670ddea956273a09f553141048`  
**Starting `main` SHA:** `be5f10aef3cf536420adcffdb9302b6b3b6c0955`  
**Migration:** `database/migrations/versions/20260907_0008_publication_reports.py`  
**Final feature SHA:** _fill after push_  
**Squash SHA on develop:** _fill after merge_  
**CI run ID:** _fill after green gate_

## Scope

B7 activates live publication from an **APPROVED** evaluation ledger:

* Prepare / generate publication package (annotated PDF + audience report PDFs/JSON)
* Explicit **Publish results** gate (never auto-publish)
* Annotated paper viewer with **final human-approved scores only**
* Student / parent / teacher published report resolvers

**Not in B7:** analytics aggregations, adaptive learning / mastery topics (B8).

## Persistence

Tables: `published_results`, `annotations`  
Also: `ai_execution_records.published_result_id`; `PipelineJob.stage` includes `PUBLICATION`.

## Semantics

* Ledger snapshot SHA-256 over approved EvaluationRun + leaf QuestionEvaluations + CriterionEvaluation finals + review actions
* Published scores = `final_human_approved_score` only (never `proposed_ai_score`)
* Annotations source_type `LEDGER` or `HUMAN`; score marks from final decisions
* Exports under `{tenant}/exports/{submission}/publication/{version}/…` (write-once)
* Consumer `published-result` / report resolvers → 404 until `PUBLISHED`
* Narrative: `AI` | `FIXED` | `RULES_FALLBACK` via `AI_PROVIDER_TEXT`

## Frontend capability boundary

```
evaluation = live
publication = live
reports = live
analytics = mock
learning = mock
```

Live UUIDs never enter mock analytics/learning.

## Residual debt

* Manual annotation draw UX (API exists)
* In-app GENERATED JSON report preview pages (PDF downloads + annotated paper available)
* Class analytics / mastery / learning deferred to B8

## Verification

| Check | Status |
|-------|--------|
| Backend B7 pytest | green locally |
| Frontend Vitest B7 | green locally |
| GitHub Actions (six jobs) | _after PR_ |

Confirm post-merge: `origin/main` remains `be5f10aef3cf536420adcffdb9302b6b3b6c0955`.
