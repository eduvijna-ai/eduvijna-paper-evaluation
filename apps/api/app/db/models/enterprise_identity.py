"""B19 enterprise identity, SSO, SCIM, LTI, roster, and webhook models."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class EnterpriseIdentityProvider(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "enterprise_identity_providers"
    __table_args__ = (
        CheckConstraint(
            "protocol IN ('OIDC','SAML')",
            name="ck_enterprise_identity_providers_protocol",
        ),
        CheckConstraint(
            "account_linking_policy IN ('NONE','VERIFIED_EMAIL_EXPLICIT')",
            name="ck_enterprise_identity_providers_linking",
        ),
        CheckConstraint(
            "status IN ('ACTIVE','DISABLED')",
            name="ck_enterprise_identity_providers_status",
        ),
        UniqueConstraint(
            "tenant_id",
            "name",
            name="uq_enterprise_identity_providers_tenant_name",
        ),
        Index("ix_enterprise_identity_providers_tenant", "tenant_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(150))
    protocol: Mapped[str] = mapped_column(String(16))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    config_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )
    issuer: Mapped[str | None] = mapped_column(String(512), nullable=True)
    client_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    authorization_endpoint: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    token_endpoint: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    jwks_uri: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    metadata_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(512), nullable=True)
    sso_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    jit_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    account_linking_policy: Mapped[str] = mapped_column(
        String(64), default="NONE", server_default="NONE"
    )
    role_mapping_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )
    encrypted_client_secret: Mapped[str | None] = mapped_column(Text, nullable=True)
    encrypted_saml_idp_cert: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", server_default="ACTIVE")


class ExternalUserIdentity(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "external_user_identities"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "provider_id",
            "external_subject",
            name="uq_external_user_identities_tenant_provider_subject",
        ),
        Index("ix_external_user_identities_tenant_user", "tenant_id", "user_id"),
        Index("ix_external_user_identities_provider", "provider_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    provider_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("enterprise_identity_providers.id", ondelete="CASCADE")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    protocol: Mapped[str] = mapped_column(String(16))
    external_subject: Mapped[str] = mapped_column(String(512))
    issuer: Mapped[str] = mapped_column(String(512))
    external_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    last_authenticated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class AuthTransaction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "auth_transactions"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('OIDC_STATE','OIDC_CODE','SAML','LTI','SSO_EXCHANGE')",
            name="ck_auth_transactions_kind",
        ),
        Index("ix_auth_transactions_tenant_state", "tenant_id", "state"),
        Index("ix_auth_transactions_exchange_hash", "exchange_code_hash"),
        Index("ix_auth_transactions_expires", "expires_at"),
    )

    kind: Mapped[str] = mapped_column(String(32))
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    provider_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("enterprise_identity_providers.id", ondelete="SET NULL"), nullable=True
    )
    state: Mapped[str | None] = mapped_column(String(255), nullable=True)
    nonce: Mapped[str | None] = mapped_column(String(255), nullable=True)
    code_challenge: Mapped[str | None] = mapped_column(String(255), nullable=True)
    encrypted_code_verifier: Mapped[str | None] = mapped_column(Text, nullable=True)
    exchange_code_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ReplayMarker(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "replay_markers"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "kind",
            "marker_key",
            name="uq_replay_markers_tenant_kind_key",
        ),
        Index("ix_replay_markers_expires", "expires_at"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(64))
    marker_key: Mapped[str] = mapped_column(String(128))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class IntegrationCredential(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "integration_credentials"
    __table_args__ = (
        UniqueConstraint(
            "key_prefix",
            name="uq_integration_credentials_key_prefix",
        ),
        Index("ix_integration_credentials_tenant", "tenant_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(150))
    key_prefix: Mapped[str] = mapped_column(String(32))
    secret_hash: Mapped[str] = mapped_column(String(64))
    scopes_json: Mapped[list[Any]] = mapped_column(JSONB, default=list, server_default="[]")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class LtiPlatform(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "lti_platforms"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "issuer",
            "client_id",
            "deployment_id",
            name="uq_lti_platforms_tenant_issuer_client_deployment",
        ),
        Index("ix_lti_platforms_tenant", "tenant_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(150), default="LTI Platform")
    issuer: Mapped[str] = mapped_column(String(512))
    client_id: Mapped[str] = mapped_column(String(255))
    deployment_id: Mapped[str] = mapped_column(String(255))
    auth_login_url: Mapped[str] = mapped_column(String(1024))
    token_url: Mapped[str] = mapped_column(String(1024))
    jwks_url: Mapped[str] = mapped_column(String(1024))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    role_mapping_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )
    encrypted_tool_private_jwk: Mapped[str | None] = mapped_column(Text, nullable=True)
    tool_public_jwks_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )


class LtiResourceLink(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "lti_resource_links"
    __table_args__ = (
        UniqueConstraint(
            "platform_id",
            "context_id",
            "resource_link_id",
            name="uq_lti_resource_links_platform_context_resource",
        ),
        Index("ix_lti_resource_links_tenant", "tenant_id"),
    )

    platform_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("lti_platforms.id", ondelete="CASCADE")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    context_id: Mapped[str] = mapped_column(String(255))
    resource_link_id: Mapped[str] = mapped_column(String(255))
    assessment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("assessments.id", ondelete="SET NULL"), nullable=True
    )
    class_section_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("class_sections.id", ondelete="SET NULL"), nullable=True
    )
    ags_lineitem_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    nrps_memberships_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    last_launch_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ExternalRosterIdentity(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "external_roster_identities"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "provider_key",
            "external_stable_id",
            name="uq_external_roster_identities_tenant_provider_ext",
        ),
        Index("ix_external_roster_identities_student", "tenant_id", "student_id"),
        CheckConstraint(
            "status IN ('ACTIVE','INACTIVE')",
            name="ck_external_roster_identities_status",
        ),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    provider_key: Mapped[str] = mapped_column(String(100))
    external_stable_id: Mapped[str] = mapped_column(String(255))
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"))
    class_section_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("class_sections.id", ondelete="SET NULL"), nullable=True
    )
    academic_year_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("academic_years.id", ondelete="SET NULL"), nullable=True
    )
    source: Mapped[str] = mapped_column(String(64), default="SIS")
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", server_default="ACTIVE")
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RosterSyncRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "roster_sync_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('RUNNING','SUCCEEDED','FAILED')",
            name="ck_roster_sync_runs_status",
        ),
        Index("ix_roster_sync_runs_tenant", "tenant_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    provider_key: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(32), default="RUNNING")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    summary_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )


class GradePassback(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "grade_passbacks"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_grade_passbacks_tenant_idempotency",
        ),
        CheckConstraint(
            "state IN ('PENDING','DELIVERED','FAILED','REJECTED')",
            name="ck_grade_passbacks_state",
        ),
        Index("ix_grade_passbacks_tenant_result", "tenant_id", "published_result_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    lti_platform_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("lti_platforms.id", ondelete="CASCADE")
    )
    resource_link_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("lti_resource_links.id", ondelete="CASCADE")
    )
    published_result_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("published_results.id", ondelete="CASCADE")
    )
    published_result_version: Mapped[int] = mapped_column(Integer)
    external_user_id: Mapped[str] = mapped_column(String(255))
    lineitem_url: Mapped[str] = mapped_column(String(1024))
    score: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    max_score: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    idempotency_key: Mapped[str] = mapped_column(String(128))
    state: Mapped[str] = mapped_column(String(32), default="PENDING")
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    latest_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class WebhookEndpoint(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "webhook_endpoints"
    __table_args__ = (Index("ix_webhook_endpoints_tenant", "tenant_id"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(150))
    destination_url: Mapped[str] = mapped_column(String(1024))
    encrypted_signing_secret: Mapped[str] = mapped_column(Text)
    event_types_json: Mapped[list[Any]] = mapped_column(
        JSONB, default=list, server_default="[]"
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class OutboundEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "outbound_events"
    __table_args__ = (
        UniqueConstraint("event_uuid", name="uq_outbound_events_event_uuid"),
        CheckConstraint(
            "dispatch_state IN ('PENDING','DISPATCHING','DELIVERED','FAILED','PARTIAL')",
            name="ck_outbound_events_dispatch_state",
        ),
        Index("ix_outbound_events_tenant_type", "tenant_id", "event_type"),
    )

    event_uuid: Mapped[uuid.UUID] = mapped_column(unique=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    event_type: Mapped[str] = mapped_column(String(100))
    schema_version: Mapped[str] = mapped_column(String(32), default="1")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source_entity_type: Mapped[str] = mapped_column(String(100))
    source_entity_id: Mapped[uuid.UUID] = mapped_column()
    source_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payload_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )
    dispatch_state: Mapped[str] = mapped_column(
        String(32), default="PENDING", server_default="PENDING"
    )


class WebhookDelivery(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "webhook_deliveries"
    __table_args__ = (
        UniqueConstraint(
            "endpoint_id",
            "event_id",
            name="uq_webhook_deliveries_endpoint_event",
        ),
        CheckConstraint(
            "status IN ('PENDING','SUCCEEDED','FAILED','RETRYING')",
            name="ck_webhook_deliveries_status",
        ),
        Index("ix_webhook_deliveries_next_attempt", "next_attempt_at"),
    )

    endpoint_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("webhook_endpoints.id", ondelete="CASCADE")
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("outbound_events.id", ondelete="CASCADE")
    )
    status: Mapped[str] = mapped_column(String(32), default="PENDING")
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    next_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    terminal_failure: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )


class WebhookDeliveryAttempt(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "webhook_delivery_attempts"
    __table_args__ = (
        UniqueConstraint(
            "delivery_id",
            "attempt_number",
            name="uq_webhook_delivery_attempts_delivery_number",
        ),
    )

    delivery_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("webhook_deliveries.id", ondelete="CASCADE")
    )
    attempt_number: Mapped[int] = mapped_column(Integer)
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_sanitized: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
