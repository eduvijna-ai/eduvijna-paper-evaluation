"""Streaming upload validation for CVB submission evidence."""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass

from fastapi import HTTPException, UploadFile

ALLOWED_MIME = {
    "application/pdf": (b"%PDF",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/jpeg": (b"\xff\xd8\xff",),
}

MIME_BY_EXT = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}


@dataclass(frozen=True)
class ValidatedUpload:
    filename: str
    mime_type: str
    content_sha256: str
    byte_size: int
    # Bounded by SUBMISSION_UPLOAD_MAX_BYTES (default 50 MiB) — buffered after streaming hash.
    body: bytes


def _detect_mime(filename: str, declared: str | None, header: bytes) -> str:
    lower = filename.lower()
    ext_mime = None
    for ext, mime in MIME_BY_EXT.items():
        if lower.endswith(ext):
            ext_mime = mime
            break
    if ext_mime is None:
        raise HTTPException(
            status_code=400,
            detail={"code": "UNSUPPORTED_MEDIA_TYPE", "message": "Only PDF, PNG, or JPEG accepted"},
        )

    declared_norm = (declared or "").split(";")[0].strip().lower()
    allowed_declared = declared_norm in ALLOWED_MIME or declared_norm == "application/octet-stream"
    if declared_norm and not allowed_declared:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "UNSUPPORTED_MEDIA_TYPE",
                "message": "Declared MIME type is not allowed",
            },
        )

    signatures = ALLOWED_MIME[ext_mime]
    if not any(header.startswith(sig) for sig in signatures):
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_FILE_SIGNATURE",
                "message": "File content does not match an allowed PDF/PNG/JPEG signature",
            },
        )
    return ext_mime


async def validate_and_buffer_upload(
    upload: UploadFile,
    *,
    max_bytes: int,
) -> ValidatedUpload:
    filename = upload.filename or "upload.bin"
    hasher = hashlib.sha256()
    chunks: list[bytes] = []
    total = 0
    header = b""

    while True:
        chunk = await upload.read(1024 * 1024)
        if not chunk:
            break
        if not header:
            header = chunk[:16]
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=413,
                detail={
                    "code": "FILE_TOO_LARGE",
                    "message": f"Upload exceeds maximum of {max_bytes} bytes",
                },
            )
        hasher.update(chunk)
        chunks.append(chunk)

    if total == 0:
        raise HTTPException(
            status_code=400,
            detail={"code": "EMPTY_FILE", "message": "Upload file is empty"},
        )

    mime = _detect_mime(filename, upload.content_type, header)
    body = b"".join(chunks)
    return ValidatedUpload(
        filename=filename,
        mime_type=mime,
        content_sha256=hasher.hexdigest(),
        byte_size=total,
        body=body,
    )


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_stream(stream: io.BufferedIOBase, chunk_size: int = 1024 * 1024) -> str:
    hasher = hashlib.sha256()
    while True:
        chunk = stream.read(chunk_size)
        if not chunk:
            break
        hasher.update(chunk)
    return hasher.hexdigest()
