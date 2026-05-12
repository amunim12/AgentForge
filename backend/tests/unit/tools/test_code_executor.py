"""Tests for the code_executor tool — E2B sandbox is mocked."""
from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock

import pytest

from app.tools.code_executor import _truncate, code_executor


def test_truncate_short_passthrough() -> None:
    assert _truncate("abc") == "abc"


def test_truncate_long_appends_marker() -> None:
    out = _truncate("a" * 5000)
    assert out.startswith("a" * 4000)
    assert "truncated" in out


def _install_fake_e2b(
    monkeypatch: pytest.MonkeyPatch,
    execution: object,
) -> MagicMock:
    """Inject a fake e2b_code_interpreter module that returns `execution`."""

    def _sandbox_factory(*_a: object, **_kw: object) -> MagicMock:
        sb = MagicMock()
        sb.__enter__.return_value = sb
        sb.__exit__.return_value = False
        sb.run_code.return_value = execution
        return sb

    fake_module = types.ModuleType("e2b_code_interpreter")
    fake_module.Sandbox = _sandbox_factory  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "e2b_code_interpreter", fake_module)
    return _sandbox_factory  # type: ignore[return-value]


@pytest.mark.asyncio
async def test_code_executor_returns_stdout(monkeypatch: pytest.MonkeyPatch) -> None:
    execution = MagicMock()
    execution.logs = MagicMock(stdout=["hello"], stderr=[])
    execution.results = []
    execution.error = None
    _install_fake_e2b(monkeypatch, execution)

    out = await code_executor.ainvoke({"code": "print('hello')"})
    assert "stdout" in out
    assert "hello" in out


@pytest.mark.asyncio
async def test_code_executor_reports_error_traceback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    execution = MagicMock()
    execution.logs = MagicMock(stdout=[], stderr=[])
    execution.results = []
    execution.error = MagicMock(traceback="ZeroDivisionError: division by zero")
    _install_fake_e2b(monkeypatch, execution)

    out = await code_executor.ainvoke({"code": "1/0"})
    assert "error" in out
    assert "ZeroDivisionError" in out


@pytest.mark.asyncio
async def test_code_executor_no_output(monkeypatch: pytest.MonkeyPatch) -> None:
    execution = MagicMock()
    execution.logs = MagicMock(stdout=[], stderr=[])
    execution.results = []
    execution.error = None
    _install_fake_e2b(monkeypatch, execution)

    out = await code_executor.ainvoke({"code": "x = 1"})
    assert out == "(no output)"


@pytest.mark.asyncio
async def test_code_executor_handles_missing_e2b(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "e2b_code_interpreter", None)
    out = await code_executor.ainvoke({"code": "print(1)"})
    assert out.startswith("Code executor unavailable")
