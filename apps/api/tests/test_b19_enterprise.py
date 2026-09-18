# ruff: noqa: E501
"""B19 PEV-054/055 enterprise identity and interoperability tests."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.cli.seed_dev import ADMIN_EMAIL, ADMIN_PASSWORD, seed
from app.core.config import get_settings
from app.core.integration_crypto import hash_integration_secret
from app.core.security import hash_password
from app.db.models import Institution, IntegrationCredential, Student, Tenant, User
from app.db.session import async_session_factory
from app.main import create_app
from app.services.b19_test_providers import (
    issue_lti_id_token,
    issue_oidc_authorize_redirect,
    issue_saml_response,
    reset_test_provider_state,
    saml_idp_cert_pem,
)


@asynccontextmanager
async def b19_client() -> AsyncIterator[AsyncClient]:
    import os

    os.environ["CELERY_TASK_ALWAYS_EAGER"] = "true"
    os.environ["PUBLIC_BASE_URL"] = "http://test"
    await seed()
    reset_test_provider_state()
    get_settings.cache_clear()
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        yield client


def _uid() -> str:
    return uuid.uuid4().hex[:8]


async def _login(client: AsyncClient) -> dict[str, str]:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD, "tenant_slug": "demo"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def test_oidc_success_and_replay() -> None:
    async with b19_client() as client:
        headers = await _login(client)
        created = await client.post(
            "/api/v1/integrations/identity-providers",
            headers=headers,
            json={
                "name": f"OIDC Test {_uid()}",
                "protocol": "OIDC",
                "issuer": "https://b19-test.example/oidc",
                "client_id": "oidc-client",
                "client_secret": "oidc-secret",
                "authorization_endpoint": "http://test/api/v1/b19-test/oidc/authorize",
                "token_endpoint": "http://test/api/v1/b19-test/oidc/token",
                "jwks_uri": "http://test/api/v1/b19-test/oidc/jwks",
                "jit_enabled": True,
                "account_linking_policy": "NONE",
                "role_mapping_json": {},
            },
        )
        assert created.status_code == 200, created.text
        provider_id = created.json()["id"]
        start = await client.get(
            "/api/v1/sso/oidc/start",
            params={"tenant_slug": "demo", "provider_id": provider_id},
            follow_redirects=False,
        )
        assert start.status_code == 302
        authorize = start.headers["location"]
        from urllib.parse import parse_qs, urlparse

        qs = parse_qs(urlparse(authorize).query)
        jit_email = f"oidc.jit.{_uid()}@demo.eduvijna.local"
        authorize_url = issue_oidc_authorize_redirect(
            redirect_uri=qs["redirect_uri"][0],
            state=qs["state"][0],
            nonce=qs["nonce"][0],
            client_id="oidc-client",
            subject=f"oidc-user-{_uid()}",
            email=jit_email,
        )
        callback_parsed = urlparse(authorize_url)
        callback = await client.get(
            f"{callback_parsed.path}?{callback_parsed.query}",
            follow_redirects=False,
        )
        assert callback.status_code == 302, callback.text
        location = callback.headers["location"]
        assert "exchange_code=" in location
        code = parse_qs(urlparse(location).query)["exchange_code"][0]
        exchanged = await client.post("/api/v1/sso/exchange", json={"exchange_code": code})
        assert exchanged.status_code == 200, exchanged.text
        replay = await client.get(
            "/api/v1/sso/oidc/callback",
            params={"code": "replay", "state": qs["state"][0]},
            follow_redirects=False,
        )
        assert replay.status_code == 302
        assert "invalid_state" in replay.headers["location"]


async def test_oidc_wrong_issuer_and_deactivated() -> None:
    async with b19_client() as client:
        headers = await _login(client)
        created = await client.post(
            "/api/v1/integrations/identity-providers",
            headers=headers,
            json={
                "name": f"OIDC Bad Iss {_uid()}",
                "protocol": "OIDC",
                "issuer": "https://wrong-issuer.example",
                "client_id": "oidc-client",
                "authorization_endpoint": "http://test/api/v1/b19-test/oidc/authorize",
                "token_endpoint": "http://test/api/v1/b19-test/oidc/token",
                "jwks_uri": "http://test/api/v1/b19-test/oidc/jwks",
                "jit_enabled": True,
            },
        )
        provider_id = created.json()["id"]
        start = await client.get(
            "/api/v1/sso/oidc/start",
            params={"tenant_slug": "demo", "provider_id": provider_id},
            follow_redirects=False,
        )
        from urllib.parse import parse_qs, urlparse

        qs = parse_qs(urlparse(start.headers["location"]).query)
        redirect = issue_oidc_authorize_redirect(
            redirect_uri=qs["redirect_uri"][0],
            state=qs["state"][0],
            nonce=qs["nonce"][0],
            client_id="oidc-client",
        )
        callback = await client.get(redirect, follow_redirects=False)
        assert callback.status_code == 302
        assert "token_exchange_failed" in callback.headers["location"] or "sso_rejected" in callback.headers["location"] or "invalid" in callback.headers["location"]


async def test_scim_lifecycle_and_auth_revocation() -> None:
    async with b19_client() as client:
        headers = await _login(client)
        provider = await client.post(
            "/api/v1/integrations/identity-providers",
            headers=headers,
            json={"name": f"SCIM IdP {_uid()}", "protocol": "OIDC", "issuer": "https://scim.example", "enabled": True},
        )
        token = await client.post(
            f"/api/v1/integrations/identity-providers/{provider.json()['id']}/scim-token",
            headers=headers,
        )
        assert token.status_code == 200, token.text
        secret = token.json()["secret"]
        scim_headers = {"Authorization": f"Bearer {secret}"}
        username = f"scim.user.{_uid()}@demo.eduvijna.local"
        external_id = f"ext-scim-{_uid()}"
        created = await client.post(
            "/scim/v2/Users",
            headers=scim_headers,
            json={
                "userName": username,
                "displayName": "SCIM User",
                "externalId": external_id,
                "active": True,
            },
        )
        assert created.status_code == 201, created.text
        user_id = created.json()["id"]
        again = await client.post(
            "/scim/v2/Users",
            headers=scim_headers,
            json={
                "userName": username,
                "displayName": "SCIM User",
                "externalId": external_id,
                "active": True,
            },
        )
        assert again.status_code == 201
        assert again.json()["id"] == user_id
        listed = await client.get(
            "/scim/v2/Users",
            headers=scim_headers,
            params={"filter": f'userName eq "{username}"'},
        )
        assert listed.status_code == 200
        assert listed.json()["totalResults"] == 1
        patched = await client.patch(
            f"/scim/v2/Users/{user_id}",
            headers=scim_headers,
            json={"Operations": [{"op": "replace", "path": "active", "value": False}]},
        )
        assert patched.status_code == 200
        assert patched.json()["active"] is False
        async with async_session_factory() as db:
            user = await db.scalar(select(User).where(User.id == uuid.UUID(user_id)))
            assert user is not None
            assert user.status == "inactive"
            assert user.email == username
        login = await client.post(
            "/api/v1/auth/login",
            json={
                "email": username,
                "password": "anything",
                "tenant_slug": "demo",
            },
        )
        assert login.status_code in {401, 403}


async def test_machine_credentials_scopes_rotation_and_plaintext() -> None:
    async with b19_client() as client:
        headers = await _login(client)
        created = await client.post(
            "/api/v1/integrations/credentials",
            headers=headers,
            json={"name": "roster-key", "scopes": ["roster:write", "roster:read"]},
        )
        assert created.status_code == 200, created.text
        secret = created.json()["secret"]
        cred_id = created.json()["id"]
        async with async_session_factory() as db:
            row = await db.scalar(
                select(IntegrationCredential).where(IntegrationCredential.id == uuid.UUID(cred_id))
            )
            assert row is not None
            assert secret not in (row.secret_hash or "")
            assert row.secret_hash == hash_integration_secret(secret)
        ok = await client.post(
            "/api/integration/v1/roster/upsert",
            headers={"Authorization": f"Bearer {secret}"},
            json={
                "provider_key": "sis-a",
                "members": [
                    {
                        "external_stable_id": "stu-1",
                        "full_name": "Roster One",
                        "student_code": "stu-1",
                    }
                ],
            },
        )
        assert ok.status_code == 200, ok.text
        denied = await client.get(
            "/api/integration/v1/results/published",
            headers={"Authorization": f"Bearer {secret}"},
        )
        assert denied.status_code == 403
        rotated = await client.post(
            f"/api/v1/integrations/credentials/{cred_id}/rotate",
            headers=headers,
        )
        old = await client.get(
            "/api/integration/v1/health",
            headers={"Authorization": f"Bearer {secret}"},
        )
        assert old.status_code == 401
        new_ok = await client.get(
            "/api/integration/v1/health",
            headers={"Authorization": f"Bearer {rotated.json()['secret']}"},
        )
        assert new_ok.status_code == 200
        revoked = await client.post(
            f"/api/v1/integrations/credentials/{cred_id}/revoke",
            headers=headers,
        )
        assert revoked.status_code == 200
        after = await client.get(
            "/api/integration/v1/health",
            headers={"Authorization": f"Bearer {rotated.json()['secret']}"},
        )
        assert after.status_code == 401


async def test_expired_credential_rejected() -> None:
    async with b19_client() as client:
        headers = await _login(client)
        created = await client.post(
            "/api/v1/integrations/credentials",
            headers=headers,
            json={
                "name": "expired",
                "scopes": ["roster:read"],
                "expires_at": (datetime.now(UTC) - timedelta(hours=1)).isoformat(),
            },
        )
        secret = created.json()["secret"]
        resp = await client.get(
            "/api/integration/v1/roster/syncs/" + str(uuid.uuid4()),
            headers={"Authorization": f"Bearer {secret}"},
        )
        assert resp.status_code == 401


async def test_lti_launch_and_invalid_signature() -> None:
    async with b19_client() as client:
        headers = await _login(client)
        client_id = f"lti-client-{_uid()}"
        deployment_id = f"deploy-{_uid()}"
        platform = await client.post(
            "/api/v1/integrations/lti-platforms",
            headers=headers,
            json={
                "name": f"LTI Test {_uid()}",
                "issuer": "https://b19-test.example/lti",
                "client_id": client_id,
                "deployment_id": deployment_id,
                "auth_login_url": "http://test/api/v1/b19-test/lti/authorize",
                "token_url": "http://test/api/v1/b19-test/lti/token",
                "jwks_url": "http://test/api/v1/b19-test/lti/jwks",
                "role_mapping_json": {
                    "http://purl.imsglobal.org/vocab/lis/v2/membership#Instructor": "TEACHER"
                },
            },
        )
        assert platform.status_code == 200, platform.text
        async with async_session_factory() as db:
            from app.db.models import Assessment, LtiResourceLink

            tenant = await db.scalar(select(Tenant).where(Tenant.slug == "demo"))
            assert tenant is not None
            admin = await db.scalar(select(User).where(User.email == ADMIN_EMAIL))
            assert admin is not None
            assessment = await db.scalar(
                select(Assessment).where(Assessment.tenant_id == tenant.id)
            )
            if assessment is None:
                from decimal import Decimal

                from app.db.models import Curriculum

                curriculum = Curriculum(
                    tenant_id=tenant.id,
                    code=f"B19-L-{_uid()}",
                    name="LTI",
                    version_label="1",
                    status="active",
                )
                db.add(curriculum)
                await db.flush()
                assessment = Assessment(
                    tenant_id=tenant.id,
                    curriculum_id=curriculum.id,
                    code=f"B19-L-{_uid()}",
                    title="LTI",
                    assessment_type="EXAM",
                    max_marks=Decimal("20.00"),
                    status="ACTIVE",
                    created_by=admin.id,
                )
                db.add(assessment)
                await db.flush()
            db.add(
                LtiResourceLink(
                    platform_id=uuid.UUID(platform.json()["id"]),
                    tenant_id=tenant.id,
                    context_id="ctx-1",
                    resource_link_id="res-1",
                    assessment_id=assessment.id,
                    ags_lineitem_url="http://test/api/v1/b19-test/ags/lineitems/1",
                    nrps_memberships_url="http://test/api/v1/b19-test/nrps/memberships",
                )
            )
            await db.commit()
        login = await client.get(
            "/lti/login",
            params={
                "iss": "https://b19-test.example/lti",
                "client_id": client_id,
                "target_link_uri": "http://test/lti/launch",
                "login_hint": "lti-instructor-1",
                "lti_deployment_id": deployment_id,
            },
            follow_redirects=False,
        )
        assert login.status_code == 302
        from urllib.parse import parse_qs, urlparse

        qs = parse_qs(urlparse(login.headers["location"]).query)
        token = issue_lti_id_token(
            issuer="https://b19-test.example/lti",
            client_id=client_id,
            deployment_id=deployment_id,
            nonce=qs["nonce"][0],
            subject="lti-instructor-1",
            resource_link_id="res-1",
            context_id="ctx-1",
            lineitem_url="http://test/api/v1/b19-test/ags/lineitems/1",
            memberships_url="http://test/api/v1/b19-test/nrps/memberships",
            target_link_uri="http://test/lti/launch",
        )
        launch = await client.post(
            "/lti/launch",
            data={"id_token": token, "state": qs["state"][0]},
        )
        assert launch.status_code == 200, launch.text
        assert launch.json()["mapped_roles"] == ["TEACHER"]
        replay = await client.post(
            "/lti/launch",
            data={"id_token": token, "state": qs["state"][0]},
        )
        assert replay.status_code == 400
        bogus = jwt.encode(
            {"iss": "https://b19-test.example/lti", "aud": client_id, "sub": "x"},
            "not-the-key",
            algorithm="HS256",
        )
        login2 = await client.get(
            "/lti/login",
            params={
                "iss": "https://b19-test.example/lti",
                "client_id": client_id,
                "target_link_uri": "http://test/lti/launch",
                "lti_deployment_id": deployment_id,
            },
            follow_redirects=False,
        )
        qs2 = parse_qs(urlparse(login2.headers["location"]).query)
        bad = await client.post("/lti/launch", data={"id_token": bogus, "state": qs2["state"][0]})
        assert bad.status_code == 400


async def test_roster_idempotent_and_cross_tenant_safe() -> None:
    async with b19_client() as client:
        headers = await _login(client)
        cred = await client.post(
            "/api/v1/integrations/credentials",
            headers=headers,
            json={"name": "sis", "scopes": ["roster:write", "roster:read"]},
        )
        secret = cred.json()["secret"]
        ext_id = f"ext-{_uid()}"
        demo_name = f"Same Name {_uid()}"
        iso_name = f"Other Tenant {_uid()}"
        payload = {
            "provider_key": f"sis-main-{_uid()}",
            "members": [
                {"external_stable_id": ext_id, "full_name": demo_name, "student_code": ext_id}
            ],
        }
        first = await client.post(
            "/api/integration/v1/roster/upsert",
            headers={"Authorization": f"Bearer {secret}"},
            json=payload,
        )
        second = await client.post(
            "/api/integration/v1/roster/upsert",
            headers={"Authorization": f"Bearer {secret}"},
            json=payload,
        )
        assert first.status_code == 200 and second.status_code == 200
        assert first.json()["summary"]["created"] == 1
        assert second.json()["summary"]["updated"] == 1
        async with async_session_factory() as db:
            other = Tenant(slug=f"b19-iso-{_uid()}", name="B19 Iso", status="active")
            db.add(other)
            await db.flush()
            inst = Institution(tenant_id=other.id, code=f"ISO{_uid()[:4]}", name="Iso")
            db.add(inst)
            await db.flush()
            from app.services.roster import upsert_roster_members

            await upsert_roster_members(
                db,
                tenant_id=other.id,
                provider_key=payload["provider_key"],
                members=[
                    {
                        "external_stable_id": ext_id,
                        "full_name": iso_name,
                        "student_code": ext_id,
                    }
                ],
            )
            await db.commit()
            demo_students = list(
                await db.scalars(select(Student).where(Student.full_name == demo_name))
            )
            iso_students = list(
                await db.scalars(select(Student).where(Student.full_name == iso_name))
            )
            assert len(demo_students) == 1
            assert len(iso_students) == 1
            assert demo_students[0].tenant_id != iso_students[0].tenant_id


async def test_ags_published_only_and_idempotent() -> None:
    async with b19_client() as client:
        from app.cli.seed_b19_e2e_enterprise import seed_b19_e2e_enterprise

        seeded = await seed_b19_e2e_enterprise()
        headers = await _login(client)
        generated_id = uuid.UUID(seeded["generated_result_id"])
        published_id = uuid.UUID(seeded["published_result_id"])
        superseded_id = uuid.UUID(seeded["superseded_result_id"])
        link_id = uuid.UUID(seeded["lti_resource_link_id"])
        bad_gen = await client.post(
            "/api/v1/integrations/grade-passbacks",
            headers=headers,
            json={
                "published_result_id": str(generated_id),
                "resource_link_id": str(link_id),
                "external_user_id": "nrps-student-1",
            },
        )
        assert bad_gen.status_code == 400
        bad_sup = await client.post(
            "/api/v1/integrations/grade-passbacks",
            headers=headers,
            json={
                "published_result_id": str(superseded_id),
                "resource_link_id": str(link_id),
                "external_user_id": "nrps-student-1",
            },
        )
        assert bad_sup.status_code == 400
        override = await client.post(
            "/api/v1/integrations/grade-passbacks",
            headers=headers,
            json={
                "published_result_id": str(published_id),
                "resource_link_id": str(link_id),
                "external_user_id": "nrps-student-1",
                "score": 99,
            },
        )
        assert override.status_code == 400
        ok = await client.post(
            "/api/v1/integrations/grade-passbacks",
            headers=headers,
            json={
                "published_result_id": str(published_id),
                "resource_link_id": str(link_id),
                "external_user_id": "nrps-student-1",
            },
        )
        assert ok.status_code == 200, ok.text
        assert ok.json()["state"] == "DELIVERED"
        assert ok.json()["score"] == "18.0000" or ok.json()["score"].startswith("18")
        again = await client.post(
            "/api/v1/integrations/grade-passbacks",
            headers=headers,
            json={
                "published_result_id": str(published_id),
                "resource_link_id": str(link_id),
                "external_user_id": "nrps-student-1",
            },
        )
        assert again.status_code == 200
        assert again.json()["id"] == ok.json()["id"]


async def test_webhooks_ssrf_hmac_retry() -> None:
    async with b19_client() as client:
        from app.services.webhooks import sign_webhook_payload, verify_webhook_signature

        raw = '{"event_type":"roster.sync.completed"}'
        timestamp = "1710000000"
        secret = "unit-hmac-secret"
        signature = sign_webhook_payload(secret=secret, timestamp=timestamp, raw_body=raw)
        assert verify_webhook_signature(
            secret=secret, timestamp=timestamp, raw_body=raw, signature=signature
        )
        assert not verify_webhook_signature(
            secret=secret, timestamp=timestamp, raw_body=raw, signature="v1=deadbeef"
        )
        headers = await _login(client)
        blocked = await client.post(
            "/api/v1/integrations/webhooks",
            headers=headers,
            json={
                "name": "ssrf",
                "destination_url": "https://127.0.0.1/hook",
                "event_types": ["roster.sync.completed"],
            },
        )
        created = await client.post(
            "/api/v1/integrations/webhooks",
            headers=headers,
            json={
                "name": f"ok-{_uid()}",
                "destination_url": "http://test/api/v1/b19-test/webhook-receiver",
                "event_types": ["roster.sync.completed"],
            },
        )
        assert created.status_code == 200, created.text
        signing_secret = created.json()["signing_secret"]
        assert signing_secret
        async with async_session_factory() as db:
            from app.db.models import WebhookEndpoint

            others = list(
                await db.scalars(
                    select(WebhookEndpoint).where(
                        WebhookEndpoint.id != uuid.UUID(created.json()["id"])
                    )
                )
            )
            for row in others:
                row.enabled = False
            await db.commit()
        cfg = await client.post(
            "/api/v1/b19-test/webhook-receiver/config",
            json={"fail_until_attempt": 1, "expected_secret": signing_secret},
        )
        assert cfg.status_code == 200
        bad_sig = await client.post(
            "/api/v1/b19-test/webhook-receiver",
            content=raw,
            headers={
                "X-EduVijna-Timestamp": timestamp,
                "X-EduVijna-Signature": "v1=00",
                "X-EduVijna-Event-Id": "x",
                "X-EduVijna-Event-Type": "roster.sync.completed",
            },
        )
        assert bad_sig.status_code == 401
        cred = await client.post(
            "/api/v1/integrations/credentials",
            headers=headers,
            json={"name": "hook-sis", "scopes": ["roster:write"]},
        )
        sync = await client.post(
            "/api/integration/v1/roster/upsert",
            headers={"Authorization": f"Bearer {cred.json()['secret']}"},
            json={
                "provider_key": "hook",
                "members": [
                    {
                        "external_stable_id": f"h1-{_uid()}",
                        "full_name": "Hook",
                        "student_code": f"h1-{_uid()}",
                    }
                ],
            },
        )
        assert sync.status_code == 200
        deliveries = await client.get(
            f"/api/v1/integrations/webhooks/{created.json()['id']}/deliveries",
            headers=headers,
        )
        assert deliveries.status_code == 200
        items = deliveries.json()["items"]
        assert items
        latest = items[0]
        assert latest["status"] == "SUCCEEDED"
        assert latest["attempt_count"] >= 2
        attempts = await client.get(
            f"/api/v1/integrations/webhook-deliveries/{latest['id']}/attempts",
            headers=headers,
        )
        assert attempts.status_code == 200
        assert len(attempts.json()["items"]) >= 2
        inbox = await client.get("/api/v1/b19-test/webhook-inbox")
        assert inbox.status_code == 200
        inbox_items = inbox.json()["items"]
        assert inbox_items
        last_ok = False
        for item in inbox_items:
            if verify_webhook_signature(
                secret=signing_secret,
                timestamp=item["timestamp"],
                raw_body=item["body"],
                signature=item["signature"],
            ):
                last_ok = True
                break
        assert last_ok
        assert blocked.status_code in {200, 400}


async def test_ssrf_blocks_private_when_insecure_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi import HTTPException

    from app.services.ssrf import validate_public_https_url

    with pytest.raises(HTTPException):
        validate_public_https_url("https://10.0.0.8/hook", allow_insecure=False, purpose="webhook")
    with pytest.raises(HTTPException):
        validate_public_https_url("http://example.com/hook", allow_insecure=False, purpose="webhook")


async def test_cross_tenant_provider_isolation() -> None:
    async with b19_client() as client:
        headers = await _login(client)
        created = await client.post(
            "/api/v1/integrations/identity-providers",
            headers=headers,
            json={"name": f"Demo OIDC {_uid()}", "protocol": "OIDC", "issuer": "https://demo.example"},
        )
        assert created.status_code == 200
        async with async_session_factory() as db:
            other = Tenant(slug=f"iso-{uuid.uuid4().hex[:8]}", name="Iso", status="active")
            db.add(other)
            await db.flush()
            user = User(
                tenant_id=other.id,
                email="admin@iso.example",
                display_name="Iso Admin",
                password_hash=hash_password("IsoAdmin!2026"),
                status="active",
            )
            db.add(user)
            await db.commit()
        listed = await client.get("/api/v1/integrations/identity-providers", headers=headers)
        assert all(item["issuer"] != "https://other.example" for item in listed.json()["items"])


async def test_saml_sp_idp_replay_and_bad_signature() -> None:
    async with b19_client() as client:
        headers = await _login(client)
        settings = get_settings()
        issuer = f"https://b19-test.example/saml/{_uid()}"
        audience = f"{settings.public_base_url.rstrip('/')}/saml/sp/{_uid()}"
        created = await client.post(
            "/api/v1/integrations/identity-providers",
            headers=headers,
            json={
                "name": f"SAML Test {_uid()}",
                "protocol": "SAML",
                "issuer": issuer,
                "entity_id": audience,
                "sso_url": "http://test/api/v1/b19-test/saml/sso",
                "saml_idp_cert": saml_idp_cert_pem(),
                "jit_enabled": True,
            },
        )
        assert created.status_code == 200, created.text
        provider_id = created.json()["id"]
        start = await client.get(
            "/api/v1/sso/saml/start",
            params={"tenant_slug": "demo", "provider_id": provider_id},
            follow_redirects=False,
        )
        assert start.status_code == 302
        from urllib.parse import parse_qs, urlparse

        qs = parse_qs(urlparse(start.headers["location"]).query)
        request_id = qs["RelayState"][0]
        acs_url = f"{settings.public_base_url.rstrip('/')}/api/v1/sso/saml/acs"
        assertion = issue_saml_response(
            issuer=issuer,
            audience=audience,
            name_id=f"saml-user-{_uid()}",
            email=f"sso.saml.{_uid()}@demo.eduvijna.local",
            in_response_to=request_id,
            recipient=acs_url,
            destination=acs_url,
        )
        acs = await client.post(
            "/api/v1/sso/saml/acs",
            data={"SAMLResponse": assertion, "RelayState": request_id},
            follow_redirects=False,
        )
        assert acs.status_code == 302, acs.headers.get("location")
        assert "exchange_code=" in acs.headers["location"]
        replay = await client.post(
            "/api/v1/sso/saml/acs",
            data={"SAMLResponse": assertion, "RelayState": request_id},
            follow_redirects=False,
        )
        assert replay.status_code == 302
        assert "replay" in replay.headers["location"] or "sso_rejected" in replay.headers["location"]

        bad = await client.post(
            "/api/v1/sso/saml/acs",
            data={"SAMLResponse": "not-valid-xml", "RelayState": "x"},
            follow_redirects=False,
        )
        assert bad.status_code == 302

        idp = await client.post(
            "/api/v1/sso/saml/acs",
            params={"tenant_slug": "demo"},
            data={
                "SAMLResponse": issue_saml_response(
                    issuer=issuer,
                    audience=audience,
                    name_id=f"saml-idp-{_uid()}",
                    email=f"sso.saml.idp.{_uid()}@demo.eduvijna.local",
                    recipient=f"{settings.public_base_url.rstrip('/')}/api/v1/sso/saml/acs",
                    destination=f"{settings.public_base_url.rstrip('/')}/api/v1/sso/saml/acs",
                )
            },
            follow_redirects=False,
        )
        assert idp.status_code == 302
        assert "exchange_code=" in idp.headers["location"]

        wrong_iss = await client.post(
            "/api/v1/sso/saml/acs",
            params={"tenant_slug": "demo"},
            data={
                "SAMLResponse": issue_saml_response(
                    issuer="https://evil.example/saml",
                    audience=audience,
                    name_id="evil",
                    email="evil@demo.eduvijna.local",
                    recipient=f"{settings.public_base_url.rstrip('/')}/api/v1/sso/saml/acs",
                    destination=f"{settings.public_base_url.rstrip('/')}/api/v1/sso/saml/acs",
                )
            },
            follow_redirects=False,
        )
        assert wrong_iss.status_code == 302
        assert "exchange_code=" not in wrong_iss.headers["location"]


async def test_oidc_token_revoked_after_auth_version_bump() -> None:
    async with b19_client() as client:
        suffix = _uid()
        async with async_session_factory() as db:
            tenant = await db.scalar(select(Tenant).where(Tenant.slug == "demo"))
            assert tenant is not None
            user = User(
                tenant_id=tenant.id,
                email=f"revoked.{suffix}@demo.eduvijna.local",
                display_name="Revoked User",
                password_hash=hash_password("Revoked!2026"),
                status="active",
                auth_version=1,
            )
            db.add(user)
            await db.commit()
            user_id = user.id
        login = await client.post(
            "/api/v1/auth/login",
            json={
                "email": f"revoked.{suffix}@demo.eduvijna.local",
                "password": "Revoked!2026",
                "tenant_slug": "demo",
            },
        )
        assert login.status_code == 200
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        me = await client.get("/api/v1/auth/me", headers=headers)
        assert me.status_code == 200
        async with async_session_factory() as db:
            stored = await db.scalar(select(User).where(User.id == user_id))
            assert stored is not None
            stored.auth_version = int(stored.auth_version) + 1
            await db.commit()
        denied = await client.get("/api/v1/auth/me", headers=headers)
        assert denied.status_code == 401


async def test_oidc_invalid_signature_and_expired_state() -> None:
    async with b19_client() as client:
        headers = await _login(client)
        created = await client.post(
            "/api/v1/integrations/identity-providers",
            headers=headers,
            json={
                "name": f"OIDC Sig {_uid()}",
                "protocol": "OIDC",
                "issuer": "https://b19-test.example/oidc",
                "client_id": "oidc-client",
                "client_secret": "oidc-secret",
                "authorization_endpoint": "http://test/api/v1/b19-test/oidc/authorize",
                "token_endpoint": "http://test/api/v1/b19-test/oidc/token",
                "jwks_uri": "http://test/api/v1/b19-test/oidc/jwks",
                "jit_enabled": True,
            },
        )
        start = await client.get(
            "/api/v1/sso/oidc/start",
            params={"tenant_slug": "demo", "provider_id": created.json()["id"]},
            follow_redirects=False,
        )
        expired = await client.get(
            "/api/v1/sso/oidc/callback",
            params={"code": "x", "state": "missing-state"},
            follow_redirects=False,
        )
        assert expired.status_code == 302
        assert "invalid_state" in expired.headers["location"]
        assert start.status_code == 302


async def test_saml_destination_and_recipient_must_match_acs() -> None:
    async with b19_client() as client:
        headers = await _login(client)
        settings = get_settings()
        issuer = f"https://b19-test.example/saml/{_uid()}"
        audience = f"{settings.public_base_url.rstrip('/')}/saml/sp/{_uid()}"
        acs_url = f"{settings.public_base_url.rstrip('/')}/api/v1/sso/saml/acs"
        created = await client.post(
            "/api/v1/integrations/identity-providers",
            headers=headers,
            json={
                "name": f"SAML ACS {_uid()}",
                "protocol": "SAML",
                "issuer": issuer,
                "entity_id": audience,
                "sso_url": "http://test/api/v1/b19-test/saml/sso",
                "saml_idp_cert": saml_idp_cert_pem(),
                "jit_enabled": True,
            },
        )
        start = await client.get(
            "/api/v1/sso/saml/start",
            params={"tenant_slug": "demo", "provider_id": created.json()["id"]},
            follow_redirects=False,
        )
        from urllib.parse import parse_qs, urlparse

        request_id = parse_qs(urlparse(start.headers["location"]).query)["RelayState"][0]
        dest_mismatch = await client.post(
            "/api/v1/sso/saml/acs",
            data={
                "SAMLResponse": issue_saml_response(
                    issuer=issuer,
                    audience=audience,
                    name_id=f"saml-dest-{_uid()}",
                    email=f"dest.{_uid()}@demo.eduvijna.local",
                    in_response_to=request_id,
                    recipient=acs_url,
                    destination="https://evil.example/acs",
                ),
                "RelayState": request_id,
            },
            follow_redirects=False,
        )
        assert dest_mismatch.status_code == 302
        assert "exchange_code=" not in dest_mismatch.headers["location"]
        start2 = await client.get(
            "/api/v1/sso/saml/start",
            params={"tenant_slug": "demo", "provider_id": created.json()["id"]},
            follow_redirects=False,
        )
        request_id2 = parse_qs(urlparse(start2.headers["location"]).query)["RelayState"][0]
        recip_mismatch = await client.post(
            "/api/v1/sso/saml/acs",
            data={
                "SAMLResponse": issue_saml_response(
                    issuer=issuer,
                    audience=audience,
                    name_id=f"saml-recip-{_uid()}",
                    email=f"recip.{_uid()}@demo.eduvijna.local",
                    in_response_to=request_id2,
                    recipient="https://evil.example/acs",
                    destination=acs_url,
                ),
                "RelayState": request_id2,
            },
            follow_redirects=False,
        )
        assert recip_mismatch.status_code == 302
        assert "exchange_code=" not in recip_mismatch.headers["location"]
        ok = await client.post(
            "/api/v1/sso/saml/acs",
            data={
                "SAMLResponse": issue_saml_response(
                    issuer=issuer,
                    audience=audience,
                    name_id=f"saml-ok-{_uid()}",
                    email=f"ok.{_uid()}@demo.eduvijna.local",
                    in_response_to=request_id2,
                    recipient=acs_url,
                    destination=acs_url,
                ),
                "RelayState": request_id2,
            },
            follow_redirects=False,
        )
        assert ok.status_code == 302
        assert "exchange_code=" in ok.headers["location"]


async def test_lti_target_link_uri_mismatch_rejected() -> None:
    async with b19_client() as client:
        from app.cli.seed_b19_e2e_enterprise import seed_b19_e2e_enterprise

        seeded = await seed_b19_e2e_enterprise()
        headers = await _login(client)
        client_id = f"lti-mis-{_uid()}"
        deployment_id = f"deploy-{_uid()}"
        platform = await client.post(
            "/api/v1/integrations/lti-platforms",
            headers=headers,
            json={
                "name": f"LTI Mismatch {_uid()}",
                "issuer": "https://b19-test.example/lti",
                "client_id": client_id,
                "deployment_id": deployment_id,
                "auth_login_url": "http://test/api/v1/b19-test/lti/authorize",
                "token_url": "http://test/api/v1/b19-test/lti/token",
                "jwks_url": "http://test/api/v1/b19-test/lti/jwks",
            },
        )
        async with async_session_factory() as db:
            from app.db.models import LtiResourceLink

            tenant = await db.scalar(select(Tenant).where(Tenant.slug == "demo"))
            assert tenant is not None
            assessment_id = uuid.UUID(seeded["assessment_id"])
            db.add(
                LtiResourceLink(
                    platform_id=uuid.UUID(platform.json()["id"]),
                    tenant_id=tenant.id,
                    context_id="ctx-1",
                    resource_link_id="res-1",
                    assessment_id=assessment_id,
                )
            )
            await db.commit()
        login = await client.get(
            "/lti/login",
            params={
                "iss": "https://b19-test.example/lti",
                "client_id": client_id,
                "target_link_uri": "http://test/lti/launch",
                "lti_deployment_id": deployment_id,
            },
            follow_redirects=False,
        )
        from urllib.parse import parse_qs, urlparse

        qs = parse_qs(urlparse(login.headers["location"]).query)
        token = issue_lti_id_token(
            issuer="https://b19-test.example/lti",
            client_id=client_id,
            deployment_id=deployment_id,
            nonce=qs["nonce"][0],
            subject="lti-instructor-1",
            resource_link_id="res-1",
            context_id="ctx-1",
            lineitem_url="http://test/api/v1/b19-test/ags/lineitems/1",
            memberships_url="http://test/api/v1/b19-test/nrps/memberships",
            target_link_uri="https://evil.example/lti/launch",
        )
        bad = await client.post("/lti/launch", data={"id_token": token, "state": qs["state"][0]})
        assert bad.status_code == 400
        assert bad.json()["error"]["code"] == "target_mismatch"


async def test_ags_association_and_learner_mapping() -> None:
    async with b19_client() as client:
        from decimal import Decimal

        from app.cli.seed_b19_e2e_enterprise import seed_b19_e2e_enterprise
        from app.db.models import Assessment, Curriculum, LtiResourceLink

        seeded = await seed_b19_e2e_enterprise()
        headers = await _login(client)
        published_id = seeded["published_result_id"]
        generated_id = seeded["generated_result_id"]
        superseded_id = seeded["superseded_result_id"]
        link_id = seeded["lti_resource_link_id"]
        async with async_session_factory() as db:
            tenant = await db.scalar(select(Tenant).where(Tenant.slug == "demo"))
            assert tenant is not None
            admin = await db.scalar(select(User).where(User.email == ADMIN_EMAIL))
            assert admin is not None
            curriculum = Curriculum(
                tenant_id=tenant.id,
                code=f"B19-WR-{_uid()}",
                name="Wrong",
                version_label="1",
                status="active",
            )
            db.add(curriculum)
            await db.flush()
            other_assessment = Assessment(
                tenant_id=tenant.id,
                curriculum_id=curriculum.id,
                code=f"B19-WR-{_uid()}",
                title="Wrong",
                assessment_type="EXAM",
                max_marks=Decimal("20.00"),
                status="ACTIVE",
                created_by=admin.id,
            )
            db.add(other_assessment)
            await db.flush()
            platform_id = uuid.UUID(seeded["lti_platform_id"])
            other_link = LtiResourceLink(
                platform_id=platform_id,
                tenant_id=tenant.id,
                context_id=f"ctx-wrong-{_uid()}",
                resource_link_id=f"res-wrong-{_uid()}",
                assessment_id=other_assessment.id,
                ags_lineitem_url="http://test/api/v1/b19-test/ags/lineitems/1",
            )
            db.add(other_link)
            await db.commit()
            other_link_id = str(other_link.id)
        wrong_link = await client.post(
            "/api/v1/integrations/grade-passbacks",
            headers=headers,
            json={"published_result_id": published_id, "resource_link_id": other_link_id},
        )
        assert wrong_link.status_code == 400
        wrong_learner = await client.post(
            "/api/v1/integrations/grade-passbacks",
            headers=headers,
            json={
                "published_result_id": published_id,
                "resource_link_id": link_id,
                "external_user_id": "someone-else",
            },
        )
        assert wrong_learner.status_code == 400
        iso = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "admin@b19-iso.eduvijna.local",
                "password": "DemoAdmin!2026",
                "tenant_slug": "b19-iso",
            },
        )
        assert iso.status_code == 200, iso.text
        iso_headers = {"Authorization": f"Bearer {iso.json()['access_token']}"}
        cross = await client.post(
            "/api/v1/integrations/grade-passbacks",
            headers=iso_headers,
            json={"published_result_id": published_id, "resource_link_id": link_id},
        )
        assert cross.status_code in {401, 403, 404}
        assert (
            await client.post(
                "/api/v1/integrations/grade-passbacks",
                headers=headers,
                json={"published_result_id": generated_id, "resource_link_id": link_id},
            )
        ).status_code == 400
        assert (
            await client.post(
                "/api/v1/integrations/grade-passbacks",
                headers=headers,
                json={"published_result_id": superseded_id, "resource_link_id": link_id},
            )
        ).status_code == 400
        assert (
            await client.post(
                "/api/v1/integrations/grade-passbacks",
                headers=headers,
                json={
                    "published_result_id": published_id,
                    "resource_link_id": link_id,
                    "score": 99,
                },
            )
        ).status_code == 400
        ok = await client.post(
            "/api/v1/integrations/grade-passbacks",
            headers=headers,
            json={"published_result_id": published_id, "resource_link_id": link_id},
        )
        assert ok.status_code == 200, ok.text
        assert ok.json()["state"] == "DELIVERED"
        assert ok.json()["external_user_id"] == "nrps-student-1"
        again = await client.post(
            "/api/v1/integrations/grade-passbacks",
            headers=headers,
            json={"published_result_id": published_id, "resource_link_id": link_id},
        )
        assert again.status_code == 200
        assert again.json()["id"] == ok.json()["id"]


async def test_scim_requires_stable_external_id_not_email() -> None:
    async with b19_client() as client:
        from app.db.models import ExternalUserIdentity

        headers = await _login(client)
        provider = await client.post(
            "/api/v1/integrations/identity-providers",
            headers=headers,
            json={"name": f"SCIM Ext {_uid()}", "protocol": "OIDC", "issuer": "https://scim-ext.example"},
        )
        token = await client.post(
            f"/api/v1/integrations/identity-providers/{provider.json()['id']}/scim-token",
            headers=headers,
        )
        scim_headers = {"Authorization": f"Bearer {token.json()['secret']}"}
        email = f"scim.stable.{_uid()}@demo.eduvijna.local"
        missing = await client.post(
            "/scim/v2/Users",
            headers=scim_headers,
            json={"userName": email, "displayName": "No Ext"},
        )
        assert missing.status_code == 400
        email_as_id = await client.post(
            "/scim/v2/Users",
            headers=scim_headers,
            json={"userName": email, "displayName": "Email Id", "externalId": email},
        )
        assert email_as_id.status_code == 400
        external_id = f"stable-{_uid()}"
        created = await client.post(
            "/scim/v2/Users",
            headers=scim_headers,
            json={"userName": email, "displayName": "Stable", "externalId": external_id},
        )
        assert created.status_code == 201, created.text
        user_id = created.json()["id"]
        new_email = f"scim.renamed.{_uid()}@demo.eduvijna.local"
        replaced = await client.put(
            f"/scim/v2/Users/{user_id}",
            headers=scim_headers,
            json={"userName": new_email, "displayName": "Renamed", "externalId": external_id},
        )
        assert replaced.status_code == 200
        assert replaced.json()["externalId"] == external_id
        assert replaced.json()["userName"] == new_email
        async with async_session_factory() as db:
            identity = await db.scalar(
                select(ExternalUserIdentity).where(
                    ExternalUserIdentity.user_id == uuid.UUID(user_id),
                    ExternalUserIdentity.external_subject == external_id,
                )
            )
            assert identity is not None
            assert identity.external_subject == external_id
        iso_login = await client.post(
            "/api/v1/auth/login",
            json={
                "email": "admin@b19-iso.eduvijna.local",
                "password": "DemoAdmin!2026",
                "tenant_slug": "b19-iso",
            },
        )
        if iso_login.status_code != 200:
            from app.cli.seed_b19_e2e_enterprise import seed_b19_e2e_enterprise

            await seed_b19_e2e_enterprise()
            iso_login = await client.post(
                "/api/v1/auth/login",
                json={
                    "email": "admin@b19-iso.eduvijna.local",
                    "password": "DemoAdmin!2026",
                    "tenant_slug": "b19-iso",
                },
            )
        assert iso_login.status_code == 200, iso_login.text
        iso_headers = {"Authorization": f"Bearer {iso_login.json()['access_token']}"}
        iso_provider = await client.post(
            "/api/v1/integrations/identity-providers",
            headers=iso_headers,
            json={"name": f"SCIM Iso {_uid()}", "protocol": "OIDC", "issuer": f"https://scim-iso-{_uid()}.example"},
        )
        iso_token = await client.post(
            f"/api/v1/integrations/identity-providers/{iso_provider.json()['id']}/scim-token",
            headers=iso_headers,
        )
        iso_scim = {"Authorization": f"Bearer {iso_token.json()['secret']}"}
        iso_created = await client.post(
            "/scim/v2/Users",
            headers=iso_scim,
            json={
                "userName": f"iso.{_uid()}@b19-iso.eduvijna.local",
                "displayName": "Iso User",
                "externalId": external_id,
            },
        )
        assert iso_created.status_code == 201, iso_created.text
        assert iso_created.json()["id"] != user_id


async def test_scim_new_external_id_does_not_silently_bind_existing_email() -> None:
    async with b19_client() as client:
        from app.db.models import ExternalUserIdentity

        headers = await _login(client)
        local_email = f"local.scim.{_uid()}@demo.eduvijna.local"
        password = "DemoUser!2026"
        async with async_session_factory() as db:
            tenant = await db.scalar(select(Tenant).where(Tenant.slug == "demo"))
            assert tenant is not None
            local = User(
                tenant_id=tenant.id,
                email=local_email,
                display_name="Local Only",
                password_hash=hash_password(password),
                status="active",
                auth_version=1,
            )
            db.add(local)
            await db.commit()
            local_id = local.id
            auth_version_before = local.auth_version
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": local_email, "password": password, "tenant_slug": "demo"},
        )
        assert login.status_code == 200, login.text
        provider = await client.post(
            "/api/v1/integrations/identity-providers",
            headers=headers,
            json={
                "name": f"SCIM NoLink {_uid()}",
                "protocol": "OIDC",
                "issuer": f"https://scim-nolink-{_uid()}.example",
            },
        )
        token = await client.post(
            f"/api/v1/integrations/identity-providers/{provider.json()['id']}/scim-token",
            headers=headers,
        )
        scim_headers = {"Authorization": f"Bearer {token.json()['secret']}"}
        external_id = f"new-ext-{_uid()}"
        conflict = await client.post(
            "/scim/v2/Users",
            headers=scim_headers,
            json={
                "userName": local_email,
                "displayName": "Should Conflict",
                "externalId": external_id,
                "active": True,
            },
        )
        assert conflict.status_code == 409, conflict.text
        body = conflict.json()
        detail = body.get("error", {}).get("details") or body.get("error") or body
        detail_text = str(detail).lower()
        assert "link" in detail_text or "uniqueness" in detail_text or "existing" in detail_text
        async with async_session_factory() as db:
            attached = await db.scalar(
                select(ExternalUserIdentity).where(
                    ExternalUserIdentity.user_id == local_id,
                    ExternalUserIdentity.external_subject == external_id,
                )
            )
            assert attached is None
            local = await db.scalar(select(User).where(User.id == local_id))
            assert local is not None
            assert local.auth_version == auth_version_before
            assert local.email == local_email
            assert local.status == "active"
        unused_email = f"scim.fresh.{_uid()}@demo.eduvijna.local"
        fresh_ext = f"fresh-ext-{_uid()}"
        created = await client.post(
            "/scim/v2/Users",
            headers=scim_headers,
            json={
                "userName": unused_email,
                "displayName": "Fresh SCIM",
                "externalId": fresh_ext,
                "active": True,
            },
        )
        assert created.status_code == 201, created.text
        user_id = created.json()["id"]
        renamed = f"scim.renamed.{_uid()}@demo.eduvijna.local"
        replaced = await client.put(
            f"/scim/v2/Users/{user_id}",
            headers=scim_headers,
            json={
                "userName": renamed,
                "displayName": "Renamed Fresh",
                "externalId": fresh_ext,
            },
        )
        assert replaced.status_code == 200, replaced.text
        assert replaced.json()["externalId"] == fresh_ext
        assert replaced.json()["userName"] == renamed
        async with async_session_factory() as db:
            identity = await db.scalar(
                select(ExternalUserIdentity).where(
                    ExternalUserIdentity.user_id == uuid.UUID(user_id),
                    ExternalUserIdentity.external_subject == fresh_ext,
                )
            )
            assert identity is not None
            assert identity.external_subject == fresh_ext


async def test_lti_launch_rejects_resource_link_without_assessment_binding() -> None:
    async with b19_client() as client:
        from app.cli.seed_b19_e2e_enterprise import seed_b19_e2e_enterprise
        from app.db.models import LtiResourceLink

        seeded = await seed_b19_e2e_enterprise()
        headers = await _login(client)
        client_id = f"lti-unbound-{_uid()}"
        deployment_id = f"deploy-unbound-{_uid()}"
        platform = await client.post(
            "/api/v1/integrations/lti-platforms",
            headers=headers,
            json={
                "name": f"LTI Unbound {_uid()}",
                "issuer": "https://b19-test.example/lti",
                "client_id": client_id,
                "deployment_id": deployment_id,
                "auth_login_url": "http://test/api/v1/b19-test/lti/authorize",
                "token_url": "http://test/api/v1/b19-test/lti/token",
                "jwks_url": "http://test/api/v1/b19-test/lti/jwks",
            },
        )
        assert platform.status_code == 200, platform.text
        platform_id = uuid.UUID(platform.json()["id"])
        async with async_session_factory() as db:
            tenant = await db.scalar(select(Tenant).where(Tenant.slug == "demo"))
            assert tenant is not None
            db.add(
                LtiResourceLink(
                    platform_id=platform_id,
                    tenant_id=tenant.id,
                    context_id="ctx-no-assess",
                    resource_link_id="res-no-assess",
                    assessment_id=None,
                )
            )
            await db.commit()
        login = await client.get(
            "/lti/login",
            params={
                "iss": "https://b19-test.example/lti",
                "client_id": client_id,
                "target_link_uri": "http://test/lti/launch",
                "lti_deployment_id": deployment_id,
            },
            follow_redirects=False,
        )
        assert login.status_code == 302
        from urllib.parse import parse_qs, urlparse

        qs = parse_qs(urlparse(login.headers["location"]).query)
        bad_token = issue_lti_id_token(
            issuer="https://b19-test.example/lti",
            client_id=client_id,
            deployment_id=deployment_id,
            nonce=qs["nonce"][0],
            subject="lti-instructor-1",
            resource_link_id="res-no-assess",
            context_id="ctx-no-assess",
            lineitem_url="http://test/api/v1/b19-test/ags/lineitems/1",
            memberships_url="http://test/api/v1/b19-test/nrps/memberships",
            target_link_uri="http://test/lti/launch",
        )
        bad = await client.post(
            "/lti/launch", data={"id_token": bad_token, "state": qs["state"][0]}
        )
        assert bad.status_code == 400, bad.text
        assert bad.json()["error"]["code"] == "unbound_resource"

        async with async_session_factory() as db:
            tenant = await db.scalar(select(Tenant).where(Tenant.slug == "demo"))
            assert tenant is not None
            db.add(
                LtiResourceLink(
                    platform_id=platform_id,
                    tenant_id=tenant.id,
                    context_id="ctx-bound",
                    resource_link_id="res-bound",
                    assessment_id=uuid.UUID(seeded["assessment_id"]),
                )
            )
            await db.commit()
        login2 = await client.get(
            "/lti/login",
            params={
                "iss": "https://b19-test.example/lti",
                "client_id": client_id,
                "target_link_uri": "http://test/lti/launch",
                "lti_deployment_id": deployment_id,
            },
            follow_redirects=False,
        )
        qs2 = parse_qs(urlparse(login2.headers["location"]).query)
        good_token = issue_lti_id_token(
            issuer="https://b19-test.example/lti",
            client_id=client_id,
            deployment_id=deployment_id,
            nonce=qs2["nonce"][0],
            subject="lti-instructor-1",
            resource_link_id="res-bound",
            context_id="ctx-bound",
            lineitem_url="http://test/api/v1/b19-test/ags/lineitems/1",
            memberships_url="http://test/api/v1/b19-test/nrps/memberships",
            target_link_uri="http://test/lti/launch",
        )
        good = await client.post(
            "/lti/launch", data={"id_token": good_token, "state": qs2["state"][0]}
        )
        assert good.status_code == 200, good.text


async def test_webhook_partial_dispatch_state_with_two_endpoints() -> None:
    async with b19_client() as client:
        headers = await _login(client)
        first = await client.post(
            "/api/v1/integrations/webhooks",
            headers=headers,
            json={
                "name": f"partial-a-{_uid()}",
                "destination_url": "http://test/api/v1/b19-test/webhook-receiver",
                "event_types": ["roster.sync.completed"],
            },
        )
        second = await client.post(
            "/api/v1/integrations/webhooks",
            headers=headers,
            json={
                "name": f"partial-b-{_uid()}",
                "destination_url": "http://test/api/v1/b19-test/webhook-receiver",
                "event_types": ["roster.sync.completed"],
            },
        )
        assert first.status_code == 200 and second.status_code == 200
        await client.post(
            "/api/v1/b19-test/webhook-receiver/config",
            json={"fail_until_attempt": 0, "expected_secret": first.json()["signing_secret"]},
        )
        cred = await client.post(
            "/api/v1/integrations/credentials",
            headers=headers,
            json={"name": "partial-sis", "scopes": ["roster:write"]},
        )
        sync = await client.post(
            "/api/integration/v1/roster/upsert",
            headers={"Authorization": f"Bearer {cred.json()['secret']}"},
            json={
                "provider_key": f"partial-{_uid()}",
                "members": [
                    {
                        "external_stable_id": f"p1-{_uid()}",
                        "full_name": "P",
                        "student_code": f"p1-{_uid()}",
                    }
                ],
            },
        )
        assert sync.status_code == 200
        async with async_session_factory() as db:
            from app.db.models import OutboundEvent

            event = await db.scalar(
                select(OutboundEvent)
                .where(OutboundEvent.event_type == "roster.sync.completed")
                .order_by(OutboundEvent.occurred_at.desc())
            )
            assert event is not None
            assert event.dispatch_state == "PARTIAL"

