# B12 — Longitudinal mastery and mistake intelligence

**Branch:** `b12/longitudinal-mastery-mistake-intelligence`  
**PR base:** `develop` (never `main`)  
**Starting `develop` SHA:** `4e013bf408b6a936ffde00f53b92f1cc3580a4f3`  
**Starting `main` SHA:** `30c96af951ce418eb446beb7c35b679e3697b047`  
**Approval:** APP-003 / Issue #42  
**Migration:** `database/migrations/versions/20260907_0012_b12_longitudinal_mastery_mistake_intelligence.py`  
**Final feature SHA:** `41eb9dc8e3d25c3da5b5587f94240a4a3dc34824`  
**CI run ID:** `34153925361`  
**Squash SHA:** `c4e2888698411004e5ae35c584843340848fa687`  
**Final develop:** `c4e2888698411004e5ae35c584843340848fa687`  
**Final main:** `30c96af951ce418eb446beb7c35b679e3697b047` (unchanged at B12 merge)

```text
CI: Infrastructure / Contracts / Backend / Frontend /
Frontend E2E / Frontend E2E Real = SUCCESS (run 34153925361)

Feature branch: deleted after squash-merge of PR #43
Post-merge develop commit: none
Do not push a post-merge docs commit to develop.
No main change at B12 merge time.
```

## Scope (implemented)

* **PEV-035** Repeated error analysis across distinct published results  
* **PEV-036** Potentially recoverable marks by academic error class  
* **PEV-037** Longitudinal `MasteryState` + historical `MasteryStateSnapshot` trend  
* **PEV-038** Persistent student mistake notebook (curriculum-only practice)

**Not implemented (deferred):**

| Ticket | Topic |
|--------|--------|
| PEV-041 | Curriculum resource / open-web assignment |
| PEV-043 | Reassessment instantiation + mastery update from approved blueprints |
| PEV-058 | Gold benchmark dataset |
| PEV-059 | AI regression testing against gold dataset |
| FUTURE_ENTERPRISE | All FUTURE_ENTERPRISE PEVs unchanged |

**Explicit non-goals for B12:**

* No new AI inference / no new AI provider operations  
* B8 `MasteryEvidence` remains immutable source evidence (`B8_V1`)  
* No merge to `main` in this tranche  

## Persistence

Migration `20260907_0012` creates:

| Table | Role |
|-------|------|
| `mastery_states` | Current longitudinal aggregate per student × node × `B12_V1` |
| `mastery_state_snapshots` | Cumulative historical state per published result (trend) |
| `mistake_notebook_entries` | Per PR × QE × academic_error_code notebook rows |

**Preserved / not mutated:**

* `mastery_evidence` — immutable B8 rows; B12 reads only  
* No new `PipelineJob` stage — B12 runs after B8 evidence insert inside existing `ANALYTICS` materialization, plus explicit rebuild  

### MasteryState fields (`B12_V1`)

* `concept_mastery` / `execution_accuracy` — nullable `NUMERIC(10,6)` in 0..1; **null** = insufficient decisive evidence  
* `concept_decisive_count`, `execution_decisive_count`  
* `concept_inconclusive_count`, `execution_inconclusive_count`  
* `evidence_count`, `source_evidence_hash`, `algorithm_version=B12_V1`  
* `last_updated_at`, `created_at`  
* Unique: `(tenant_id, student_id, curriculum_node_id, algorithm_version)`

## Source rule

* Longitudinal mastery / notebook: only `MasteryEvidence` with `algorithm_version = B8_V1` joined to `PublishedResult.status = PUBLISHED`  
* Recoverable marks: published ledger `CriterionEvaluation.final_marks` only (never `proposed_*`)  
* Review / system codes never count as academic recurrence or notebook entries  

## Publication / backfill hook

On B8 analytics materialization (same ANALYTICS job, after evidence insert):

1. Insert/idempotent-upsert immutable `MasteryEvidence`  
2. Call `materialize_b12_for_student(...)` for the published student  

Historical / operator backfill:

```text
POST /api/v1/analytics/students/{student_id}/b12/rebuild
```

Permission: `analytics:materialize`. Idempotent upserts on unique grains; does not rewrite B8 evidence.

## B12_V1 algorithm (summary)

Server modules:

* `apps/api/app/services/b12_algorithm.py` — pure deterministic aggregates  
* `apps/api/app/services/b12_materialization.py` — persistence + query projections  

### Unweighted decisive aggregate

Per curriculum node, CONCEPT and EXECUTION strengths are aggregated independently:

* Decisive = `STRONG` + `WEAK` only  
* Ratio = `strong / (strong + weak)` quantized to `1e-6`  
* `INCONCLUSIVE` counted separately; **never** treated as weakness  
* When decisive count is 0 → ratio is **null** (insufficient decisive evidence)  
* `evidence_count` = concept strengths length + execution strengths length  
* `source_evidence_hash` = SHA-256 of sorted contributing evidence UUID strings  

Snapshots rebuild cumulatively in published-result chronological order (`published_at` nulls last, then `created_at`, then id).

### Repeated errors (PEV-035)

* Unique grain: `published_result × question_evaluation × academic_error_code`  
* Recurrence threshold: **≥ 2 distinct published results** for the same error code  
* Review / non-academic codes excluded  

### Recoverable marks (PEV-036)

* Per academic criterion: `lost = max_marks - final_marks` (`Decimal`; floor at 0)  
* Attribute only when error code is academic and not review  
* Cap: attributed ≤ total lost; unattributed = remainder  
* Disclaimer (contract const): analytical estimate, not guaranteed recovery  

### Mistake notebook (PEV-038)

* Grain: `tenant × student × published_result × question_evaluation × academic_error_code` (+ `algorithm_version`)  
* Recommended practice kinds: `CONCEPT_CHECK` / `EXECUTION_PRACTICE` / `PROCEDURE_PRACTICE` only (curriculum-constrained)  
* Links ACTIVE B9 `LearningRecommendation` IDs when target node + kind match; **no open-web URLs**  

## Contracts / schemas

| Artifact | Path |
|----------|------|
| Mastery state | `packages/contracts/schemas/mastery-state.schema.json` |
| Mastery trend | `packages/contracts/schemas/mastery-trend.schema.json` |
| Repeated errors | `packages/contracts/schemas/repeated-errors.schema.json` |
| Recoverable marks | `packages/contracts/schemas/recoverable-marks.schema.json` |
| Mistake notebook | `packages/contracts/schemas/mistake-notebook.schema.json` |
| Rebuild result | `packages/contracts/schemas/b12-rebuild-result.schema.json` |
| OpenAPI | `packages/contracts/openapi.yaml` (B12 paths + components) |

## APIs

| Method | Path | Permission |
|--------|------|------------|
| GET | `/api/v1/analytics/students/{id}/mastery-state` | `analytics:read` |
| GET | `/api/v1/analytics/students/{id}/mastery-trend` | `analytics:read` |
| GET | `/api/v1/analytics/students/{id}/repeated-errors` | `analytics:read` |
| GET | `/api/v1/analytics/students/{id}/recoverable-marks` | `analytics:read` |
| GET | `/api/v1/analytics/students/{id}/mistake-notebook` | `analytics:read` |
| POST | `/api/v1/analytics/students/{id}/b12/rebuild` | `analytics:materialize` |

Optional query on mastery-trend: `curriculum_node_id`.

## Backend implementation summary

* Models: `MasteryState`, `MasteryStateSnapshot`, `MistakeNotebookEntry` in `apps/api/app/db/models/mastery.py`  
* Materialization upserts via PostgreSQL `ON CONFLICT` on unique constraints  
* Audit: `b12_materialized` on student entity with counts + overall evidence hash  
* Tenant proof: all queries filter `tenant_id` from auth context; cross-tenant student → `404 NOT_FOUND`  
* Rebuild requires `analytics:materialize` (read-only roles cannot rebuild)  

## Frontend implementation summary

* Domain types + disclaimer: `apps/web/src/lib/types/domain.ts`  
* HTTP mappers / adapter: `apps/web/src/lib/api/http/analytics.ts`  
* Hybrid: live analytics routes B12 to HTTP; mock serves demo fixtures only — live UUIDs refused (`B12_MOCK_DEMO_ONLY`); no silent mock fallback  
* UI: `B12Sections` on student analytics page (`/analytics/students/[studentId]`)  
* Testids: `b12-longitudinal-mastery`, `b12-repeated-errors`, `b12-recoverable-marks`, `b12-mistake-notebook`, `b12-recoverable-disclaimer`  

## Security / tenancy

* All B12 reads and rebuilds scoped by `auth.tenant_id`  
* Student must exist in-tenant or endpoints return `NOT_FOUND`  
* Cross-tenant isolation covered by API tests  
* No new AI surface; no external resource URLs in notebook practice kinds  

## Tests

| Suite | Coverage |
|-------|----------|
| Backend unit | `apps/api/tests/test_b12_algorithm.py` — decisive aggregate, null when no decisive, hash stability |
| Backend API / integration | `apps/api/tests/test_b12_longitudinal_intelligence.py` — publish gates, trend, inconclusive independence, rebuild idempotency + evidence immutability, repeated-error threshold/dedupe/review exclusion, recoverable Decimal + cap, notebook links, tenant isolation + rebuild permission |
| Frontend Vitest | `B12Sections.test.tsx`, `b12-analytics.test.ts` (mappers + hybrid routing) |
| Mock Playwright | `apps/web/e2e/b12-analytics.spec.ts` (+ smoke B12 section visibility) |
| Real Playwright | `apps/web/e2e/real/zz-b12-longitudinal.spec.ts` |

Local/CI pass counts (authoritative CI run `34153925361`): backend pytest **178**; Vitest **169**; mock Playwright **16**; real Playwright **12**.

## Residual debt / technical debt

* Class-section cohort filter on assessment analytics (carry-over from B8)  
* Richer materialization / rebuild progress UI  
* Weighted / time-decayed mastery algorithms beyond unweighted `B12_V1` not in scope  
* Psychometrics (PEV-048) still FUTURE_ENTERPRISE  

> Historical note at B12 merge: PEV-041 and PEV-043 were still deferred then; they were later implemented under B13/B14 (see Post-CVB Phase 1 release report).

## Verification

| Check | Status |
|-------|--------|
| Backend pytest | 178 passed (CI run 34153925361) |
| Frontend Vitest | 169 passed |
| Mock Playwright | 16 passed |
| Real Playwright (incl. B12) | 12 passed |
| Contracts validate | SUCCESS |
| Ruff / mypy --strict | SUCCESS |
| docker compose config | SUCCESS |
| GitHub Actions (six jobs) | SUCCESS — run `34153925361` |
| Squash-merge to develop | `c4e2888698411004e5ae35c584843340848fa687` (PR #43) |
| `main` unchanged | `30c96af951ce418eb446beb7c35b679e3697b047` |
| Issue #42 | CLOSED |
| Issue #1 | CLOSED (CVB v0.1 release; closed 2026-09-07) |

## Document control

| Version | Date | Change |
|---------|------|--------|
| 0.2 | 2026-09-09 | Fill merge-time evidence from GitHub (PR #43 / CI 34153925361) for Post-CVB Phase 1 release reconciliation |
| 0.1 | 2026-09-08 | Initial B12 engineering report from implementation on feature branch |
