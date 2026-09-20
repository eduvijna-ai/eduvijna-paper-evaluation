# EduVijna Paper Evaluation API

Python 3.12 FastAPI foundation for the EduVijna Paper Evaluation service.

## Local development

### Cursor / VS Code F5 (recommended for MAT)

1. Create a venv once: `python -m venv .venv` then `.venv\Scripts\python.exe -m pip install -e ".[dev]"` (Unix: `.venv/bin/python -m pip install -e ".[dev]"`).
2. Copy `apps/api/.env.local.example` → `apps/api/.env.local` if missing (F5 prepare also does this).
3. From the repo root, select **EduVijna Backend + Worker — Local MAT** and press **F5**.

That starts Docker postgres/redis/minio (if needed), applies committed migrations, then runs host uvicorn on `http://127.0.0.1:18000` plus Celery worker+beat. It does **not** reseed or reset volumes.

### Manual

```bash
python -m venv .venv
pip install -e ".[dev]"
# load apps/api/.env.local (host ports), then:
uvicorn app.main:app --host 127.0.0.1 --port 18000 --reload
```

Configuration is read from environment variables (and VS Code `envFile`). Common settings are
`DATABASE_URL`, `ENVIRONMENT`, `GIT_SHA`, `LOG_LEVEL`, and `API_VERSION`.

From the repository root, apply migrations with:

```bash
alembic -c apps/api/alembic.ini upgrade head
```

Run checks from `apps/api`:

```bash
pytest
ruff check .
mypy app
```
