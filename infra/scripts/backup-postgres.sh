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

# Prefer the end-to-end disposable Docker drill on Windows/local:
#   powershell -NoProfile -ExecutionPolicy Bypass -File infra/scripts/run-disposable-dr-drill.ps1
if [ "${DR_EXECUTE-}" = "1" ] && command -v pg_dump >/dev/null 2>&1; then
  mkdir -p "$(dirname "${DISPOSABLE_BACKUP_PATH}")"
  if [ -n "${DISPOSABLE_DATABASE_URL-}" ]; then
    pg_dump --format=custom --file="${DISPOSABLE_BACKUP_PATH}" "${DISPOSABLE_DATABASE_URL}"
  else
    export PGPASSWORD="${DISPOSABLE_POSTGRES_PASSWORD-}"
    pg_dump -h "${DISPOSABLE_POSTGRES_HOST}" -p "${DISPOSABLE_POSTGRES_PORT}" \
      -U "${DISPOSABLE_POSTGRES_USER}" -d "${DISPOSABLE_POSTGRES_DB}" \
      --format=custom --file="${DISPOSABLE_BACKUP_PATH}"
  fi
  echo "${SCRIPT_NAME}: backed up [${TARGET_DESC}] -> [${DISPOSABLE_BACKUP_PATH}]"
  exit 0
fi

echo "${SCRIPT_NAME}: safety-validated; set DR_EXECUTE=1 with pg_dump available to run, or use run-disposable-dr-drill.ps1"
echo "${SCRIPT_NAME}: target=[${TARGET_DESC}] path=[${DISPOSABLE_BACKUP_PATH}]"
exit 0
