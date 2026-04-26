"""Unit tests for the Settings parser."""
from __future__ import annotations

import pytest

from app.core.config import Settings


_BASE_ENV = {
    "SECRET_KEY": "x" * 48,
    "GOOGLE_API_KEY": "g",
    "GROQ_API_KEY": "g",
    "TAVILY_API_KEY": "t",
    "LANGCHAIN_API_KEY": "l",
    "E2B_API_KEY": "e",
    "UPSTASH_REDIS_REST_URL": "https://x.upstash.io",
    "UPSTASH_REDIS_REST_TOKEN": "tok",
}


def _build(env: dict[str, str], monkeypatch: pytest.MonkeyPatch) -> Settings:
    for k in list(_BASE_ENV.keys()) + list(env.keys()) + [
        "ALLOWED_ORIGINS",
        "CRITIC_SCORE_THRESHOLD",
    ]:
        monkeypatch.delenv(k, raising=False)
    for k, v in {**_BASE_ENV, **env}.items():
        monkeypatch.setenv(k, v)
    return Settings(_env_file=None)  # type: ignore[call-arg]


def test_allowed_origins_csv(monkeypatch: pytest.MonkeyPatch) -> None:
    s = _build({"ALLOWED_ORIGINS": "http://a.com, http://b.com"}, monkeypatch)
    assert s.ALLOWED_ORIGINS == ["http://a.com", "http://b.com"]


def test_allowed_origins_json_array(monkeypatch: pytest.MonkeyPatch) -> None:
    s = _build({"ALLOWED_ORIGINS": '["http://a.com","http://b.com"]'}, monkeypatch)
    assert s.ALLOWED_ORIGINS == ["http://a.com", "http://b.com"]


def test_allowed_origins_blank(monkeypatch: pytest.MonkeyPatch) -> None:
    s = _build({"ALLOWED_ORIGINS": ""}, monkeypatch)
    assert s.ALLOWED_ORIGINS == []


def test_threshold_out_of_range_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValueError):
        _build({"CRITIC_SCORE_THRESHOLD": "1.5"}, monkeypatch)


def test_secret_key_too_short_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValueError):
        _build({"SECRET_KEY": "short"}, monkeypatch)
