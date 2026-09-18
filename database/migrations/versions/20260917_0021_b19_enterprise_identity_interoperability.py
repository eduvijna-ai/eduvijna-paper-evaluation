"""b19_enterprise_identity_interoperability

Revision ID: 20260917_0021
Revises: 20260910_0020
Create Date: 2026-09-17 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260917_0021"
down_revision: str | None = "20260910_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("auth_version", sa.Integer(), server_default="1", nullable=False),
    )

    op.create_table(
        "enterprise_identity_providers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("protocol", sa.String(length=16), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "config_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("issuer", sa.String(length=512), nullable=True),
        sa.Column("client_id", sa.String(length=255), nullable=True),
        sa.Column("authorization_endpoint", sa.String(length=1024), nullable=True),
        sa.Column("token_endpoint", sa.String(length=1024), nullable=True),
        sa.Column("jwks_uri", sa.String(length=1024), nullable=True),
        sa.Column("metadata_url", sa.String(length=1024), nullable=True),
        sa.Column("entity_id", sa.String(length=512), nullable=True),
        sa.Column("sso_url", sa.String(length=1024), nullable=True),
        sa.Column("jit_enabled", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "account_linking_policy",
            sa.String(length=64),
            server_default="NONE",
            nullable=False,
        ),
        sa.Column(
            "role_mapping_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("encrypted_client_secret", sa.Text(), nullable=True),
        sa.Column("encrypted_saml_idp_cert", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="ACTIVE", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "protocol IN ('OIDC','SAML')",
            name="ck_enterprise_identity_providers_protocol",
        ),
        sa.CheckConstraint(
            "account_linking_policy IN ('NONE','VERIFIED_EMAIL_EXPLICIT')",
            name="ck_enterprise_identity_providers_linking",
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE','DISABLED')",
            name="ck_enterprise_identity_providers_status",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "name", name="uq_enterprise_identity_providers_tenant_name"
        ),
    )
    op.create_index(
        "ix_enterprise_identity_providers_tenant",
        "enterprise_identity_providers",
        ["tenant_id"],
    )

    op.create_table(
        "external_user_identities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("provider_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("protocol", sa.String(length=16), nullable=False),
        sa.Column("external_subject", sa.String(length=512), nullable=False),
        sa.Column("issuer", sa.String(length=512), nullable=False),
        sa.Column("external_email", sa.String(length=320), nullable=True),
        sa.Column("last_authenticated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["provider_id"],
            ["enterprise_identity_providers.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "provider_id",
            "external_subject",
            name="uq_external_user_identities_tenant_provider_subject",
        ),
    )
    op.create_index(
        "ix_external_user_identities_tenant_user",
        "external_user_identities",
        ["tenant_id", "user_id"],
    )
    op.create_index(
        "ix_external_user_identities_provider",
        "external_user_identities",
        ["provider_id"],
    )

    op.create_table(
        "auth_transactions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("provider_id", sa.Uuid(), nullable=True),
        sa.Column("state", sa.String(length=255), nullable=True),
        sa.Column("nonce", sa.String(length=255), nullable=True),
        sa.Column("code_challenge", sa.String(length=255), nullable=True),
        sa.Column("encrypted_code_verifier", sa.Text(), nullable=True),
        sa.Column("exchange_code_hash", sa.String(length=64), nullable=True),
        sa.Column(
            "payload_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "kind IN ('OIDC_STATE','OIDC_CODE','SAML','LTI','SSO_EXCHANGE')",
            name="ck_auth_transactions_kind",
        ),
        sa.ForeignKeyConstraint(
            ["provider_id"],
            ["enterprise_identity_providers.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_auth_transactions_tenant_state",
        "auth_transactions",
        ["tenant_id", "state"],
    )
    op.create_index(
        "ix_auth_transactions_exchange_hash",
        "auth_transactions",
        ["exchange_code_hash"],
    )
    op.create_index("ix_auth_transactions_expires", "auth_transactions", ["expires_at"])

    op.create_table(
        "replay_markers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("marker_key", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "kind",
            "marker_key",
            name="uq_replay_markers_tenant_kind_key",
        ),
    )
    op.create_index("ix_replay_markers_expires", "replay_markers", ["expires_at"])

    op.create_table(
        "integration_credentials",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("key_prefix", sa.String(length=32), nullable=False),
        sa.Column("secret_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "scopes_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column("enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "key_prefix",
            name="uq_integration_credentials_key_prefix",
        ),
    )
    op.create_index(
        "ix_integration_credentials_tenant",
        "integration_credentials",
        ["tenant_id"],
    )

    op.create_table(
        "lti_platforms",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("issuer", sa.String(length=512), nullable=False),
        sa.Column("client_id", sa.String(length=255), nullable=False),
        sa.Column("deployment_id", sa.String(length=255), nullable=False),
        sa.Column("auth_login_url", sa.String(length=1024), nullable=False),
        sa.Column("token_url", sa.String(length=1024), nullable=False),
        sa.Column("jwks_url", sa.String(length=1024), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "role_mapping_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("encrypted_tool_private_jwk", sa.Text(), nullable=True),
        sa.Column(
            "tool_public_jwks_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "issuer",
            "client_id",
            "deployment_id",
            name="uq_lti_platforms_tenant_issuer_client_deployment",
        ),
    )
    op.create_index("ix_lti_platforms_tenant", "lti_platforms", ["tenant_id"])

    op.create_table(
        "lti_resource_links",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("platform_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("context_id", sa.String(length=255), nullable=False),
        sa.Column("resource_link_id", sa.String(length=255), nullable=False),
        sa.Column("assessment_id", sa.Uuid(), nullable=True),
        sa.Column("class_section_id", sa.Uuid(), nullable=True),
        sa.Column("ags_lineitem_url", sa.String(length=1024), nullable=True),
        sa.Column("nrps_memberships_url", sa.String(length=1024), nullable=True),
        sa.Column("last_launch_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["assessment_id"], ["assessments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["class_section_id"], ["class_sections.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["platform_id"], ["lti_platforms.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "platform_id",
            "context_id",
            "resource_link_id",
            name="uq_lti_resource_links_platform_context_resource",
        ),
    )
    op.create_index("ix_lti_resource_links_tenant", "lti_resource_links", ["tenant_id"])

    op.create_table(
        "external_roster_identities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("provider_key", sa.String(length=100), nullable=False),
        sa.Column("external_stable_id", sa.String(length=255), nullable=False),
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("class_section_id", sa.Uuid(), nullable=True),
        sa.Column("academic_year_id", sa.Uuid(), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="ACTIVE", nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE','INACTIVE')",
            name="ck_external_roster_identities_status",
        ),
        sa.ForeignKeyConstraint(
            ["academic_year_id"], ["academic_years.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["class_section_id"], ["class_sections.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "provider_key",
            "external_stable_id",
            name="uq_external_roster_identities_tenant_provider_ext",
        ),
    )
    op.create_index(
        "ix_external_roster_identities_student",
        "external_roster_identities",
        ["tenant_id", "student_id"],
    )

    op.create_table(
        "roster_sync_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("provider_key", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "summary_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('RUNNING','SUCCEEDED','FAILED')",
            name="ck_roster_sync_runs_status",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_roster_sync_runs_tenant", "roster_sync_runs", ["tenant_id"])

    op.create_table(
        "grade_passbacks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("lti_platform_id", sa.Uuid(), nullable=False),
        sa.Column("resource_link_id", sa.Uuid(), nullable=False),
        sa.Column("published_result_id", sa.Uuid(), nullable=False),
        sa.Column("published_result_version", sa.Integer(), nullable=False),
        sa.Column("external_user_id", sa.String(length=255), nullable=False),
        sa.Column("lineitem_url", sa.String(length=1024), nullable=False),
        sa.Column("score", sa.Numeric(10, 4), nullable=False),
        sa.Column("max_score", sa.Numeric(10, 4), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("latest_error", sa.Text(), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "state IN ('PENDING','DELIVERED','FAILED','REJECTED')",
            name="ck_grade_passbacks_state",
        ),
        sa.ForeignKeyConstraint(["lti_platform_id"], ["lti_platforms.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["published_result_id"], ["published_results.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["resource_link_id"], ["lti_resource_links.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_grade_passbacks_tenant_idempotency",
        ),
    )
    op.create_index(
        "ix_grade_passbacks_tenant_result",
        "grade_passbacks",
        ["tenant_id", "published_result_id"],
    )

    op.create_table(
        "webhook_endpoints",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("destination_url", sa.String(length=1024), nullable=False),
        sa.Column("encrypted_signing_secret", sa.Text(), nullable=False),
        sa.Column(
            "event_types_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column("enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_webhook_endpoints_tenant", "webhook_endpoints", ["tenant_id"])

    op.create_table(
        "outbound_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_uuid", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("schema_version", sa.String(length=32), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_entity_type", sa.String(length=100), nullable=False),
        sa.Column("source_entity_id", sa.Uuid(), nullable=False),
        sa.Column("source_version", sa.Integer(), nullable=True),
        sa.Column(
            "payload_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "dispatch_state",
            sa.String(length=32),
            server_default="PENDING",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "dispatch_state IN ('PENDING','DISPATCHING','DELIVERED','FAILED','PARTIAL')",
            name="ck_outbound_events_dispatch_state",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_uuid", name="uq_outbound_events_event_uuid"),
    )
    op.create_index(
        "ix_outbound_events_tenant_type",
        "outbound_events",
        ["tenant_id", "event_type"],
    )

    op.create_table(
        "webhook_deliveries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("endpoint_id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("terminal_failure", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('PENDING','SUCCEEDED','FAILED','RETRYING')",
            name="ck_webhook_deliveries_status",
        ),
        sa.ForeignKeyConstraint(
            ["endpoint_id"], ["webhook_endpoints.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["event_id"], ["outbound_events.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "endpoint_id",
            "event_id",
            name="uq_webhook_deliveries_endpoint_event",
        ),
    )
    op.create_index(
        "ix_webhook_deliveries_next_attempt",
        "webhook_deliveries",
        ["next_attempt_at"],
    )

    op.create_table(
        "webhook_delivery_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("delivery_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("error_sanitized", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["delivery_id"], ["webhook_deliveries.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "delivery_id",
            "attempt_number",
            name="uq_webhook_delivery_attempts_delivery_number",
        ),
    )


def downgrade() -> None:
    op.drop_table("webhook_delivery_attempts")
    op.drop_index("ix_webhook_deliveries_next_attempt", table_name="webhook_deliveries")
    op.drop_table("webhook_deliveries")
    op.drop_index("ix_outbound_events_tenant_type", table_name="outbound_events")
    op.drop_table("outbound_events")
    op.drop_index("ix_webhook_endpoints_tenant", table_name="webhook_endpoints")
    op.drop_table("webhook_endpoints")
    op.drop_index("ix_grade_passbacks_tenant_result", table_name="grade_passbacks")
    op.drop_table("grade_passbacks")
    op.drop_index("ix_roster_sync_runs_tenant", table_name="roster_sync_runs")
    op.drop_table("roster_sync_runs")
    op.drop_index(
        "ix_external_roster_identities_student", table_name="external_roster_identities"
    )
    op.drop_table("external_roster_identities")
    op.drop_index("ix_lti_resource_links_tenant", table_name="lti_resource_links")
    op.drop_table("lti_resource_links")
    op.drop_index("ix_lti_platforms_tenant", table_name="lti_platforms")
    op.drop_table("lti_platforms")
    op.drop_index("ix_integration_credentials_tenant", table_name="integration_credentials")
    op.drop_table("integration_credentials")
    op.drop_index("ix_replay_markers_expires", table_name="replay_markers")
    op.drop_table("replay_markers")
    op.drop_index("ix_auth_transactions_expires", table_name="auth_transactions")
    op.drop_index("ix_auth_transactions_exchange_hash", table_name="auth_transactions")
    op.drop_index("ix_auth_transactions_tenant_state", table_name="auth_transactions")
    op.drop_table("auth_transactions")
    op.drop_index(
        "ix_external_user_identities_provider", table_name="external_user_identities"
    )
    op.drop_index(
        "ix_external_user_identities_tenant_user", table_name="external_user_identities"
    )
    op.drop_table("external_user_identities")
    op.drop_index(
        "ix_enterprise_identity_providers_tenant",
        table_name="enterprise_identity_providers",
    )
    op.drop_table("enterprise_identity_providers")
    op.drop_column("users", "auth_version")
