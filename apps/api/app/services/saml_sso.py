# ruff: noqa: E501
"""SAML 2.0 SP-initiated and IdP-initiated SSO with signxml verification."""

from __future__ import annotations

import base64
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode
from xml.etree import ElementTree as ET

from fastapi import HTTPException
from lxml import etree
from signxml import XMLVerifier  # type: ignore[attr-defined]
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.integration_crypto import decrypt_secret, hash_opaque_token
from app.db.models import AuthTransaction, EnterpriseIdentityProvider
from app.services.enterprise_identity import (
    create_sso_exchange_code,
    record_replay_or_raise,
    resolve_or_provision_user,
)

NS = {
    "samlp": "urn:oasis:names:tc:SAML:2.0:protocol",
    "saml": "urn:oasis:names:tc:SAML:2.0:assertion",
    "ds": "http://www.w3.org/2000/09/xmldsig#",
}


def build_authn_request_xml(
    *,
    request_id: str,
    issue_instant: datetime,
    issuer: str,
    destination: str,
    acs_url: str,
) -> str:
    root = ET.Element(
        "{urn:oasis:names:tc:SAML:2.0:protocol}AuthnRequest",
        {
            "ID": request_id,
            "Version": "2.0",
            "IssueInstant": issue_instant.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "Destination": destination,
            "AssertionConsumerServiceURL": acs_url,
            "ProtocolBinding": "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST",
        },
    )
    issuer_el = ET.SubElement(root, "{urn:oasis:names:tc:SAML:2.0:assertion}Issuer")
    issuer_el.text = issuer
    return ET.tostring(root, encoding="unicode")


async def start_saml_login(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    provider_id: uuid.UUID,
    settings: Settings | None = None,
) -> dict[str, str]:
    cfg = settings or get_settings()
    provider = await db.scalar(
        select(EnterpriseIdentityProvider).where(
            EnterpriseIdentityProvider.id == provider_id,
            EnterpriseIdentityProvider.tenant_id == tenant_id,
            EnterpriseIdentityProvider.protocol == "SAML",
            EnterpriseIdentityProvider.enabled.is_(True),
        )
    )
    if provider is None:
        raise HTTPException(404, detail={"code": "not_found", "message": "SAML provider not found"})
    if not provider.sso_url:
        raise HTTPException(
            400,
            detail={"code": "provider_misconfigured", "message": "SAML SSO URL missing"},
        )

    request_id = f"_{secrets.token_hex(16)}"
    acs_url = f"{cfg.public_base_url.rstrip('/')}/api/v1/sso/saml/acs"
    sp_entity_id = provider.entity_id or f"{cfg.public_base_url.rstrip('/')}/saml/sp/{provider.id}"
    now = datetime.now(UTC)
    authn_xml = build_authn_request_xml(
        request_id=request_id,
        issue_instant=now,
        issuer=sp_entity_id,
        destination=provider.sso_url,
        acs_url=acs_url,
    )
    tx = AuthTransaction(
        kind="SAML",
        tenant_id=tenant_id,
        provider_id=provider.id,
        state=request_id,
        payload_json={"acs_url": acs_url, "sp_entity_id": sp_entity_id},
        expires_at=now + timedelta(minutes=10),
    )
    db.add(tx)
    await db.flush()

    encoded = base64.b64encode(authn_xml.encode("utf-8")).decode("ascii")
    redirect_url = f"{provider.sso_url}?{urlencode({'SAMLRequest': encoded, 'RelayState': request_id})}"
    return {"redirect_url": redirect_url, "request_id": request_id}


def _parse_conditions(assertion: etree._Element) -> tuple[datetime, datetime]:
    conditions = assertion.find("saml:Conditions", NS)
    if conditions is None:
        raise HTTPException(
            400, detail={"code": "invalid_assertion", "message": "Missing Conditions"}
        )
    not_before = conditions.get("NotBefore")
    not_on_or_after = conditions.get("NotOnOrAfter")
    if not not_on_or_after:
        raise HTTPException(
            400, detail={"code": "invalid_assertion", "message": "Missing NotOnOrAfter"}
        )
    nb = (
        datetime.fromisoformat(not_before.replace("Z", "+00:00"))
        if not_before
        else datetime.now(UTC) - timedelta(minutes=1)
    )
    noa = datetime.fromisoformat(not_on_or_after.replace("Z", "+00:00"))
    return nb, noa


async def process_saml_response(
    db: AsyncSession,
    *,
    saml_response_b64: str,
    relay_state: str | None = None,
    provider_id: uuid.UUID | None = None,
    tenant_id: uuid.UUID | None = None,
    settings: Settings | None = None,
) -> dict[str, str]:
    cfg = settings or get_settings()
    try:
        xml_bytes = base64.b64decode(saml_response_b64)
    except Exception as exc:
        raise HTTPException(
            400, detail={"code": "invalid_saml", "message": "Invalid SAMLResponse encoding"}
        ) from exc

    parser = etree.XMLParser(resolve_entities=False, no_network=True, dtd_validation=False)
    try:
        root = etree.fromstring(xml_bytes, parser)
    except etree.XMLSyntaxError as exc:
        raise HTTPException(
            400, detail={"code": "invalid_saml", "message": "Invalid SAML XML"}
        ) from exc

    issuer_el = root.find("saml:Issuer", NS)
    if issuer_el is None or not issuer_el.text:
        assertion = root.find("saml:Assertion", NS)
        if assertion is not None:
            issuer_el = assertion.find("saml:Issuer", NS)
    issuer = (issuer_el.text or "").strip() if issuer_el is not None else ""

    provider: EnterpriseIdentityProvider | None = None
    if provider_id and tenant_id:
        provider = await db.scalar(
            select(EnterpriseIdentityProvider).where(
                EnterpriseIdentityProvider.id == provider_id,
                EnterpriseIdentityProvider.tenant_id == tenant_id,
                EnterpriseIdentityProvider.protocol == "SAML",
            )
        )
    elif relay_state:
        tx = await db.scalar(
            select(AuthTransaction).where(
                AuthTransaction.kind == "SAML",
                AuthTransaction.state == relay_state,
            )
        )
        if tx is not None:
            provider = await db.scalar(
                select(EnterpriseIdentityProvider).where(
                    EnterpriseIdentityProvider.id == tx.provider_id
                )
            )
    if provider is None and issuer and tenant_id:
        provider = await db.scalar(
            select(EnterpriseIdentityProvider).where(
                EnterpriseIdentityProvider.protocol == "SAML",
                EnterpriseIdentityProvider.issuer == issuer,
                EnterpriseIdentityProvider.tenant_id == tenant_id,
                EnterpriseIdentityProvider.enabled.is_(True),
            )
        )
    if provider is None or not provider.enabled:
        raise HTTPException(
            400, detail={"code": "unknown_idp", "message": "Unknown or disabled SAML IdP"}
        )
    if not provider.encrypted_saml_idp_cert:
        raise HTTPException(
            400, detail={"code": "provider_misconfigured", "message": "SAML IdP cert missing"}
        )

    cert_pem = decrypt_secret(provider.encrypted_saml_idp_cert)
    assertion_el = root.find("saml:Assertion", NS)
    if assertion_el is None:
        raise HTTPException(
            400, detail={"code": "invalid_assertion", "message": "Assertion missing"}
        )
    try:
        verified = XMLVerifier().verify(assertion_el, x509_cert=cert_pem)
        assertion = getattr(verified, "signed_xml", None)
        if assertion is None and isinstance(verified, list) and verified:
            assertion = getattr(verified[0], "signed_xml", None)
        if assertion is None:
            raise HTTPException(
                400, detail={"code": "invalid_assertion", "message": "Signed assertion missing"}
            )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            400, detail={"code": "invalid_signature", "message": "SAML signature invalid"}
        ) from exc

    if getattr(assertion, "tag", None) != f"{{{NS['saml']}}}Assertion":
        raise HTTPException(
            400, detail={"code": "invalid_assertion", "message": "Signed assertion missing"}
        )
    signed_assertion: Any = assertion

    not_before, not_on_or_after = _parse_conditions(signed_assertion)
    now = datetime.now(UTC)
    if now < not_before - timedelta(seconds=60) or now >= not_on_or_after:
        raise HTTPException(
            400, detail={"code": "assertion_expired", "message": "Assertion outside validity"}
        )

    audience_ok = False
    sp_entity = provider.entity_id or f"{cfg.public_base_url.rstrip('/')}/saml/sp/{provider.id}"
    accepted_audiences = {sp_entity}
    if provider.client_id:
        accepted_audiences.add(provider.client_id)
    for aud in signed_assertion.findall(".//saml:Audience", NS):
        if (aud.text or "").strip() in accepted_audiences:
            audience_ok = True
    if not audience_ok:
        raise HTTPException(
            400, detail={"code": "audience_mismatch", "message": "Audience mismatch"}
        )

    if provider.issuer and issuer and issuer != provider.issuer:
        raise HTTPException(
            400, detail={"code": "issuer_mismatch", "message": "Issuer mismatch"}
        )

    assertion_id = signed_assertion.get("ID") or hash_opaque_token(saml_response_b64)
    await record_replay_or_raise(
        db,
        tenant_id=provider.tenant_id,
        kind="saml_assertion",
        marker_key=str(assertion_id),
        expires_at=not_on_or_after,
    )

    subject = signed_assertion.find("saml:Subject/saml:NameID", NS)
    if subject is None or not subject.text:
        raise HTTPException(
            400, detail={"code": "missing_nameid", "message": "NameID missing"}
        )
    name_id = subject.text.strip()

    email = None
    display_name = None
    roles: list[str] = []
    for attr in signed_assertion.findall(".//saml:Attribute", NS):
        name = attr.get("Name") or attr.get("FriendlyName") or ""
        values = [
            (v.text or "").strip()
            for v in attr.findall("saml:AttributeValue", NS)
            if v.text
        ]
        lname = name.lower()
        if "email" in lname and values:
            email = values[0].lower()
        elif "displayname" in lname or name.endswith("name") and values:
            display_name = values[0]
        elif "role" in lname or "group" in lname:
            roles.extend(values)

    # InResponseTo binding for SP-initiated
    subject_confirm = signed_assertion.find(
        ".//saml:SubjectConfirmationData", NS
    )
    in_response_to = subject_confirm.get("InResponseTo") if subject_confirm is not None else None
    if in_response_to:
        tx = await db.scalar(
            select(AuthTransaction).where(
                AuthTransaction.kind == "SAML",
                AuthTransaction.state == in_response_to,
                AuthTransaction.tenant_id == provider.tenant_id,
            )
        )
        if tx is None or tx.consumed_at is not None or tx.expires_at <= now:
            raise HTTPException(
                400,
                detail={"code": "invalid_inresponseto", "message": "Invalid InResponseTo"},
            )
        tx.consumed_at = now

    user = await resolve_or_provision_user(
        db,
        provider=provider,
        external_subject=name_id,
        issuer=provider.issuer or issuer,
        email=email,
        display_name=display_name,
        email_verified=False,
        external_roles=roles,
    )
    exchange_code = await create_sso_exchange_code(
        db, tenant_id=provider.tenant_id, provider_id=provider.id, user=user
    )
    frontend = cfg.frontend_base_url.rstrip("/")
    return {
        "redirect_url": f"{frontend}/sso/complete?exchange_code={exchange_code}",
        "exchange_code": exchange_code,
    }


def build_signed_assertion_for_tests(
    *,
    assertion_id: str,
    issuer: str,
    name_id: str,
    audience: str,
    email: str,
    not_before: datetime,
    not_on_or_after: datetime,
    private_key_pem: str,
    cert_pem: str,
    in_response_to: str | None = None,
) -> str:
    """Helper used by test providers to mint signed SAML Responses."""
    from signxml import XMLSigner  # type: ignore[attr-defined]

    subject_confirm_attrs = {
        "NotOnOrAfter": not_on_or_after.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "Recipient": audience,
    }
    if in_response_to:
        subject_confirm_attrs["InResponseTo"] = in_response_to

    assertion_xml = f"""
    <saml:Assertion xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"
        xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
        ID="{assertion_id}" Version="2.0"
        IssueInstant="{not_before.strftime('%Y-%m-%dT%H:%M:%SZ')}">
      <saml:Issuer>{issuer}</saml:Issuer>
      <saml:Subject>
        <saml:NameID Format="urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress">{name_id}</saml:NameID>
        <saml:SubjectConfirmation Method="urn:oasis:names:tc:SAML:2.0:cm:bearer">
          <saml:SubjectConfirmationData {" ".join(f'{k}="{v}"' for k, v in subject_confirm_attrs.items())}/>
        </saml:SubjectConfirmation>
      </saml:Subject>
      <saml:Conditions NotBefore="{not_before.strftime('%Y-%m-%dT%H:%M:%SZ')}"
          NotOnOrAfter="{not_on_or_after.strftime('%Y-%m-%dT%H:%M:%SZ')}">
        <saml:AudienceRestriction>
          <saml:Audience>{audience}</saml:Audience>
        </saml:AudienceRestriction>
      </saml:Conditions>
      <saml:AttributeStatement>
        <saml:Attribute Name="email">
          <saml:AttributeValue xsi:type="xs:string" xmlns:xs="http://www.w3.org/2001/XMLSchema">{email}</saml:AttributeValue>
        </saml:Attribute>
      </saml:AttributeStatement>
      <saml:AuthnStatement AuthnInstant="{not_before.strftime('%Y-%m-%dT%H:%M:%SZ')}">
        <saml:AuthnContext>
          <saml:AuthnContextClassRef>urn:oasis:names:tc:SAML:2.0:ac:classes:PasswordProtectedTransport</saml:AuthnContextClassRef>
        </saml:AuthnContext>
      </saml:AuthnStatement>
    </saml:Assertion>
    """.strip()

    assertion = etree.fromstring(assertion_xml.encode("utf-8"))
    signed_assertion = XMLSigner(c14n_algorithm="http://www.w3.org/2001/10/xml-exc-c14n#").sign(
        assertion, key=private_key_pem, cert=cert_pem
    )
    response = etree.Element(
        "{urn:oasis:names:tc:SAML:2.0:protocol}Response",
        nsmap={
            "samlp": "urn:oasis:names:tc:SAML:2.0:protocol",
            "saml": "urn:oasis:names:tc:SAML:2.0:assertion",
        },
        ID=f"_resp{secrets.token_hex(8)}",
        Version="2.0",
        IssueInstant=not_before.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )
    iss = etree.SubElement(response, "{urn:oasis:names:tc:SAML:2.0:assertion}Issuer")
    iss.text = issuer
    status = etree.SubElement(response, "{urn:oasis:names:tc:SAML:2.0:protocol}Status")
    etree.SubElement(
        status,
        "{urn:oasis:names:tc:SAML:2.0:protocol}StatusCode",
        Value="urn:oasis:names:tc:SAML:2.0:status:Success",
    )
    response.append(signed_assertion)
    return base64.b64encode(etree.tostring(response)).decode("ascii")
