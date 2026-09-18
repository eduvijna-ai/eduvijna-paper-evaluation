"""SSRF-safe URL validation for outbound integration fetches and webhooks."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

from fastapi import HTTPException


def _is_unsafe_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def validate_public_https_url(
    url: str,
    *,
    allow_insecure: bool = False,
    purpose: str = "outbound",
) -> str:
    """Validate destination URL; reject private/loopback hosts unless allow_insecure."""
    parsed = urlparse(url)
    if parsed.scheme not in {"https", "http"}:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_url", "message": f"Invalid {purpose} URL scheme"},
        )
    if parsed.scheme != "https" and not allow_insecure:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "insecure_url",
                "message": f"{purpose} URL must use HTTPS",
            },
        )
    if not parsed.hostname:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_url", "message": f"Invalid {purpose} URL host"},
        )
    host = parsed.hostname
    if allow_insecure:
        return url

    try:
        addr = ipaddress.ip_address(host)
        if _is_unsafe_ip(addr):
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "ssrf_blocked",
                    "message": f"{purpose} URL resolves to a blocked address",
                },
            )
        return url
    except ValueError:
        pass

    try:
        infos = socket.getaddrinfo(host, parsed.port or 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_url", "message": f"Unable to resolve {purpose} host"},
        ) from exc

    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if _is_unsafe_ip(ip):
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "ssrf_blocked",
                    "message": f"{purpose} URL resolves to a blocked address",
                },
            )
    return url
