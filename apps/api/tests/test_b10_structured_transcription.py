"""B10 PEV-013 structured transcription segment contracts."""

from __future__ import annotations

import inspect
import uuid
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.ai.providers.fixed import FixedStructureProvider
from app.ai.types import (
    TranscriptionInput,
    TranscriptionResult,
    TranscriptionSegment,
    TranscriptionTable,
)
from app.services import transcription as transcription_service


def test_legacy_text_only_segment_validates() -> None:
    seg = TranscriptionSegment.model_validate({"text": "legacy answer line"})
    assert seg.kind == "TEXT"
    assert seg.text == "legacy answer line"
    assert seg.latex is None
    assert seg.table is None


def test_math_segment_with_latex() -> None:
    seg = TranscriptionSegment(
        kind="MATH",
        latex=r"\frac{a}{b}",
        step_index=1,
        confidence=Decimal("0.9"),
    )
    assert seg.kind == "MATH"
    assert seg.latex == r"\frac{a}{b}"
    assert seg.text is None


def test_table_segment_ok() -> None:
    seg = TranscriptionSegment(
        kind="TABLE",
        table=TranscriptionTable(rows=[["h1", "h2"], ["1", "2"]]),
        step_index=2,
    )
    assert seg.table is not None
    assert len(seg.table.rows) == 2


def test_invalid_non_rectangular_table_rejected() -> None:
    with pytest.raises(ValidationError):
        TranscriptionSegment(
            kind="TABLE",
            table=TranscriptionTable(rows=[["a", "b"], ["only-one"]]),
        )


def test_oversized_table_cell_rejected() -> None:
    with pytest.raises(ValidationError):
        TranscriptionSegment(
            kind="TABLE",
            table=TranscriptionTable(rows=[["ok"], ["x" * 501]]),
        )


def test_transcription_confidence_is_stage_field_not_segment() -> None:
    result = TranscriptionResult(
        text="body",
        segments=[
            TranscriptionSegment(text="body", confidence=Decimal("0.5")),
        ],
        transcription_confidence=Decimal("0.77"),
        unreadable=False,
    )
    dumped = result.model_dump(mode="json")
    assert "transcription_confidence" in dumped
    assert Decimal(str(dumped["transcription_confidence"])) == Decimal("0.77")
    assert "confidence" in dumped["segments"][0]
    assert Decimal(str(dumped["segments"][0]["confidence"])) == Decimal("0.5")
    # Stage confidence remains on the result, not folded into segments-only.
    assert result.transcription_confidence == Decimal("0.77")
    assert result.segments[0].confidence == Decimal("0.5")


def test_human_correction_confidence_null_semantics_preserved() -> None:
    source = inspect.getsource(transcription_service.put_manual_transcription)
    assert 'source_type="HUMAN"' in source
    assert "transcription_confidence=None" in source
    assert "Do not fabricate human confidence" in source


@pytest.mark.asyncio
async def test_fixed_provider_emits_math_and_table_segments() -> None:
    provider = FixedStructureProvider(allow_non_test=True)
    result = await provider.transcribe_answer(
        TranscriptionInput(
            submission_id=uuid.uuid4(),
            answer_region_id=uuid.uuid4(),
            crop_content_sha256="a" * 64,
        )
    )
    kinds = {s.kind for s in result.segments}
    assert "MATH" in kinds
    assert "TABLE" in kinds
    assert "TEXT" in kinds
    assert result.transcription_confidence == Decimal("0.7700")
