"""Tests for the web_search tool — Tavily client is mocked."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.tools import web_search as ws_module
from app.tools.web_search import _format_results, web_search


def test_format_results_empty() -> None:
    assert _format_results({}) == "No results found."


def test_format_results_with_answer_and_items() -> None:
    raw = {
        "answer": "AgentForge is great",
        "results": [
            {"title": "Hello", "url": "https://h.example", "content": "world"},
            {"title": "Two", "url": "https://t.example", "content": "x" * 1000},
        ],
    }
    formatted = _format_results(raw)
    assert "Summary: AgentForge is great" in formatted
    assert "[1] Hello" in formatted
    assert "[2] Two" in formatted
    # Long content is truncated.
    assert "…" in formatted or "â¦" in formatted


@pytest.mark.asyncio
async def test_web_search_invokes_client(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = MagicMock()
    fake_client.search.return_value = {
        "answer": "answer",
        "results": [{"title": "R", "url": "u", "content": "c"}],
    }
    monkeypatch.setattr(ws_module, "_client", fake_client)

    out = await web_search.ainvoke({"query": "vector db", "max_results": 3})
    assert "[1] R" in out
    fake_client.search.assert_called_once()
    # max_results bounded into [1, 10].
    args = fake_client.search.call_args
    assert args.kwargs["max_results"] == 3
    assert args.kwargs["query"] == "vector db"


@pytest.mark.asyncio
async def test_web_search_clamps_max_results(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = MagicMock()
    fake_client.search.return_value = {"results": []}
    monkeypatch.setattr(ws_module, "_client", fake_client)

    await web_search.ainvoke({"query": "q", "max_results": 999})
    assert fake_client.search.call_args.kwargs["max_results"] == 10


@pytest.mark.asyncio
async def test_web_search_returns_failure_message_on_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = MagicMock()
    fake_client.search.side_effect = RuntimeError("network down")
    monkeypatch.setattr(ws_module, "_client", fake_client)

    out = await web_search.ainvoke({"query": "x"})
    assert out.startswith("Web search failed")
