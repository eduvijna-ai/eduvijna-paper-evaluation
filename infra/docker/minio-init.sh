#!/bin/sh
# Create the local papers bucket if missing (idempotent).
set -eu

MC_ALIAS="${MC_ALIAS:-local}"
ENDPOINT="${S3_ENDPOINT_URL:-http://minio:9000}"
ACCESS_KEY="${MINIO_ROOT_USER:-eduvijna_minio}"
SECRET_KEY="${MINIO_ROOT_PASSWORD:-eduvijna_minio_dev_only}"
BUCKET="${S3_BUCKET:-eduvijna-papers}"

until curl -sf "${ENDPOINT}/minio/health/live" >/dev/null 2>&1; do
  sleep 1
done

mc alias set "${MC_ALIAS}" "${ENDPOINT}" "${ACCESS_KEY}" "${SECRET_KEY}"
mc mb --ignore-existing "${MC_ALIAS}/${BUCKET}"
echo "MinIO bucket ready: ${BUCKET}"
