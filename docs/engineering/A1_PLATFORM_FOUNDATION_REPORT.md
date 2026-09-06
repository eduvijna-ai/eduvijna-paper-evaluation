# A1 Platform Foundation Report

## API and response convention

A1 resources use direct JSON resource objects and arrays under `/api/v1`; errors retain the
shared `{ "error": { "code", "message", "correlation_id", "details" } }` envelope. The API
implements login/me, the current institution, academic-year, class-section, student and
guardian list/create/get/patch operations, student-guardian link/unlink, and CSV
validate/commit. `/health`, `/ready`, and system version remain unchanged.

## Tenant and authorization strategy

The server derives `tenant_id` exclusively from the signed access token. Every entity lookup
includes that tenant predicate, so a foreign-tenant identifier returns 404. Domain handlers
consume the provider-neutral `AuthContext`; `JwtAuthProvider` is the CVB implementation and
can later be replaced by OIDC. Argon2 hashes passwords. Tokens use HS256 and contain `sub`,
`tenant_id`, `roles`, `permissions`, `iat`, `exp`, and `typ=access`.

Role constants are `PLATFORM_ADMIN`, `INSTITUTION_ADMIN`, `TEACHER`, `EVALUATOR`, `STUDENT`,
`PARENT`, `EXAM_CONTROLLER`, `ACADEMIC_COORDINATOR`, `HOD`, `MODERATOR`, and `AUDITOR`.
Permission constants are `institution:read`, `academic_year:read/write`,
`class_section:read/write`, `student:read/write/import`, and `guardian:read/write`.
`INSTITUTION_ADMIN` receives all A1 permissions; the exact mappings live in
`app/core/authorization.py`.

## Student CSV import

The exact UTF-8 header is:

`student_code,admission_number,roll_number,full_name,academic_year,class_section`

Validation trims values, enforces configured byte/row limits, resolves tenant-scoped academic
years and sections, and records `VALID`, `DUPLICATE_IN_FILE`, `DUPLICATE_EXISTING`,
`UNKNOWN_CLASS`, or `MISSING_REQUIRED_FIELD` outcomes in an expiring import session. It never
writes students or stores the source file. Commit inserts only valid rows in one transaction;
replaying a committed session returns the prior result. A synthetic template is in
`docs/engineering/samples/student_import_template.csv`.

## Migration and audit

Migration `20260904_0002` extends users and roles, adds role-permission wiring, migrates legacy
student names/codes, adds academic-year, admission and roll data, applies scoped uniqueness,
and adds import sessions. It can downgrade to the Day-1 schema without editing migration
`20260904_0001`. Student create/update, committed imports, guardian create/link/unlink,
academic-year changes and class-section changes produce tenant-scoped audit events. Passwords
and tokens are never included.

## Local seed workflow

After migration, run `infra/scripts/seed.ps1` or:

`docker compose exec api python -m app.cli.seed_dev`

This idempotently creates tenant `demo`, its institution, roles, permissions, role wiring,
academic year `2026-27`, class `Grade 10 / A`, and:

- Email: `admin@demo.eduvijna.local`
- Password: `DemoAdmin!2026` (synthetic local-only credential)

## Configuration and limitations

Set `AUTH_TOKEN_SECRET` outside local/test. `AUTH_TOKEN_TTL_MINUTES`, `AUTH_ALGORITHM`,
`STUDENT_IMPORT_MAX_BYTES`, and `STUDENT_IMPORT_MAX_ROWS` are configurable. CVB currently
supports password/JWT authentication only; password reset, MFA, refresh tokens, SSO, delete
operations, pagination and custom tenant role administration are intentionally outside A1.
