# B16 — Enterprise grading, moderation & grievance

**Branch:** `b16/enterprise-grading-moderation-grievance`  
**PR base:** `develop` (never `main`)  
**Starting `develop` SHA:** `11e64b15d0fee80daa98e40618a54a619c04dc66`  
**Starting `main` SHA:** `50fc217ab54ea7c526994b98266a1914accc8d34`  
**Approval:** APP-008 / Issue #60  
**Migration:** `database/migrations/versions/20260909_0017_b16_enterprise_grading_moderation_grievance.py`  
**Final feature SHA:** `_TBD_`  
**CI run ID:** `_TBD_`  
**Squash SHA:** `_TBD_`  
**Final develop:** `_TBD_`  
**Final main:** `50fc217ab54ea7c526994b98266a1914accc8d34` (must remain unchanged)

## Scope

* **PEV-044** Horizontal grading (question-level work items)
* **PEV-045** Configurable moderation workflows
* **PEV-046** Formal grievance and re-evaluation

Release state remains **FUTURE_ENTERPRISE** (unchanged).

## Implemented surfaces

### Backend

* Migration `20260909_0017` — grading pools/members/work items, moderation policies/stages/cases/actions, grievance cases; `EvaluationRun.run_kind` / `supersedes_run_id` / `grievance_case_id`; submission `MODERATION_REVIEW`; published `SUPERSEDED`.
* RBAC permissions: `grading:*`, `moderation:*`, `grievance:*` mapped to enterprise roles.
* Services + `/api/v1/operations/*` APIs for pool lifecycle, allocation, evaluator queue, moderation decide, grievance accept/reject/resolve.
* Finalize routes to `MODERATION_REVIEW` when an active policy exists; otherwise legacy `APPROVED`.
* Publication prepare links `supersedes_result_id` to current PUBLISHED; publish marks prior as `SUPERSEDED`.
* Analytics continue to filter `status == PUBLISHED` (superseded excluded — count once).

### Contracts

* JSON schemas: grading-pool, grading-work-item, moderation-policy, moderation-case, grievance-case.
* OpenAPI paths for operations endpoints; `validate.mjs` required paths updated; request schemas `additionalProperties: false`.

### Frontend

* AppShell Operations nav → `/operations/grading`
* Pages: grading pools, my-queue, moderation, grievances
* HTTP + mock adapters, hybrid `operations` capability, Vitest `b16-operations.test.ts`
* Playwright `e2e/b16-operations.spec.ts` (mock) and `e2e/real/zz-b16-operations.spec.ts`

### Tests

* Backend `apps/api/tests/test_b16_enterprise_ops.py` — pool lifecycle, invalid member, allocate no-dup, isolation, progress, multi-stage moderation + SoD + RETURN preserves ReviewActions, legacy finalize, grievance accept/reject, supersede, analytics once, tenant 404s.

### Governance notes

* REQUIREMENTS_REGISTER PEV-044/045/046 annotated **Implemented in B16 (APP-008 / Issue #60)** — release state unchanged FUTURE_ENTERPRISE.
* Staff-submitted grievances on behalf of requester (no student/parent object-level grievance portal in B16).

## Deferred (not in APP-008)

PEV-048, PEV-049, PEV-050, PEV-051, PEV-054, PEV-055, PEV-056, PEV-057.

---

## B16.1 remediation (APP-008 / Issue #62)

**Branch:** `b16/fix-enterprise-governance-invariants`  
**Baseline `develop` SHA:** `dbfc6bc7084ae12cfcdebe302ada89efe78c0fae` (B16 squash)  
**`main` SHA (unchanged):** `50fc217ab54ea7c526994b98266a1914accc8d34`  
**Migration head:** unchanged `20260909_0017_b16_enterprise_grading_moderation_grievance`  
**Final feature SHA / CI / squash:** recorded at merge time

### Independent-audit findings addressed

1. **Ownership gap:** B16 work-item APIs enforced assignment, but authoritative B6 ledger mutations (`accept` / `override` / `feedback` / `escalate`) authorized primarily via `evaluation:review`, allowing cross-assignment bypass.
2. **Superseded B12 projections:** Historical `MasteryStateSnapshot` / `MistakeNotebookEntry` rows for SUPERSEDED V1 could still appear on current read APIs; current `MasteryState` did not prune stale nodes.
3. **Real E2E smoke:** Prior real suite only checked operations endpoint/page reachability, not the B16 lifecycle.

### Ownership remediation (Blocker A)

* Shared policy: `apps/api/app/services/grading_access.py`
* Enforced inside `evaluation` service mutation boundary for all four review actions
* Governing work-item statuses: `QUEUED`, `IN_PROGRESS`, `SUBMITTED`, `RETURNED` (not `COMPLETED`)
* Governance override: roles `{INSTITUTION_ADMIN, EXAM_CONTROLLER, HOD, ACADEMIC_COORDINATOR}` **and** permission `grading:manage` (not `evaluation:review` alone; not EVALUATOR/TEACHER)
* Stable error: `GRADING_ASSIGNMENT_FORBIDDEN` (HTTP 403); foreign tenant → `NOT_FOUND`
* Legacy path unchanged when no governing work item exists

### Superseded projection remediation (Blocker B)

* Current mastery-trend and mistake-notebook reads join `PublishedResult` and require `status == PUBLISHED`
* Materialize deletes stale current `MasteryState` rows no longer backed by PUBLISHED evidence
* Historical ledger/evidence/snapshot/notebook rows retained for audit
* Regression: `test_b16_1_grievance_v1_v2_no_double_count_b12`; B15 locked-case compatibility: `test_b16_1_b15_locked_case_survives_supersession`

### Real lifecycle E2E (Blocker C)

* Replaced `zz-b13b-operations.spec.ts` with `zz-b16-enterprise-ops.spec.ts`
* Exercises: horizontal pool → ownership 403 → evaluator submit → moderation RETURN/APPROVE → V1 publish → grievance RE_EVALUATION → V2 publish / V1 SUPERSEDED → analytics/B12 single-attempt assertions
* Demo seed users (CI/local only): evaluator-a/b, moderator, hod

### Classification

PEV-044 / PEV-045 / PEV-046 remain **FUTURE_ENTERPRISE**. No PEV-048+. No `main` promotion.
