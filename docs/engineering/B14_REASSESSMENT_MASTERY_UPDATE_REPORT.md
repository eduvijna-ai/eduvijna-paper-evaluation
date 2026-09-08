# B14 — Reassessment and mastery update

**Branch:** `b14/reassessment-mastery-update`  
**PR base:** `develop` (never `main`)  
**Starting `develop` SHA:** `6e3444c895d506a4938d1ddd4dbb56f3158846c8`  
**Starting `main` SHA:** `30c96af951ce418eb446beb7c35b679e3697b047`  
**Approval:** APP-005 / Issue #48  
**Migration:** `database/migrations/versions/20260908_0014_b14_reassessment_mastery_update.py`  
**Final feature SHA:** `_TBD_`  
**CI run ID:** `_TBD_`  
**Squash SHA:** `_TBD_`  
**Final develop:** `_TBD_`  
**Final main:** `30c96af951ce418eb446beb7c35b679e3697b047` (must remain unchanged)

```text
CI: Infrastructure / Contracts / Backend / Frontend /
Frontend E2E / Frontend E2E Real = _TBD_

Feature branch: _TBD_
Post-merge develop commit: _TBD_
Do not push a post-merge docs commit to develop.
No main change.
```

## Scope (implemented)

* **PEV-043** Reassessment instantiation from an APPROVED B9 improvement-assessment blueprint + mastery-delta projection after the linked reassessment reaches PUBLISHED

**Not implemented (deferred):**

| Ticket | Topic |
|--------|--------|
| PEV-058 | Gold benchmark dataset |
| PEV-059 | AI regression testing against gold dataset |
| FUTURE_ENTERPRISE | All FUTURE_ENTERPRISE PEVs unchanged |

**Explicit non-goals for B14:**

* No new AI generation / no new AI provider operations / no open-web discovery  
* No auto-creation of answer key or rubric on instantiate (teacher/authoring gates remain)  
* No parallel grading or publication path — reuses Assessment → Submission → evaluation ledger → human approval → publication  
* No rewrite of immutable B8 `MasteryEvidence` or B12 longitudinal algorithm (`B12_V1`)  
* No merge to `main` in this tranche  

## Persistence

Migration `20260908_0014` creates:

| Table | Role |
|-------|------|
| `reassessments` | Tenant-scoped link from APPROVED blueprint → DRAFT `Assessment` / version; status `CREATED` → `SUBMITTED` → `PUBLISHED` |
| `reassessment_items` | Blueprint item ↔ created `QuestionVersion` linkage + snapshot fields |
| `reassessment_mastery_deltas` | Per-node B12 baseline at instantiate; post/delta filled after published B12 snapshot |

Also adds `ck_assessments_assessment_type` allowing `EXAM` | `IMPROVEMENT_REASSESSMENT` (existing rows must be `EXAM` before upgrade).

**Preserved / not mutated:**

* B8 `mastery_evidence` — immutable; B14 never writes  
* B12 `mastery_states` / `mastery_state_snapshots` / `mistake_notebook_entries` — produced only by existing B12 materialization; B14 reads baselines/snapshots and stores projection rows  
* B9 blueprint / recommendation rows — referenced; not rewritten on instantiate  

### Reassessment

* Unique: `(tenant_id, improvement_assessment_id)` — one reassessment per approved blueprint  
* Unique: `assessment_id` — one reassessment row per Assessment  
* `instantiation_hash` — SHA-256 of sorted normalized teacher-supplied item content (prompt, marks, type, instructions)  
* `algorithm_version = B14_V1`  
* Status lifecycle: `CREATED` (instantiated) → `SUBMITTED` (student attempt bound) → `PUBLISHED` (mastery deltas filled from B12 snapshot)  

### ReassessmentItem

* Unique: `(reassessment_id, improvement_assessment_item_id)`  
* Unique: `question_version_id`  
* Snapshots blueprint `item_code`, `template_kind`, `question_template_ref`  

### ReassessmentMasteryDelta

* Unique grain: `(tenant_id, reassessment_id, curriculum_node_id, algorithm_version)`  
* Baseline fields captured at instantiate from current B12 `MasteryState` (or empty/null when no state)  
* Post fields + `concept_delta` / `execution_delta` filled from B12 `MasteryStateSnapshot` for the linked published result  
* Baselines never mutated on rebuild  

## B9 → Assessment linkage

Instantiate (APPROVED blueprint + READY plan + non-stale `input_hash`) creates:

1. `Assessment` with `assessment_type=IMPROVEMENT_REASSESSMENT`, `status=DRAFT`  
2. `AssessmentVersion` v1 DRAFT with leaf `Question` / `QuestionVersion` rows + `PRIMARY` curriculum mappings  
3. `Reassessment` + `ReassessmentItem` rows linking blueprint items to those question versions  
4. Baseline `ReassessmentMasteryDelta` rows for distinct blueprint curriculum nodes  

**No answer-key or rubric auto-creation.** Existing authoring / AK / rubric / READY→ACTIVE / evaluation / publication gates still apply before a submission can be fully graded and published.

## Idempotency

* Primary: unique `(tenant_id, improvement_assessment_id)`  
* Content fingerprint: `instantiation_hash`  
* Re-POST with the **same** hash returns the existing reassessment (serialize)  
* Re-POST with a **different** hash → `409 REASSESSMENT_ALREADY_INSTANTIATED`  
* Concurrent create races resolve via IntegrityError → same-hash reuse or already-instantiated error  

## Student binding (single attempt)

On submission create/identity bind for an `IMPROVEMENT_REASSESSMENT` assessment:

* Student must match `reassessment.student_id` (`409 REASSESSMENT_STUDENT_MISMATCH`)  
* First bind sets `submission_id` and status `SUBMITTED`  
* A second distinct submission → `409 REASSESSMENT_ATTEMPT_BOUND`  

## Mastery delta (`B14_V1`)

Projection only — not a second mastery algorithm.

* **Baseline:** B12 `MasteryState` at instantiate time (per blueprint node)  
* **Post:** B12 `MasteryStateSnapshot` for the linked PUBLISHED result × node (after B12 materialization)  
* **Formula** (`apps/api/app/services/reassessment_mastery.py`): `post - baseline` when **both** sides non-null; otherwise **null** (never coerced to zero)  
* Quantization: `1e-6`, `ROUND_HALF_UP`  

Publication hook (same ANALYTICS job, **after** B8 evidence insert and B12 materialize):

```text
_insert_evidence_rows → materialize_b12_for_student → materialize_b14_for_published_result
```

Operator backfill:

```text
POST /api/v1/reassessments/{reassessment_id}/b14/rebuild
```

Permission: `analytics:materialize`. Requires a PUBLISHED result; asserts baselines unchanged (`REASSESSMENT_BASELINE_MUTATED` if they would change).

## Contracts / schemas

| Artifact | Path |
|----------|------|
| Reassessment detail | `packages/contracts/schemas/reassessment.schema.json` |
| Instantiate request | `packages/contracts/schemas/reassessment-instantiate.schema.json` |
| List / workspace embed | `packages/contracts/schemas/reassessment-list.schema.json` |
| Rebuild result | `packages/contracts/schemas/b14-rebuild-result.schema.json` |
| OpenAPI | `packages/contracts/openapi.yaml` (B14 paths + components; workspace `reassessments`) |

## APIs

| Method | Path | Permission |
|--------|------|------------|
| POST | `/api/v1/improvement-assessments/{blueprint_id}/reassessment` | `assessment:manage` |
| GET | `/api/v1/reassessments/{reassessment_id}` | `learning:read` |
| POST | `/api/v1/reassessments/{reassessment_id}/b14/rebuild` | `analytics:materialize` |

Learning workspace `GET /api/v1/learning/students/{student_id}` embeds `reassessments` for the selected curriculum (newest first).

## Backend implementation summary

* Models: `Reassessment`, `ReassessmentItem`, `ReassessmentMasteryDelta` in `apps/api/app/db/models/reassessment.py`  
* Services: `apps/api/app/services/reassessment.py` (instantiate / bind / materialize / rebuild / serialize); `reassessment_mastery.py` (pure `compute_delta`)  
* Router: `apps/api/app/api/v1/reassessment.py` (mounted on `/api/v1`)  
* Hooks: `bind_submission_if_reassessment` from submissions path; `materialize_b14_for_published_result` from analytics ANALYTICS job after B12  
* Audit: `reassessment_instantiated`, `reassessment_submission_bound`, `reassessment_mastery_materialized`  
* Tenant proof: all queries filter `tenant_id` from auth context; missing/cross-tenant → `404 NOT_FOUND`  

## Frontend implementation summary

* Contracts/OpenAPI published for hybrid wiring  
* Live learning workspace copy that still states reassessment is “not live” should be updated when UI ships instantiate/detail/delta surfaces  
* Frontend Vitest / Playwright: `_TBD_` at merge time  

## Security / tenancy

* All B14 reads and mutations scoped by `auth.tenant_id`  
* Blueprint / student / curriculum / reassessment outside tenant → `NOT_FOUND` (404)  
* Instantiate requires `assessment:manage`; get requires `learning:read`; rebuild requires `analytics:materialize`  
* Stale blueprint vs current learning evidence → `409 REASSESSMENT_BLUEPRINT_STALE`  
* Non-APPROVED blueprint → `409 REASSESSMENT_BLUEPRINT_NOT_APPROVED`  
* No new AI surface; no open-web resource assignment in this tranche  

## B8 / B12 preservation

* B14 never inserts or updates `MasteryEvidence`  
* Longitudinal mastery remains `B12_V1` only; B14 stores comparison rows keyed off B12 state/snapshots  
* Tests assert B8 evidence and B12 row counts unchanged across instantiate / bind / rebuild paths where covered  

## Tests

| Suite | Coverage |
|-------|----------|
| Backend API / integration | `apps/api/tests/test_b14_reassessment_mastery.py` — APPROVED-only instantiate; idempotent hash reuse; DRAFT Assessment without AK/rubric auto; student bind single-attempt; publish→B12→B14 delta null semantics; rebuild baseline immutability; permission gates |
| Frontend Vitest | `_TBD_` |
| Mock / Real Playwright | `_TBD_` |

Local/CI pass counts: `_TBD_` at merge time.

## Residual debt / technical debt

* Teacher must still author/approve AK + rubric and advance assessment readiness before full evaluation pipeline  
* Frontend instantiate / mastery-delta UX may lag backend contracts  
* PEV-058/059 gold benchmark / AI regression still deferred  
* All FUTURE_ENTERPRISE PEVs unchanged  
* No merge to `main` until a later founder-approved release milestone  

## Verification

| Check | Status |
|-------|--------|
| Backend pytest | `_TBD_` |
| Frontend Vitest | `_TBD_` |
| Mock Playwright | `_TBD_` |
| Real Playwright | `_TBD_` |
| Contracts validate | `_TBD_` |
| Ruff / mypy --strict | `_TBD_` |
| docker compose config | `_TBD_` |
| GitHub Actions (six jobs) | `_TBD_` |
| Squash-merge to develop | `_TBD_` |
| `main` unchanged | required `30c96af951ce418eb446beb7c35b679e3697b047` |
| Issue #48 | `_TBD_` |
| Issue #1 | closed/completed during CVB release |

## Document control

| Version | Date | Change |
|---------|------|--------|
| 0.1 | 2026-09-08 | Initial B14 engineering report from implementation on feature branch |
