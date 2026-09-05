# A2 Test Matrix

Executable gate modules:
- `apps/api/tests/test_a2_gate_matrix.py`
- `apps/api/tests/test_a2_review_fixes.py`

| Case ID | Assertion | Test function |
|---------|-----------|---------------|
| A2-T01 | Curriculum create/list | `test_a2_curriculum_tree_cycles_and_prerequisites` |
| A2-T02 | Ordered curriculum tree | same |
| A2-T03 | Parent cycle rejected | same |
| A2-T04 | Prerequisite reverse cycle rejected | same |
| A2-T04b | Three-node prerequisite cycle A→B→C→A rejected | same |
| A2-T05 | Assessment + initial version | `test_a2_assessment_question_marks_and_delete` |
| A2-T06 | Nested question tree | same |
| A2-T07 | Decimal leaf reconcile (Case A: 2+3=5) | same |
| A2-T07b | PATCH assessment max_marks syncs DRAFT version | same |
| A2-T08 | DRAFT question delete | same |
| A2-T09–T16 | Mapping, answer key, rubric, approve, immutability, READY | `test_a2_answer_key_rubric_mapping_and_readiness` |
| A2-T17–T18 | Incomplete READY + invalid transition | `test_a2_readiness_rejects_incomplete_and_transition_invalid` |
| A2-T19–T22 | RBAC, tenant isolation, cross-tenant 404, audit | `test_a2_rbac_tenant_isolation_and_audit` |
| A2-T23–T24 | AI 503 + AiExecutionRecord | `test_a2_ai_unavailable_is_controlled_and_recorded` |
| A2-T25 | manage-without-approve → 403 | `test_a2_manage_cannot_approve_and_ai_proposed_review` |
| A2-T26 | Manual AI_PROPOSED rejected | same |
| A2-T27 | DEDUCTIVE / ALL_OR_NOTHING reconciliation | `test_a2_domain_service_edges` |
| A2-FIX-T01 | max_marks=0, no questions → READY 409 | `test_a2_fix_t01_zero_marks_no_questions_ready_rejected` |
| A2-FIX-T02 | max_marks>0, no questions → READY 409 | `test_a2_fix_t02_positive_marks_no_questions_ready_rejected` |
| A2-FIX-T03 | container-only → READY 409 | `test_a2_fix_t03_container_only_ready_rejected` |
| A2-FIX-T04 | leaf + approvals → READY 200 | `test_a2_fix_t04_leaf_ready_succeeds` |
| A2-FIX-T05 | READY → new AnswerKeyVersion 409 | `test_a2_fix_t05_t12_ready_freeze_and_state` |
| A2-FIX-T06 | READY → new RubricVersion 409 | same |
| A2-FIX-T07 | ACTIVE → new AnswerKeyVersion 409 | `test_a2_fix_t07_t08_active_freeze` |
| A2-FIX-T08 | ACTIVE → new RubricVersion 409 | same |
| A2-FIX-T09 | DRAFT → new answer-key version allowed | `test_a2_fix_t05_t12_ready_freeze_and_state` |
| A2-FIX-T10 | RUBRIC_REVIEW → rubric revision allowed | `test_a2_fix_t10_rubric_review_revision_allowed` |
| A2-FIX-T11 | blocked revision leaves APPROVED unchanged | `test_a2_fix_t05_t12_ready_freeze_and_state` |
| A2-FIX-T12 | blocked revision leaves assessment state unchanged | same |
| A2-FIX-T13 | answer-key audit omits answer_text | `test_a2_fix_t13_t15_answer_key_audit_redaction` |
| A2-FIX-T14 | structured_answer not in audit | same |
| A2-FIX-T15 | audit retains ids/action/version | same |
| A2-FIX-T16 | assessment PATCH → AssessmentPatch | `test_a2_fix_t16_t20_openapi_patch_schemas` |
| A2-FIX-T17 | curriculum PATCH → CurriculumPatch | same |
| A2-FIX-T18 | curriculum-node PATCH → CurriculumNodePatch | same |
| A2-FIX-T19 | question-version PATCH → QuestionVersionPatch | same |
| A2-FIX-T20 | all A1/A2 PATCH ops have requestBody | same |
| A2-FIX-T21 | oversized AI proposal → 422 | `test_a2_fix_t21_t25_ai_payload_and_summary` |
| A2-FIX-T22 | arbitrary AI fields → 422 | same |
| A2-FIX-T23 | AiExecutionRecord redacted | same |
| A2-FIX-T24 | unconfigured AI → 503 | same |
| A2-FIX-T25 | AI never auto-approves | same |
| A2-FIX-T26 | manual AI_PROPOSED → 422 | `test_a2_fix_t26_manual_ai_proposed_rejected` |
| A2-FIX-T27 | server provenance helper | `test_a2_fix_t27_server_ai_provenance_assignment` |

Scoring invariant: only `LEAF_SCORABLE` leaves contribute to assessment totals.
READY requires ≥1 LEAF_SCORABLE leaf, mark reconcile, approved answer key + reconciled rubric per leaf.
Curriculum mapping is **not** required for READY.
Academic answer-key/rubric/mapping mutation is frozen for READY/ACTIVE/CLOSED/ARCHIVED.
Database CASCADE supports controlled CVB draft teardown; no public API deletes approved academic history.
