"""Custom exception types and a FastAPI handler registrar.

We never leak internal/LLM error messages to clients â the registrar maps
each exception class to a sanitized HTTP response.
"""
from __future__ import annotations

import structlog
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

logger = structlog.get_logger()


class AgentForgeError(Exception):
    """Base for all application-defined exceptions."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    public_message: str = "An internal error occurred."


class InvalidTokenError(AgentForgeError):
    status_code = status.HTTP_401_UNAUTHORIZED
    public_message = "Could not validate credentials."


class AuthenticationError(AgentForgeError):
    status_code = status.HTTP_401_UNAUTHORIZED
    public_message = "Authentication failed."


class PermissionDeniedError(AgentForgeError):
    status_code = status.HTTP_403_FORBIDDEN
    public_message = "You do not have permission to perform this action."


class NotFoundError(AgentForgeError):
    status_code = status.HTTP_404_NOT_FOUND
    public_message = "Resource not found."


class DuplicateResourceError(AgentForgeError):
    status_code = status.HTTP_409_CONFLICT
    public_message = "Resource already exists."


class AgentExecutionError(AgentForgeError):
    status_code = status.HTTP_502_BAD_GATEWAY
    public_message = "Agent pipeline failed. Please retry."


def _build_handler(_status: int):
    async def _handler(_request: Request, exc: AgentForgeError) -> JSONResponse:
        logger.warning(
            "AgentForge error",
            exc_type=type(exc).__name__,
            detail=str(exc),
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.public_message},
        )

    return _handler


async def _unhandled_handler(_request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception", exc_type=type(exc).__name__)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error."},
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Wire up application exception handlers on app startup."""
    app.add_exception_handler(AgentForgeError, _build_handler(0))  # type: ignore[arg-type]
    app.add_exception_handler(Exception, _unhandled_handler)
