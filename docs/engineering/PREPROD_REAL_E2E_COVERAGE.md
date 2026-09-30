# PREPROD-002 — Real-backend E2E coverage

**Status:** Active engineering gate (CI)  
**Suite:** `apps/web/e2e/real/` via `pnpm test:e2e:real` (`playwright.real.config.ts`)  
**Related:** [PRODUCTION_READINESS.md](../production/PRODUCTION_READINESS.md), [DEVELOPMENT_WORKFLOW.md](./DEVELOPMENT_WORKFLOW.md)

This document inventories automated **real HTTP/backend** Playwright coverage. It does **not** reopen founder MAT manual testing and must **not** destroy MAT volumes.

---

## 1. Critical workflow map

| Stage | Covered by | Notes |
|-------|------------|-------|
| Admin login / platform CRUD / logout | `platform.spec.ts` | Academic years, sections, students, guardians |
| Academic + curriculum foundation | `authoring.spec.ts`, `publication.spec.ts` (API setup) | Curriculum + assessment created for live pipeline |
| Teacher authoring (AI path) | `zz-b10-authoring.spec.ts` | Upload paper → parse → apply → READY/ACTIVE |
| Assessment ACTIVE | authoring + publication helpers | Transition READY → ACTIVE |
| Upload | `ingestion.spec.ts`, `publication.spec.ts`, mapping/transcription/evaluation | Multipart upload against real API + MinIO |
| Identity | `ingestion.spec.ts`, `mapping.spec.ts`, `transcription.spec.ts`, `publication.spec.ts` | Confirm candidate |
| Mapping | `mapping.spec.ts`, `transcription.spec.ts`, `publication.spec.ts` | Assign / blank / finalize |
| Transcription | `transcription.spec.ts`, `publication.spec.ts` | Confirm + finalize → READY_FOR_EVALUATION |
| Evaluation review | `evaluation.spec.ts` (UI); `publication.spec.ts` (API accept/override/finalize) | See intentional API shortcut below |
| Publication | `publication.spec.ts` | Generate package → publish → immutable |
| Analytics persistence | `publication.spec.ts`, `zz-b8-analytics.spec.ts` | Published attempt counts |
| Learning / reports | `publication.spec.ts`, `zz-b9-learning.spec.ts` | Live learning mode after publish |

**Spine suite:** `publication.spec.ts` exercises upload → identity → mapping → transcription → APPROVED → publish → analytics/learning, then **logout + re-login** and re-asserts HTTP + UI persistence (PREPROD-002).

Extended enterprise suites (`zz-b12` … `zz-b20`, `zz-b16`) deepen specialized domains; they are not substitutes for the publication spine.

---

## 2. Largest gap closed vs remaining

| Item | Disposition |
|------|-------------|
| **Published / analytics state after logout + re-login** | **Closed in `publication.spec.ts`** — API + UI assertions after fresh login |
| Multi-role handoff (admin → separate teacher user mid-flow) | **Remaining / accepted** — demo admin carries permissions; role boundaries covered elsewhere (e.g. B20 evaluator path) |
| Full evaluation **UI** inside publication spine | **Intentional API shortcut** — UI ledger covered by `evaluation.spec.ts`; publication spine prioritizes publish + persistence |
| Founder MAT manual path | **Out of scope** — MAT-001..017 PASS BY FOUNDER; founder E2E NOT EXECUTED |
| OCR / mapping correction teacher actions | **Out of scope** — [PREPROD_CORRECTION_WORKFLOW_DISPOSITION.md](./PREPROD_CORRECTION_WORKFLOW_DISPOSITION.md) |

---

## 3. Intentional skips / non-skips

| Pattern | Reason |
|---------|--------|
| No `test.skip` / `test.fix` in `e2e/real/` for the critical path | Real suite must fail closed when backend is up; CI expects green or red |
| B17 / B18 / B20 specs document “never skip” | Deterministic seeded cohorts; conditional skip would hide regressions |
| Adaptive UI branches (e.g. add region if no AI badge) | Not skips — provider/fixture variance handling while remaining on live path |
| Evaluation finalize via API in `publication.spec.ts` | Documented reliability trade-off; not a silent skip of evaluation |

If a future real test must skip, require an inline comment with ticket/reason and prefer `test.fix(..., false)` with a string reason over bare `test.skip`.

---

## 4. How CI runs real E2E

GitHub Actions job **Frontend** (`.github/workflows/ci.yml`):

1. Build `.env` from `.env.example` with `AI_PROVIDER_*=fixed`, `UPLOAD_SCANNER=fixed`, B19 test flags  
2. `docker compose up -d --build postgres redis minio api worker`  
3. Alembic upgrade + `seed_dev` + B17/B18/B19 E2E seed CLIs  
4. Wait for `http://127.0.0.1:18000/health`  
5. `pnpm install` + Playwright Chromium  
6. `pnpm test:e2e:real` with `API_UPSTREAM_URL=http://127.0.0.1:18000`  
7. Always `docker compose down -v` on that **CI disposable** stack (never founder MAT)

Local equivalent (disposable stack only — not MAT):

```bash
# from repo root, after disposable compose + migrate + seed_dev
cd apps/web
API_UPSTREAM_URL=http://127.0.0.1:18000 pnpm test:e2e:real
```

**Without Docker:** still land/improve specs and docs (this file). Do not claim local green real E2E. Rely on CI Frontend job for the live stack. Unit/lint/typecheck remain runnable without Docker.

---

## 5. Safety

- Do not reopen founder MAT to satisfy PREPROD-002.  
- Do not run destructive `docker compose down -v` against founder MAT volumes.  
- CI `down -v` applies only to the ephemeral Actions compose project.
