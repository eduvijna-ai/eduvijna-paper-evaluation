#!/usr/bin/env sh
# SAFE STUB: restore object storage into disposable bucket only.
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

is_mat_bucket() {
  case "$1" in
    eduvijna-papers|eduvijna) return 0 ;;
    *) return 1 ;;
  esac
}

is_mat_endpoint() {
  printf '%s' "$1" | grep -E ':19000(/|$)' >/dev/null 2>&1
}

looks_disposable() {
  printf '%s' "$1" | grep -Ei 'disposable|drill|tmp|throwaway' >/dev/null 2>&1
}

require_var DISPOSABLE_S3_ENDPOINT_URL
require_var DISPOSABLE_S3_BUCKET
require_var DISPOSABLE_BACKUP_PATH
require_var DISPOSABLE_RESTORE_CONFIRM
if [ "${DISPOSABLE_RESTORE_CONFIRM}" != "YES_DISPOSABLE_ONLY" ]; then
  refuse "set DISPOSABLE_RESTORE_CONFIRM=YES_DISPOSABLE_ONLY to acknowledge isolated restore"
fi

if is_mat_bucket "${DISPOSABLE_S3_BUCKET}" || is_mat_endpoint "${DISPOSABLE_S3_ENDPOINT_URL}"; then
  if [ "${OVERRIDE_MAT_SAFETY-}" != "1" ]; then
    refuse "restore bucket/endpoint looks like MAT/local MinIO default (bucket='${DISPOSABLE_S3_BUCKET}')."
  fi
  echo "${SCRIPT_NAME}: WARNING: OVERRIDE_MAT_SAFETY=1 set; still prefer disposable targets." >&2
fi

if ! looks_disposable "${DISPOSABLE_S3_BUCKET}" && ! looks_disposable "${DISPOSABLE_BACKUP_PATH}"; then
  if [ "${OVERRIDE_MAT_SAFETY-}" != "1" ]; then
    refuse "bucket/path does not look disposable (include disposable|drill|tmp)."
  fi
fi

echo "${SCRIPT_NAME}: STUB — would restore ${DISPOSABLE_BACKUP_PATH} into s3://${DISPOSABLE_S3_BUCKET} at ${DISPOSABLE_S3_ENDPOINT_URL}"
echo "${SCRIPT_NAME}: NEVER overwrite founder MAT object volumes."
exit 0
