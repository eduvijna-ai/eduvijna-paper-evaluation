"""S3-compatible object storage for immutable submission evidence (ADR-003/009)."""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, BinaryIO, cast

import boto3
from botocore.exceptions import ClientError

from app.core.config import Settings, get_settings


class StorageImmutabilityError(RuntimeError):
    """Raised when a write would overwrite an existing raw object key."""


class StorageNotFoundError(LookupError):
    """Raised when an object key is missing."""


@dataclass(frozen=True)
class PutResult:
    key: str
    byte_size: int


def raw_object_key(tenant_id: uuid.UUID, content_sha256: str, filename: str) -> str:
    ext = _extension(filename)
    return f"{tenant_id}/raw/{content_sha256[:16]}/{uuid.uuid4()}{ext}"


def derived_page_key(tenant_id: uuid.UUID, submission_id: uuid.UUID, page_index: int) -> str:
    return f"{tenant_id}/derived/{submission_id}/pages/{page_index:04d}.png"


def _extension(filename: str) -> str:
    lower = filename.lower()
    if lower.endswith(".pdf"):
        return ".pdf"
    if lower.endswith(".png"):
        return ".png"
    if lower.endswith(".jpg") or lower.endswith(".jpeg"):
        return ".jpg"
    return ".bin"


class ObjectStorage:
    """Thin boto3 wrapper with write-once semantics for raw keys."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._client: Any | None = None

    @property
    def client(self) -> Any:
        if self._client is None:
            self._client = boto3.client(
                "s3",
                endpoint_url=self.settings.s3_endpoint_url,
                aws_access_key_id=self.settings.s3_access_key,
                aws_secret_access_key=self.settings.s3_secret_key,
                region_name=self.settings.s3_region,
            )
        return self._client

    def ensure_bucket(self) -> None:
        """Idempotent local/CI bootstrap only — never required in production."""
        bucket = self.settings.s3_bucket
        try:
            self.client.head_bucket(Bucket=bucket)
        except ClientError:
            self.client.create_bucket(Bucket=bucket)

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.settings.s3_bucket, Key=key)
            return True
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            if code in {"404", "NoSuchKey", "NotFound", "404 Not Found"}:
                return False
            raise

    def put_raw_bytes(
        self,
        *,
        key: str,
        body: bytes,
        content_type: str,
    ) -> PutResult:
        if self.exists(key):
            raise StorageImmutabilityError(f"raw key already exists: {key}")
        if "/raw/" not in key:
            raise ValueError("raw uploads must use a /raw/ key prefix")
        self.client.put_object(
            Bucket=self.settings.s3_bucket,
            Key=key,
            Body=body,
            ContentType=content_type,
        )
        return PutResult(key=key, byte_size=len(body))

    def put_derived_bytes(
        self,
        *,
        key: str,
        body: bytes,
        content_type: str = "image/png",
    ) -> PutResult:
        if "/derived/" not in key:
            raise ValueError("derived uploads must use a /derived/ key prefix")
        self.client.put_object(
            Bucket=self.settings.s3_bucket,
            Key=key,
            Body=body,
            ContentType=content_type,
        )
        return PutResult(key=key, byte_size=len(body))

    def get_bytes(self, key: str) -> bytes:
        try:
            response = self.client.get_object(Bucket=self.settings.s3_bucket, Key=key)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            if code in {"404", "NoSuchKey", "NotFound"}:
                raise StorageNotFoundError(key) from exc
            raise
        return cast(bytes, response["Body"].read())

    def open_stream(self, key: str) -> BinaryIO:
        try:
            response = self.client.get_object(Bucket=self.settings.s3_bucket, Key=key)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            if code in {"404", "NoSuchKey", "NotFound"}:
                raise StorageNotFoundError(key) from exc
            raise
        return cast(BinaryIO, response["Body"])

    def iter_chunks(self, key: str, chunk_size: int = 1024 * 1024) -> Iterator[bytes]:
        stream = self.open_stream(key)
        while True:
            chunk = stream.read(chunk_size)
            if not chunk:
                break
            yield chunk
