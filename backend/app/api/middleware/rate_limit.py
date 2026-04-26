"""Shared SlowAPI limiter instance.

Routes import `limiter` and decorate endpoints with
`@limiter.limit("N/unit")`. The limiter is installed on the FastAPI app
in `main.py`.
"""
from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[settings.RATE_LIMIT_API_DEFAULT],
    headers_enabled=True,
)
