#!/usr/bin/env sh
# Ensure Docker deps, free host port 18000, and apply committed migrations for F5.
# Starts only postgres, redis, and minio. Does not start Docker api/worker.
# Never generates migrations, never reseeds, never resets volumes.
set -eu

cd "$(dirname "$0")/../.."
REPO_ROOT="$(pwd)"

step() { printf '==> %s\n' "$1"; }
fail() { printf 'ERROR: %s\n' "$1" >&2; exit 1; }

step "Checking Docker"
command -v docker >/dev/null 2>&1 || fail "Docker is not on PATH. Install Docker Desktop and retry."
docker info >/dev/null 2>&1 || fail "Docker is installed but the engine is not running. Start Docker Desktop and retry."

ENV_EXAMPLE="$REPO_ROOT/apps/api/.env.local.example"
ENV_LOCAL="$REPO_ROOT/apps/api/.env.local"
[ -f "$ENV_EXAMPLE" ] || fail "Missing $ENV_EXAMPLE"
if [ ! -f "$ENV_LOCAL" ]; then
  cp "$ENV_EXAMPLE" "$ENV_LOCAL"
  step "Created apps/api/.env.local from .env.local.example"
fi

WEB_ENV_EXAMPLE="$REPO_ROOT/apps/web/.env.local.example"
WEB_ENV_LOCAL="$REPO_ROOT/apps/web/.env.local"
if [ -f "$WEB_ENV_EXAMPLE" ] && [ ! -f "$WEB_ENV_LOCAL" ]; then
  cp "$WEB_ENV_EXAMPLE" "$WEB_ENV_LOCAL"
  step "Created apps/web/.env.local from .env.local.example"
fi

if [ -x "$REPO_ROOT/apps/api/.venv/bin/python" ]; then
  PYTHON="$REPO_ROOT/apps/api/.venv/bin/python"
elif [ -x "$REPO_ROOT/apps/api/.venv/Scripts/python.exe" ]; then
  PYTHON="$REPO_ROOT/apps/api/.venv/Scripts/python.exe"
else
  fail "Missing apps/api/.venv. From apps/api run: python3.12 -m venv .venv && .venv/bin/python -m pip install -e '.[dev]'"
fi

step "Starting Docker dependencies (postgres redis minio) - not api/worker"
if ! docker compose up -d --wait postgres redis minio; then
  step "docker compose --wait failed; retrying without --wait"
  docker compose up -d postgres redis minio
  n=0
  while [ "$n" -lt 45 ]; do
    pg="$(docker compose ps postgres --format '{{.Health}}' 2>/dev/null || true)"
    rd="$(docker compose ps redis --format '{{.Health}}' 2>/dev/null || true)"
    mn="$(docker compose ps minio --format '{{.Health}}' 2>/dev/null || true)"
    if [ "$pg" = "healthy" ] && [ "$rd" = "healthy" ] && [ "$mn" = "healthy" ]; then
      break
    fi
    n=$((n + 1))
    sleep 2
  done
  pg="$(docker compose ps postgres --format '{{.Health}}' 2>/dev/null || true)"
  rd="$(docker compose ps redis --format '{{.Health}}' 2>/dev/null || true)"
  mn="$(docker compose ps minio --format '{{.Health}}' 2>/dev/null || true)"
  [ "$pg" = "healthy" ] && [ "$rd" = "healthy" ] && [ "$mn" = "healthy" ] \
    || fail "postgres/redis/minio did not become healthy in time."
fi

# Host F5 binds 127.0.0.1:18000 - stop compose api/worker if present (volumes preserved).
running="$(docker compose ps --status running --services 2>/dev/null || true)"
to_stop=""
for svc in api worker; do
  echo "$running" | grep -qx "$svc" && to_stop="$to_stop $svc"
done
if [ -n "$(echo "$to_stop" | tr -d '[:space:]')" ]; then
  step "Stopping Docker api/worker to free port 18000 (volumes kept):$to_stop"
  # shellcheck disable=SC2086
  docker compose stop $to_stop || fail "Could not stop Docker api/worker. Free port 18000 manually and retry."
fi

step "Loading apps/api/.env.local into this process"
set -a
# shellcheck disable=SC1090
. "$ENV_LOCAL"
set +a
[ -n "${DATABASE_URL:-}" ] || fail "DATABASE_URL is not set after loading apps/api/.env.local"
case "$DATABASE_URL" in
  *@postgres:*|*@postgres/*|*@redis:*|*@minio:*)
    fail "apps/api/.env.local still uses Docker DNS names. Host F5 must use 127.0.0.1 publish ports."
    ;;
esac

step "Alembic upgrade head (committed migrations only; no seed/reset)"
cd "$REPO_ROOT/apps/api"
"$PYTHON" -m alembic -c alembic.ini upgrade head \
  || fail "Alembic upgrade head failed. Confirm PostgreSQL is reachable at 127.0.0.1:15432."
"$PYTHON" -m alembic -c alembic.ini current \
  || fail "Could not read Alembic current revision after upgrade."

step "Local API dependencies ready. F5 API listens on http://127.0.0.1:18000 (Docker volumes preserved)."
