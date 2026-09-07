# Security Baseline

**Product:** EduVijna Paper Evaluation (CVB v0.1)  
**Last updated:** 2026-09-07  
**Related:** [ADR-005](adrs/ADR-005-tenant-aware-data-model.md), [ADR-009](adrs/ADR-009-immutable-raw-source-papers.md), [SECURITY.md](../SECURITY.md) (future)

---

## 1. Purpose

Minimum security requirements for CVB development, demo, and pilot deployment. Enterprise hardening (SSO, SCIM, penetration testing) is scheduled for `FUTURE_ENTERPRISE` — this baseline still applies.

---

## 2. Secrets Management

### 2.1 No secrets in git

| Allowed in repo | Forbidden in repo |
|-----------------|-------------------|
| `.env.example` with placeholder values | `.env`, `.env.local`, `.env.production` |
| Documentation referencing variable **names** | API keys, DB passwords, JWT signing keys |
| Docker Compose with dev-only defaults | Production credentials |

**Enforcement:**

- `.gitignore` includes `.env`, `*.pem`, `credentials.json`, `secrets/`
- Pre-commit hook (future): secret scanning
- CI fails if known secret patterns detected

### 2.2 Local configuration

```bash
cp .env.example .env
# Edit .env locally — never commit
```

All services read secrets from environment variables only.

### 2.3 Production (future)

- Secrets in vault / cloud secret manager
- Rotate keys on schedule; no keys in container images

---

## 3. Tenant Isolation

Per ADR-005:

| Layer | Control |
|-------|---------|
| **Database** | `tenant_id NOT NULL` on all tenant data; RLS policies |
| **Application** | Repository base requires tenant filter; middleware sets `app.tenant_id` |
| **API** | JWT + `X-Tenant-ID` validation; cross-tenant ID → `404` |
| **Workers** | `tenant_id` in every Celery task kwargs |
| **Object storage** | Key prefix `/{tenant_id}/...`; bucket policies deny cross-prefix access |
| **AI** | `AiExecutionRecord.tenant_id`; no cross-tenant batching |

**Prohibited:** Global queries without tenant predicate on tenant-scoped tables.

---

## 4. Immutable Source Papers

Per ADR-009:

- Original uploads **write-once** to S3/MinIO with content hash (`source_content_hash` / `content_sha256`).
- No in-place overwrite of source blobs; corrections use new submission or overlay annotations.
- Delete attempts on source objects logged as `AuditEvent` and denied in application layer.
- Annotations stored separately (`annotations` table + overlay PDF generation).

### 4.1 Upload malware scan hook (PEV-069 — B10)

Provider-neutral scan seam (`apps/api/app/services/upload_scanner.py`):

| `UPLOAD_SCANNER` | Behavior |
|------------------|----------|
| `none` (default) | Always `NOT_CONFIGURED` — never claims `CLEAN` |
| `fixed` | Deterministic CI scanner; **forbidden in production** |

Scan runs **before** any object-storage write for:

- Raw submission uploads
- Assessment question-paper artifacts (`assessment_artifacts`)

`REJECTED` → `422 MALWARE_DETECTED`; scanner `ERROR` → `502 UPLOAD_SCAN_FAILED`.  
Production AV product adapter is residual debt; the CVB contract requires the hook point, not a specific vendor.

---

## 5. RBAC Foundation

CVB implements role-based access from Day 1:

| Role | Typical permissions |
|------|---------------------|
| `INSTITUTION_ADMIN` | Tenant config, user management, publish |
| `TEACHER` | Assessment setup, rubric approval, review, publish |
| `REVIEWER` | Submission review, override marks |
| `VIEWER` | Read published results only |

- Permissions checked at API route level (not UI-only).
- `UserRole` assignments scoped by `tenant_id` (+ optional `institution_id`).
- Privileged actions (`publish`, `override`, `user grant`) emit `AuditEvent`.

**Future:** SSO/OIDC replaces placeholder auth without changing RBAC model.

---

## 6. Audit Events

All significant actions append **`audit_events`** (append-only):

- Authentication success/failure (placeholder)
- Submission upload, source access attempts
- Question-paper artifact upload / authoring apply
- Ledger override, review actions
- Rubric publish, assessment state change
- Publication release
- Failed authorization attempts

Fields: `actor_user_id`, `entity_type`, `entity_id`, `action`, `correlation_id`, `payload_json`, `created_at`.

### 6.1 Correlation IDs (PEV-072 — B10)

- Middleware accepts or generates `X-Correlation-ID` (max 100; safe charset) and echoes it on responses.
- `add_audit_event` auto-attaches the request correlation ID when omitted.
- Authoring AI runs persist `correlation_id` for API → worker linkage.
- Prefer the centralized writer; direct `AuditEvent(` construction is allowlisted in tests.

**Retention:** Per tenant config; minimum 1 year for pilot.

---

## 7. Data Handling (CVB)

### 7.1 Synthetic demo data only

- Repository seeds **synthetic** students, names, and papers.
- No real student PII in git, fixtures, or screenshots committed to repo.
- Demo uploads use generated or licensed sample scripts.

### 7.2 Pilot institution data

- Real pilot data lives only in deployed environment databases and object storage.
- Export/backup procedures documented before pilot; not in repo.

---

## 8. AI Security

| Rule | Rationale |
|------|-----------|
| Frontend never holds provider API keys | Keys in worker/API env only |
| No whole-PDF unconstrained grading prompt | Prevents mark hallucination bypass |
| Narrative generation only on approved ledger | Reports cannot drift from reviewed marks |
| `AiExecutionRecord` for every call | Forensics and cost control |
| Input artifacts by S3 reference | Avoid Postgres blob leakage in backups |

---

## 9. Network & Transport (CVB local)

- Local dev: HTTP acceptable on localhost only.
- Staging/production: HTTPS mandatory; HSTS recommended.
- CORS restricted to known frontend origins (`CORS_ORIGINS` in `.env.example`).

---

## 10. Dependency & Container Hygiene

- Pin dependencies (`requirements.txt`, `pnpm-lock.yaml`).
- Base Docker images from trusted registries; regular updates post-CVB.
- Non-root container user in production Compose/K8s (future).

---

## 11. Incident Response (Minimal)

1. Revoke compromised keys in provider dashboard + env rotation.
2. Query `audit_events` and `ai_execution_records` by `correlation_id`.
3. Notify founder + pilot institution per contract.

Full IR playbook — post-CVB enterprise track.

---

## 12. Developer Checklist (PR)

- [ ] No secrets in diff
- [ ] New tables have `tenant_id` where applicable
- [ ] New endpoints enforce permission check
- [ ] Mutations emit audit event
- [ ] Cross-tenant test case returns 404
- [ ] Synthetic fixtures only

---

## 13. Document Control

| Version | Date | Change |
|---------|------|--------|
| 0.1 | 2026-09-04 | Initial security baseline |
| 0.2 | 2026-09-07 | B10 upload scan hook + audit correlation enforcement |
