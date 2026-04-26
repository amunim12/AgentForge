"""Orchestrator tests â the three agents are stubbed; we verify routing + DB."""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agents import orchestrator as orch
from app.core.exceptions import AgentExecutionError
from app.db.models import Task, TaskStatus, User


@pytest_asyncio.fixture
async def _patch_orch_db(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Route the orchestrator's `get_db_session` at the test in-memory DB."""

    @asynccontextmanager
    async def _gds():
        async with session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    monkeypatch.setattr(orch, "get_db_session", _gds)


@pytest_asyncio.fixture
async def _persisted_task(
    test_user: User, db_session: AsyncSession, _patch_orch_db: None
) -> Task:
    task = Task(
        title="orchestrator test",
        description="exercise the agent pipeline end to end",
        user_id=test_user.id,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)
    return task


def _fake_plan() -> dict[str, Any]:
    return {
        "task_summary": "do a thing",
        "complexity": "low",
        "estimated_steps": 1,
        "steps": [],
        "success_criteria": "done",
    }


def _fake_execution(text: str = "## Final\nbody") -> dict[str, Any]:
    return {
        "formatted_output": text,
        "steps_completed": 1,
        "tool_calls": [],
        "duration_ms": 12,
    }


def _fake_verdict(score: float, verdict: str = "accept") -> dict[str, Any]:
    return {"score": score, "verdict": verdict, "rubric": {}, "feedback": "ok"}


def test_should_rerun_finishes_when_score_meets_threshold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(orch.settings, "CRITIC_SCORE_THRESHOLD", 0.8)
    monkeypatch.setattr(orch.settings, "MAX_CRITIC_ITERATIONS", 3)
    assert orch.should_rerun({"critic_score": 0.9, "iteration": 1}) == "finish"


def test_should_rerun_finishes_when_iteration_cap_hit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(orch.settings, "CRITIC_SCORE_THRESHOLD", 0.8)
    monkeypatch.setattr(orch.settings, "MAX_CRITIC_ITERATIONS", 2)
    assert orch.should_rerun({"critic_score": 0.5, "iteration": 2}) == "finish"


def test_should_rerun_loops_when_low_score_and_under_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(orch.settings, "CRITIC_SCORE_THRESHOLD", 0.8)
    monkeypatch.setattr(orch.settings, "MAX_CRITIC_ITERATIONS", 3)
    assert orch.should_rerun({"critic_score": 0.4, "iteration": 1}) == "rerun_executor"


@pytest.mark.asyncio
async def test_pipeline_happy_path_finalizes_task(
    monkeypatch: pytest.MonkeyPatch,
    _persisted_task: Task,
    db_session: AsyncSession,
) -> None:
    monkeypatch.setattr(orch, "run_planner", AsyncMock(return_value=_fake_plan()))
    monkeypatch.setattr(orch, "run_executor", AsyncMock(return_value=_fake_execution()))
    monkeypatch.setattr(
        orch, "run_critic", AsyncMock(return_value=_fake_verdict(0.95))
    )

    published: list[dict[str, Any]] = []

    async def _capture(_task_id: str, payload: dict[str, Any]) -> None:
        published.append(payload)

    monkeypatch.setattr(orch, "publish_task_update", _capture)
    monkeypatch.setattr(orch, "store_task_memory", AsyncMock())

    await orch.run_agent_pipeline(
        _persisted_task.id, _persisted_task.description
    )

    await db_session.refresh(_persisted_task)
    assert _persisted_task.status == TaskStatus.COMPLETED
    assert _persisted_task.final_result.startswith("## Final")
    assert _persisted_task.critic_score == pytest.approx(0.95)

    types_seen = {p["type"] for p in published}
    assert "task_complete" in types_seen
    assert "agent_done" in types_seen


@pytest.mark.asyncio
async def test_pipeline_marks_failed_on_agent_error(
    monkeypatch: pytest.MonkeyPatch,
    _persisted_task: Task,
    db_session: AsyncSession,
) -> None:
    monkeypatch.setattr(
        orch,
        "run_planner",
        AsyncMock(side_effect=AgentExecutionError("planner died")),
    )
    monkeypatch.setattr(orch, "run_executor", AsyncMock())
    monkeypatch.setattr(orch, "run_critic", AsyncMock())

    published: list[dict[str, Any]] = []

    async def _capture(_task_id: str, payload: dict[str, Any]) -> None:
        published.append(payload)

    monkeypatch.setattr(orch, "publish_task_update", _capture)

    await orch.run_agent_pipeline(
        _persisted_task.id, _persisted_task.description
    )

    await db_session.refresh(_persisted_task)
    assert _persisted_task.status == TaskStatus.FAILED
    assert _persisted_task.error_message
    assert any(p["type"] == "task_failed" for p in published)


@pytest.mark.asyncio
async def test_pipeline_marks_failed_on_unexpected_exception(
    monkeypatch: pytest.MonkeyPatch,
    _persisted_task: Task,
    db_session: AsyncSession,
) -> None:
    monkeypatch.setattr(
        orch, "run_planner", AsyncMock(side_effect=RuntimeError("boom"))
    )
    monkeypatch.setattr(orch, "run_executor", AsyncMock())
    monkeypatch.setattr(orch, "run_critic", AsyncMock())
    monkeypatch.setattr(orch, "publish_task_update", AsyncMock())

    await orch.run_agent_pipeline(
        _persisted_task.id, _persisted_task.description
    )

    await db_session.refresh(_persisted_task)
    assert _persisted_task.status == TaskStatus.FAILED


@pytest.mark.asyncio
async def test_pipeline_skips_when_task_missing(
    monkeypatch: pytest.MonkeyPatch,
    _patch_orch_db: None,
) -> None:
    planner = AsyncMock()
    monkeypatch.setattr(orch, "run_planner", planner)
    monkeypatch.setattr(orch, "publish_task_update", AsyncMock())

    await orch.run_agent_pipeline("does-not-exist", "irrelevant")
    planner.assert_not_called()


@pytest.mark.asyncio
async def test_update_task_status_persists(
    _persisted_task: Task, db_session: AsyncSession, _patch_orch_db: None
) -> None:
    await orch._update_task_status(_persisted_task.id, TaskStatus.PLANNING)
    await db_session.refresh(_persisted_task)
    assert _persisted_task.status == TaskStatus.PLANNING


@pytest.mark.asyncio
async def test_persist_task_field_writes_arbitrary_columns(
    _persisted_task: Task, db_session: AsyncSession, _patch_orch_db: None
) -> None:
    await orch._persist_task_field(
        _persisted_task.id, planner_output='{"a": 1}', critic_score=0.42
    )
    await db_session.refresh(_persisted_task)
    assert _persisted_task.planner_output == '{"a": 1}'
    assert _persisted_task.critic_score == pytest.approx(0.42)
