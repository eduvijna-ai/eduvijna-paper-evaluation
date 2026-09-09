# B15 — Gold benchmark dataset and AI regression gate

**Branch:** `b15/gold-benchmark-ai-regression`  
**PR base:** `develop` (never `main`)  
**Starting `develop` SHA:** `79201d726e38942b45ee51927950bcaaa58b080b`  
**Starting `main` SHA:** `30c96af951ce418eb446beb7c35b679e3697b047`  
**Approval:** APP-006 / Issue #53  
**Migration:** `database/migrations/versions/20260909_0016_b15_gold_benchmark_ai_regression.py`  
**Final feature SHA:** `a019f41890a6338836f4797d3c1eeb4bf8bbe66b`  
**CI run ID:** `34324303479`  
**Squash SHA:** `5658e16527ff99dee23182729d6b2134e06200ed`  
**Final develop (B15):** `5658e16527ff99dee23182729d6b2134e06200ed`  
**B15.1 follow-up:** PR #56 feature `9f2a3537adce9c258a71fa864db5b2acbf495c45` / CI `34331383763` / squash `a3905bdce04a684af4cf2b1617a183540ed0a264`  
**Final main:** `30c96af951ce418eb446beb7c35b679e3697b047` (unchanged at B15/B15.1 merge)

```text
CI: Infrastructure / Contracts / Backend / Frontend /
Frontend E2E / Frontend E2E Real = SUCCESS (run 34324303479; B15.1 run 34331383763)

Feature branch: deleted after squash-merge of PR #54 (B15.1 branch deleted after PR #56)
Post-merge develop commit: none
Do not push a post-merge docs commit to develop.
No main change at B15 merge time.
```

## Scope (implemented)

* **PEV-058** Tenant-scoped, versioned, human-adjudicated gold benchmark dataset  
* **PEV-059** Isolated AI regression execution with deterministic metrics, threshold snapshots, and a release-gate command/API  

**Not implemented (deferred / out of scope):**

| Ticket | Topic |
|--------|--------|
| PEV-044–046, 048–051, 054–057 | FUTURE_ENTERPRISE / other deferred |
| — | Model training/fine-tuning; cross-tenant gold pool; automatic provider/model deployment; `main` promotion |

## Persistence

Migration `20260909_0016` creates:

| Table | Role |
|-------|------|
| `benchmark_datasets` | Tenant-scoped logical dataset (`code` unique per tenant) |
| `benchmark_dataset_versions` | Versioned DRAFT→LOCKED snapshots + frozen threshold profile |
| `benchmark_cases` | Human-adjudicated gold cases linked to published QE evidence |
| `benchmark_regression_runs` | Immutable candidate regression runs + metrics/verdict |
| `benchmark_regression_case_results` | Per-case diffs vs gold; optional `AiExecutionRecord` link |

**Preserved / not mutated by regression:**

* `question_evaluations` / criterion evaluations / review actions  
* `published_results` / annotations  
* B8 `mastery_evidence`, B12 mastery/mistake state, B14 reassessment rows  

### Version lifecycle

* Versions begin `DRAFT` (cases may be added/removed)  
* Lock requires ≥1 case; freezes `content_hash`, actor, timestamp, threshold snapshot  
* Locked versions are immutable; further gold changes require a new version  

### Case eligibility / adjudication

* Source must be `PublishedResult.status == PUBLISHED`  
* Linked `QuestionEvaluation` must have human-final workflow (`ACCEPTED` / `OVERRIDDEN`) and `final_human_approved_score`  
* Case freezes expected marks, max marks, canonical error codes, ledger/evidence hashes, and a PII-free `replay_fixture`  
* `adjudicated_by` / `adjudicated_at` record the human confirming gold membership  
* Duplicate `(version, question_evaluation_id)` is idempotent  

## Regression metrics (`B15_V1` / `B15_DEFAULT_V1`)

| Metric | Formula |
|--------|---------|
| `missing_output_rate` | `missing_count / n` |
| `mean_abs_score_error` | mean `|actual − expected|` over non-missing |
| `exact_score_agreement_rate` | `exact_match_count / n` (tolerance from snapshot; default 0) |
| `taxonomy_agreement_rate` | matches / cases with gold taxonomy; `1.0` if none applicable |
| `safety_invariant_failure_rate` | structural invalid outputs (e.g. marks > max) / `n` |

Overall **PASS** iff all threshold comparisons hold (`≤` for `max_*`, `≥` for `min_*`). Empty run (`n=0`) fails safety.

Default thresholds at version create (editable until lock):

* `max_missing_output_rate = 0.0`  
* `max_mean_abs_score_error = 0.25`  
* `min_exact_score_agreement_rate = 1.0`  
* `min_taxonomy_agreement_rate = 1.0`  
* `max_safety_invariant_failure_rate = 0.0`  
* `score_tolerance = 0.0`  

## Isolated candidates (CI-safe)

| Model | Behavior |
|-------|----------|
| `fixed-benchmark-pass` | Returns gold expected marks/codes |
| `fixed-benchmark-regress` | Off-score + wrong taxonomy → FAIL |
| `fixed-benchmark-invalid` | Marks > max → safety FAIL |

Provider abstraction only; mandatory CI never requires live third-party AI credentials.

## Release gate

* API: `GET /api/v1/quality/regression-runs/{id}/gate`  
* CLI: `python -m app.cli.regression_gate --run-id <UUID>` → exit `0` PASS / `1` FAIL  
* Determines release **eligibility**; does not deploy providers/models  

## APIs / security

* Paths under `/api/v1/quality/...` (see OpenAPI + JSON Schemas)  
* RBAC: `quality:read` vs `quality:manage`  
* Tenant miss → `404 NOT_FOUND`  
* Audit: dataset/version/case/lock/run/gate events with actor + entity ids  
* Idempotency: case add, version lock, regression start (`idempotency_key`)  

## Frontend

* Workspace: `/quality/benchmarks`  
* Curate DRAFT cases from eligible published sources, lock versions, run/inspect regressions, view gold vs candidate diffs and gate verdict  
* Hybrid: no mock fallback for live UUIDs when connected to real backend  

## Verification

| Check | Status |
|-------|--------|
| Backend pytest | 218 passed (CI run 34324303479); 224 after B15.1 (34331383763) |
| Frontend Vitest | 205 passed |
| Mock Playwright | 20 passed |
| Real Playwright (incl. B15) | 15 passed |
| Contracts validate | SUCCESS |
| Ruff / mypy --strict | SUCCESS |
| docker compose config | SUCCESS |
| GitHub Actions (six jobs) | SUCCESS — runs `34324303479` / `34331383763` |
| Squash-merge to develop | `5658e16527ff99dee23182729d6b2134e06200ed` (PR #54); B15.1 `a3905bdce04a684af4cf2b1617a183540ed0a264` (PR #56) |
| `main` unchanged | `30c96af951ce418eb446beb7c35b679e3697b047` |
| Issue #53 | CLOSED |
| Issue #55 (B15.1) | CLOSED |
| Issue #1 | CLOSED (CVB v0.1 release; closed 2026-09-07) |

## Document control

| Version | Date | Change |
|---------|------|--------|
| 0.2 | 2026-09-09 | Fill merge-time evidence from GitHub (PR #54/#56) for Post-CVB Phase 1 release reconciliation |
| 0.1 | 2026-09-09 | Initial B15 engineering report from implementation on feature branch |
