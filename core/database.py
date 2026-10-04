"""
core/database.py
================
SQLAlchemy async engine and session factory.
Single source of truth for DB connectivity — used by both the API
(via FastAPI DI) and background tasks (via direct instantiation).

CONSTANT — do not modify for business customization.
"""

from __future__ import annotations

import os
from typing import AsyncGenerator

import structlog
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

log = structlog.get_logger()

DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://opsgrid:postgres@localhost:5432/opsgrid",
)

_connect_args: dict = {}
# asyncpg defaults to SSL which fails for local Docker PostgreSQL.
# Only enable SSL for remote hosts (e.g. Supabase pooler).
if "localhost" in DATABASE_URL or "127.0.0.1" in DATABASE_URL:
    _connect_args["ssl"] = False
else:
    # Supabase transaction-mode pooler requires statement_cache_size=0
    # (no prepared statements — pooler doesn't support them)
    _connect_args["statement_cache_size"] = 0

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_size=int(os.getenv("DB_POOL_SIZE", "10")),
    max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "20")),
    pool_pre_ping=True,
    pool_recycle=3600,
    connect_args=_connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency — yields a scoped AsyncSession per request.
    Commits on clean exit, rolls back on exception.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_raw_session() -> AsyncSession:
    """
    Returns a raw session for use OUTSIDE of FastAPI DI context
    (background tasks, CLI). Caller is responsible for commit/close.
    """
    return AsyncSessionLocal()