"""B18.1 clustering reproducibility + CO/PO mapping governance."""

from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.ai.providers.embedding import FixedEmbeddingProviderAlt
from app.core.config import get_settings
from app.core.security import JwtAuthProvider
from app.db.models import OutcomeDefinition
from app.db.models.outcome_intelligence import AnswerClusterRun
from app.db.session import async_session_factory
from app.services.outcome_intelligence import compute_mapping_activation_hash
from tests.test_b3_submission_ingestion import _headers
from tests.test_b7_publication_reports import _to_approved, api_client_publication
from tests.test_b8_analytics_mastery import (
    _publish_approved,
    _ready_assessment_with_curriculum,
)
from tests.test_b17_psychometrics import _clone_published_cohort
from tests.test_b18_answer_clustering import (
    _detail_code,
    _set_transcription_patterns,
)


@pytest.mark.asyncio
async def test_b18_1_cluster_identity_includes_embedding_metadata() -> None:
    async with api_client_publication(text_provider="fixed") as client:
        headers = await _headers(client)
        data = await _ready_assessment_with_curriculum(client, headers)
        sid, _ = await _to_approved(client, headers, data)
        prid = await _publish_approved(client, headers, sid)
        await _clone_published_cohort(template_pr_id=uuid.UUID(prid), extra_count=5)
        question_id = data["leaf_a"]["question_id"]
        av_id = data["version_id"]
        await _set_transcription_patterns(
            assessment_version_id=uuid.UUID(av_id),
            question_id=uuid.UUID(question_id),
        )

        body = {
            "assessment_version_id": av_id,
            "question_id": question_id,
            "similarity_threshold": 0.75,
        }
        r1 = await client.post("/api/v1/quality/answer-clusters/runs", headers=headers, json=body)
        assert r1.status_code == 200, r1.text
        run1 = r1.json()
        assert run1["status"] == "COMPLETED"
        assert run1["embedding_provider"] == "fixed"
        assert run1["embedding_model"] == "fixed-embed-v1"
        assert run1["embedding_model_version"] == "1"

        # Same complete identity → same run
        r2 = await client.post("/api/v1/quality/answer-clusters/runs", headers=headers, json=body)
        assert r2.status_code == 200
        assert r2.json()["id"] == run1["id"]
        assert r2.json()["source_set_hash"] == run1["source_set_hash"]

        # Threshold change → new run
        r_thr = await client.post(
            "/api/v1/quality/answer-clusters/runs",
            headers=headers,
            json={**body, "similarity_threshold": 0.9},
        )
        assert r_thr.status_code == 200
        assert r_thr.json()["id"] != run1["id"]

        # Model version change → new run; historical run immutable
        alt = FixedEmbeddingProviderAlt(model_version="2")
        with patch(
            "app.services.outcome_intelligence.get_embedding_provider",
            return_value=alt,
        ):
            r_ver = await client.post(
                "/api/v1/quality/answer-clusters/runs", headers=headers, json=body
            )
        assert r_ver.status_code == 200, r_ver.text
        run_ver = r_ver.json()
        assert run_ver["id"] != run1["id"]
        assert run_ver["embedding_model_version"] == "2"
        assert run_ver["source_set_hash"] == run1["source_set_hash"]

        # Model change → new run
        alt_model = FixedEmbeddingProviderAlt(model="fixed-embed-v2", model_version="1")
        with patch(
            "app.services.outcome_intelligence.get_embedding_provider",
            return_value=alt_model,
        ):
            r_model = await client.post(
                "/api/v1/quality/answer-clusters/runs", headers=headers, json=body
            )
        assert r_model.status_code == 200
        assert r_model.json()["id"] not in {run1["id"], run_ver["id"]}
        assert r_model.json()["embedding_model"] == "fixed-embed-v2"

        # Provider name change → new run
        alt_prov = FixedEmbeddingProviderAlt(
            provider_name="fixed-alt", model="fixed-embed-v1", model_version="1"
        )
        with patch(
            "app.services.outcome_intelligence.get_embedding_provider",
            return_value=alt_prov,
        ):
            r_prov = await client.post(
                "/api/v1/quality/answer-clusters/runs", headers=headers, json=body
            )
        assert r_prov.status_code == 200
        assert r_prov.json()["embedding_provider"] == "fixed-alt"
        assert r_prov.json()["id"] not in {
            run1["id"],
            run_ver["id"],
            r_model.json()["id"],
        }

        # Historical run frozen
        get_old = await client.get(
            f"/api/v1/quality/answer-clusters/runs/{run1['id']}", headers=headers
        )
        assert get_old.status_code == 200
        old = get_old.json()
        assert old["embedding_model_version"] == "1"
        assert old["source_set_hash"] == run1["source_set_hash"]
        assert old["source_result_count"] == run1["source_result_count"]
        assert set(old["source_published_result_ids"]) == set(run1["source_published_result_ids"])


@pytest.mark.asyncio
async def test_b18_1_mapping_weight_and_active_outcome_and_activation_hash() -> None:
    async with api_client_publication(text_provider="fixed") as client:
        headers = await _headers(client)
        data = await _ready_assessment_with_curriculum(client, headers)
        sid, _ = await _to_approved(client, headers, data, override_answered=Decimal("4.0"))
        prid = await _publish_approved(client, headers, sid)
        await _clone_published_cohort(template_pr_id=uuid.UUID(prid), extra_count=1)
        question_id = data["leaf_a"]["question_id"]
        av_id = data["version_id"]

        co1 = await client.post(
            "/api/v1/outcomes/definitions",
            headers=headers,
            json={
                "outcome_type": "CO",
                "code": f"CO1-{uuid.uuid4().hex[:8]}",
                "title": "CO One",
            },
        )
        assert co1.status_code == 200, co1.text
        co1_id = co1.json()["id"]
        co2 = await client.post(
            "/api/v1/outcomes/definitions",
            headers=headers,
            json={
                "outcome_type": "CO",
                "code": f"CO2-{uuid.uuid4().hex[:8]}",
                "title": "CO Two",
            },
        )
        assert co2.status_code == 200
        co2_id = co2.json()["id"]
        po1 = await client.post(
            "/api/v1/outcomes/definitions",
            headers=headers,
            json={
                "outcome_type": "PO",
                "code": f"PO1-{uuid.uuid4().hex[:8]}",
                "title": "PO One",
            },
        )
        assert po1.status_code == 200
        po1_id = po1.json()["id"]
        po2 = await client.post(
            "/api/v1/outcomes/definitions",
            headers=headers,
            json={
                "outcome_type": "PO",
                "code": f"PO2-{uuid.uuid4().hex[:8]}",
                "title": "PO Two",
            },
        )
        assert po2.status_code == 200
        po2_id = po2.json()["id"]

        ms = await client.post(
            "/api/v1/outcomes/mapping-sets",
            headers=headers,
            json={"assessment_version_id": av_id, "title": "B18.1 map v1"},
        )
        assert ms.status_code == 200, ms.text
        ms_id = ms.json()["id"]

        for bad in (0, -0.1, 1.01, 2):
            bad_map = await client.post(
                f"/api/v1/outcomes/mapping-sets/{ms_id}/mappings",
                headers=headers,
                json={
                    "question_id": question_id,
                    "outcome_definition_id": co1_id,
                    "weight": bad,
                },
            )
            assert bad_map.status_code in {400, 422}, bad
            if bad_map.status_code == 400:
                assert _detail_code(bad_map) == "INVALID_WEIGHT"

        ok1 = await client.post(
            f"/api/v1/outcomes/mapping-sets/{ms_id}/mappings",
            headers=headers,
            json={
                "question_id": question_id,
                "outcome_definition_id": co1_id,
                "weight": 1,
            },
        )
        assert ok1.status_code == 200, ok1.text
        ok25 = await client.post(
            f"/api/v1/outcomes/mapping-sets/{ms_id}/mappings",
            headers=headers,
            json={
                "question_id": question_id,
                "outcome_definition_id": co2_id,
                "weight": 0.25,
            },
        )
        assert ok25.status_code == 200, ok25.text
        await client.post(
            f"/api/v1/outcomes/mapping-sets/{ms_id}/mappings",
            headers=headers,
            json={
                "question_id": question_id,
                "outcome_definition_id": po1_id,
                "weight": 0.5,
            },
        )
        await client.post(
            f"/api/v1/outcomes/mapping-sets/{ms_id}/mappings",
            headers=headers,
            json={
                "question_id": question_id,
                "outcome_definition_id": po2_id,
                "weight": 0.75,
            },
        )

        # Retire an outcome and try to map it on a fresh draft set
        async with async_session_factory() as db:
            retired = await db.scalar(
                select(OutcomeDefinition).where(OutcomeDefinition.id == uuid.UUID(co2_id))
            )
            assert retired is not None
            retired.status = "RETIRED"
            await db.commit()

        ms2 = await client.post(
            "/api/v1/outcomes/mapping-sets",
            headers=headers,
            json={"assessment_version_id": av_id, "title": "B18.1 map draft retired"},
        )
        assert ms2.status_code == 200
        ms2_id = ms2.json()["id"]
        retired_map = await client.post(
            f"/api/v1/outcomes/mapping-sets/{ms2_id}/mappings",
            headers=headers,
            json={
                "question_id": question_id,
                "outcome_definition_id": co2_id,
                "weight": 0.5,
            },
        )
        assert retired_map.status_code == 409
        assert _detail_code(retired_map) == "OUTCOME_NOT_ACTIVE"

        # Restore CO2 ACTIVE for activation of ms_id, then retire after mapping
        async with async_session_factory() as db:
            restored = await db.scalar(
                select(OutcomeDefinition).where(OutcomeDefinition.id == uuid.UUID(co2_id))
            )
            assert restored is not None
            restored.status = "ACTIVE"
            await db.commit()

        # Activation succeeds with hash
        act = await client.post(f"/api/v1/outcomes/mapping-sets/{ms_id}/activate", headers=headers)
        assert act.status_code == 200, act.text
        act_body = act.json()
        assert act_body["status"] == "ACTIVE"
        assert act_body["activation_hash"]
        hash_v1 = act_body["activation_hash"]

        detail = await client.get(f"/api/v1/outcomes/mapping-sets/{ms_id}", headers=headers)
        assert detail.status_code == 200
        mapping_rows = detail.json().get("mappings") or []
        ctx = JwtAuthProvider(get_settings()).verify_access_token(
            headers["Authorization"].removeprefix("Bearer ")
        )
        tenant_id = ctx.tenant_id
        recomputed = compute_mapping_activation_hash(
            tenant_id=tenant_id,
            assessment_id=uuid.UUID(act_body["assessment_id"]),
            assessment_version_id=uuid.UUID(act_body["assessment_version_id"]),
            mapping_set_id=uuid.UUID(act_body["id"]),
            version_number=int(act_body["version_number"]),
            mappings=[
                (
                    uuid.UUID(m["question_id"]),
                    uuid.UUID(m["question_version_id"]),
                    uuid.UUID(m["outcome_definition_id"]),
                    Decimal(str(m["weight"])),
                )
                for m in mapping_rows
            ],
        )
        assert hash_v1 == recomputed
        # Shuffle order must not change hash
        shuffled = list(reversed(mapping_rows))
        recomputed_shuffled = compute_mapping_activation_hash(
            tenant_id=tenant_id,
            assessment_id=uuid.UUID(act_body["assessment_id"]),
            assessment_version_id=uuid.UUID(act_body["assessment_version_id"]),
            mapping_set_id=uuid.UUID(act_body["id"]),
            version_number=int(act_body["version_number"]),
            mappings=[
                (
                    uuid.UUID(m["question_id"]),
                    uuid.UUID(m["question_version_id"]),
                    uuid.UUID(m["outcome_definition_id"]),
                    Decimal(str(m["weight"])),
                )
                for m in shuffled
            ],
        )
        assert recomputed_shuffled == hash_v1

        # ACTIVE set immutable
        add_active = await client.post(
            f"/api/v1/outcomes/mapping-sets/{ms_id}/mappings",
            headers=headers,
            json={
                "question_id": question_id,
                "outcome_definition_id": po1_id,
                "weight": 0.1,
            },
        )
        assert add_active.status_code == 409
        assert _detail_code(add_active) == "MAPPING_SET_NOT_DRAFT"

        # New version + retire outcome before activation blocks activate
        ms3 = await client.post(
            "/api/v1/outcomes/mapping-sets",
            headers=headers,
            json={"assessment_version_id": av_id, "title": "B18.1 map v2"},
        )
        assert ms3.status_code == 200
        ms3_id = ms3.json()["id"]
        assert ms3.json()["version_number"] >= 2
        ms3_version = int(ms3.json()["version_number"])
        map_then_retire = await client.post(
            f"/api/v1/outcomes/mapping-sets/{ms3_id}/mappings",
            headers=headers,
            json={
                "question_id": question_id,
                "outcome_definition_id": co1_id,
                "weight": 0.5,
            },
        )
        assert map_then_retire.status_code == 200
        async with async_session_factory() as db:
            row = await db.scalar(
                select(OutcomeDefinition).where(OutcomeDefinition.id == uuid.UUID(co1_id))
            )
            assert row is not None
            row.status = "RETIRED"
            await db.commit()
        act_fail = await client.post(
            f"/api/v1/outcomes/mapping-sets/{ms3_id}/activate", headers=headers
        )
        assert act_fail.status_code == 409
        assert _detail_code(act_fail) == "OUTCOME_NOT_ACTIVE"

        # Restore CO1 and activate v2 — v1 hash unchanged
        async with async_session_factory() as db:
            row = await db.scalar(
                select(OutcomeDefinition).where(OutcomeDefinition.id == uuid.UUID(co1_id))
            )
            assert row is not None
            row.status = "ACTIVE"
            await db.commit()
        act2 = await client.post(
            f"/api/v1/outcomes/mapping-sets/{ms3_id}/activate", headers=headers
        )
        assert act2.status_code == 200, act2.text
        assert act2.json()["activation_hash"]
        assert act2.json()["activation_hash"] != hash_v1

        v1_after = await client.get(f"/api/v1/outcomes/mapping-sets/{ms_id}", headers=headers)
        assert v1_after.status_code == 200
        assert v1_after.json()["status"] == "RETIRED"
        assert v1_after.json()["activation_hash"] == hash_v1

        # RETIRED immutable
        add_retired = await client.post(
            f"/api/v1/outcomes/mapping-sets/{ms_id}/mappings",
            headers=headers,
            json={
                "question_id": question_id,
                "outcome_definition_id": po2_id,
                "weight": 0.2,
            },
        )
        assert add_retired.status_code == 409

        # Report stores mapping activation identity
        report = await client.post(
            "/api/v1/outcomes/attainment-reports",
            headers=headers,
            json={"assessment_version_id": av_id, "mapping_set_id": ms3_id},
        )
        assert report.status_code == 200, report.text
        rb = report.json()
        assert rb["mapping_set_id"] == ms3_id
        assert rb["mapping_activation_hash"] == act2.json()["activation_hash"]
        assert rb["mapping_set_version_number"] == ms3_version


@pytest.mark.asyncio
async def test_b18_1_concurrent_cluster_create_is_db_safe() -> None:
    """Duplicate creates with identical identity are DB-unique and idempotent under concurrency."""
    import asyncio

    from sqlalchemy import text

    async with api_client_publication(text_provider="fixed") as client:
        headers = await _headers(client)
        data = await _ready_assessment_with_curriculum(client, headers)
        sid, _ = await _to_approved(client, headers, data)
        prid = await _publish_approved(client, headers, sid)
        await _clone_published_cohort(template_pr_id=uuid.UUID(prid), extra_count=5)
        question_id = data["leaf_a"]["question_id"]
        av_id = data["version_id"]
        await _set_transcription_patterns(
            assessment_version_id=uuid.UUID(av_id),
            question_id=uuid.UUID(question_id),
        )
        body = {
            "assessment_version_id": av_id,
            "question_id": question_id,
            "similarity_threshold": 0.75,
        }

        first = await client.post(
            "/api/v1/quality/answer-clusters/runs", headers=headers, json=body
        )
        assert first.status_code == 200, first.text
        run_id = first.json()["id"]
        source_hash = first.json()["source_set_hash"]

        async def _create() -> dict:
            r = await client.post(
                "/api/v1/quality/answer-clusters/runs", headers=headers, json=body
            )
            assert r.status_code == 200, r.text
            return r.json()

        # Concurrent identical requests after the run exists must stay idempotent.
        results = await asyncio.gather(_create(), _create(), _create())
        assert {r["id"] for r in results} == {run_id}
        assert all(r["source_set_hash"] == source_hash for r in results)

        async with async_session_factory() as db:
            names = {
                row[0]
                for row in (
                    await db.execute(
                        text(
                            """
                            SELECT conname FROM pg_constraint
                            WHERE conrelid = 'answer_cluster_runs'::regclass
                              AND contype = 'u'
                            """
                        )
                    )
                ).fetchall()
            }
            assert "uq_answer_cluster_runs_repro_identity" in names

            # Direct DB uniqueness: inserting a second row with the same identity fails.
            existing = await db.scalar(
                select(AnswerClusterRun).where(AnswerClusterRun.id == uuid.UUID(run_id))
            )
            assert existing is not None
            from datetime import UTC, datetime

            dup = AnswerClusterRun(
                tenant_id=existing.tenant_id,
                assessment_id=existing.assessment_id,
                assessment_version_id=existing.assessment_version_id,
                question_id=existing.question_id,
                question_version_id=existing.question_version_id,
                cohort_definition=dict(existing.cohort_definition or {}),
                algorithm_version=existing.algorithm_version,
                similarity_threshold=existing.similarity_threshold,
                source_set_hash=existing.source_set_hash,
                source_result_count=existing.source_result_count,
                source_published_result_ids=list(existing.source_published_result_ids or []),
                embedding_provider=existing.embedding_provider,
                embedding_model=existing.embedding_model,
                embedding_model_version=existing.embedding_model_version,
                embedding_dim=existing.embedding_dim,
                cluster_count=0,
                status="PENDING",
                requested_by=existing.requested_by,
                requested_at=datetime.now(UTC),
            )
            db.add(dup)
            with pytest.raises(Exception) as raised:
                await db.flush()
            assert "uq_answer_cluster_runs_repro_identity" in str(raised.value)
            await db.rollback()
