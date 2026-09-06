"""Derived answer-region crop generation (B5)."""

from __future__ import annotations

import hashlib
import io
import uuid
from decimal import Decimal

from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.models import AnswerRegion, SubmissionPage
from app.services.storage import ObjectStorage
from app.services.upload_validation import sha256_bytes


def bbox_fingerprint(
    *,
    x: Decimal | float,
    y: Decimal | float,
    width: Decimal | float,
    height: Decimal | float,
) -> str:
    payload = f"{float(x):.6f}:{float(y):.6f}:{float(width):.6f}:{float(height):.6f}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def derived_region_crop_key(
    tenant_id: uuid.UUID,
    submission_id: uuid.UUID,
    region_id: uuid.UUID,
    bbox_hash: str,
) -> str:
    return (
        f"{tenant_id}/derived/{submission_id}/regions/{region_id}/{bbox_hash}.png"
    )


async def ensure_region_crop(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    submission_id: uuid.UUID,
    region: AnswerRegion,
    page: SubmissionPage,
    storage: ObjectStorage | None = None,
    settings: Settings | None = None,
) -> tuple[str, str]:
    """Generate or reuse a derived crop for the region's current bbox.

    Returns ``(crop_storage_key, crop_content_sha256)``.
    Never writes under ``/raw/``.
    """
    settings = settings or get_settings()
    storage = storage or ObjectStorage(settings)

    if page.tenant_id != tenant_id or region.tenant_id != tenant_id:
        raise PermissionError("tenant scope mismatch for crop generation")
    if page.id != region.submission_page_id:
        raise ValueError("region/page mismatch")

    bbox_hash = bbox_fingerprint(
        x=region.bbox_x,
        y=region.bbox_y,
        width=region.bbox_width,
        height=region.bbox_height,
    )
    key = derived_region_crop_key(tenant_id, submission_id, region.id, bbox_hash)

    # Reuse when fingerprint still matches persisted crop metadata.
    if (
        region.crop_storage_key == key
        and region.crop_content_sha256
        and storage.exists(key)
    ):
        return region.crop_storage_key, region.crop_content_sha256

    page_bytes = storage.get_bytes(page.image_storage_key)
    with Image.open(io.BytesIO(page_bytes)) as image:
        image = image.convert("RGB")
        w, h = image.size
        left = int(float(region.bbox_x) * w)
        top = int(float(region.bbox_y) * h)
        right = int((float(region.bbox_x) + float(region.bbox_width)) * w)
        bottom = int((float(region.bbox_y) + float(region.bbox_height)) * h)
        left = max(0, min(left, w - 1))
        top = max(0, min(top, h - 1))
        right = max(left + 1, min(right, w))
        bottom = max(top + 1, min(bottom, h))
        crop = image.crop((left, top, right, bottom))
        out = io.BytesIO()
        crop.save(out, format="PNG")
        png = out.getvalue()

    digest = sha256_bytes(png)
    storage.put_derived_bytes(key=key, body=png, content_type="image/png")
    region.crop_storage_key = key
    region.crop_content_sha256 = digest
    await db.flush()
    return key, digest
