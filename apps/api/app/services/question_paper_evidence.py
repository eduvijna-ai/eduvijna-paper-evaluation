"""Build bounded question-paper evidence from immutable AssessmentArtifact bytes."""

from __future__ import annotations

import hashlib
import io
import logging
from typing import Any

from app.ai.types import QuestionPaperEvidencePage, QuestionPaperParseInput
from app.core.config import Settings, get_settings
from app.db.models import Assessment, AssessmentArtifact, AssessmentVersion
from app.services.storage import ObjectStorage, StorageNotFoundError

logger = logging.getLogger(__name__)


class QuestionPaperEvidenceError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_and_verify_artifact_bytes(
    artifact: AssessmentArtifact,
    *,
    storage: ObjectStorage | None = None,
) -> bytes:
    store = storage or ObjectStorage()
    if not store.exists(artifact.storage_key):
        raise QuestionPaperEvidenceError(
            "ASSESSMENT_ARTIFACT_INTEGRITY_ERROR",
            "Assessment artifact storage object is missing",
        )
    try:
        raw = store.get_bytes(artifact.storage_key)
    except StorageNotFoundError as exc:
        raise QuestionPaperEvidenceError(
            "ASSESSMENT_ARTIFACT_INTEGRITY_ERROR",
            "Assessment artifact storage object is missing",
        ) from exc
    if len(raw) != int(artifact.byte_size):
        raise QuestionPaperEvidenceError(
            "ASSESSMENT_ARTIFACT_INTEGRITY_ERROR",
            "Stored artifact byte size does not match record",
        )
    if _sha256(raw) != artifact.content_sha256:
        raise QuestionPaperEvidenceError(
            "ASSESSMENT_ARTIFACT_INTEGRITY_ERROR",
            "Stored artifact SHA-256 does not match record",
        )
    return raw


def _useful_text(text: str) -> str | None:
    cleaned = " ".join(text.split()).strip()
    if len(cleaned) < 8:
        return None
    return cleaned


def _render_page_png(
    page: Any,
    *,
    max_pixels: int,
    max_image_bytes: int,
) -> tuple[bytes | None, int | None, int | None]:
    """Render a page to a bounded PNG. Returns (png, width, height)."""
    rect = page.rect
    width = float(rect.width)
    height = float(rect.height)
    if width <= 0 or height <= 0:
        return None, None, None
    # Target ~150 DPI equivalent but cap total pixels.
    scale = min(2.0, (max_pixels / (width * height)) ** 0.5)
    if scale <= 0:
        return None, None, None
    try:
        import pymupdf
    except ImportError as exc:  # pragma: no cover
        raise QuestionPaperEvidenceError(
            "QUESTION_PAPER_EVIDENCE_UNAVAILABLE",
            "PyMuPDF is required for PDF evidence extraction",
        ) from exc
    mat = pymupdf.Matrix(scale, scale)  # type: ignore[no-untyped-call]
    pix = page.get_pixmap(matrix=mat, alpha=False)
    if pix.width * pix.height > max_pixels:
        return None, None, None
    png = pix.tobytes("png")
    if len(png) > max_image_bytes:
        return None, None, None
    return png, int(pix.width), int(pix.height)


def extract_pdf_evidence(
    raw: bytes,
    *,
    settings: Settings | None = None,
) -> list[QuestionPaperEvidencePage]:
    cfg = settings or get_settings()
    try:
        import pymupdf
    except ImportError as exc:  # pragma: no cover
        raise QuestionPaperEvidenceError(
            "QUESTION_PAPER_EVIDENCE_UNAVAILABLE",
            "PyMuPDF is required for PDF evidence extraction",
        ) from exc

    try:
        doc = pymupdf.open(stream=raw, filetype="pdf")  # type: ignore[no-untyped-call]
    except Exception as exc:  # noqa: BLE001
        raise QuestionPaperEvidenceError(
            "QUESTION_PAPER_EVIDENCE_INVALID",
            "Uploaded PDF could not be opened",
        ) from exc

    try:
        page_count = doc.page_count
        if page_count <= 0:
            raise QuestionPaperEvidenceError(
                "QUESTION_PAPER_EVIDENCE_EMPTY",
                "PDF has no pages",
            )
        if page_count > cfg.authoring_parse_max_pages:
            raise QuestionPaperEvidenceError(
                "QUESTION_PAPER_TOO_MANY_PAGES",
                f"PDF exceeds max pages ({cfg.authoring_parse_max_pages})",
            )

        pages: list[QuestionPaperEvidencePage] = []
        total_chars = 0
        for index in range(page_count):
            page = doc.load_page(index)  # type: ignore[no-untyped-call]
            raw_text = page.get_text("text") or ""
            useful = _useful_text(raw_text)
            page_text: str | None = None
            if useful is not None:
                capped = useful[: cfg.authoring_parse_max_page_text_chars]
                remaining = cfg.authoring_parse_max_text_chars - total_chars
                if remaining <= 0:
                    page_text = None
                else:
                    page_text = capped[:remaining]
                    total_chars += len(page_text)

            png: bytes | None = None
            width: int | None = None
            height: int | None = None
            if page_text is None:
                png, width, height = _render_page_png(
                    page,
                    max_pixels=cfg.authoring_parse_max_render_pixels,
                    max_image_bytes=cfg.authoring_parse_max_image_bytes,
                )

            pages.append(
                QuestionPaperEvidencePage(
                    page_index=index,
                    extracted_text=page_text,
                    rendered_image_png=png,
                    width=width,
                    height=height,
                    has_visual_evidence=png is not None,
                )
            )

        if not any(p.extracted_text or p.has_visual_evidence for p in pages):
            raise QuestionPaperEvidenceError(
                "QUESTION_PAPER_EVIDENCE_EMPTY",
                "No usable text or visual evidence extracted from PDF",
            )
        return pages
    finally:
        doc.close()  # type: ignore[no-untyped-call]


def extract_image_evidence(
    raw: bytes,
    *,
    mime_type: str,
    settings: Settings | None = None,
) -> list[QuestionPaperEvidencePage]:
    cfg = settings or get_settings()
    if len(raw) > cfg.authoring_parse_max_image_bytes:
        raise QuestionPaperEvidenceError(
            "QUESTION_PAPER_IMAGE_TOO_LARGE",
            "Image exceeds authoring parse byte bound",
        )
    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover
        raise QuestionPaperEvidenceError(
            "QUESTION_PAPER_EVIDENCE_UNAVAILABLE",
            "Pillow is required for image question-paper evidence",
        ) from exc

    try:
        with Image.open(io.BytesIO(raw)) as img:
            img.load()
            width, height = img.size
            if width * height > cfg.authoring_parse_max_render_pixels:
                raise QuestionPaperEvidenceError(
                    "QUESTION_PAPER_IMAGE_TOO_LARGE",
                    "Image exceeds authoring parse pixel bound",
                )
            # Re-encode as PNG for a stable multimodal payload.
            buf = io.BytesIO()
            converted = img.convert("RGB") if img.mode not in {"RGB", "L"} else img
            converted.save(buf, format="PNG", optimize=True)
            png = buf.getvalue()
    except QuestionPaperEvidenceError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise QuestionPaperEvidenceError(
            "QUESTION_PAPER_EVIDENCE_INVALID",
            f"Uploaded {mime_type} could not be decoded",
        ) from exc

    if len(png) > cfg.authoring_parse_max_image_bytes:
        raise QuestionPaperEvidenceError(
            "QUESTION_PAPER_IMAGE_TOO_LARGE",
            "Encoded image exceeds authoring parse byte bound",
        )
    return [
        QuestionPaperEvidencePage(
            page_index=0,
            extracted_text=None,
            rendered_image_png=png,
            width=width,
            height=height,
            has_visual_evidence=True,
        )
    ]


def build_parse_input_from_artifact(
    *,
    assessment: Assessment,
    version: AssessmentVersion,
    artifact: AssessmentArtifact,
    settings: Settings | None = None,
    storage: ObjectStorage | None = None,
) -> QuestionPaperParseInput:
    cfg = settings or get_settings()
    raw = load_and_verify_artifact_bytes(artifact, storage=storage)
    mime = (artifact.mime_type or "").lower()
    filename_l = artifact.original_filename.lower()
    if mime == "application/pdf" or filename_l.endswith(".pdf"):
        pages = extract_pdf_evidence(raw, settings=cfg)
    elif mime in {"image/png", "image/jpeg", "image/jpg"} or filename_l.endswith(
        (".png", ".jpg", ".jpeg")
    ):
        pages = extract_image_evidence(raw, mime_type=mime or "image/png", settings=cfg)
    else:
        raise QuestionPaperEvidenceError(
            "QUESTION_PAPER_UNSUPPORTED_MIME",
            f"Unsupported question-paper MIME type: {mime or 'unknown'}",
        )

    return QuestionPaperParseInput(
        assessment_id=assessment.id,
        assessment_version_id=version.id,
        assessment_title=assessment.title,
        max_marks=version.max_marks,
        assessment_artifact_id=artifact.id,
        content_sha256=artifact.content_sha256,
        mime_type=artifact.mime_type,
        original_filename=artifact.original_filename,
        evidence_pages=pages,
    )


def evidence_trace_summary(pages: list[QuestionPaperEvidencePage]) -> dict[str, Any]:
    """Safe summary for AiExecutionRecord — never includes bytes/base64."""
    return {
        "page_count": len(pages),
        "text_page_count": sum(1 for p in pages if p.extracted_text),
        "visual_page_count": sum(1 for p in pages if p.has_visual_evidence),
        "text_char_count": sum(len(p.extracted_text or "") for p in pages),
    }
