"""Application configuration via Pydantic Settings.

All secrets and environment-specific values must come through this module.
Never read os.environ directly from application code.
"""
from __future__ import annotations

import json
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # --------------------------------------------------------------------
    # App
    # --------------------------------------------------------------------
    APP_NAME: str = "AgentForge"
    DEBUG: bool = False
    SECRET_KEY: str = Field(
        ...,
        min_length=32,
        description="HMAC/JWT signing key. Generate with `openssl rand -hex 32`.",
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # --------------------------------------------------------------------
    # LLM APIs
    # --------------------------------------------------------------------
    GOOGLE_API_KEY: str
    GROQ_API_KEY: str
    TAVILY_API_KEY: str
    LANGCHAIN_API_KEY: str
    E2B_API_KEY: str

    # --------------------------------------------------------------------
    # Redis (Upstash REST)
    # --------------------------------------------------------------------
    UPSTASH_REDIS_REST_URL: str
    UPSTASH_REDIS_REST_TOKEN: str

    # --------------------------------------------------------------------
    # Database
    # --------------------------------------------------------------------
    DATABASE_URL: str = "sqlite+aiosqlite:///./agentforge.db"

    # --------------------------------------------------------------------
    # ChromaDB
    # --------------------------------------------------------------------
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8001

    # --------------------------------------------------------------------
    # CORS
    # --------------------------------------------------------------------
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000"]

    # --------------------------------------------------------------------
    # Agent Config
    # --------------------------------------------------------------------
    MAX_CRITIC_ITERATIONS: int = 3
    CRITIC_SCORE_THRESHOLD: float = 0.75
    MAX_TOKENS_PER_AGENT: int = 4096

    # --------------------------------------------------------------------
    # LangSmith Tracing
    # --------------------------------------------------------------------
    LANGCHAIN_TRACING_V2: bool = True
    LANGCHAIN_PROJECT: str = "agentforge"

    # --------------------------------------------------------------------
    # Rate Limiting
    # --------------------------------------------------------------------
    RATE_LIMIT_TASK_CREATE: str = "10/hour"
    RATE_LIMIT_API_DEFAULT: str = "100/minute"

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def _parse_origins(cls, v: object) -> list[str]:
        """Accept either a JSON array string or a comma-separated string."""
        if isinstance(v, list):
            return [str(x).strip() for x in v]
        if isinstance(v, str):
            stripped = v.strip()
            if not stripped:
                return []
            if stripped.startswith("["):
                try:
                    parsed = json.loads(stripped)
                    if isinstance(parsed, list):
                        return [str(x).strip() for x in parsed]
                except json.JSONDecodeError:
                    pass
            return [item.strip() for item in stripped.split(",") if item.strip()]
        raise ValueError("ALLOWED_ORIGINS must be a list or string")

    @field_validator("CRITIC_SCORE_THRESHOLD")
    @classmethod
    def _threshold_in_range(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("CRITIC_SCORE_THRESHOLD must be between 0.0 and 1.0")
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance. Cached so env is parsed once."""
    return Settings()  # type: ignore[call-arg]


settings = get_settings()
