# A2 Test Matrix

Executable gate module: `apps/api/tests/test_a2_gate_matrix.py`

| Case ID | Assertion | Test function |
|---------|-----------|---------------|
| A2-T01 | Curriculum create/list | `test_a2_curriculum_tree_cycles_and_prerequisites` |
| A2-T02 | Ordered curriculum tree | same |
| A2-T03 | Parent cycle rejected | same |
| A2-T04 | Prerequisite reverse cycle rejected | same |
| A2-T04b | Three-node prerequisite cycle A→B→C→A rejected | same |
| A2-T05 | Assessment + initial version | `test_a2_assessment_question_marks_and_delete` |
| A2-T06 | Nested question tree | same |
| A2-T07 | Decimal leaf reconcile (Case A: 2+3=5, no double-count) | same |
| A2-T07b | PATCH assessment max_marks syncs DRAFT version | same |
| A2-T08 | DRAFT question delete | same |
| A2-T09–T16 | Mapping, answer key, rubric, approve, immutability, READY | `test_a2_answer_key_rubric_mapping_and_readiness` |
| A2-T17–T18 | Incomplete READY + invalid transition | `test_a2_readiness_rejects_incomplete_and_transition_invalid` |
| A2-T19–T22 | RBAC empty perms, tenant list isolation, cross-tenant 404, audit | `test_a2_rbac_tenant_isolation_and_audit` |
| A2-T23–T24 | AI 503 + AiExecutionRecord | `test_a2_ai_unavailable_is_controlled_and_recorded` |
| A2-T25 | manage-without-approve → 403 | `test_a2_manage_cannot_approve_and_ai_proposed_review` |
| A2-T26 | AI_PROPOSED forces REVIEW_REQUIRED | same |
| A2-T27 | DEDUCTIVE / ALL_OR_NOTHING reconciliation semantics | `test_a2_domain_service_edges` |

Scoring invariant: only leaf questions with `LEAF_SCORABLE` contribute to assessment totals.
`CONTAINER_DERIVED` parents are display aggregates and are never double-counted.

Rubric invariant:
- ADDITIVE criteria sum must equal question max.
- DEDUCTIVE deduction envelope must equal question max (starts from question max; not naive “any criteria”).
- ALL_OR_NOTHING criterion bands must each equal question max.

READY policy: leaf mark reconcile + approved answer key + approved reconciled rubric per scorable leaf.
Curriculum mapping is **not** required for READY in A2.
