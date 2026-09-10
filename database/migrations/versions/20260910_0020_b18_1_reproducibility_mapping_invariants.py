"""b18_1_reproducibility_mapping_invariants (+ B18.2 provenance preservation)

Revision ID: 20260910_0020
Revises: 20260910_0019
Create Date: 2026-09-10 16:00:00.000000

B18.1:
- Expand answer_cluster_runs uniqueness to include embedding identity
- Persist outcome_mapping_sets.activation_hash
- Persist outcome_attainment_report_runs.mapping_activation_hash
- Deterministically backfill activation hashes for existing ACTIVE/RETIRED sets

B18.2 (unreleased develop correction of this same revision):
- Do NOT clamp or delete historically valid B18 mapping weights (e.g. 1.5)
- Introduce weight_policy_version for legacy vs strict weight governance
- DB constraint allows legacy (policy=1) weights > 0; strict (policy>=2)
  requires 0 < weight <= 1
- Backfill activation / report hashes from ACTUAL persisted weights
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from decimal import Decimal
from uuid import UUID

import sqlalchemy as sa
from alembic import op
from sqlalchemy.sql import text

revision: str = "20260910_0020"
down_revision: str | None = "20260910_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

WEIGHT_QUANTUM = Decimal("0.0001")


def _normalize_weight(weight: Decimal | float | str) -> Decimal:
    return Decimal(str(weight)).quantize(WEIGHT_QUANTUM)


def _compute_mapping_activation_hash(
    *,
    tenant_id: UUID,
    assessment_id: UUID,
    assessment_version_id: UUID,
    mapping_set_id: UUID,
    version_number: int,
    mappings: list[tuple[UUID, UUID, UUID, Decimal]],
) -> str:
    """Must match app.services.outcome_intelligence.compute_mapping_activation_hash."""
    lines = [
        f"tenant_id={tenant_id}",
        f"assessment_id={assessment_id}",
        f"assessment_version_id={assessment_version_id}",
        f"mapping_set_id={mapping_set_id}",
        f"version_number={int(version_number)}",
    ]
    mapping_lines = [
        "mapping="
        f"{question_id}|{question_version_id}|{outcome_id}|"
        f"{_normalize_weight(weight)}"
        for question_id, question_version_id, outcome_id, weight in mappings
    ]
    mapping_lines.sort()
    lines.extend(mapping_lines)
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def upgrade() -> None:
    # --- Cluster run uniqueness includes embedding identity ---
    op.drop_constraint(
        "uq_answer_cluster_runs_tenant_av_q_hash_algo_thr",
        "answer_cluster_runs",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_answer_cluster_runs_repro_identity",
        "answer_cluster_runs",
        [
            "tenant_id",
            "assessment_version_id",
            "question_id",
            "source_set_hash",
            "algorithm_version",
            "similarity_threshold",
            "embedding_provider",
            "embedding_model",
            "embedding_model_version",
            "embedding_dim",
        ],
    )

    # --- Legacy vs strict weight policy (B18.2) ---
    # Existing B18 rows (created under weight > 0 only) are tagged policy=1.
    # New inserts default to policy=2 (strict 0 < weight <= 1).
    # NEVER clamp weight > 1 or delete historically valid rows.
    op.add_column(
        "question_outcome_mappings",
        sa.Column(
            "weight_policy_version",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
    )
    op.alter_column(
        "question_outcome_mappings",
        "weight_policy_version",
        server_default="2",
    )
    op.drop_constraint(
        "ck_question_outcome_mappings_weight_positive",
        "question_outcome_mappings",
        type_="check",
    )
    op.create_check_constraint(
        "ck_question_outcome_mappings_weight_policy",
        "question_outcome_mappings",
        "("
        "(weight_policy_version = 1 AND weight > 0) OR "
        "(weight_policy_version >= 2 AND weight > 0 AND weight <= 1)"
        ")",
    )
    # Prevent client/ORM bypass by rewriting policy on existing rows.
    op.execute(
        text(
            """
            CREATE OR REPLACE FUNCTION forbid_weight_policy_version_change()
            RETURNS trigger AS $$
            BEGIN
              IF NEW.weight_policy_version IS DISTINCT FROM OLD.weight_policy_version THEN
                RAISE EXCEPTION 'weight_policy_version is immutable'
                  USING ERRCODE = 'check_violation';
              END IF;
              RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
            """
        )
    )
    op.execute(
        text(
            """
            DROP TRIGGER IF EXISTS trg_question_outcome_mappings_weight_policy_immutable
              ON question_outcome_mappings
            """
        )
    )
    op.execute(
        text(
            """
            CREATE TRIGGER trg_question_outcome_mappings_weight_policy_immutable
              BEFORE UPDATE ON question_outcome_mappings
              FOR EACH ROW
              EXECUTE PROCEDURE forbid_weight_policy_version_change()
            """
        )
    )

    # --- Activation hash on mapping sets ---
    op.add_column(
        "outcome_mapping_sets",
        sa.Column("activation_hash", sa.String(length=64), nullable=True),
    )

    # --- Mapping activation identity on attainment reports ---
    op.add_column(
        "outcome_attainment_report_runs",
        sa.Column("mapping_activation_hash", sa.String(length=64), nullable=True),
    )

    conn = op.get_bind()
    sets = conn.execute(
        text(
            """
            SELECT id, tenant_id, assessment_id, assessment_version_id,
                   version_number, status
            FROM outcome_mapping_sets
            WHERE status IN ('ACTIVE', 'RETIRED')
            """
        )
    ).fetchall()
    for row in sets:
        mapping_set_id = row[0]
        mappings = conn.execute(
            text(
                """
                SELECT question_id, question_version_id, outcome_definition_id, weight
                FROM question_outcome_mappings
                WHERE mapping_set_id = :msid
                """
            ),
            {"msid": mapping_set_id},
        ).fetchall()
        payload = [
            (m[0], m[1], m[2], Decimal(str(m[3]))) for m in mappings
        ]
        activation_hash = _compute_mapping_activation_hash(
            tenant_id=row[1],
            assessment_id=row[2],
            assessment_version_id=row[3],
            mapping_set_id=mapping_set_id,
            version_number=int(row[4]),
            mappings=payload,
        )
        conn.execute(
            text(
                """
                UPDATE outcome_mapping_sets
                SET activation_hash = :ah
                WHERE id = :msid
                """
            ),
            {"ah": activation_hash, "msid": mapping_set_id},
        )
        conn.execute(
            text(
                """
                UPDATE outcome_attainment_report_runs
                SET mapping_activation_hash = :ah
                WHERE mapping_set_id = :msid
                  AND mapping_activation_hash IS NULL
                """
            ),
            {"ah": activation_hash, "msid": mapping_set_id},
        )


def downgrade() -> None:
    op.execute(
        text(
            """
            DROP TRIGGER IF EXISTS trg_question_outcome_mappings_weight_policy_immutable
              ON question_outcome_mappings
            """
        )
    )
    op.execute(text("DROP FUNCTION IF EXISTS forbid_weight_policy_version_change()"))
    op.drop_column("outcome_attainment_report_runs", "mapping_activation_hash")
    op.drop_column("outcome_mapping_sets", "activation_hash")

    op.drop_constraint(
        "ck_question_outcome_mappings_weight_policy",
        "question_outcome_mappings",
        type_="check",
    )
    op.drop_column("question_outcome_mappings", "weight_policy_version")
    op.create_check_constraint(
        "ck_question_outcome_mappings_weight_positive",
        "question_outcome_mappings",
        "weight > 0",
    )

    op.drop_constraint(
        "uq_answer_cluster_runs_repro_identity",
        "answer_cluster_runs",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_answer_cluster_runs_tenant_av_q_hash_algo_thr",
        "answer_cluster_runs",
        [
            "tenant_id",
            "assessment_version_id",
            "question_id",
            "source_set_hash",
            "algorithm_version",
            "similarity_threshold",
        ],
    )
