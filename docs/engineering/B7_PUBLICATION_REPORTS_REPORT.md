# B7 — Publication, reports, annotated paper

**Branch:** `b7/publication-reports-annotated-paper` (deleted after squash-merge)  
**PR:** [#33](https://github.com/eduvijna-ai/eduvijna-paper-evaluation/pull/33)  
**PR base:** `develop` (never `main`)  
**Starting `develop` SHA:** `e726bae2ac4745670ddea956273a09f553141048`  
**Starting `main` SHA:** `be5f10aef3cf536420adcffdb9302b6b3b6c0955`  
**Migration:** `database/migrations/versions/20260907_0008_publication_reports.py`  
**Final feature SHA:** `3f3ce07803e80d358c81c225bfc64269db380914`  
**Squash SHA on develop:** `1b6d51e09f7990da98e3749e21d7e3c2ba610827`  
**CI run ID:** `34076457655`  
**Final `develop`:** `1b6d51e09f7990da98e3749e21d7e3c2ba610827`  
**Final `main`:** `be5f10aef3cf536420adcffdb9302b6b3b6c0955` (unchanged)

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

* Ledger snapshot SHA-256 over approved EvaluationRun + leaf QuestionEvaluations + CriterionEvaluation finals
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

## Test counts (CI `34076457655`)

| Suite | Count |
|-------|-------|
| Backend pytest | 97 passed |
| Frontend Vitest | 128 passed (27 files) |
| Mock Playwright | 15 passed |
| Real Playwright | 8 passed |

## Residual debt

* Manual annotation draw UX (API exists)
* In-app GENERATED JSON report preview pages (PDF downloads + annotated paper available)
* Class analytics / mastery / learning deferred to B8

## Verification

| Check | Status |
|-------|--------|
| Backend B7 pytest | green |
| Frontend Vitest B7 | green |
| GitHub Actions (six jobs) | SUCCESS (`34076457655`) |
| Squash-merge to develop | MERGED |
| `main` unchanged | confirmed `be5f10aef3cf536420adcffdb9302b6b3b6c0955` |
| Issue #1 | CLOSED (CVB v0.1 release confirmed 2026-09-07; historical B7 text previously said OPEN) |

## Post-merge note (B8 baseline)

```text
B7 squash SHA:
1b6d51e09f7990da98e3749e21d7e3c2ba610827

B7 CI:
34076457655

Post-merge docs-only follow-up:
8d6f58149530b1b9fa5a1543ac851882cd4fef28

B8 baseline:
8d6f58149530b1b9fa5a1543ac851882cd4fef28
```

`8d6f5814…` is documentation-only (not application code). Class analytics / mastery evidence are implemented in B8 (not in this report’s residual “deferred to B8” line above, which described the B7-era boundary).
