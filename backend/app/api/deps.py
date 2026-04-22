"""Reusable FastAPI dependencies (DB + auth)."""
from __future__ import annotations

from collections.abc import AsyncGenerator

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError, InvalidTokenError
from app.core.security import decode_token
from app.db.models import User
from app.db.session import get_session

# tokenUrl is informational for OpenAPI docs; actual login is at /api/auth/login.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_session():
        yield session


async def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Resolve the authenticated user from the bearer token."""
    if not token:
        raise AuthenticationError("Missing authorization header")

    payload = decode_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise InvalidTokenError("Token missing subject")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise AuthenticationError("User not found")
    if not user.is_active:
        raise AuthenticationError("User is disabled")
    return user


async def get_current_active_user(
    user: User = Depends(get_current_user),
) -> User:
    return user
