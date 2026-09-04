#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/../.."

if docker compose ps --status running --services | grep -qx api; then
  docker compose exec -T api alembic -c /app/alembic.ini upgrade head
else
  cd apps/api
  python -m alembic -c alembic.ini upgrade head
fi
