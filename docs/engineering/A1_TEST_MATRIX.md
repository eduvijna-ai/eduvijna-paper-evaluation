# A1 Test Matrix (Release Gate)

Branch: `cursor-a/platform-foundation`  
Scope: Auth, tenancy, RBAC, students, CSV import, guardians, audit  
Parameterized / grouped tests are acceptable when assertions are identifiable.

| ID | Requirement | Test file | Test function/node | Status | Notes |
|----|-------------|-----------|--------------------|--------|-------|
| A1-T01 | Valid login succeeds | `test_a1_gate_matrix.py` | `test_a1_t01_valid_login` | PASS | Also covered by integration helper `_login` |
| A1-T02 | Invalid password fails generically | `test_a1_gate_matrix.py` | `test_a1_t02_invalid_password_generic` | PASS | Message `Invalid credentials` |
| A1-T03 | Unknown user fails generically | `test_a1_gate_matrix.py` | `test_a1_t03_unknown_user_generic` | PASS | Same generic wording |
| A1-T04 | Protected endpoint without token rejected | `test_a1_gate_matrix.py` | `test_a1_t04_protected_without_token` | PASS | `GET /students` → 401 |
| A1-T05 | Malformed/invalid token rejected | `test_a1_gate_matrix.py` | `test_a1_t05_malformed_token_rejected` | PASS | |
| A1-T06 | Expired token rejected | `test_a1_gate_matrix.py` | `test_a1_t06_expired_token_rejected` | PASS | Also rejects `alg=none` |
| A1-T07 | Tenant/user context from token not body | `test_a1_gate_matrix.py` | `test_a1_t07_context_from_token_not_body` | PASS | Extra `tenant_id` cannot reassign tenant |
| A1-T08 | Tenant A cannot list Tenant B students | `test_a1_gate_matrix.py` | `test_a1_tenancy_isolation_matrix` | PASS | |
| A1-T09 | Tenant A cannot get Tenant B student | `test_a1_gate_matrix.py` / `test_platform_integration.py` | `test_a1_tenancy_isolation_matrix` / `test_auth_tenant_rbac_crud_import_and_audit` | PASS | 404 |
| A1-T10 | Tenant A cannot update Tenant B student | `test_a1_gate_matrix.py` | `test_a1_tenancy_isolation_matrix` | PASS | 404 |
| A1-T11 | Tenant A cannot access Tenant B class section | `test_a1_gate_matrix.py` | `test_a1_tenancy_isolation_matrix` | PASS | 404 |
| A1-T12 | Tenant A cannot access Tenant B guardian | `test_a1_gate_matrix.py` | `test_a1_tenancy_isolation_matrix` | PASS | 404 |
| A1-T13 | Cannot override tenant_id via payload | `test_a1_gate_matrix.py` | `test_a1_tenancy_isolation_matrix` / `test_a1_t07_*` | PASS | Server sets tenant from auth |
| A1-T14 | Institution admin allowed | `test_a1_gate_matrix.py` | `test_a1_rbac_and_students_crud` | PASS | |
| A1-T15 | Unauthorized role denied | `test_a1_gate_matrix.py` / `test_platform_integration.py` | `test_a1_rbac_and_students_crud` | PASS | STUDENT token → 403 |
| A1-T16 | Permission dependency enforced server-side | `test_a1_gate_matrix.py` | `test_a1_rbac_and_students_crud` | PASS | |
| A1-T17 | Create student | `test_a1_gate_matrix.py` | `test_a1_rbac_and_students_crud` | PASS | |
| A1-T18 | Get student | `test_a1_gate_matrix.py` | `test_a1_rbac_and_students_crud` | PASS | |
| A1-T19 | Update student | `test_a1_gate_matrix.py` | `test_a1_rbac_and_students_crud` | PASS | |
| A1-T20 | Duplicate student identifier | `test_a1_gate_matrix.py` | `test_a1_rbac_and_students_crud` | PASS | 409 |
| A1-T21 | Valid UTF-8 CSV validates | `test_a1_gate_matrix.py` | `test_a1_import_and_limits` | PASS | |
| A1-T22 | Duplicate within file | `test_a1_gate_matrix.py` | `test_a1_import_and_limits` | PASS | |
| A1-T23 | Duplicate existing student | `test_a1_gate_matrix.py` | `test_a1_import_and_limits` | PASS | |
| A1-T24 | Malformed row detected | `test_a1_gate_matrix.py` | `test_a1_import_and_limits` | PASS | `INVALID` |
| A1-T25 | Missing required field | `test_a1_gate_matrix.py` | `test_a1_import_and_limits` | PASS | |
| A1-T26 | Unknown class | `test_a1_gate_matrix.py` | `test_a1_import_and_limits` | PASS | |
| A1-T27 | Validation writes zero students | `test_a1_gate_matrix.py` | `test_a1_import_and_limits` | PASS | Count unchanged |
| A1-T28 | Commit persists valid records | `test_a1_gate_matrix.py` | `test_a1_import_and_limits` | PASS | |
| A1-T29 | Commit is transactional | `test_a1_gate_matrix.py` | `test_a1_import_and_limits` | PASS | Conflict mid-commit → rollback |
| A1-T30 | Repeated commit idempotent | `test_a1_gate_matrix.py` | `test_a1_import_and_limits` | PASS | |
| A1-T31 | File/row limit enforced | `test_a1_gate_matrix.py` | `test_a1_import_and_limits` | PASS | Row limit → 413 |
| A1-T32 | Create guardian | `test_a1_gate_matrix.py` | `test_a1_guardians_and_audit` | PASS | |
| A1-T33 | Link guardian | `test_a1_gate_matrix.py` | `test_a1_guardians_and_audit` | PASS | |
| A1-T34 | Unlink guardian | `test_a1_gate_matrix.py` | `test_a1_guardians_and_audit` | PASS | |
| A1-T35 | Cross-tenant guardian link rejected | `test_a1_gate_matrix.py` | `test_a1_tenancy_isolation_matrix` | PASS | 404 |
| A1-T36 | Student create audit | `test_a1_gate_matrix.py` | `test_a1_guardians_and_audit` | PASS | |
| A1-T37 | Student update audit | `test_a1_gate_matrix.py` | `test_a1_guardians_and_audit` | PASS | |
| A1-T38 | Import commit audit | `test_a1_gate_matrix.py` | `test_a1_guardians_and_audit` | PASS | |
| A1-T39 | Guardian audit | `test_a1_gate_matrix.py` | `test_a1_guardians_and_audit` | PASS | |
| A1-T40 | Academic/class modification audit | `test_a1_gate_matrix.py` | `test_a1_guardians_and_audit` | PASS | |
| A1-T41 | Password/token never in audit payload | `test_a1_gate_matrix.py` | `test_a1_guardians_and_audit` | PASS | Payload scan |

**Gate rule:** Every ID A1-T01..A1-T41 must be PASS before merge.
