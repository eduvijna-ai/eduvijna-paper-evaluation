# B13 — Curriculum resource assignment

**Branch:** `b13/curriculum-resource-assignment`  
**PR base:** `develop` (never `main`)  
**Starting `develop` SHA:** `c73cfafe34aa71cfed1b0d1f85bea5f441c95182`  
**Starting `main` SHA:** `30c96af951ce418eb446beb7c35b679e3697b047`  
**Approval:** APP-004 / Issue #45  
**Migration:** `database/migrations/versions/20260907_0013_b13_curriculum_resource_assignment.py`  
**Final feature SHA:** `09f2aea2e1cfd7705fa09a4b6643627afce6a2d5`  
**CI run ID:** `34190373453`  
**Squash SHA:** `8396f2349658cfc7a94ed5b4b37475bfed8d8049`  
**Final develop:** `8396f2349658cfc7a94ed5b4b37475bfed8d8049`  
**Final main:** `30c96af951ce418eb446beb7c35b679e3697b047` (unchanged at B13 merge)

```text
CI: Infrastructure / Contracts / Backend / Frontend /
Frontend E2E / Frontend E2E Real = SUCCESS (run 34190373453)

Feature branch: deleted after squash-merge of PR #46
Post-merge develop commit: none
Do not push a post-merge docs commit to develop.
No main change at B13 merge time.
```

## Scope (implemented)

* **PEV-041** Tenant-scoped, institution-approved curriculum resource catalog + student assignment (no open-web discovery)

**Not implemented (deferred):**

| Ticket | Topic |
|--------|--------|
| PEV-043 | Reassessment instantiation + mastery update from approved blueprints |
| PEV-058 | Gold benchmark dataset |
| PEV-059 | AI regression testing against gold dataset |
| FUTURE_ENTERPRISE | All FUTURE_ENTERPRISE PEVs unchanged |

**Explicit non-goals for B13:**

* No open-web search, crawling, or arbitrary external URL assignment  
* `content_ref` is an opaque internal catalog key — `http://`, `https://`, and protocol-relative `//` refs are rejected  
* B9 `LearningRecommendation` / B12 `MasteryEvidence` / `MasteryState` / mistake notebook are reference-only (no mutation from assignment)  
* No merge to `main` in this tranche  

## Persistence

Migration `20260907_0013` creates:

| Table | Role |
|-------|------|
| `curriculum_resources` | Tenant catalog of approved practice materials per curriculum |
| `curriculum_resource_nodes` | Many-to-many mapping resource → curriculum nodes |
| `student_resource_assignments` | Student assignment of an ACTIVE catalog resource (optional B9 recommendation link) |

**Preserved / not mutated:**

* B8 `mastery_evidence` — immutable; B13 does not write  
* B12 `mastery_states` / `mastery_state_snapshots` / `mistake_notebook_entries` — B13 does not write  
* B9 `learning_recommendations` — may be referenced by FK; status/rationale/timestamps unchanged on assign  

### CurriculumResource

* Kinds: `PRACTICE_SET`, `WORKED_EXAMPLE`, `CONCEPT_NOTE`, `INTERNAL_PACKET`  
* Status lifecycle: `DRAFT` → `APPROVED` → `ACTIVE` (or `DEACTIVATED` from `APPROVED`/`ACTIVE`)  
* Unique: `(tenant_id, curriculum_id, code)`  
* `content_ref` — opaque internal key (max 512); open-web URLs rejected at create/update  
* Approval metadata: `approved_by`, `approved_at`  
* Node mappings required (≥1) for create and for approve; replace blocked when `DEACTIVATED`  
* After leave-DRAFT: `resource_kind` and `content_ref` immutable  

### StudentResourceAssignment

* Statuses: `ASSIGNED`, `CANCELLED`  
* Optional `learning_recommendation_id` (SET NULL on recommendation delete)  
* Assignable only when resource `status = ACTIVE`  
* Recommendation linkage rules (when provided): same tenant, same student, `ACTIVE`, and `target_node_id` ∈ resource node set  

### Idempotency (ASSIGNED grain)

Partial unique index (PostgreSQL 16 `NULLS NOT DISTINCT`):

```text
UNIQUE (tenant_id, student_id, resource_id, learning_recommendation_id)
WHERE status = 'ASSIGNED'
NULLS NOT DISTINCT
```

Re-POSTing the same grain returns the existing `ASSIGNED` row (no duplicate). Race on the unique index also resolves to the winning row.

## Contracts / schemas

| Artifact | Path |
|----------|------|
| Curriculum resource | `packages/contracts/schemas/curriculum-resource.schema.json` |
| Create / update / nodes / list | `curriculum-resource-*.schema.json` |
| Student assignment | `packages/contracts/schemas/student-resource-assignment.schema.json` |
| Assignment create / list | `student-resource-assignment-*.schema.json` |
| OpenAPI | `packages/contracts/openapi.yaml` (B13 paths + components; workspace `resource_assignments`) |

## APIs

| Method | Path | Permission |
|--------|------|------------|
| GET | `/api/v1/learning/resources` | `learning:read` |
| POST | `/api/v1/learning/resources` | `curriculum:manage` |
| GET | `/api/v1/learning/resources/{resource_id}` | `learning:read` |
| PATCH | `/api/v1/learning/resources/{resource_id}` | `curriculum:manage` |
| POST | `/api/v1/learning/resources/{resource_id}/approve` | `learning:approve` |
| POST | `/api/v1/learning/resources/{resource_id}/activate` | `learning:approve` |
| POST | `/api/v1/learning/resources/{resource_id}/deactivate` | `learning:approve` |
| PUT | `/api/v1/learning/resources/{resource_id}/nodes` | `curriculum:manage` |
| GET | `/api/v1/learning/students/{student_id}/resource-assignments` | `learning:read` |
| POST | `/api/v1/learning/students/{student_id}/resource-assignments` | `learning:assign` |
| POST | `/api/v1/learning/resource-assignments/{assignment_id}/cancel` | `learning:assign` |

Optional list filters: resources — `curriculum_id`, `status`; assignments — `curriculum_id`, `status`.

Learning workspace `GET /api/v1/learning/students/{student_id}` embeds `resource_assignments` (ASSIGNED only for selected curriculum), ordered by `assigned_at` desc.

## Backend implementation summary

* Models: `CurriculumResource`, `CurriculumResourceNode`, `StudentResourceAssignment` in `apps/api/app/db/models/resources.py`  
* Service: `apps/api/app/services/resources.py` — catalog CRUD/lifecycle, assignment create/cancel, open-web reject, workspace helper  
* Router: `apps/api/app/api/v1/resources.py` (mounted on `/api/v1`)  
* Permissions: `learning:assign` added to capability catalog; granted to `INSTITUTION_ADMIN` and `TEACHER` (not `EVALUATOR`)  
* Audit actions include `resource_created` / `resource_updated` / `resource_nodes_replaced` / `resource_approved` / `resource_activated` / `resource_deactivated` / `ASSIGN_RESOURCE` / `CANCEL_RESOURCE_ASSIGNMENT`  
* Tenant proof: all queries filter `tenant_id` from auth context; missing/cross-tenant entities → `404 NOT_FOUND`  

## Frontend implementation summary

* Catalog management at `/learning/resources` (create DRAFT, approve/activate/deactivate, status filter)
* Learning workspace: assigned-resources section distinct from B9 recommendations; assign/cancel controls
* HTTP + hybrid + mock adapters; live UUID mock fallback rejected (`B13_MOCK_DEMO_ONLY`)
* Vitest `b13-resources.test.ts`; mock `e2e/b13-resources.spec.ts`; real `e2e/real/zz-b13-resources.spec.ts`
* App shell nav link to Resource catalog

## Security / tenancy

* All B13 reads and mutations scoped by `auth.tenant_id`  
* Curriculum, student, resource, assignment, or recommendation outside tenant → `NOT_FOUND` (404), not permission leakage  
* Cross-tenant isolation covered by API tests  
* Open-web `content_ref` → `409 RESOURCE_OPEN_WEB_REJECTED`  
* Non-ACTIVE assign → `409 RESOURCE_NOT_ASSIGNABLE`  
* Assign/cancel require `learning:assign` (read-only learning roles cannot assign)  

## B9 / B12 preservation

* Assignment may optionally link an ACTIVE B9 recommendation; linkage does not rewrite recommendation fields  
* Tests assert B8 evidence counts and B12 mastery/notebook counts unchanged across catalog + assign flows  
* No new AI inference; no PipelineJob stage  

## Tests

| Suite | Coverage |
|-------|----------|
| Backend unit | `test_reject_open_web_content_ref_unit` — opaque refs allowed; `http`/`https`/`//` rejected |
| Backend API / integration | `apps/api/tests/test_b13_curriculum_resources.py` — create→approve→activate→assign→workspace embed; tenant isolation + status gates; idempotent assign + cancel history; recommendation linkage without mutation + open-web reject; `learning:assign` permission gate |
| Frontend Vitest | hybrid + mapper coverage in B13 suite |
| Mock / Real Playwright | B13 dedicated specs in mock + real suites |

Local/CI pass counts (authoritative CI run `34190373453`): backend pytest **184**; Vitest **180**; mock Playwright **18**; real Playwright **13**.

## Residual debt / technical debt

* Partial unique ASSIGNED grain relies on PostgreSQL `NULLS NOT DISTINCT` (PG 16)
* No open-web content browser; `content_ref` is opaque institutional catalog text only
* Catalog create requires knowing curriculum node UUIDs (tree picker can be enriched later)
* Richer content packaging beyond opaque `content_ref` (no blob/CDN integration in B13)  
* Open-web discovery remains permanently out of CVB policy for this product surface  

> Historical note at B13 merge: PEV-043 and PEV-058/059 were still deferred then; later delivered under B14/B15.

## Verification

| Check | Status |
|-------|--------|
| Backend pytest | 184 passed (CI run 34190373453) |
| Frontend Vitest | 180 passed |
| Mock Playwright | 18 passed |
| Real Playwright | 13 passed |
| Contracts validate | SUCCESS |
| Ruff / mypy --strict | SUCCESS |
| docker compose config | SUCCESS |
| GitHub Actions (six jobs) | SUCCESS — run `34190373453` |
| Squash-merge to develop | `8396f2349658cfc7a94ed5b4b37475bfed8d8049` (PR #46) |
| `main` unchanged | `30c96af951ce418eb446beb7c35b679e3697b047` |
| Issue #45 | CLOSED |
| Issue #1 | CLOSED (CVB v0.1 release; closed 2026-09-07) |

## Document control

| Version | Date | Change |
|---------|------|--------|
| 0.2 | 2026-09-09 | Fill merge-time evidence from GitHub (PR #46 / CI 34190373453) for Post-CVB Phase 1 release reconciliation |
| 0.1 | 2026-09-08 | Initial B13 engineering report from implementation on feature branch |
