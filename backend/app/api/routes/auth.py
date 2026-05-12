"""Authentication endpoints: register, login, refresh, me."""

import structlog
from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col

from app.api.deps import get_current_user, get_db
from app.api.middleware.rate_limit import limiter
from app.core.exceptions import (
    AuthenticationError,
    DuplicateResourceError,
    InvalidTokenError,
)
from app.core.security import (
    REFRESH_TOKEN_TYPE,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db.models import User
from app.schemas.auth import (
    RefreshRequest,
    Token,
    UserCreate,
    UserLogin,
    UserRead,
)

logger = structlog.get_logger()

router = APIRouter()


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/hour")
async def register(
    request: Request,
    response: Response,
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> User:
    existing = await db.execute(
        select(User).where(
            or_(col(User.email) == payload.email, col(User.username) == payload.username)
        )
    )
    if existing.scalar_one_or_none():
        raise DuplicateResourceError("Email or username already registered")

    user = User(
        email=payload.email,
        username=payload.username,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/login", response_model=Token)
@limiter.limit("5/minute")
async def login(
    request: Request,
    response: Response,
    payload: UserLogin,
    db: AsyncSession = Depends(get_db),
) -> Token:
    result = await db.execute(
        select(User).where(
            or_(col(User.email) == payload.identifier, col(User.username) == payload.identifier)
        )
    )
    user = result.scalar_one_or_none()
    if not user or not verify_password(payload.password, user.hashed_password):
        logger.warning(
            "Failed login attempt",
            identifier=payload.identifier,
            ip=request.client.host if request.client else "unknown",
        )
        raise AuthenticationError("Invalid credentials")
    if not user.is_active:
        logger.warning(
            "Login attempt for disabled account",
            user_id=str(user.id),
            ip=request.client.host if request.client else "unknown",
        )
        raise AuthenticationError("User is disabled")

    return Token(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/refresh", response_model=Token)
@limiter.limit("20/minute")
async def refresh_token(
    request: Request,
    response: Response,
    payload: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> Token:
    claims = decode_token(payload.refresh_token, expected_type=REFRESH_TOKEN_TYPE)
    user_id = claims["sub"]

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise InvalidTokenError("User not found or disabled")

    return Token(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.get("/me", response_model=UserRead)
async def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user
