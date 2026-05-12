"""Unit tests for password hashing and JWT lifecycle."""
from __future__ import annotations

from datetime import timedelta

import pytest

from app.core.exceptions import InvalidTokenError
from app.core.security import (
    ACCESS_TOKEN_TYPE,
    REFRESH_TOKEN_TYPE,
    _create_token,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_hash_password_is_unique_each_call() -> None:
    a = hash_password("hunter22-strong")
    b = hash_password("hunter22-strong")
    assert a != b
    assert verify_password("hunter22-strong", a)
    assert verify_password("hunter22-strong", b)


def test_verify_rejects_wrong_password() -> None:
    h = hash_password("real-password")
    assert verify_password("real-password", h) is True
    assert verify_password("WRONG", h) is False


def test_verify_password_invalid_hash_returns_false() -> None:
    # Garbage hash should not raise.
    assert verify_password("anything", "not-a-bcrypt-hash") is False


def test_access_token_roundtrip() -> None:
    token = create_access_token("user-123")
    payload = decode_token(token, expected_type=ACCESS_TOKEN_TYPE)
    assert payload["sub"] == "user-123"
    assert payload["type"] == ACCESS_TOKEN_TYPE


def test_refresh_token_roundtrip() -> None:
    token = create_refresh_token("user-abc")
    payload = decode_token(token, expected_type=REFRESH_TOKEN_TYPE)
    assert payload["sub"] == "user-abc"
    assert payload["type"] == REFRESH_TOKEN_TYPE


def test_decode_rejects_wrong_token_type() -> None:
    access = create_access_token("u1")
    with pytest.raises(InvalidTokenError):
        decode_token(access, expected_type=REFRESH_TOKEN_TYPE)


def test_decode_rejects_garbage_token() -> None:
    with pytest.raises(InvalidTokenError):
        decode_token("not-a-jwt")


def test_decode_rejects_expired_token() -> None:
    expired = _create_token(
        subject="u1",
        token_type=ACCESS_TOKEN_TYPE,
        expires_delta=timedelta(seconds=-1),
    )
    with pytest.raises(InvalidTokenError):
        decode_token(expired)
