"""PEV-069 upload malware scan hook (provider-neutral seam)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from app.core.config import Settings, get_settings

ScanStatus = Literal["NOT_CONFIGURED", "CLEAN", "REJECTED", "ERROR"]


@dataclass(frozen=True)
class UploadScanResult:
    status: ScanStatus
    detail: str | None = None


class UploadScanner(Protocol):
    async def scan(
        self, *, filename: str, mime_type: str, content: bytes
    ) -> UploadScanResult: ...


class NoneUploadScanner:
    """No-op scanner — always NOT_CONFIGURED; never reports CLEAN."""

    async def scan(
        self, *, filename: str, mime_type: str, content: bytes
    ) -> UploadScanResult:
        return UploadScanResult(status="NOT_CONFIGURED")


class FixedUploadScanner:
    """Deterministic CI/testing scanner. Rejects obvious malware markers."""

    async def scan(
        self, *, filename: str, mime_type: str, content: bytes
    ) -> UploadScanResult:
        lower = filename.lower()
        if "malware" in lower:
            return UploadScanResult(status="REJECTED", detail="filename_marker")
        if content.startswith(b"MALWARE"):
            return UploadScanResult(status="REJECTED", detail="content_marker")
        return UploadScanResult(status="CLEAN")


def get_upload_scanner(settings: Settings | None = None) -> UploadScanner:
    settings = settings or get_settings()
    mode = (settings.upload_scanner or "none").strip().lower()
    if mode in {"", "none"}:
        return NoneUploadScanner()
    if mode == "fixed":
        env = settings.environment.lower()
        if env in {"production", "prod"}:
            raise RuntimeError("fixed upload scanner is not allowed in production")
        return FixedUploadScanner()
    raise RuntimeError(f"Unsupported UPLOAD_SCANNER={mode!r}")
