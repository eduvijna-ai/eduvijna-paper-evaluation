#!/usr/bin/env sh
# SAFE STUB: backup disposable S3-compatible object storage only.
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
# Credentials: DISPOSABLE_S3_ACCESS_KEY / DISPOSABLE_S3_SECRET_KEY — never echo secrets.

if is_mat_bucket "${DISPOSABLE_S3_BUCKET}" || is_mat_endpoint "${DISPOSABLE_S3_ENDPOINT_URL}"; then
  if [ "${OVERRIDE_MAT_SAFETY-}" != "1" ]; then
    refuse "object-storage target looks like MAT/local MinIO default (bucket='${DISPOSABLE_S3_BUCKET}' endpoint='${DISPOSABLE_S3_ENDPOINT_URL}')."
  fi
  echo "${SCRIPT_NAME}: WARNING: OVERRIDE_MAT_SAFETY=1 set; still prefer disposable bucket/endpoint." >&2
fi

if ! looks_disposable "${DISPOSABLE_S3_BUCKET}" && ! looks_disposable "${DISPOSABLE_BACKUP_PATH}"; then
  if [ "${OVERRIDE_MAT_SAFETY-}" != "1" ]; then
    refuse "bucket/path does not look disposable (include disposable|drill|tmp)."
  fi
fi

echo "${SCRIPT_NAME}: STUB — would sync s3://${DISPOSABLE_S3_BUCKET} from ${DISPOSABLE_S3_ENDPOINT_URL} to ${DISPOSABLE_BACKUP_PATH}"
echo "${SCRIPT_NAME}: Use aws CLI or compatible tool against DISPOSABLE_* only. Do not touch MAT miniodata volume."
exit 0
