# A2 Curriculum and Assessment Report

## Scope

A2 adds a tenant-scoped curriculum graph, assessment and question versioning, answer-key and
rubric approval foundations, curriculum mappings, workflow readiness, and auditable AI proposal
capability checks. It does not implement an AI provider.

## Persistence and tenancy

Revision `20260905_0003` follows `20260904_0002` and creates all A2 tables with UUID keys,
tenant ownership, timestamps where applicable, JSONB structured fields, and `Numeric(10,2)`
marks. API lookups always bind resource ID and authenticated tenant; cross-tenant references
return 404. Database uniqueness constraints protect stable codes and version numbers.

## Curriculum

Curricula contain ordered, typed nodes. Tree assembly is deterministic by sequence and code.
Parent reassignment walks ancestors before writing. Prerequisite insertion runs DFS over the
proposed graph and rejects self-edges and indirect cycles.

## Assessment and questions

Creating an assessment creates version 1. Allowed transitions are:

- `DRAFT -> RUBRIC_REVIEW` or `DRAFT -> READY`
- `RUBRIC_REVIEW -> DRAFT` or `RUBRIC_REVIEW -> READY`
- `READY -> ACTIVE` or `READY -> DRAFT`
- `ACTIVE -> CLOSED`
- `CLOSED -> ARCHIVED`

Direct `DRAFT -> READY` is intentionally allowed only after the same readiness gate used from
rubric review. Question editing and deletion require both the assessment and version to remain
`DRAFT`.

Scoring decision: **LEAF_SCORABLE leaves carry marks; CONTAINER_DERIVED parents are display
aggregates derived from descendants — never double-count.**

## Answer keys, rubrics, and readiness

Answer-key approval uses `assessment:approve`. Approved answer-key and rubric versions are
immutable and return 409 on PATCH; subsequent work creates a new version and supersedes the
approved version. ADDITIVE rubric criteria must total question max marks. DEDUCTIVE criteria
start from question max and therefore are not summed into the additive total.

READY requires:

1. leaf marks equal assessment-version max marks;
2. every scorable leaf has an approved answer-key version;
3. every scorable leaf has an approved rubric version;
4. every approved rubric reconciles.

## Authorization and audit

Institution administrators receive every A2 permission. Teachers receive curriculum,
assessment, and rubric read/manage permissions plus the approval permissions needed for
teacher-authoring workflows. Evaluators receive read permissions only. Mutations and approvals
write `AuditEvent` records without answer content, tokens, or credentials.

## AI proposals

The service defines a provider protocol. With no configured provider, proposal endpoints persist
an `AiExecutionRecord` with `UNAVAILABLE` and return HTTP 503 with
`AI_PROVIDER_UNAVAILABLE`. They never fabricate proposal content.

## Contract and verification

OpenAPI now describes A2 routes, decimal-string marks, status enums, scoring modes, and approval
behavior. `A2_TEST_MATRIX.md` maps the release-gate tests. Remaining verification evidence is
recorded in `VERIFICATION_REPORT.md`.
