"""Tests for the in-memory notebook tool."""
from __future__ import annotations

import pytest

from app.tools.file_tool import (
    _MAX_FILES,
    file_tool,
    reset_notebook,
    snapshot_notebook,
)


@pytest.fixture(autouse=True)
def _clean_notebook() -> None:
    reset_notebook()
    yield
    reset_notebook()


def _invoke(**kwargs: object) -> str:
    """Invoke the @tool-decorated function; LangChain wraps it as a Runnable."""
    return file_tool.invoke(kwargs)  # type: ignore[attr-defined]


def test_write_then_read() -> None:
    out = _invoke(action="write", name="notes.md", content="hello")
    assert "Wrote" in out
    assert _invoke(action="read", name="notes.md") == "hello"


def test_append_concatenates() -> None:
    _invoke(action="write", name="log.txt", content="a")
    _invoke(action="append", name="log.txt", content="b")
    assert _invoke(action="read", name="log.txt") == "ab"


def test_read_missing_returns_error() -> None:
    out = _invoke(action="read", name="nope")
    assert out.startswith("Error")


def test_list_empty_then_populated() -> None:
    assert "empty" in _invoke(action="list").lower()
    _invoke(action="write", name="a", content="x")
    listing = _invoke(action="list")
    assert "a" in listing


def test_delete_entry() -> None:
    _invoke(action="write", name="rm-me", content="...")
    out = _invoke(action="delete", name="rm-me")
    assert "Deleted" in out
    assert "rm-me" not in snapshot_notebook()


def test_write_requires_content() -> None:
    out = _invoke(action="write", name="x", content="")
    assert out.startswith("Error")


def test_capacity_limit() -> None:
    for i in range(_MAX_FILES):
        _invoke(action="write", name=f"f{i}", content="x")
    overflow = _invoke(action="write", name="extra", content="x")
    assert "capacity" in overflow.lower()


def test_reset_clears_notebook() -> None:
    _invoke(action="write", name="keep", content="x")
    reset_notebook()
    assert snapshot_notebook() == {}
