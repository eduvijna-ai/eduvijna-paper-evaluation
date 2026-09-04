#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/../.."

docker compose config --quiet
sh infra/scripts/lint.sh
sh infra/scripts/typecheck.sh
sh infra/scripts/test.sh
node packages/contracts/scripts/validate.mjs
