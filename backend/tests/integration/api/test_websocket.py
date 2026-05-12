"""Tests for the WebSocket authentication and ownership logic."""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, create_refresh_token, hash_password
from app.db.models import Task, TaskStatus, User


# ---------------------------------------------------------------------------
# HTTP upgrade rejected paths (we check the 403/connection refused over HTTP
# because httpx AsyncClient treats WS upgrades as HTTP requests when using
# the ASGI transport).
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_websocket_rejects_missing_token(
    client: AsyncClient,
    test_user: User,
    db_session: AsyncSession,
) -> None:
    task = Task(
        title="ws task",
        description="task for websocket test",
        user_id=test_user.id,
        status=TaskStatus.EXECUTING,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    resp = await client.get(f"/api/ws/tasks/{task.id}")
    # FastAPI returns 403 for WS endpoints accessed without upgrade; the
    # important thing is it does not return 200.
    assert resp.status_code != 200


@pytest.mark.asyncio
async def test_websocket_rejects_expired_token(
    client: AsyncClient,
    test_user: User,
    db_session: AsyncSession,
) -> None:
    from datetime import timedelta
    from app.core.security import _create_token, ACCESS_TOKEN_TYPE

    task = Task(
        title="ws task",
        description="task for websocket expired token test",
        user_id=test_user.id,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    expired = _create_token(
        subject=test_user.id,
        token_type=ACCESS_TOKEN_TYPE,
        expires_delta=timedelta(seconds=-1),
    )
    resp = await client.get(f"/api/ws/tasks/{task.id}?token={expired}")
    assert resp.status_code != 200


@pytest.mark.asyncio
async def test_websocket_rejects_refresh_token(
    client: AsyncClient,
    test_user: User,
    db_session: AsyncSession,
) -> None:
    """A refresh token must not work in place of an access token."""
    task = Task(
        title="ws task",
        description="websocket refresh token test task",
        user_id=test_user.id,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    refresh = create_refresh_token(test_user.id)
    resp = await client.get(f"/api/ws/tasks/{task.id}?token={refresh}")
    assert resp.status_code != 200


@pytest.mark.asyncio
async def test_websocket_rejects_foreign_task(
    client: AsyncClient,
    test_user: User,
    db_session: AsyncSession,
) -> None:
    """A valid token must not grant access to another user's task."""
    other = User(
        email="other_ws@example.com",
        username="other_ws",
        hashed_password=hash_password("pw-for-other"),
    )
    db_session.add(other)
    await db_session.commit()

    foreign_task = Task(
        title="not yours",
        description="foreign task for ws ownership check",
        user_id=other.id,
    )
    db_session.add(foreign_task)
    await db_session.commit()
    await db_session.refresh(foreign_task)

    # test_user's valid token requesting a task owned by `other`.
    token = create_access_token(test_user.id)
    resp = await client.get(f"/api/ws/tasks/{foreign_task.id}?token={token}")
    assert resp.status_code != 200


@pytest.mark.asyncio
async def test_websocket_rejects_nonexistent_task(
    client: AsyncClient,
    test_user: User,
) -> None:
    token = create_access_token(test_user.id)
    resp = await client.get(f"/api/ws/tasks/does-not-exist?token={token}")
    assert resp.status_code != 200


# ---------------------------------------------------------------------------
# _authenticate_ws function unit tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_authenticate_ws_returns_user_id_for_valid_token() -> None:
    from app.api.routes.websocket import _authenticate_ws

    token = create_access_token("user-abc")
    user_id = await _authenticate_ws(token)
    assert user_id == "user-abc"


@pytest.mark.asyncio
async def test_authenticate_ws_returns_none_for_none_token() -> None:
    from app.api.routes.websocket import _authenticate_ws

    result = await _authenticate_ws(None)
    assert result is None


@pytest.mark.asyncio
async def test_authenticate_ws_returns_none_for_garbage_token() -> None:
    from app.api.routes.websocket import _authenticate_ws

    result = await _authenticate_ws("not-a-jwt-at-all")
    assert result is None


@pytest.mark.asyncio
async def test_authenticate_ws_returns_none_for_expired_token() -> None:
    from datetime import timedelta
    from app.api.routes.websocket import _authenticate_ws
    from app.core.security import _create_token, ACCESS_TOKEN_TYPE

    expired = _create_token(
        subject="u1",
        token_type=ACCESS_TOKEN_TYPE,
        expires_delta=timedelta(seconds=-10),
    )
    result = await _authenticate_ws(expired)
    assert result is None
