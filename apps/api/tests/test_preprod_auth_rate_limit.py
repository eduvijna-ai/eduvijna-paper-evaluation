"""Unit tests for auth login failed-attempt rate limiting (SPR-001)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.services import auth_rate_limit as arl


class _FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, int] = {}

    def get(self, key: str) -> str | None:
        if key not in self.store:
            return None
        return str(self.store[key])

    def incr(self, key: str) -> int:
        self.store[key] = self.store.get(key, 0) + 1
        return self.store[key]

    def expire(self, key: str, _seconds: int) -> None:
        return None

    def pipeline(self) -> _FakePipe:
        return _FakePipe(self)


class _FakePipe:
    def __init__(self, redis: _FakeRedis) -> None:
        self._redis = redis
        self._ops: list[tuple[str, str]] = []

    def incr(self, key: str) -> _FakePipe:
        self._ops.append(("incr", key))
        return self

    def expire(self, key: str, _seconds: int) -> _FakePipe:
        self._ops.append(("expire", key))
        return self

    def execute(self) -> list[object]:
        out: list[object] = []
        for op, key in self._ops:
            if op == "incr":
                out.append(self._redis.incr(key))
            else:
                out.append(True)
        return out


@pytest.fixture(autouse=True)
def _reset_client(monkeypatch: pytest.MonkeyPatch) -> None:
    arl.reset_rate_limit_client_for_tests()
    fake = _FakeRedis()
    monkeypatch.setattr(arl, "_client", lambda _settings: fake)
    yield fake
    arl.reset_rate_limit_client_for_tests()


def _request(ip: str = "203.0.113.10") -> MagicMock:
    req = MagicMock()
    req.headers = {}
    req.client = SimpleNamespace(host=ip)
    return req


def test_auth_login_rate_limit_blocks_after_email_failures(
    _reset_client: _FakeRedis,
) -> None:
    settings = SimpleNamespace(
        environment="production",
        auth_login_fail_limit_per_email_per_minute=3,
        auth_login_fail_limit_per_ip_per_minute=100,
        celery_broker_url="redis://localhost:6379/0",
    )
    req = _request()
    for _ in range(3):
        arl.record_auth_login_failure(
            request=req, email="attacker@example.com", settings=settings  # type: ignore[arg-type]
        )
    with pytest.raises(HTTPException) as exc:
        arl.check_auth_login_rate_limit(
            request=req, email="attacker@example.com", settings=settings  # type: ignore[arg-type]
        )
    assert exc.value.status_code == 429
    assert exc.value.detail["code"] == "auth_rate_limited"


def test_auth_login_rate_limit_disabled_when_limits_zero(
    _reset_client: _FakeRedis,
) -> None:
    settings = SimpleNamespace(
        environment="production",
        auth_login_fail_limit_per_email_per_minute=0,
        auth_login_fail_limit_per_ip_per_minute=0,
        celery_broker_url="redis://localhost:6379/0",
    )
    req = _request()
    for _ in range(50):
        arl.record_auth_login_failure(
            request=req, email="x@example.com", settings=settings  # type: ignore[arg-type]
        )
    arl.check_auth_login_rate_limit(
        request=req, email="x@example.com", settings=settings  # type: ignore[arg-type]
    )


def test_auth_login_rate_limit_fail_open_in_local_when_redis_down(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    arl.reset_rate_limit_client_for_tests()

    def boom(_settings: object) -> object:
        raise RuntimeError("redis down")

    monkeypatch.setattr(arl, "_client", boom)
    settings = SimpleNamespace(
        environment="local",
        auth_login_fail_limit_per_email_per_minute=1,
        auth_login_fail_limit_per_ip_per_minute=1,
        celery_broker_url="redis://localhost:6379/0",
    )
    arl.check_auth_login_rate_limit(
        request=_request(), email="y@example.com", settings=settings  # type: ignore[arg-type]
    )


def test_auth_login_rate_limit_fail_closed_in_production_when_redis_down(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    arl.reset_rate_limit_client_for_tests()

    def boom(_settings: object) -> object:
        raise RuntimeError("redis down")

    monkeypatch.setattr(arl, "_client", boom)
    settings = SimpleNamespace(
        environment="production",
        auth_login_fail_limit_per_email_per_minute=1,
        auth_login_fail_limit_per_ip_per_minute=1,
        celery_broker_url="redis://localhost:6379/0",
    )
    with pytest.raises(HTTPException) as exc:
        arl.check_auth_login_rate_limit(
            request=_request(), email="y@example.com", settings=settings  # type: ignore[arg-type]
        )
    assert exc.value.status_code == 503
