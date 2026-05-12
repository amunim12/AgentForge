"""Executor tests â the underlying LangChain agent is fully mocked."""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents import executor as executor_module
from app.core.exceptions import AgentExecutionError


@pytest.fixture
def _fake_agent_executor(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Stub out create_tool_calling_agent + AgentExecutor so no LLM is touched."""
    monkeypatch.setattr(
        executor_module, "create_tool_calling_agent", lambda *_a, **_kw: MagicMock()
    )
    fake = MagicMock()
    monkeypatch.setattr(executor_module, "AgentExecutor", lambda **_kw: fake)
    monkeypatch.setattr(executor_module, "_build_llm", lambda: MagicMock())
    monkeypatch.setattr(executor_module, "reset_notebook", lambda: None)
    return fake


@pytest.mark.asyncio
async def test_executor_returns_formatted_output(
    _fake_agent_executor: MagicMock,
) -> None:
    _fake_agent_executor.ainvoke = AsyncMock(
        return_value={"output": "## Final answer\nDone.", "intermediate_steps": []}
    )

    result = await executor_module.run_executor(
        plan={"steps": [{"step_id": 1}, {"step_id": 2}]},
        task_id="task-1",
        task_description="task",
    )
    assert result["formatted_output"].startswith("## Final answer")
    assert result["steps_completed"] == 2
    assert result["tool_calls"] == []
    assert isinstance(result["duration_ms"], int)


@pytest.mark.asyncio
async def test_executor_emits_tool_call_events(
    _fake_agent_executor: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    action = MagicMock()
    action.tool = "web_search"
    action.tool_input = {"query": "vector dbs"}
    _fake_agent_executor.ainvoke = AsyncMock(
        return_value={
            "output": "answer",
            "intermediate_steps": [(action, "search results here")],
        }
    )

    published: list[dict[str, Any]] = []

    async def _capture(_task_id: str, payload: dict[str, Any]) -> None:
        published.append(payload)

    monkeypatch.setattr(executor_module, "publish_task_update", _capture)

    result = await executor_module.run_executor(
        plan={"steps": [{"step_id": 1}]},
        task_id="task-2",
        task_description="task",
    )
    assert len(result["tool_calls"]) == 1
    assert result["tool_calls"][0]["tool"] == "web_search"
    tool_events = [e for e in published if e["type"] == "agent_tool_call"]
    assert tool_events and tool_events[0]["tool"] == "web_search"


@pytest.mark.asyncio
async def test_executor_truncates_long_observations(
    _fake_agent_executor: MagicMock,
) -> None:
    action = MagicMock()
    action.tool = "code_executor"
    action.tool_input = "print('x')"
    long_observation = "y" * 2000
    _fake_agent_executor.ainvoke = AsyncMock(
        return_value={
            "output": "done",
            "intermediate_steps": [(action, long_observation)],
        }
    )

    result = await executor_module.run_executor(
        plan={"steps": []},
        task_id="task-3",
        task_description="task",
    )
    preview = result["tool_calls"][0]["output_preview"]
    assert len(preview) <= 510


@pytest.mark.asyncio
async def test_executor_wraps_invocation_errors(
    _fake_agent_executor: MagicMock,
) -> None:
    _fake_agent_executor.ainvoke = AsyncMock(side_effect=RuntimeError("groq exploded"))
    with pytest.raises(AgentExecutionError):
        await executor_module.run_executor(
            plan={"steps": []},
            task_id="task-4",
            task_description="task",
        )


@pytest.mark.asyncio
async def test_executor_wraps_agent_build_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(executor_module, "_build_llm", lambda: MagicMock())
    monkeypatch.setattr(executor_module, "reset_notebook", lambda: None)

    def _boom(*_a: Any, **_kw: Any) -> Any:
        raise RuntimeError("missing tool spec")

    monkeypatch.setattr(executor_module, "create_tool_calling_agent", _boom)

    with pytest.raises(AgentExecutionError):
        await executor_module.run_executor(
            plan={"steps": []},
            task_id="task-5",
            task_description="task",
        )
