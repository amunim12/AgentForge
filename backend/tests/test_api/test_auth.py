"""End-to-end tests for the auth router."""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_refresh_token, hash_password
from app.db.models import User


@pytest.mark.asyncio
async def test_register_creates_user(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/auth/register",
        json={
            "email": "new@example.com",
            "username": "newbie",
            "password": "correct-horse-battery",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "new@example.com"
    assert body["username"] == "newbie"
    assert "hashed_password" not in body


@pytest.mark.asyncio
async def test_register_rejects_duplicate_email(
    client: AsyncClient, test_user: User
) -> None:
    resp = await client.post(
        "/api/auth/register",
        json={
            "email": test_user.email,
            "username": "different-name",
            "password": "correct-horse-battery",
        },
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_register_validates_email(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/auth/register",
        json={
            "email": "not-an-email",
            "username": "abc",
            "password": "correct-horse-battery",
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_login_with_email_succeeds(
    client: AsyncClient, test_user: User
) -> None:
    resp = await client.post(
        "/api/auth/login",
        json={"identifier": test_user.email, "password": "correct-horse-battery"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]


@pytest.mark.asyncio
async def test_login_with_username_succeeds(
    client: AsyncClient, test_user: User
) -> None:
    resp = await client.post(
        "/api/auth/login",
        json={"identifier": test_user.username, "password": "correct-horse-battery"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_login_wrong_password_rejected(
    client: AsyncClient, test_user: User
) -> None:
    resp = await client.post(
        "/api/auth/login",
        json={"identifier": test_user.email, "password": "WRONG-PASSWORD-here"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_disabled_user_rejected(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    user = User(
        email="disabled@example.com",
        username="disabled",
        hashed_password=hash_password("correct-horse-battery"),
        is_active=False,
    )
    db_session.add(user)
    await db_session.commit()

    resp = await client.post(
        "/api/auth/login",
        json={"identifier": user.email, "password": "correct-horse-battery"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_requires_token(client: AsyncClient) -> None:
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_returns_current_user(
    client: AsyncClient, auth_headers: dict[str, str], test_user: User
) -> None:
    resp = await client.get("/api/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == test_user.id
    assert body["email"] == test_user.email


@pytest.mark.asyncio
async def test_refresh_returns_new_pair(
    client: AsyncClient, test_user: User
) -> None:
    refresh = create_refresh_token(test_user.id)
    resp = await client.post(
        "/api/auth/refresh", json={"refresh_token": refresh}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"]
    assert body["refresh_token"]


@pytest.mark.asyncio
async def test_refresh_rejects_access_token(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    # Pass an access token where a refresh token is expected.
    access = auth_headers["Authorization"].split(" ", 1)[1]
    resp = await client.post(
        "/api/auth/refresh", json={"refresh_token": access}
    )
    assert resp.status_code == 401
