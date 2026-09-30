#!/usr/bin/env sh
# SAFE STUB: orchestrate synthetic DR restore drill on disposable resources only.
# Does NOT destroy MAT volumes. Does NOT run docker compose down -v.
set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname "$0")" && pwd)"
SCRIPT_NAME="$(basename "$0")"

refuse() {
  echo "${SCRIPT_NAME}: REFUSED: $*" >&2
  exit 2
}

require_var() {
  eval "val=\${$1-}"
  if [ -z "${val}" ]; then
    refuse "missing required env var $1"
  fi
}

require_var DISPOSABLE_BACKUP_DIR
require_var DISPOSABLE_RESTORE_CONFIRM
if [ "${DISPOSABLE_RESTORE_CONFIRM}" != "YES_DISPOSABLE_ONLY" ]; then
  refuse "set DISPOSABLE_RESTORE_CONFIRM=YES_DISPOSABLE_ONLY"
fi

# Postgres disposable target
if [ -z "${DISPOSABLE_DATABASE_URL-}" ]; then
  require_var DISPOSABLE_POSTGRES_HOST
  require_var DISPOSABLE_POSTGRES_PORT
  require_var DISPOSABLE_POSTGRES_DB
  require_var DISPOSABLE_POSTGRES_USER
fi

# Object storage disposable target
require_var DISPOSABLE_S3_ENDPOINT_URL
require_var DISPOSABLE_S3_BUCKET

export DISPOSABLE_BACKUP_PATH="${DISPOSABLE_BACKUP_DIR}/postgres.dump"
echo "${SCRIPT_NAME}: step 1/4 backup-postgres (stub)"
sh "${SCRIPT_DIR}/backup-postgres.sh"

export DISPOSABLE_BACKUP_PATH="${DISPOSABLE_BACKUP_DIR}/object-storage"
echo "${SCRIPT_NAME}: step 2/4 backup-object-storage (stub)"
sh "${SCRIPT_DIR}/backup-object-storage.sh"

export DISPOSABLE_BACKUP_PATH="${DISPOSABLE_BACKUP_DIR}/postgres.dump"
echo "${SCRIPT_NAME}: step 3/4 restore-postgres (stub) — operator must recreate disposable DB out-of-band"
sh "${SCRIPT_DIR}/restore-postgres.sh"

export DISPOSABLE_BACKUP_PATH="${DISPOSABLE_BACKUP_DIR}/object-storage"
echo "${SCRIPT_NAME}: step 4/4 restore-object-storage (stub)"
sh "${SCRIPT_DIR}/restore-object-storage.sh"

echo "${SCRIPT_NAME}: STUB drill complete. Record duration/RTO observations in docs/production/BACKUP_RESTORE_DR.md"
echo "${SCRIPT_NAME}: Redis is not SoT — expect empty broker after synthetic rebuild."
exit 0
