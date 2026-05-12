"""Application configuration via Pydantic Settings.

All secrets and environment-specific values must come through this module.
Never read os.environ directly from application code.
"""

import json
from functools import lru_cache
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import (
    BaseSettings,
    EnvSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)


class _OriginsEnvSource(EnvSettingsSource):
    """pydantic-settings v2 treats list[str] as a "complex" field and requires
    the env var to be JSON-parseable.  That breaks comma-separated and plain-URL
    values that our field validator is designed to handle.

    Bypassing complex-field handling for ALLOWED_ORIGINS lets the raw string
    reach the field validator, which already supports JSON, CSV, and plain URLs.
    """

    def prepare_field_value(
        self,
        field_name: str,
        field: Any,
        value: Any,
        value_is_complex: bool,
    ) -> Any:
        if field_name == "ALLOWED_ORIGINS" and isinstance(value, str):
            return value
        return super().prepare_field_value(field_name, field, value, value_is_complex)


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
    MAX_AGENT_ITERATIONS: int = 15

    # --------------------------------------------------------------------
    # Database Connection Pool
    # --------------------------------------------------------------------
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30

    # --------------------------------------------------------------------
    # ChromaDB Auth (optional)
    # --------------------------------------------------------------------
    CHROMA_AUTH_TOKEN: str = ""

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

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,  # noqa: ARG002 — replaced by _OriginsEnvSource
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            _OriginsEnvSource(settings_cls, case_sensitive=cls.model_config.get("case_sensitive")),
            dotenv_settings,
            file_secret_settings,
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance. Cached so env is parsed once."""
    return Settings()


settings = get_settings()
