#!/usr/bin/env sh
# SAFE STUB: backup disposable PostgreSQL only.
# Requires DISPOSABLE_* env vars. Refuses MAT Compose defaults unless OVERRIDE_MAT_SAFETY=1.
# NEVER point at founder MAT volumes. Does not run docker compose down -v.
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

# Prefer URL; else discrete vars.
if [ -n "${DISPOSABLE_DATABASE_URL-}" ]; then
  TARGET_DESC="${DISPOSABLE_DATABASE_URL}"
  # Extract crude db name / port hints from URL for safety checks (best-effort).
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
  # DISPOSABLE_POSTGRES_PASSWORD may come from env or secret manager — do not echo it.
  DB_NAME="${DISPOSABLE_POSTGRES_DB}"
  DB_PORT="${DISPOSABLE_POSTGRES_PORT}"
  TARGET_DESC="${DISPOSABLE_POSTGRES_HOST}:${DISPOSABLE_POSTGRES_PORT}/${DISPOSABLE_POSTGRES_DB}"
fi

if is_mat_db_name "${DB_NAME:-}" || is_mat_port "${DB_PORT:-}"; then
  if [ "${OVERRIDE_MAT_SAFETY-}" != "1" ]; then
    refuse "target looks like MAT/local Compose default (db='${DB_NAME:-}' port='${DB_PORT:-}'). Use disposable names/ports or set OVERRIDE_MAT_SAFETY=1 (still prefer disposable)."
  fi
  echo "${SCRIPT_NAME}: WARNING: OVERRIDE_MAT_SAFETY=1 set; still prefer disposable targets." >&2
fi

if ! looks_disposable "${DB_NAME:-}" && ! looks_disposable "${DISPOSABLE_BACKUP_PATH}" && ! looks_disposable "${TARGET_DESC}"; then
  if [ "${OVERRIDE_MAT_SAFETY-}" != "1" ]; then
    refuse "name/path does not look disposable (include disposable|drill|tmp). Refusing."
  fi
fi

echo "${SCRIPT_NAME}: STUB — would backup Postgres from [${TARGET_DESC}] to [${DISPOSABLE_BACKUP_PATH}]"
echo "${SCRIPT_NAME}: Implement with pg_dump against DISPOSABLE_* only. No MAT volumes."
echo "${SCRIPT_NAME}: Example (not executed): pg_dump --format=custom --file=\"\$DISPOSABLE_BACKUP_PATH\" \"\$DISPOSABLE_DATABASE_URL\""
exit 0
