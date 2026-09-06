# EduVijna Paper Evaluation

Enterprise AI-assisted handwritten assessment platform — Client Validation Build (CVB) v0.1.

## Overview

EduVijna evaluates raw, unmarked handwritten answer sheets through a structured pipeline:

**source evidence → structured understanding → rubric decisions → evaluation ledger → human approval → published result → learning evidence**

AI proposes; institution/teacher remains the final authority.

## Repository layout

| Path | Owner | Purpose |
|------|-------|---------|
| `apps/api` | Cursor A | FastAPI backend |
| `workers` | Cursor A | Celery workers |
| `ai` | Cursor A | AI provider abstractions |
| `infra` | Cursor A | Docker & scripts |
| `database/migrations` | Cursor A | Alembic migrations |
| `apps/web` | Cursor B | Next.js frontend (CVB shell + mock API) |
| `packages/ui` | Cursor B | Shared UI package (placeholder) |
| `packages/contracts` | Shared | OpenAPI & JSON schemas |

## Quick start

```bash
# Bootstrap local environment
make bootstrap   # or: infra/scripts/bootstrap.sh / .ps1

# Start infrastructure + API
make up

# Run verification suite
make verify
```

See [docs/engineering/DEVELOPMENT_WORKFLOW.md](docs/engineering/DEVELOPMENT_WORKFLOW.md) for full developer workflow.

## Documentation

- [Master Product Scope](docs/product/MASTER_PRODUCT_SCOPE.md)
- [Requirements Register](docs/product/REQUIREMENTS_REGISTER.md)
- [Architecture](docs/architecture/ADR_INDEX.md)
- [Verification Report](docs/engineering/VERIFICATION_REPORT.md)

## License

Proprietary — EduVijna. All rights reserved.
