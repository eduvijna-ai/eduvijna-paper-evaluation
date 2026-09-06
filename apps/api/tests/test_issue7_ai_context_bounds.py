"""Issue #7 — bound AI proposal context values."""

from __future__ import annotations

import json
import uuid

import pytest
from pydantic import ValidationError

from app.services.ai_context_bounds import (
    CONTEXT_MAX_KEY_LENGTH,
    CONTEXT_MAX_KEYS,
    CONTEXT_MAX_SERIALIZED_BYTES,
    CONTEXT_MAX_VALUE_LENGTH,
    validate_ai_proposal_context,
)
from app.services.ai_proposals import (
    AnswerKeyProposalRequest,
    CurriculumMappingProposalRequest,
    RubricProposalRequest,
    build_ai_request_summary,
)


def _max_valid_context() -> dict[str, str]:
    # Stay under serialized byte budget with max keys.
    value = "v" * 100
    return {f"k{i:02d}": value for i in range(CONTEXT_MAX_KEYS)}


def test_issue7_max_valid_boundary() -> None:
    ctx = _max_valid_context()
    assert validate_ai_proposal_context(ctx) == ctx
    for cls in (
        AnswerKeyProposalRequest,
        RubricProposalRequest,
        CurriculumMappingProposalRequest,
    ):
        kwargs: dict = {"context": ctx}
        if cls is CurriculumMappingProposalRequest:
            kwargs["question_version_id"] = uuid.uuid4()
        else:
            kwargs["question_version_id"] = uuid.uuid4()
        cls(**kwargs)


def test_issue7_value_too_long() -> None:
    with pytest.raises(ValidationError):
        AnswerKeyProposalRequest(
            question_version_id=uuid.uuid4(),
            context={"k": "x" * (CONTEXT_MAX_VALUE_LENGTH + 1)},
        )


def test_issue7_key_too_long() -> None:
    with pytest.raises(ValidationError):
        RubricProposalRequest(
            question_version_id=uuid.uuid4(),
            context={"k" * (CONTEXT_MAX_KEY_LENGTH + 1): "ok"},
        )


def test_issue7_too_many_keys() -> None:
    ctx = {f"k{i}": "v" for i in range(CONTEXT_MAX_KEYS + 1)}
    with pytest.raises(ValidationError):
        CurriculumMappingProposalRequest(
            question_version_id=uuid.uuid4(),
            context=ctx,
        )


def test_issue7_serialized_payload_too_large() -> None:
    # Few keys but oversized total UTF-8 bytes.
    ctx = {"a": "字" * 6000}  # multibyte chars inflate byte size
    encoded = json.dumps(ctx, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    assert len(encoded) > CONTEXT_MAX_SERIALIZED_BYTES
    with pytest.raises(ValidationError):
        AnswerKeyProposalRequest(question_version_id=uuid.uuid4(), context=ctx)


def test_issue7_multibyte_utf8_byte_enforcement() -> None:
    # Under character length per value, but total UTF-8 bytes exceed limit via CJK.
    ctx = {f"k{i}": "测" * CONTEXT_MAX_VALUE_LENGTH for i in range(8)}
    encoded = json.dumps(ctx, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    assert len(encoded) > CONTEXT_MAX_SERIALIZED_BYTES
    with pytest.raises((ValidationError, ValueError)):
        AnswerKeyProposalRequest(question_version_id=uuid.uuid4(), context=ctx)


def test_issue7_non_string_value_rejected() -> None:
    with pytest.raises(ValidationError):
        AnswerKeyProposalRequest.model_validate(
            {
                "question_version_id": str(uuid.uuid4()),
                "context": {"k": 123},
            }
        )


def test_issue7_request_summary_redacted() -> None:
    secret = "TOP_SECRET_CONTEXT_VALUE"
    request = AnswerKeyProposalRequest(
        question_version_id=uuid.uuid4(),
        instructions="do not store this full instruction text forever",
        context={"topic": secret, "unit": "u1"},
    )
    summary = build_ai_request_summary(
        operation="propose_answer_key",
        request=request,
        requested_by=uuid.uuid4(),
    )
    blob = json.dumps(summary)
    assert secret not in blob
    assert "do not store this full instruction" not in blob
    assert summary["operation"] == "propose_answer_key"
    assert summary["instruction_length"] == len(request.instructions or "")
    assert summary["context_key_count"] == 2
    assert set(summary["context_keys"]) == {"topic", "unit"}
