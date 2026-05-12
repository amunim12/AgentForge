"""Ingestion tests: user data flows correctly through registration and auth.

These tests verify that user data is stored and retrieved exactly as expected —
hashed passwords, unique constraints, token-to-user binding, and that sensitive
fields never leak through the API boundary.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token, hash_password, verify_password
from app.db.models import User


# ---------------------------------------------------------------------------
# Registration ingestion
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_register_stores_hashed_password_not_plaintext(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    resp = await client.post(
        "/api/auth/register",
        json={
            "email": "hashtest@example.com",
            "username": "hashtest",
            "password": "correct-horse-battery",
        },
    )
    assert resp.status_code == 201

    result = await db_session.execute(
        select(User).where(User.email == "hashtest@example.com")
    )
    user = result.scalar_one()

    # Plaintext must never be stored.
    assert user.hashed_password != "correct-horse-battery"
    # Bcrypt hash must verify correctly.
    assert verify_password("correct-horse-battery", user.hashed_password)


@pytest.mark.asyncio
async def test_register_stores_email_and_username_exactly(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    resp = await client.post(
        "/api/auth/register",
        json={
            "email": "exact@example.com",
            "username": "exact_user",
            "password": "correct-horse-battery",
        },
    )
    assert resp.status_code == 201

    result = await db_session.execute(
        select(User).where(User.email == "exact@example.com")
    )
    user = result.scalar_one()
    assert user.email == "exact@example.com"
    assert user.username == "exact_user"


@pytest.mark.asyncio
async def test_register_sets_is_active_true_by_default(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    resp = await client.post(
        "/api/auth/register",
        json={
            "email": "active@example.com",
            "username": "active_user",
            "password": "correct-horse-battery",
        },
    )
    assert resp.status_code == 201

    result = await db_session.execute(
        select(User).where(User.email == "active@example.com")
    )
    user = result.scalar_one()
    assert user.is_active is True


@pytest.mark.asyncio
async def test_register_response_never_exposes_hashed_password(
    client: AsyncClient,
) -> None:
    resp = await client.post(
        "/api/auth/register",
        json={
            "email": "noleak@example.com",
            "username": "noleak",
            "password": "correct-horse-battery",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert "hashed_password" not in body
    assert "password" not in body


@pytest.mark.asyncio
async def test_register_enforces_unique_email(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    payload = {
        "email": "dup@example.com",
        "username": "first",
        "password": "correct-horse-battery",
    }
    r1 = await client.post("/api/auth/register", json=payload)
    assert r1.status_code == 201

    r2 = await client.post(
        "/api/auth/register",
        json={**payload, "username": "second"},
    )
    assert r2.status_code == 409

    # Only one row must exist.
    result = await db_session.execute(select(User).where(User.email == "dup@example.com"))
    rows = result.scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_register_enforces_unique_username(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    r1 = await client.post(
        "/api/auth/register",
        json={"email": "u1@example.com", "username": "shared_name", "password": "correct-horse-battery"},
    )
    assert r1.status_code == 201

    r2 = await client.post(
        "/api/auth/register",
        json={"email": "u2@example.com", "username": "shared_name", "password": "correct-horse-battery"},
    )
    assert r2.status_code == 409


# ---------------------------------------------------------------------------
# Login → token integrity
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_login_token_contains_correct_user_id(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await client.post(
        "/api/auth/register",
        json={
            "email": "tokencheck@example.com",
            "username": "tokencheck",
            "password": "correct-horse-battery",
        },
    )

    result = await db_session.execute(
        select(User).where(User.email == "tokencheck@example.com")
    )
    user = result.scalar_one()

    resp = await client.post(
        "/api/auth/login",
        json={"identifier": "tokencheck@example.com", "password": "correct-horse-battery"},
    )
    assert resp.status_code == 200
    body = resp.json()

    payload = decode_token(body["access_token"])
    assert payload["sub"] == user.id


@pytest.mark.asyncio
async def test_login_returns_both_token_types(
    client: AsyncClient,
) -> None:
    await client.post(
        "/api/auth/register",
        json={
            "email": "twotokens@example.com",
            "username": "twotokens",
            "password": "correct-horse-battery",
        },
    )
    resp = await client.post(
        "/api/auth/login",
        json={"identifier": "twotokens@example.com", "password": "correct-horse-battery"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]
    # Both must be distinct tokens.
    assert body["access_token"] != body["refresh_token"]


@pytest.mark.asyncio
async def test_access_token_and_refresh_token_have_different_types(
    client: AsyncClient,
) -> None:
    await client.post(
        "/api/auth/register",
        json={
            "email": "tokentypes@example.com",
            "username": "tokentypes",
            "password": "correct-horse-battery",
        },
    )
    resp = await client.post(
        "/api/auth/login",
        json={"identifier": "tokentypes@example.com", "password": "correct-horse-battery"},
    )
    body = resp.json()

    access_payload = decode_token(body["access_token"])
    refresh_payload = decode_token(body["refresh_token"], expected_type="refresh")

    assert access_payload["type"] == "access"
    assert refresh_payload["type"] == "refresh"
    assert access_payload["sub"] == refresh_payload["sub"]


# ---------------------------------------------------------------------------
# /me endpoint — DB state matches response
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_me_endpoint_returns_persisted_db_data(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    await client.post(
        "/api/auth/register",
        json={
            "email": "mecheck@example.com",
            "username": "mecheck",
            "password": "correct-horse-battery",
        },
    )

    result = await db_session.execute(
        select(User).where(User.email == "mecheck@example.com")
    )
    db_user = result.scalar_one()

    login_resp = await client.post(
        "/api/auth/login",
        json={"identifier": "mecheck@example.com", "password": "correct-horse-battery"},
    )
    token = login_resp.json()["access_token"]

    me_resp = await client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_resp.status_code == 200
    body = me_resp.json()

    assert body["id"] == db_user.id
    assert body["email"] == db_user.email
    assert body["username"] == db_user.username
    assert "hashed_password" not in body


# ---------------------------------------------------------------------------
# Token refresh produces usable new tokens
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_refresh_new_access_token_works_for_me(
    client: AsyncClient,
) -> None:
    await client.post(
        "/api/auth/register",
        json={
            "email": "refresh_flow@example.com",
            "username": "refresh_flow",
            "password": "correct-horse-battery",
        },
    )
    login = await client.post(
        "/api/auth/login",
        json={"identifier": "refresh_flow@example.com", "password": "correct-horse-battery"},
    )
    old_refresh = login.json()["refresh_token"]

    refresh_resp = await client.post(
        "/api/auth/refresh",
        json={"refresh_token": old_refresh},
    )
    assert refresh_resp.status_code == 200
    new_access = refresh_resp.json()["access_token"]

    me_resp = await client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {new_access}"},
    )
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == "refresh_flow@example.com"


# ---------------------------------------------------------------------------
# Disabled user cannot log in
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_disabled_user_cannot_login_after_deactivation(
    client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Deactivating a user in the DB must block subsequent logins."""
    await client.post(
        "/api/auth/register",
        json={
            "email": "deactivate@example.com",
            "username": "deactivate_me",
            "password": "correct-horse-battery",
        },
    )

    result = await db_session.execute(
        select(User).where(User.email == "deactivate@example.com")
    )
    user = result.scalar_one()
    user.is_active = False
    await db_session.commit()

    resp = await client.post(
        "/api/auth/login",
        json={"identifier": "deactivate@example.com", "password": "correct-horse-battery"},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Registration validates weak passwords
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_register_rejects_short_password(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/auth/register",
        json={
            "email": "weak@example.com",
            "username": "weakpw",
            "password": "short",
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_register_rejects_invalid_email_format(client: AsyncClient) -> None:
    resp = await client.post(
        "/api/auth/register",
        json={
            "email": "not-an-email",
            "username": "bademail",
            "password": "correct-horse-battery",
        },
    )
    assert resp.status_code == 422
