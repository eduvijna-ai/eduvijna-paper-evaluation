# A2 Test Matrix

- A2-T01–T04: Curriculum CRUD/tree, parent cycles, prerequisite cycles.
- A2-T05–T08: Assessment/version creation, question tree, Decimal reconciliation, DRAFT delete.
- A2-T09–T16: Answer key, rubric criteria, mapping, reconciliation, approval, immutability, READY.
- A2-T17–T18: Incomplete readiness and invalid workflow transitions.
- A2-T19–T22: RBAC, tenant list isolation, cross-tenant 404, audit events.
- A2-T23–T24: Controlled AI-provider error and execution-attempt persistence.

The gate tests use the A1 asynchronous `gate_client` and seeded administrator. IDs created by
tests are UUIDs and test payloads use decimal strings for all marks.

Scoring invariant: only leaf questions with `LEAF_SCORABLE` contribute to assessment totals.
`CONTAINER_DERIVED` parents are display aggregates derived from descendants and are never
double-counted. ADDITIVE rubric criteria must equal question marks; a DEDUCTIVE rubric starts
from question max marks.
