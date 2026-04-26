"""LangGraph state machine: Planner â Executor â Critic (retry loop)."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, TypedDict

import structlog
from langgraph.graph import END, StateGraph

from app.agents.critic import run_critic
from app.agents.executor import run_executor
from app.agents.planner import run_planner
from app.core.config import settings
from app.core.exceptions import AgentForgeError
from app.db.models import Task, TaskStatus
from app.db.session import get_db_session
from app.memory.chroma import store_task_memory
from app.queue.redis_client import publish_task_update

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
class AgentState(TypedDict, total=False):
    task_id: str
    task_description: str
    plan: dict[str, Any]
    execution_result: dict[str, Any]
    critic_feedback: dict[str, Any]
    critic_score: float
    iteration: int
    final_result: str


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------
async def planner_node(state: AgentState) -> AgentState:
    task_id = state["task_id"]
    await _update_task_status(task_id, TaskStatus.PLANNING)
    await publish_task_update(task_id, {"type": "agent_start", "agent": "planner"})

    plan = await run_planner(
        task_description=state["task_description"],
        task_id=task_id,
    )

    await _persist_task_field(task_id, planner_output=json.dumps(plan))
    await publish_task_update(
        task_id,
        {"type": "agent_done", "agent": "planner", "output": plan},
    )
    return {"plan": plan}


async def executor_node(state: AgentState) -> AgentState:
    task_id = state["task_id"]
    await _update_task_status(task_id, TaskStatus.EXECUTING)
    await publish_task_update(task_id, {"type": "agent_start", "agent": "executor"})

    result = await run_executor(
        plan=state["plan"],
        task_id=task_id,
        task_description=state["task_description"],
        previous_feedback=state.get("critic_feedback"),
    )

    await _persist_task_field(task_id, executor_output=json.dumps(result))
    await publish_task_update(
        task_id,
        {"type": "agent_done", "agent": "executor", "output": result},
    )
    return {"execution_result": result}


async def critic_node(state: AgentState) -> AgentState:
    task_id = state["task_id"]
    await _update_task_status(task_id, TaskStatus.CRITIQUING)
    await publish_task_update(task_id, {"type": "agent_start", "agent": "critic"})

    feedback = await run_critic(
        original_task=state["task_description"],
        plan=state["plan"],
        execution_result=state["execution_result"],
        task_id=task_id,
        iteration=state.get("iteration", 0),
    )

    next_iteration = state.get("iteration", 0) + 1
    await _persist_task_field(
        task_id,
        critic_output=json.dumps(feedback),
        critic_score=float(feedback.get("score", 0.0)),
        iteration_count=next_iteration,
    )
    await publish_task_update(
        task_id,
        {"type": "agent_done", "agent": "critic", "output": feedback},
    )
    return {
        "critic_feedback": feedback,
        "critic_score": float(feedback.get("score", 0.0)),
        "iteration": next_iteration,
    }


# ---------------------------------------------------------------------------
# Conditional routing
# ---------------------------------------------------------------------------
def should_rerun(state: AgentState) -> str:
    score = state.get("critic_score", 0.0)
    iteration = state.get("iteration", 0)
    if score >= settings.CRITIC_SCORE_THRESHOLD:
        return "finish"
    if iteration >= settings.MAX_CRITIC_ITERATIONS:
        return "finish"  # accept best effort
    return "rerun_executor"


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------
def build_graph():
    graph: StateGraph = StateGraph(AgentState)
    graph.add_node("planner", planner_node)
    graph.add_node("executor", executor_node)
    graph.add_node("critic", critic_node)

    graph.set_entry_point("planner")
    graph.add_edge("planner", "executor")
    graph.add_edge("executor", "critic")
    graph.add_conditional_edges(
        "critic",
        should_rerun,
        {"rerun_executor": "executor", "finish": END},
    )
    return graph.compile()


agent_graph = build_graph()


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------
async def _update_task_status(task_id: str, status: TaskStatus) -> None:
    async with get_db_session() as db:
        task = await db.get(Task, task_id)
        if task is None:
            return
        task.status = status
        task.updated_at = datetime.utcnow()
        await db.commit()


async def _persist_task_field(task_id: str, **fields: Any) -> None:
    if not fields:
        return
    async with get_db_session() as db:
        task = await db.get(Task, task_id)
        if task is None:
            return
        for key, value in fields.items():
            setattr(task, key, value)
        task.updated_at = datetime.utcnow()
        await db.commit()


async def _finalize_task(
    task_id: str,
    final_state: AgentState,
) -> None:
    final_output = (
        final_state.get("execution_result", {}) or {}
    ).get("formatted_output", "") or ""
    score = float(final_state.get("critic_score", 0.0))

    async with get_db_session() as db:
        task = await db.get(Task, task_id)
        if task is None:
            return
        task.status = TaskStatus.COMPLETED
        task.final_result = final_output
        task.critic_score = score
        task.iteration_count = int(final_state.get("iteration", 0))
        task.completed_at = datetime.utcnow()
        task.updated_at = task.completed_at
        await db.commit()

    # Best-effort: persist to vector store for future RAG retrieval.
    try:
        await store_task_memory(
            task_id=task_id,
            content=final_output[:8000],
            metadata={
                "task_description": final_state.get("task_description", ""),
                "score": score,
                "step": 0,
            },
        )
    except Exception:  # pragma: no cover
        pass


async def _mark_failed(task_id: str, error: str) -> None:
    async with get_db_session() as db:
        task = await db.get(Task, task_id)
        if task is None:
            return
        task.status = TaskStatus.FAILED
        task.error_message = error[:1000]
        task.updated_at = datetime.utcnow()
        await db.commit()


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------
async def run_agent_pipeline(task_id: str, task_description: str) -> None:
    """Run the full Planner â Executor â Critic loop for a single task.

    Called from FastAPI BackgroundTasks; never raises â all errors are
    captured, logged, persisted, and emitted over the WebSocket.
    """
    logger.info("Agent pipeline starting", task_id=task_id)

    # Ensure task exists before we do any real work.
    async with get_db_session() as db:
        if await db.get(Task, task_id) is None:
            logger.warning("Task disappeared before pipeline started", task_id=task_id)
            return

    initial_state: AgentState = {
        "task_id": task_id,
        "task_description": task_description,
        "plan": {},
        "execution_result": {},
        "critic_feedback": {},
        "critic_score": 0.0,
        "iteration": 0,
        "final_result": "",
    }

    try:
        final_state: AgentState = await agent_graph.ainvoke(initial_state)  # type: ignore[assignment]
    except AgentForgeError as exc:
        logger.warning("Agent pipeline aborted", task_id=task_id, error=str(exc))
        await _mark_failed(task_id, exc.public_message)
        await publish_task_update(
            task_id,
            {"type": "task_failed", "error": exc.public_message},
        )
        return
    except Exception as exc:
        logger.exception("Agent pipeline crashed", task_id=task_id)
        await _mark_failed(task_id, "Agent pipeline failed")
        await publish_task_update(
            task_id,
            {"type": "task_failed", "error": "Agent pipeline failed"},
        )
        return

    await _finalize_task(task_id, final_state)
    await publish_task_update(
        task_id,
        {
            "type": "task_complete",
            "result": (
                final_state.get("execution_result", {}) or {}
            ).get("formatted_output", ""),
            "score": float(final_state.get("critic_score", 0.0)),
        },
    )
    logger.info(
        "Agent pipeline complete",
        task_id=task_id,
        score=final_state.get("critic_score"),
        iterations=final_state.get("iteration"),
    )

