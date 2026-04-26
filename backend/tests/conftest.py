"""Shared pytest fixtures.

Sets safe dummy env vars BEFORE any application module is imported, so
`Settings()` validation passes and we never accidentally hit a real LLM
or Redis instance during tests.
"""
from __future__ import annotations

import os
import uuid
from collections.abc import AsyncGenerator, Generator
from typing import Any

import pytest
import pytest_asyncio

# --------------------------------------------------------------------------
# Env setup — must happen before app modules are imported.
# --------------------------------------------------------------------------
_TEST_ENV = {
    "SECRET_KEY": "x" * 48,
    "GOOGLE_API_KEY": "test-google-key",
    "GROQ_API_KEY": "test-groq-key",
    "TAVILY_API_KEY": "test-tavily-key",
    "LANGCHAIN_API_KEY": "test-langchain-key",
    "E2B_API_KEY": "test-e2b-key",
    "UPSTASH_REDIS_REST_URL": "https://dummy.upstash.io",
    "UPSTASH_REDIS_REST_TOKEN": "dummy-token",
    "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
    "ALLOWED_ORIGINS": "http://localhost:3000",
    "LANGCHAIN_TRACING_V2": "false",
}
for _k, _v in _TEST_ENV.items():
    os.environ.setdefault(_k, _v)


from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402
from sqlmodel import SQLModel  # noqa: E402

from app.api.deps import get_db  # noqa: E402
from app.core.security import create_access_token, hash_password  # noqa: E402
from app.db import models  # noqa: E402, F401  ensure metadata loaded
from app.db.models import User  # noqa: E402
from app.main import app  # noqa: E402


# --------------------------------------------------------------------------
# Test database — isolated in-memory SQLite per test session.
# --------------------------------------------------------------------------
@pytest_asyncio.fixture
async def test_engine() -> AsyncGenerator[Any, None]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        future=True,
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(test_engine: Any) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture
async def db_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    async with session_factory() as session:
        yield session


# --------------------------------------------------------------------------
# FastAPI client wired to the test DB.
# --------------------------------------------------------------------------
@pytest_asyncio.fixture
async def client(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncClient, None]:
    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    app.dependency_overrides.pop(get_db, None)


# --------------------------------------------------------------------------
# User + auth helpers.
# --------------------------------------------------------------------------
@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    user = User(
        id=str(uuid.uuid4()),
        email="alice@example.com",
        username="alice",
        hashed_password=hash_password("correct-horse-battery"),
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user: User) -> dict[str, str]:
    token = create_access_token(test_user.id)
    return {"Authorization": f"Bearer {token}"}


# --------------------------------------------------------------------------
# Disable rate limiting for tests so we don't get 429s on rapid calls.
# --------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _disable_rate_limit(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    from app.api.middleware import rate_limit

    monkeypatch.setattr(rate_limit.limiter, "enabled", False)
    yield


# --------------------------------------------------------------------------
# Stub network-bound singletons so nothing reaches the wire.
# --------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _stub_redis(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.queue import redis_client

    class _StubRedis:
        async def xadd(self, *args: Any, **kwargs: Any) -> str:
            return "0-0"

        async def close(self) -> None:
            return None

    monkeypatch.setattr(redis_client, "_redis_client", _StubRedis())


@pytest.fixture(autouse=True)
def _stub_chroma(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.memory import chroma

    async def _noop(*args: Any, **kwargs: Any) -> None:
        return None

    monkeypatch.setattr(chroma, "store_task_memory", _noop, raising=False)
    monkeypatch.setattr(chroma, "init_chroma", _noop, raising=False)
