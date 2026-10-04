"""
tests/conftest.py
==================
Session-scoped environment setup for the SMBFlow test suite.

Patches DATABASE_URL to SQLite in-memory BEFORE any module-level
SQLAlchemy engine creation fires.  This avoids needing a live
PostgreSQL / asyncpg connection during unit and integration tests.
"""

from __future__ import annotations

import os

# ── Patch DATABASE_URL BEFORE any project module is imported ─────────────────
_TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
os.environ["DATABASE_URL"]         = _TEST_DB_URL
os.environ.setdefault("VAULT_ENCRYPTION_KEY", "rgjRwVY4ryCn6a4Bjsw8KnpER2LK67XW1g0XuhiN88s=")
os.environ.setdefault("JWT_SECRET_KEY",       "test-jwt-secret-key-for-testing")
os.environ.setdefault("ADMIN_EMAIL",          "admin@smbflow.test")
os.environ.setdefault("ADMIN_PASSWORD",       "testpassword123")

# ── SQLite ↔ PostgreSQL JSONB compatibility shim ─────────────────────────────
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON


@compiles(JSONB, "sqlite")
def _jsonb_sqlite(type_, compiler, **kw):
    return compiler.visit_JSON(JSON(), **kw)


# ── Patch core.database to use SQLite-compatible engine kwargs ────────────────
# core/database.py passes pool_size + max_overflow which SQLite doesn't support.
# We monkey-patch the module before it's imported by the project.
import importlib
import sys
from unittest.mock import patch
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession


def _make_sqlite_engine():
    """Create a SQLite aiosqlite engine without postgres-specific kwargs."""
    return create_async_engine(_TEST_DB_URL, echo=False)


# Pre-build a module-level SQLite engine that the app will use
_test_engine = _make_sqlite_engine()
_test_session_factory = async_sessionmaker(
    _test_engine, class_=AsyncSession,
    expire_on_commit=False, autocommit=False, autoflush=False,
)

# Inject before core.database is first imported
import types as _types

_fake_db_module = _types.ModuleType("core.database")
_fake_db_module.DATABASE_URL       = _TEST_DB_URL
_fake_db_module.engine             = _test_engine
_fake_db_module.AsyncSessionLocal  = _test_session_factory


async def _get_db_override():
    async with _test_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def _get_raw_session_override():
    return _test_session_factory()


_fake_db_module.get_db          = _get_db_override
_fake_db_module.get_raw_session = _get_raw_session_override

sys.modules["core.database"] = _fake_db_module


# ── Pytest configuration ──────────────────────────────────────────────────────
import pytest


def pytest_configure(config):
    config.addinivalue_line("markers", "anyio: mark test as async using anyio")
