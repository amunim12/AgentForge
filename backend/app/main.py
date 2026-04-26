"""FastAPI application entrypoint for AgentForge."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.middleware.logging import LoggingMiddleware, configure_logging
from app.api.middleware.rate_limit import limiter
from app.api.middleware.security import add_security_headers
from app.api.routes import auth, health, tasks, websocket
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.db.session import create_db_and_tables, dispose_engine
from app.memory.chroma import init_chroma
from app.queue.redis_client import close_redis

# Configure logging before anything else emits a log line.
configure_logging(debug=settings.DEBUG)
logger = structlog.get_logger()

# Wire LangSmith env vars from our Settings so langchain picks them up.
os.environ.setdefault("LANGCHAIN_API_KEY", settings.LANGCHAIN_API_KEY)
os.environ.setdefault(
    "LANGCHAIN_TRACING_V2", "true" if settings.LANGCHAIN_TRACING_V2 else "false"
)
os.environ.setdefault("LANGCHAIN_PROJECT", settings.LANGCHAIN_PROJECT)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting AgentForge API", app_name=settings.APP_NAME)
    await create_db_and_tables()
    await init_chroma()
    logger.info("All services initialized")
    try:
        yield
    finally:
        logger.info("Shutting down AgentForge API")
        await close_redis()
        await dispose_engine()


app = FastAPI(
    title="AgentForge API",
    description="Multi-Agent AI Orchestration Platform",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS â allow only configured frontend origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)

# Security + logging middleware (order: security headers outermost, logging innermost).
app.middleware("http")(add_security_headers)
app.add_middleware(LoggingMiddleware)

# Exception handlers (custom app errors + catch-all).
register_exception_handlers(app)

# Routers
app.include_router(health.router, tags=["health"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])
app.include_router(websocket.router, prefix="/api/ws", tags=["websocket"])


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    return {"service": "agentforge-api", "docs": "/api/docs"}
