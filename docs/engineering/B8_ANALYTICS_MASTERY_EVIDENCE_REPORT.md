# B8 — Live analytics and mastery evidence

**Branch:** `b8/live-analytics-mastery-evidence` (deleted after squash-merge)  
**PR base:** `develop` (never `main`)  
**Starting `develop` SHA:** `8d6f58149530b1b9fa5a1543ac851882cd4fef28`  
**Starting `main` SHA:** `be5f10aef3cf536420adcffdb9302b6b3b6c0955`  
**Migration:** `database/migrations/versions/20260907_0009_analytics_mastery_evidence.py`  
**Final feature SHA:** `8beee3735141b2642713b7a8466018164ae928db`  
**CI run ID:** `34090226606`  
**Squash SHA:** `b960ca1af24f5b7c137cf5724e9126c25a553815`  
**Final develop:** `b960ca1af24f5b7c137cf5724e9126c25a553815`  
**Final main:** `be5f10aef3cf536420adcffdb9302b6b3b6c0955`

```text
CI: Infrastructure / Contracts / Backend / Frontend /
Frontend E2E / Frontend E2E Real = SUCCESS

Feature branch deleted.
No post-merge develop commit was used.
```

Do **not** direct-push post-merge docs to `develop`.

## Scope (implemented)

* PEV-029 Test & Class Analytics  
* PEV-032 Concept Strength & Weakness  
* PEV-033 Mastery vs Execution Separation  
* PEV-047 basic question-level analytics  

**Not implemented (deferred):** PEV-035/036/037/038, PEV-048 psychometrics.  
Learning plans / improvement blueprints → B9.

## Persistence

* Table `mastery_evidence` (immutable rows; algorithm `B8_V1`)  
* **No** `mastery_states` table (longitudinal MasteryState remains AFTER_CLIENT_APPROVAL)  
* `PipelineJob.stage` includes `ANALYTICS`

## Source rule

Only `PublishedResult.status = PUBLISHED` + `final_human_approved_score`.  
Never `proposed_ai_score`, never APPROVED/GENERATED unpublished.

## Publication hook

On B7 publish (same transaction): ensure `ANALYTICS` PipelineJob.  
After commit: enqueue Celery `analytics.materialize_published_result`.  
Broker failure does not unpublish. Historical backfill:  
`POST /api/v1/analytics/published-results/{id}/prepare`.

## B8_V1 derivation (summary)

* Review/system (UNREADABLE, OCR_…, …) → all INCONCLUSIVE  
* BLANK → all INCONCLUSIVE (not concept WEAK)  
* CONCEPT/FORMULA/INTERPRETATION/LOGIC_REASONING → concept WEAK  
* CALCULATION/… → execution WEAK; may leave concept STRONG (PEV-033)  
* METHOD/INCOMPLETE → procedure WEAK  
* Full-credit clean → STRONG ×3  
* `score_ratio` factual, separate from strength  

## APIs

* `GET /api/v1/analytics/assessments/{id}?pass_threshold_percent=`  
* `GET /api/v1/analytics/students/{id}`  
* `GET /api/v1/analytics/students/{id}/mastery-evidence`  
* `POST /api/v1/analytics/published-results/{id}/prepare`

Pass threshold: optional query only; omitted → null pass_rate. No hard-coded school policy.

Score distribution: percentage bins 0–20…80–100 with lower/upper bounds (descriptive, not Fail/Pass labels).

Question **performance** (not psychometric difficulty).

## Frontend capability (at B8 merge)

```
analytics = live
learning = mock
```

## Residual debt

* Class-section cohort filter on assessment analytics (class_section_id nullable stub)  
* Richer materialization progress UI  

## Verification

| Check | Status |
|-------|--------|
| Backend pytest | 113 passed |
| Frontend Vitest | 137 passed |
| Mock Playwright | 15 passed |
| Real Playwright | 9 passed |
| GitHub Actions (six jobs) | SUCCESS (`34090226606`) |
| Squash-merge to develop | MERGED |
| `main` unchanged | confirmed |
| Issue #1 | CLOSED (CVB v0.1 release confirmed 2026-09-07; historical B8 text previously said OPEN) |
