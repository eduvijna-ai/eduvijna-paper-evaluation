# Real-backend Playwright suite

Hybrid UI against a live API (`NEXT_PUBLIC_API_MODE=hybrid`, `API_UPSTREAM_URL`).

- Config: `apps/web/playwright.real.config.ts`
- Script: `pnpm test:e2e:real`
- Coverage inventory, intentional shortcuts, and CI steps:  
  [`docs/engineering/PREPROD_REAL_E2E_COVERAGE.md`](../../../../docs/engineering/PREPROD_REAL_E2E_COVERAGE.md)

Requires a disposable Compose stack (postgres/redis/minio/api/worker) + migrate + seed.  
**Do not** point this suite at founder MAT or destroy MAT volumes.
