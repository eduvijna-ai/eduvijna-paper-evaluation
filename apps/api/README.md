# EduVijna Paper Evaluation API

Python 3.12 FastAPI foundation for the EduVijna Paper Evaluation service.

## Local development

```bash
python -m venv .venv
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Configuration is read from environment variables. Common settings are
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
