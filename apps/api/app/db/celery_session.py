"""Celery-safe async DB sessions.

Celery workers and beat invoke ``asyncio.run`` (or an equivalent fresh loop)
per task. The process-global API engine in ``app.db.session`` pools asyncpg
connections against a prior loop; closing those connections after the loop
exits produces:

* ``RuntimeError: Event loop is closed``
* ``AttributeError: 'NoneType' object has no attribute 'send'``

Use a NullPool engine created inside the task loop and dispose it before the
loop exits. Eager in-process callers also use this path so they never dispose
the shared API engine mid-request.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import get_settings


@asynccontextmanager
async def celery_session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Yield a session factory bound to a task-local NullPool engine."""
    settings = get_settings()
    engine: AsyncEngine = create_async_engine(
        settings.database_url,
        poolclass=NullPool,
        pool_pre_ping=True,
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


@asynccontextmanager
async def celery_session() -> AsyncIterator[AsyncSession]:
    """Yield a single session for a Celery task body."""
    async with celery_session_factory() as factory:
        async with factory() as session:
            yield session
