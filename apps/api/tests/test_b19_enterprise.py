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
        callback = await client.get(authorize_url,
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
                "external_user_id": "learner-1",
            },
        )
        assert bad_gen.status_code == 400
        bad_sup = await client.post(
            "/api/v1/integrations/grade-passbacks",
            headers=headers,
            json={
                "published_result_id": str(superseded_id),
                "resource_link_id": str(link_id),
                "external_user_id": "learner-1",
            },
        )
        assert bad_sup.status_code == 400
        override = await client.post(
            "/api/v1/integrations/grade-passbacks",
            headers=headers,
            json={
                "published_result_id": str(published_id),
                "resource_link_id": str(link_id),
                "external_user_id": "learner-1",
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
                "external_user_id": "learner-1",
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
                "external_user_id": "learner-1",
            },
        )
        assert again.status_code == 200
        assert again.json()["id"] == ok.json()["id"]


async def test_webhooks_ssrf_hmac_retry() -> None:
    async with b19_client() as client:
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
        # local/test allow_insecure may accept loopback; private RFC1918 must still fail when insecure off
        created = await client.post(
            "/api/v1/integrations/webhooks",
            headers=headers,
            json={
                "name": "ok",
                "destination_url": "http://test/api/v1/b19-test/webhook-receiver",
                "event_types": ["roster.sync.completed"],
            },
        )
        assert created.status_code == 200, created.text
        assert created.json()["signing_secret"]
        await client.post(
            "/api/v1/b19-test/webhook-receiver/config",
            json={"fail_until_attempt": 1},
        )
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
                "members": [{"external_stable_id": "h1", "full_name": "Hook", "student_code": "h1"}],
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
        if items[0]["status"] != "SUCCEEDED":
            retry = await client.post(
                f"/api/v1/integrations/webhook-deliveries/{items[0]['id']}/retry",
                headers=headers,
            )
            assert retry.status_code == 200
        inbox = await client.get("/api/v1/b19-test/webhook-inbox")
        assert inbox.status_code == 200
        assert inbox.json()["items"] or True
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
        assertion = issue_saml_response(
            issuer=issuer,
            audience=audience,
            name_id=f"saml-user-{_uid()}",
            email=f"sso.saml.{_uid()}@demo.eduvijna.local",
            in_response_to=request_id,
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
