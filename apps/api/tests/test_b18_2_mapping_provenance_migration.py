"""B18.2: populated 0019 → head migration preserves legacy mapping provenance."""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings
from app.services.outcome_intelligence import (
    WEIGHT_POLICY_LEGACY,
    WEIGHT_POLICY_STRICT,
    compute_mapping_activation_hash,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
API_ROOT = REPO_ROOT / "apps" / "api"
MIGRATION_0020 = (
    REPO_ROOT
    / "database"
    / "migrations"
    / "versions"
    / "20260910_0020_b18_1_reproducibility_mapping_invariants.py"
)
REV_0019 = "20260910_0019"
MIG_DB_NAME = "eduvijna_b18_2_mig_preserve"


def _async_url() -> str:
    return os.environ.get("DATABASE_URL") or get_settings().database_url


def _with_db(url: str, db_name: str) -> str:
    parsed = urlparse(url)
    return urlunparse(parsed._replace(path=f"/{db_name}"))


def _admin_async_url() -> str:
    return _with_db(_async_url(), "postgres")


def _mig_async_url() -> str:
    return _with_db(_async_url(), MIG_DB_NAME)


def _alembic_upgrade(target: str, database_url: str) -> None:
    """Run Alembic in a subprocess so it does not nest asyncio.run in pytest."""
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "-c",
            str(API_ROOT / "alembic.ini"),
            "upgrade",
            target,
        ],
        cwd=str(API_ROOT),
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise AssertionError(
            f"alembic upgrade {target} failed ({proc.returncode}):\n"
            f"{proc.stdout}\n{proc.stderr}"
        )


async def _recreate_mig_db() -> None:
    engine = create_async_engine(_admin_async_url(), isolation_level="AUTOCOMMIT")
    async with engine.connect() as conn:
        await conn.execute(
            text(
                """
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = :name AND pid <> pg_backend_pid()
                """
            ),
            {"name": MIG_DB_NAME},
        )
        await conn.execute(text(f'DROP DATABASE IF EXISTS "{MIG_DB_NAME}"'))
        await conn.execute(text(f'CREATE DATABASE "{MIG_DB_NAME}"'))
    await engine.dispose()


async def _drop_mig_db() -> None:
    engine = create_async_engine(_admin_async_url(), isolation_level="AUTOCOMMIT")
    async with engine.connect() as conn:
        await conn.execute(
            text(
                """
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = :name AND pid <> pg_backend_pid()
                """
            ),
            {"name": MIG_DB_NAME},
        )
        await conn.execute(text(f'DROP DATABASE IF EXISTS "{MIG_DB_NAME}"'))
    await engine.dispose()


def test_b18_2_migration_0020_does_not_clamp_legacy_weights() -> None:
    source = MIGRATION_0020.read_text(encoding="utf-8")
    assert "SET weight = 1" not in source
    assert "DELETE FROM question_outcome_mappings" not in source
    assert "weight_policy_version" in source
    assert "ck_question_outcome_mappings_weight_policy" in source
    assert "forbid_weight_policy_version_change" in source


@pytest.mark.asyncio
async def test_b18_2_populated_0019_to_head_preserves_legacy_weight_and_report_provenance() -> None:
    """Real PostgreSQL upgrade: 0019 with weight 1.5 → head must preserve provenance."""
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    curriculum_id = uuid.uuid4()
    assessment_id = uuid.uuid4()
    version_id = uuid.uuid4()
    question_id = uuid.uuid4()
    qv_id = uuid.uuid4()
    co1_id = uuid.uuid4()
    co2_id = uuid.uuid4()
    mapping_set_id = uuid.uuid4()
    map_legacy_id = uuid.uuid4()
    map_half_id = uuid.uuid4()
    report_id = uuid.uuid4()
    metric_id = uuid.uuid4()
    published_id = uuid.uuid4()
    source_hash = "a" * 64
    legacy_weight = Decimal("1.5000")
    half_weight = Decimal("0.5000")
    weighted_earned = Decimal("6.000000")
    weighted_max = Decimal("7.500000")
    attainment_pct = Decimal("80.000000")

    await _recreate_mig_db()
    try:
        _alembic_upgrade(REV_0019, _mig_async_url())
        engine = create_async_engine(_mig_async_url())
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO tenants (id, slug, name, status) "
                    "VALUES (:id, :slug, :name, 'active')"
                ),
                {
                    "id": tenant_id,
                    "slug": f"b18-2-{tenant_id.hex[:8]}",
                    "name": "B18.2 Mig Tenant",
                },
            )
            await conn.execute(
                text(
                    "INSERT INTO users (id, tenant_id, email, display_name, status) "
                    "VALUES (:id, :tid, :email, :name, 'active')"
                ),
                {
                    "id": user_id,
                    "tid": tenant_id,
                    "email": f"admin-{tenant_id.hex[:8]}@b18-2.local",
                    "name": "B18.2 Admin",
                },
            )
            await conn.execute(
                text(
                    "INSERT INTO curricula (id, tenant_id, code, name, version_label, status) "
                    "VALUES (:id, :tid, :code, :name, '2026', 'active')"
                ),
                {
                    "id": curriculum_id,
                    "tid": tenant_id,
                    "code": f"CUR-{tenant_id.hex[:8]}",
                    "name": "B18.2 Curriculum",
                },
            )
            await conn.execute(
                text(
                    """
                    INSERT INTO assessments (
                      id, tenant_id, curriculum_id, code, title, assessment_type,
                      max_marks, status, created_by
                    ) VALUES (
                      :id, :tid, :cid, :code, :title, 'EXAM', 5, 'ACTIVE', :uid
                    )
                    """
                ),
                {
                    "id": assessment_id,
                    "tid": tenant_id,
                    "cid": curriculum_id,
                    "code": f"ASM-{tenant_id.hex[:8]}",
                    "title": "B18.2 Assessment",
                    "uid": user_id,
                },
            )
            await conn.execute(
                text(
                    """
                    INSERT INTO assessment_versions (
                      id, tenant_id, assessment_id, version_number, title,
                      max_marks, status, created_by
                    ) VALUES (
                      :id, :tid, :aid, 1, 'v1', 5, 'DRAFT', :uid
                    )
                    """
                ),
                {
                    "id": version_id,
                    "tid": tenant_id,
                    "aid": assessment_id,
                    "uid": user_id,
                },
            )
            await conn.execute(
                text(
                    "INSERT INTO questions (id, tenant_id, assessment_id, stable_code) "
                    "VALUES (:id, :tid, :aid, 'Q1')"
                ),
                {"id": question_id, "tid": tenant_id, "aid": assessment_id},
            )
            await conn.execute(
                text(
                    """
                    INSERT INTO question_versions (
                      id, tenant_id, assessment_version_id, question_id,
                      display_label, sequence, prompt_text, max_marks,
                      question_type, scoring_mode
                    ) VALUES (
                      :id, :tid, :vid, :qid, '1', 1, 'prompt', 5,
                      'SHORT', 'LEAF_SCORABLE'
                    )
                    """
                ),
                {
                    "id": qv_id,
                    "tid": tenant_id,
                    "vid": version_id,
                    "qid": question_id,
                },
            )
            for oid, code, title in (
                (co1_id, "CO1", "Course Outcome 1"),
                (co2_id, "CO2", "Course Outcome 2"),
            ):
                await conn.execute(
                    text(
                        """
                        INSERT INTO outcome_definitions (
                          id, tenant_id, outcome_type, code, title, status, created_by
                        ) VALUES (
                          :id, :tid, 'CO', :code, :title, 'ACTIVE', :uid
                        )
                        """
                    ),
                    {
                        "id": oid,
                        "tid": tenant_id,
                        "code": code,
                        "title": title,
                        "uid": user_id,
                    },
                )
            await conn.execute(
                text(
                    """
                    INSERT INTO outcome_mapping_sets (
                      id, tenant_id, assessment_id, assessment_version_id,
                      version_number, title, status, created_by, activated_by,
                      activated_at
                    ) VALUES (
                      :id, :tid, :aid, :vid, 1, 'legacy map', 'ACTIVE', :uid, :uid,
                      now()
                    )
                    """
                ),
                {
                    "id": mapping_set_id,
                    "tid": tenant_id,
                    "aid": assessment_id,
                    "vid": version_id,
                    "uid": user_id,
                },
            )
            await conn.execute(
                text(
                    """
                    INSERT INTO question_outcome_mappings (
                      id, tenant_id, mapping_set_id, question_id, question_version_id,
                      outcome_definition_id, weight
                    ) VALUES (
                      :id, :tid, :msid, :qid, :qvid, :oid, :weight
                    )
                    """
                ),
                {
                    "id": map_legacy_id,
                    "tid": tenant_id,
                    "msid": mapping_set_id,
                    "qid": question_id,
                    "qvid": qv_id,
                    "oid": co1_id,
                    "weight": legacy_weight,
                },
            )
            await conn.execute(
                text(
                    """
                    INSERT INTO question_outcome_mappings (
                      id, tenant_id, mapping_set_id, question_id, question_version_id,
                      outcome_definition_id, weight
                    ) VALUES (
                      :id, :tid, :msid, :qid, :qvid, :oid, :weight
                    )
                    """
                ),
                {
                    "id": map_half_id,
                    "tid": tenant_id,
                    "msid": mapping_set_id,
                    "qid": question_id,
                    "qvid": qv_id,
                    "oid": co2_id,
                    "weight": half_weight,
                },
            )
            await conn.execute(
                text(
                    """
                    INSERT INTO outcome_attainment_report_runs (
                      id, tenant_id, assessment_id, assessment_version_id,
                      mapping_set_id, mapping_set_version_number, algorithm_version,
                      source_set_hash, source_result_count, source_published_result_ids,
                      status, requested_at, completed_at
                    ) VALUES (
                      :id, :tid, :aid, :vid, :msid, 1, 'MARKS_WEIGHTED_V1',
                      :hash, 1, CAST(:pids AS jsonb), 'COMPLETED', now(), now()
                    )
                    """
                ),
                {
                    "id": report_id,
                    "tid": tenant_id,
                    "aid": assessment_id,
                    "vid": version_id,
                    "msid": mapping_set_id,
                    "hash": source_hash,
                    "pids": f'["{published_id}"]',
                },
            )
            await conn.execute(
                text(
                    """
                    INSERT INTO outcome_attainment_metrics (
                      id, tenant_id, report_run_id, outcome_definition_id,
                      outcome_type, outcome_code, outcome_title,
                      weighted_earned, weighted_max, attainment_pct, denom_status,
                      mapped_question_count, contribution_count
                    ) VALUES (
                      :id, :tid, :rid, :oid, 'CO', 'CO1', 'Course Outcome 1',
                      :earned, :max, :pct, 'OK', 1, 1
                    )
                    """
                ),
                {
                    "id": metric_id,
                    "tid": tenant_id,
                    "rid": report_id,
                    "oid": co1_id,
                    "earned": weighted_earned,
                    "max": weighted_max,
                    "pct": attainment_pct,
                },
            )
            before_metric = (
                await conn.execute(
                    text(
                        """
                        SELECT weighted_earned, weighted_max, attainment_pct
                        FROM outcome_attainment_metrics WHERE id = :id
                        """
                    ),
                    {"id": metric_id},
                )
            ).one()
            before_report = (
                await conn.execute(
                    text(
                        """
                        SELECT source_set_hash, source_published_result_ids::text,
                               source_result_count
                        FROM outcome_attainment_report_runs WHERE id = :id
                        """
                    ),
                    {"id": report_id},
                )
            ).one()
        await engine.dispose()

        _alembic_upgrade("head", _mig_async_url())

        engine = create_async_engine(_mig_async_url())
        async with engine.begin() as conn:
            after_rows = (
                await conn.execute(
                    text(
                        """
                        SELECT id, weight, weight_policy_version
                        FROM question_outcome_mappings
                        WHERE mapping_set_id = :msid
                        """
                    ),
                    {"msid": mapping_set_id},
                )
            ).fetchall()
            assert len(after_rows) == 2
            by_id = {row[0]: row for row in after_rows}
            assert Decimal(str(by_id[map_legacy_id][1])) == legacy_weight
            assert by_id[map_legacy_id][2] == WEIGHT_POLICY_LEGACY
            assert Decimal(str(by_id[map_half_id][1])) == half_weight
            assert by_id[map_half_id][2] == WEIGHT_POLICY_LEGACY

            after_metric = (
                await conn.execute(
                    text(
                        """
                        SELECT weighted_earned, weighted_max, attainment_pct
                        FROM outcome_attainment_metrics WHERE id = :id
                        """
                    ),
                    {"id": metric_id},
                )
            ).one()
            assert Decimal(str(after_metric[0])) == Decimal(str(before_metric[0]))
            assert Decimal(str(after_metric[1])) == Decimal(str(before_metric[1]))
            assert Decimal(str(after_metric[2])) == Decimal(str(before_metric[2]))

            after_report = (
                await conn.execute(
                    text(
                        """
                        SELECT source_set_hash, source_published_result_ids::text,
                               source_result_count, mapping_activation_hash
                        FROM outcome_attainment_report_runs WHERE id = :id
                        """
                    ),
                    {"id": report_id},
                )
            ).one()
            assert after_report[0] == before_report[0]
            assert after_report[1] == before_report[1]
            assert after_report[2] == before_report[2]
            assert after_report[3] is not None

            set_hash = (
                await conn.execute(
                    text(
                        "SELECT activation_hash FROM outcome_mapping_sets WHERE id = :id"
                    ),
                    {"id": mapping_set_id},
                )
            ).scalar_one()
            assert set_hash == after_report[3]

            expected = compute_mapping_activation_hash(
                tenant_id=tenant_id,
                assessment_id=assessment_id,
                assessment_version_id=version_id,
                mapping_set_id=mapping_set_id,
                version_number=1,
                mappings=[
                    (question_id, qv_id, co1_id, legacy_weight),
                    (question_id, qv_id, co2_id, half_weight),
                ],
            )
            assert set_hash == expected
            fabricated = compute_mapping_activation_hash(
                tenant_id=tenant_id,
                assessment_id=assessment_id,
                assessment_version_id=version_id,
                mapping_set_id=mapping_set_id,
                version_number=1,
                mappings=[
                    (question_id, qv_id, co1_id, Decimal("1.0000")),
                    (question_id, qv_id, co2_id, half_weight),
                ],
            )
            assert fabricated != set_hash

            co_fail = uuid.uuid4()
            await conn.execute(
                text(
                    """
                    INSERT INTO outcome_definitions (
                      id, tenant_id, outcome_type, code, title, status, created_by
                    ) VALUES (
                      :id, :tid, 'CO', 'COFAIL', 'Fail Outcome', 'ACTIVE', :uid
                    )
                    """
                ),
                {"id": co_fail, "tid": tenant_id, "uid": user_id},
            )
            with pytest.raises((IntegrityError, DBAPIError)):
                async with conn.begin_nested():
                    await conn.execute(
                        text(
                            """
                            INSERT INTO question_outcome_mappings (
                              id, tenant_id, mapping_set_id, question_id,
                              question_version_id, outcome_definition_id,
                              weight, weight_policy_version
                            ) VALUES (
                              :id, :tid, :msid, :qid, :qvid, :oid, 1.5, :pol
                            )
                            """
                        ),
                        {
                            "id": uuid.uuid4(),
                            "tid": tenant_id,
                            "msid": mapping_set_id,
                            "qid": question_id,
                            "qvid": qv_id,
                            "oid": co_fail,
                            "pol": WEIGHT_POLICY_STRICT,
                        },
                    )

            co3_id = uuid.uuid4()
            await conn.execute(
                text(
                    """
                    INSERT INTO outcome_definitions (
                      id, tenant_id, outcome_type, code, title, status, created_by
                    ) VALUES (
                      :id, :tid, 'CO', 'CO3', 'Course Outcome 3', 'ACTIVE', :uid
                    )
                    """
                ),
                {"id": co3_id, "tid": tenant_id, "uid": user_id},
            )
            await conn.execute(
                text(
                    """
                    INSERT INTO question_outcome_mappings (
                      id, tenant_id, mapping_set_id, question_id,
                      question_version_id, outcome_definition_id,
                      weight, weight_policy_version
                    ) VALUES (
                      :id, :tid, :msid, :qid, :qvid, :oid, 0.5, :pol
                    )
                    """
                ),
                {
                    "id": uuid.uuid4(),
                    "tid": tenant_id,
                    "msid": mapping_set_id,
                    "qid": question_id,
                    "qvid": qv_id,
                    "oid": co3_id,
                    "pol": WEIGHT_POLICY_STRICT,
                },
            )
            strict_row_id = (
                await conn.execute(
                    text(
                        "SELECT id FROM question_outcome_mappings "
                        "WHERE outcome_definition_id = :oid"
                    ),
                    {"oid": co3_id},
                )
            ).scalar_one()
            with pytest.raises((IntegrityError, DBAPIError)):
                async with conn.begin_nested():
                    await conn.execute(
                        text(
                            """
                            UPDATE question_outcome_mappings
                            SET weight_policy_version = :legacy, weight = 1.5
                            WHERE id = :id
                            """
                        ),
                        {"legacy": WEIGHT_POLICY_LEGACY, "id": strict_row_id},
                    )
        await engine.dispose()
    finally:
        await _drop_mig_db()
        get_settings.cache_clear()
