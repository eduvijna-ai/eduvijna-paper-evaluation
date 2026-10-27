# EduVijna Web — Paper Evaluation Frontend

Next.js App Router UI for the **Client Validation Build (CVB)**.

## Stack

- Next.js 15 (App Router) + React 19 + TypeScript strict
- Tailwind CSS v4 (`@tailwindcss/postcss`)
- TanStack Query, React Hook Form, Zod
- Vitest (unit) + Playwright (e2e smoke)
- Mock API adapter (`NEXT_PUBLIC_API_MODE=mock`, default)

## Quick start

One-time from repo root: `pnpm install`.

Everyday (founder MAT) from `apps/web`:

```bash
npm run dev
```

(`pnpm dev` / `pnpm --filter web dev` are equivalent.)

Open [http://localhost:3000/login](http://localhost:3000/login). Dev defaults (`apps/web/.env.development`) use `NEXT_PUBLIC_API_MODE=hybrid` and rewrite to `http://127.0.0.1:18000` — start the backend with F5 first.

## Scripts

| Script | Purpose |
|--------|---------|
| `pnpm dev` | Next.js dev server (Turbopack) |
| `pnpm build` | Production build |
| `pnpm start` | Start production server |
| `pnpm lint` | ESLint |
| `pnpm typecheck` | `tsc --noEmit` |
| `pnpm test` | Vitest unit tests |
| `pnpm test:watch` | Vitest watch mode |
| `pnpm test:e2e` | Playwright smoke |
| `pnpm test:e2e:ui` | Playwright UI mode |

## Architecture notes

- Authenticated routes live under `src/app/(app)` with `AppShell` (sidebar + top bar).
- `/login` is outside the shell; demo session is stored in `localStorage` (+ role cookie).
- Domain services: `src/lib/api` — typed client with **mock adapter** swappable to HTTP when OpenAPI domain endpoints exist.
- Synthetic fixtures only (`Demo Student 001`, roll `DEMO-001`). Placeholder paper viewer — no real PDFs.
- Visual language: slate/teal enterprise education — evidence, clarity, teacher efficiency.

## Key screens

- Evaluation workspace (3-column): paper · question/key/rubric · AI + teacher actions
- Identity / mapping review queues
- Student & parent reports
- Assessment / student analytics
- Adaptive learning priorities + improvement assessment blueprint

## Environment

| Variable | Default | Notes |
|----------|---------|-------|
| `NEXT_PUBLIC_API_MODE` | `hybrid` in `.env.development` (`mock` if unset) | Playwright mock e2e forces `mock`; real e2e forces `hybrid` |
| `API_UPSTREAM_URL` | `http://127.0.0.1:18000` | Next rewrite target for `/api/*`, `/health`, `/ready` |

See also:

- [FRONTEND_CONTRACT_REQUESTS.md](../../docs/engineering/FRONTEND_CONTRACT_REQUESTS.md)
- [FRONTEND_VERIFICATION_REPORT.md](../../docs/engineering/FRONTEND_VERIFICATION_REPORT.md)
