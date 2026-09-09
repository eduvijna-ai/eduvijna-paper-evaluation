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
