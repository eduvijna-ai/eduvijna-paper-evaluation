"""PREPROD-003: AI quality harness can load safe fixture and score fixed provider.

Does not claim real-paper PASS. REAL_PAPER_CORPUS_GATE remains EXTERNAL_INPUT_REQUIRED.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
AI_ROOT = REPO_ROOT / "ai"
HARNESS_MANIFEST = (
    AI_ROOT / "benchmarks" / "manifests" / "v1" / "fixtures.safe.json"
)

if str(AI_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_ROOT))

from benchmarks.report import REAL_PAPER_CORPUS_GATE  # noqa: E402
from benchmarks.runner import load_manifest, run_harness, validate_manifest  # noqa: E402
from benchmarks.scoring import score_case  # noqa: E402


def test_harness_loads_safe_manifest_and_scores_fixed_provider() -> None:
    assert HARNESS_MANIFEST.is_file()
    manifest = load_manifest(HARNESS_MANIFEST)
    errors = validate_manifest(manifest)
    assert errors == []
    assert manifest.get("real_paper_corpus") is False

    report = run_harness(manifest=manifest, provider="fixed")
    assert report["harness_ok"] is True
    assert report["real_paper_pass"] is False
    assert report["gates"]["REAL_PAPER_CORPUS_GATE"] == "EXTERNAL_INPUT_REQUIRED"
    assert REAL_PAPER_CORPUS_GATE == "EXTERNAL_INPUT_REQUIRED"
    assert report["cases"][0]["status"] == "SCORED"
    assert report["aggregate_metrics"]["evaluation_marking_accuracy"] == 1.0


def test_harness_score_case_independent_metrics() -> None:
    metrics = score_case(
        gold={
            "student_id": "s1",
            "answer_region_ids": ["r1"],
            "question_mappings": [{"region_id": "r1", "question_version_id": "q1"}],
            "transcription_text": "ok",
            "final_marks": "2.0",
            "teacher_final_marks": "2.0",
        },
        prediction={
            "student_id": "s1",
            "answer_region_ids": ["r1"],
            "question_mappings": [{"region_id": "r1", "question_version_id": "q1"}],
            "transcription_text": "ok",
            "proposed_marks": "2.0",
        },
    )
    assert all(value == 1.0 for value in metrics.values())


@pytest.mark.asyncio
async def test_openai_provider_retries_then_routes_unavailable() -> None:
    """Transient failures exhaust retries as ProviderUnavailable (review path)."""
    import uuid

    from app.ai.providers.openai import OpenAIStructureProvider, is_transient_openai_failure
    from app.ai.types import ProviderUnavailable, TranscriptionInput

    class _Transient(RuntimeError):
        status_code = 429

    assert is_transient_openai_failure(_Transient("rate limit"))

    calls = {"n": 0}

    async def flaky(operation: str, payload: dict) -> dict:
        del operation, payload
        calls["n"] += 1
        raise _Transient("rate limit")

    provider = OpenAIStructureProvider(
        api_key="sk-test-never-log",
        model_identity="m",
        model_page_analysis="m",
        model_mapping="m",
        model_transcription="m",
        caller=flaky,
        max_attempts=3,
        backoff_seconds=(0.0, 0.0, 0.0),
    )
    with pytest.raises(ProviderUnavailable):
        await provider.transcribe_answer(
            TranscriptionInput(
                submission_id=uuid.uuid4(),
                answer_region_id=uuid.uuid4(),
                crop_content_sha256="a" * 64,
            )
        )
    assert calls["n"] == 3


def test_safe_manifest_json_is_parseable() -> None:
    data = json.loads(HARNESS_MANIFEST.read_text(encoding="utf-8"))
    assert data["manifest_version"] == "1"
    assert data["cases"][0]["id"] == "safe-fixed-001"
