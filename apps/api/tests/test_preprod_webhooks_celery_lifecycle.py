"""Regression: Celery webhook delivery must not tear down on a closed event loop."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@asynccontextmanager
async def _fake_session_factory():
    session = AsyncMock()
    session.scalar = AsyncMock(return_value=None)
    session.commit = AsyncMock()

    @asynccontextmanager
    async def _session_cm():
        yield session

    def factory():
        return _session_cm()

    yield factory


@pytest.mark.asyncio
async def test_celery_session_factory_disposes_nullpool_engine() -> None:
    from sqlalchemy.pool import NullPool

    from app.db import celery_session as mod

    engine = AsyncMock()
    engine.dispose = AsyncMock()

    with patch.object(mod, "create_async_engine", return_value=engine) as create:
        async with mod.celery_session_factory() as factory:
            assert factory is not None
        create.assert_called_once()
        kwargs = create.call_args.kwargs
        assert kwargs.get("poolclass") is NullPool
        engine.dispose.assert_awaited_once()


@pytest.mark.asyncio
async def test_deliver_webhooks_async_ok_with_task_local_sessions() -> None:
    from app.tasks.celery_app import _deliver_webhooks_async

    with (
        patch(
            "app.db.celery_session.celery_session_factory",
            _fake_session_factory,
        ),
        patch(
            "app.services.webhooks.deliver_due_webhooks",
            new_callable=AsyncMock,
            return_value=0,
        ),
        patch("app.tasks.celery_app.get_settings") as get_settings,
    ):
        settings = MagicMock()
        settings.celery_task_always_eager = True
        get_settings.return_value = settings
        result = await _deliver_webhooks_async()

    assert result == {"processed": 0, "status": "ok"}


def test_deliver_webhooks_impl_multiple_fresh_event_loops() -> None:
    """Celery beat calls asyncio.run per tick; teardown must not raise."""
    from app.tasks.celery_app import _deliver_webhooks_impl

    with (
        patch(
            "app.db.celery_session.celery_session_factory",
            _fake_session_factory,
        ),
        patch(
            "app.services.webhooks.deliver_due_webhooks",
            new_callable=AsyncMock,
            return_value=0,
        ),
        patch("app.tasks.celery_app.get_settings") as get_settings,
    ):
        settings = MagicMock()
        settings.celery_task_always_eager = True
        get_settings.return_value = settings
        for _ in range(5):
            out = _deliver_webhooks_impl()
            assert out["status"] == "ok"
            assert out["processed"] == 0

    asyncio.run(asyncio.sleep(0))
