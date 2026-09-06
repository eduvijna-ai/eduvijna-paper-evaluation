#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/../.."
docker compose down -v
docker compose up -d --build
sh infra/scripts/migrate.sh
