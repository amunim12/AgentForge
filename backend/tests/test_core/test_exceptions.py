"""Unit tests for the AgentForge exception hierarchy."""
from __future__ import annotations

import pytest
from fastapi import FastAPI, status
from httpx import ASGITransport, AsyncClient

from app.core.exceptions import (
    AgentForgeError,
    AuthenticationError,
    DuplicateResourceError,
    InvalidTokenError,
    NotFoundError,
    register_exception_handlers,
)


def test_agentforge_error_has_default_public_message() -> None:
    err = AgentForgeError("internal detail")
    # public_message is a class attribute; never leak the internal arg.
    assert err.public_message and err.public_message != "internal detail"


def test_specialized_errors_have_distinct_status_codes() -> None:
    assert AuthenticationError().status_code == status.HTTP_401_UNAUTHORIZED
    assert InvalidTokenError().status_code == status.HTTP_401_UNAUTHORIZED
    assert NotFoundError().status_code == status.HTTP_404_NOT_FOUND
    assert DuplicateResourceError().status_code == status.HTTP_409_CONFLICT


@pytest.mark.asyncio
async def test_register_exception_handlers_returns_sanitized_message() -> None:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom")
    async def boom() -> None:
        raise NotFoundError("internal detail with sensitive info")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/boom")
    assert resp.status_code == 404
    body = resp.json()
    # Public message, not the internal arg.
    assert body["detail"] == NotFoundError.public_message
    assert "sensitive" not in body["detail"]
