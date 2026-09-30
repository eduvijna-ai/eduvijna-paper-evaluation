#!/usr/bin/env sh
# SAFE STUB: restore PostgreSQL into disposable instance only.
set -eu

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

is_mat_db_name() {
  case "$1" in
    eduvijna|eduvijna_mat|postgres) return 0 ;;
    *) return 1 ;;
  esac
}

is_mat_port() {
  case "$1" in
    15432) return 0 ;;
    *) return 1 ;;
  esac
}

looks_disposable() {
  printf '%s' "$1" | grep -Ei 'disposable|drill|tmp|throwaway' >/dev/null 2>&1
}

require_var DISPOSABLE_BACKUP_PATH
require_var DISPOSABLE_RESTORE_CONFIRM
if [ "${DISPOSABLE_RESTORE_CONFIRM}" != "YES_DISPOSABLE_ONLY" ]; then
  refuse "set DISPOSABLE_RESTORE_CONFIRM=YES_DISPOSABLE_ONLY to acknowledge isolated restore"
fi

if [ -n "${DISPOSABLE_DATABASE_URL-}" ]; then
  TARGET_DESC="${DISPOSABLE_DATABASE_URL}"
  DB_NAME="${DISPOSABLE_POSTGRES_DB-}"
  DB_PORT="${DISPOSABLE_POSTGRES_PORT-}"
  if [ -z "${DB_NAME}" ]; then
    DB_NAME="$(printf '%s' "${DISPOSABLE_DATABASE_URL}" | sed -n 's|.*/\([^/?]*\).*|\1|p')"
  fi
  if [ -z "${DB_PORT}" ]; then
    DB_PORT="$(printf '%s' "${DISPOSABLE_DATABASE_URL}" | sed -n 's|.*:\([0-9][0-9]*\)/.*|\1|p')"
  fi
else
  require_var DISPOSABLE_POSTGRES_HOST
  require_var DISPOSABLE_POSTGRES_PORT
  require_var DISPOSABLE_POSTGRES_DB
  require_var DISPOSABLE_POSTGRES_USER
  DB_NAME="${DISPOSABLE_POSTGRES_DB}"
  DB_PORT="${DISPOSABLE_POSTGRES_PORT}"
  TARGET_DESC="${DISPOSABLE_POSTGRES_HOST}:${DISPOSABLE_POSTGRES_PORT}/${DISPOSABLE_POSTGRES_DB}"
fi

if is_mat_db_name "${DB_NAME:-}" || is_mat_port "${DB_PORT:-}"; then
  if [ "${OVERRIDE_MAT_SAFETY-}" != "1" ]; then
    refuse "restore target looks like MAT/local Compose default (db='${DB_NAME:-}' port='${DB_PORT:-}'). Use disposable DB or OVERRIDE_MAT_SAFETY=1 (still prefer disposable)."
  fi
  echo "${SCRIPT_NAME}: WARNING: OVERRIDE_MAT_SAFETY=1 set; still prefer disposable targets." >&2
fi

if ! looks_disposable "${DB_NAME:-}" && ! looks_disposable "${TARGET_DESC}"; then
  if [ "${OVERRIDE_MAT_SAFETY-}" != "1" ]; then
    refuse "restore target name does not look disposable (include disposable|drill|tmp)."
  fi
fi

echo "${SCRIPT_NAME}: STUB — would restore [${DISPOSABLE_BACKUP_PATH}] into [${TARGET_DESC}]"
echo "${SCRIPT_NAME}: NEVER destroy founder MAT volumes. Prefer pg_restore into empty disposable DB."
echo "${SCRIPT_NAME}: Example (not executed): pg_restore --clean --if-exists --dbname=\"\$DISPOSABLE_DATABASE_URL\" \"\$DISPOSABLE_BACKUP_PATH\""
exit 0
