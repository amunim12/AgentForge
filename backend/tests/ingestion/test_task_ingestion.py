"""Ingestion tests: task data flows correctly through the full pipeline.

These tests verify that every DB state transition the pipeline performs is
persisted correctly — from task creation through all agent stages to final
storage of results and scores.
"""
from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agents import orchestrator as orch
from app.core.exceptions import AgentExecutionError
from app.db.models import Task, TaskStatus, User


# ---------------------------------------------------------------------------
# Helpers shared across tests
# ---------------------------------------------------------------------------
def _make_plan() -> dict[str, Any]:
    return {
        "task_summary": "ingestion test plan",
        "complexity": "low",
        "estimated_steps": 1,
        "steps": [
            {
                "step_id": 1,
                "title": "Do it",
                "description": "step description",
                "tool": "reasoning",
                "tool_input_hint": "think",
                "expected_output": "done",
                "dependencies": [],
                "critical": True,
            }
        ],
        "success_criteria": "completed",
    }


def _make_execution(text: str = "## Result\nFinal answer.") -> dict[str, Any]:
    return {
        "formatted_output": text,
        "steps_completed": 1,
        "tool_calls": [],
        "duration_ms": 50,
    }


def _make_verdict(score: float = 0.9, verdict: str = "accept") -> dict[str, Any]:
    return {
        "score": score,
        "verdict": verdict,
        "rubric": {"accuracy": {"score": 9, "comment": "good"}},
        "strengths": ["thorough"],
        "improvements_needed": [],
        "specific_instructions_for_next_iteration": "n/a",
    }


@pytest_asyncio.fixture
async def _db_wired_orch(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Route orchestrator's get_db_session to the test in-memory DB."""

    @asynccontextmanager
    async def _gds():  # type: ignore[return]
        async with session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    monkeypatch.setattr(orch, "get_db_session", _gds)


@pytest_asyncio.fixture
async def task_in_db(
    test_user: User,
    db_session: AsyncSession,
    _db_wired_orch: None,
) -> Task:
    task = Task(
        title="ingestion test task",
        description="verifying all pipeline stages persist to the database",
        user_id=test_user.id,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)
    return task


# ---------------------------------------------------------------------------
# Test 1: Task row exists with correct defaults immediately after creation
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_task_created_with_pending_status(
    task_in_db: Task,
    db_session: AsyncSession,
) -> None:
    await db_session.refresh(task_in_db)
    assert task_in_db.status == TaskStatus.PENDING
    assert task_in_db.iteration_count == 0
    assert task_in_db.critic_score is None
    assert task_in_db.final_result is None
    assert task_in_db.completed_at is None
    assert task_in_db.planner_output is None
    assert task_in_db.executor_output is None
    assert task_in_db.critic_output is None


# ---------------------------------------------------------------------------
# Test 2: Status transitions are persisted at each agent stage
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_status_transitions_through_pipeline_stages(
    monkeypatch: pytest.MonkeyPatch,
    task_in_db: Task,
) -> None:
    """Each agent node must update the task status in the DB."""
    statuses_recorded: list[str] = []

    original_update = orch._update_task_status

    async def _recording_update(task_id: str, status: TaskStatus) -> None:
        statuses_recorded.append(status.value)
        await original_update(task_id, status)

    monkeypatch.setattr(orch, "_update_task_status", _recording_update)
    monkeypatch.setattr(orch, "run_planner", AsyncMock(return_value=_make_plan()))
    monkeypatch.setattr(orch, "run_executor", AsyncMock(return_value=_make_execution()))
    monkeypatch.setattr(orch, "run_critic", AsyncMock(return_value=_make_verdict(0.95)))
    monkeypatch.setattr(orch, "publish_task_update", AsyncMock())
    monkeypatch.setattr(orch, "store_task_memory", AsyncMock())

    await orch.run_agent_pipeline(task_in_db.id, task_in_db.description)

    assert "planning" in statuses_recorded
    assert "executing" in statuses_recorded
    assert "critiquing" in statuses_recorded


# ---------------------------------------------------------------------------
# Test 3: Agent outputs are persisted to DB columns
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_planner_output_persisted_to_db(
    monkeypatch: pytest.MonkeyPatch,
    task_in_db: Task,
    db_session: AsyncSession,
) -> None:
    plan = _make_plan()
    monkeypatch.setattr(orch, "run_planner", AsyncMock(return_value=plan))
    monkeypatch.setattr(orch, "run_executor", AsyncMock(return_value=_make_execution()))
    monkeypatch.setattr(orch, "run_critic", AsyncMock(return_value=_make_verdict(0.92)))
    monkeypatch.setattr(orch, "publish_task_update", AsyncMock())
    monkeypatch.setattr(orch, "store_task_memory", AsyncMock())

    await orch.run_agent_pipeline(task_in_db.id, task_in_db.description)
    await db_session.refresh(task_in_db)

    assert task_in_db.planner_output is not None
    parsed = json.loads(task_in_db.planner_output)
    assert parsed["task_summary"] == plan["task_summary"]


@pytest.mark.asyncio
async def test_executor_output_persisted_to_db(
    monkeypatch: pytest.MonkeyPatch,
    task_in_db: Task,
    db_session: AsyncSession,
) -> None:
    execution = _make_execution("## My Result\nDetailed answer.")
    monkeypatch.setattr(orch, "run_planner", AsyncMock(return_value=_make_plan()))
    monkeypatch.setattr(orch, "run_executor", AsyncMock(return_value=execution))
    monkeypatch.setattr(orch, "run_critic", AsyncMock(return_value=_make_verdict(0.88)))
    monkeypatch.setattr(orch, "publish_task_update", AsyncMock())
    monkeypatch.setattr(orch, "store_task_memory", AsyncMock())

    await orch.run_agent_pipeline(task_in_db.id, task_in_db.description)
    await db_session.refresh(task_in_db)

    assert task_in_db.executor_output is not None
    parsed = json.loads(task_in_db.executor_output)
    assert parsed["formatted_output"] == "## My Result\nDetailed answer."


@pytest.mark.asyncio
async def test_critic_output_and_score_persisted_to_db(
    monkeypatch: pytest.MonkeyPatch,
    task_in_db: Task,
    db_session: AsyncSession,
) -> None:
    verdict = _make_verdict(score=0.82)
    monkeypatch.setattr(orch, "run_planner", AsyncMock(return_value=_make_plan()))
    monkeypatch.setattr(orch, "run_executor", AsyncMock(return_value=_make_execution()))
    monkeypatch.setattr(orch, "run_critic", AsyncMock(return_value=verdict))
    monkeypatch.setattr(orch, "publish_task_update", AsyncMock())
    monkeypatch.setattr(orch, "store_task_memory", AsyncMock())

    await orch.run_agent_pipeline(task_in_db.id, task_in_db.description)
    await db_session.refresh(task_in_db)

    assert task_in_db.critic_output is not None
    assert task_in_db.critic_score == pytest.approx(0.82)
    assert task_in_db.iteration_count == 1


# ---------------------------------------------------------------------------
# Test 4: Completed task has all final fields set
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_completed_task_has_all_final_fields(
    monkeypatch: pytest.MonkeyPatch,
    task_in_db: Task,
    db_session: AsyncSession,
) -> None:
    result_text = "## Final Answer\nHere is the comprehensive comparison."
    monkeypatch.setattr(orch, "run_planner", AsyncMock(return_value=_make_plan()))
    monkeypatch.setattr(orch, "run_executor", AsyncMock(return_value=_make_execution(result_text)))
    monkeypatch.setattr(orch, "run_critic", AsyncMock(return_value=_make_verdict(0.91)))
    monkeypatch.setattr(orch, "publish_task_update", AsyncMock())
    monkeypatch.setattr(orch, "store_task_memory", AsyncMock())

    await orch.run_agent_pipeline(task_in_db.id, task_in_db.description)
    await db_session.refresh(task_in_db)

    assert task_in_db.status == TaskStatus.COMPLETED
    assert task_in_db.final_result == result_text
    assert task_in_db.critic_score == pytest.approx(0.91)
    assert task_in_db.completed_at is not None  # SQLite strips tzinfo; just verify it's set


# ---------------------------------------------------------------------------
# Test 5: Failed task has error message set, status=FAILED
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_failed_task_error_message_persisted(
    monkeypatch: pytest.MonkeyPatch,
    task_in_db: Task,
    db_session: AsyncSession,
) -> None:
    monkeypatch.setattr(
        orch,
        "run_planner",
        AsyncMock(side_effect=AgentExecutionError("Planner returned malformed JSON")),
    )
    monkeypatch.setattr(orch, "run_executor", AsyncMock())
    monkeypatch.setattr(orch, "run_critic", AsyncMock())
    monkeypatch.setattr(orch, "publish_task_update", AsyncMock())

    await orch.run_agent_pipeline(task_in_db.id, task_in_db.description)
    await db_session.refresh(task_in_db)

    assert task_in_db.status == TaskStatus.FAILED
    assert task_in_db.error_message is not None
    assert len(task_in_db.error_message) > 0
    assert task_in_db.final_result is None
    assert task_in_db.completed_at is None


# ---------------------------------------------------------------------------
# Test 6: Retry loop — executor runs again after low critic score
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_pipeline_retries_executor_on_low_critic_score(
    monkeypatch: pytest.MonkeyPatch,
    task_in_db: Task,
    db_session: AsyncSession,
) -> None:
    """When the Critic scores below threshold, the Executor runs a second time."""
    monkeypatch.setattr(orch.settings, "CRITIC_SCORE_THRESHOLD", 0.80)
    monkeypatch.setattr(orch.settings, "MAX_CRITIC_ITERATIONS", 3)

    executor_call_count = 0

    async def _counting_executor(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        nonlocal executor_call_count
        executor_call_count += 1
        return _make_execution(f"## Pass {executor_call_count}\nAnswer.")

    # First critic call returns low score; second returns acceptable score.
    critic_calls: list[int] = []

    async def _staged_critic(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        call_num = len(critic_calls) + 1
        critic_calls.append(call_num)
        score = 0.60 if call_num == 1 else 0.88
        return _make_verdict(score)

    monkeypatch.setattr(orch, "run_planner", AsyncMock(return_value=_make_plan()))
    monkeypatch.setattr(orch, "run_executor", _counting_executor)
    monkeypatch.setattr(orch, "run_critic", _staged_critic)
    monkeypatch.setattr(orch, "publish_task_update", AsyncMock())
    monkeypatch.setattr(orch, "store_task_memory", AsyncMock())

    await orch.run_agent_pipeline(task_in_db.id, task_in_db.description)
    await db_session.refresh(task_in_db)

    assert executor_call_count == 2
    assert len(critic_calls) == 2
    assert task_in_db.status == TaskStatus.COMPLETED
    assert task_in_db.iteration_count == 2
    assert task_in_db.critic_score == pytest.approx(0.88)


# ---------------------------------------------------------------------------
# Test 7: Iteration cap — pipeline accepts best-effort when cap is reached
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_pipeline_accepts_best_effort_at_iteration_cap(
    monkeypatch: pytest.MonkeyPatch,
    task_in_db: Task,
    db_session: AsyncSession,
) -> None:
    monkeypatch.setattr(orch.settings, "CRITIC_SCORE_THRESHOLD", 0.90)
    monkeypatch.setattr(orch.settings, "MAX_CRITIC_ITERATIONS", 2)

    # Critic always scores below threshold.
    monkeypatch.setattr(orch, "run_planner", AsyncMock(return_value=_make_plan()))
    monkeypatch.setattr(orch, "run_executor", AsyncMock(return_value=_make_execution()))
    monkeypatch.setattr(orch, "run_critic", AsyncMock(return_value=_make_verdict(0.55)))
    monkeypatch.setattr(orch, "publish_task_update", AsyncMock())
    monkeypatch.setattr(orch, "store_task_memory", AsyncMock())

    await orch.run_agent_pipeline(task_in_db.id, task_in_db.description)
    await db_session.refresh(task_in_db)

    # Should be COMPLETED with best-effort score (not FAILED).
    assert task_in_db.status == TaskStatus.COMPLETED
    assert task_in_db.iteration_count == 2


# ---------------------------------------------------------------------------
# Test 8: WebSocket events emitted for each agent stage
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_pipeline_emits_correct_websocket_events(
    monkeypatch: pytest.MonkeyPatch,
    task_in_db: Task,
) -> None:
    published: list[dict[str, Any]] = []

    async def _capture(_task_id: str, payload: dict[str, Any]) -> None:
        published.append(payload)

    monkeypatch.setattr(orch, "run_planner", AsyncMock(return_value=_make_plan()))
    monkeypatch.setattr(orch, "run_executor", AsyncMock(return_value=_make_execution()))
    monkeypatch.setattr(orch, "run_critic", AsyncMock(return_value=_make_verdict(0.85)))
    monkeypatch.setattr(orch, "publish_task_update", _capture)
    monkeypatch.setattr(orch, "store_task_memory", AsyncMock())

    await orch.run_agent_pipeline(task_in_db.id, task_in_db.description)

    event_types = [e["type"] for e in published]
    assert "agent_start" in event_types
    assert "agent_done" in event_types
    assert "task_complete" in event_types

    agents_started = [e["agent"] for e in published if e["type"] == "agent_start"]
    assert "planner" in agents_started
    assert "executor" in agents_started
    assert "critic" in agents_started

    terminal = next(e for e in published if e["type"] == "task_complete")
    assert terminal["score"] == pytest.approx(0.85)


# ---------------------------------------------------------------------------
# Test 9: Task not found — pipeline exits immediately without calling agents
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_pipeline_exits_early_for_nonexistent_task(
    monkeypatch: pytest.MonkeyPatch,
    _db_wired_orch: None,
) -> None:
    planner = AsyncMock()
    monkeypatch.setattr(orch, "run_planner", planner)
    monkeypatch.setattr(orch, "publish_task_update", AsyncMock())

    await orch.run_agent_pipeline("does-not-exist-uuid", "any description")
    planner.assert_not_called()


# ---------------------------------------------------------------------------
# Test 10: HTTP route → DB — task row created by POST /api/tasks
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_post_task_creates_db_row(
    client: Any,
    auth_headers: dict[str, str],
    db_session: AsyncSession,
) -> None:
    from unittest.mock import AsyncMock, patch

    with patch("app.api.routes.tasks.run_agent_pipeline", new_callable=AsyncMock):
        resp = await client.post(
            "/api/tasks",
            json={
                "title": "ingestion http test",
                "description": "create a task via HTTP and verify the database row",
                "category": "Test",
            },
            headers=auth_headers,
        )

    assert resp.status_code == 201
    body = resp.json()
    task_id = body["id"]

    # The DB row must exist with the correct initial state.
    from sqlalchemy import select
    result = await db_session.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one()

    assert task.title == "ingestion http test"
    assert task.status == TaskStatus.PENDING
    assert task.category == "Test"
    assert task.iteration_count == 0
    assert task.final_result is None
