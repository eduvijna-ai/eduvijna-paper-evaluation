#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/../.."
cd apps/api
python -m pytest
