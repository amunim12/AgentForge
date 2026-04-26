"""Executor agent â runs each step of a plan using tools."""
from __future__ import annotations

import json
import time
from typing import Any

import structlog
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_groq import ChatGroq

from app.agents.prompts.executor import EXECUTOR_SYSTEM_PROMPT
from app.core.config import settings
from app.core.exceptions import AgentExecutionError
from app.queue.redis_client import publish_task_update
from app.tools.code_executor import code_executor
from app.tools.file_tool import file_tool, reset_notebook
from app.tools.web_search import web_search

logger = structlog.get_logger()

_MAX_AGENT_ITERATIONS = 15


def _build_llm() -> ChatGroq:
    return ChatGroq(
        groq_api_key=settings.GROQ_API_KEY,
        model_name="llama-3.1-70b-versatile",
        temperature=0.1,
        max_tokens=settings.MAX_TOKENS_PER_AGENT,
    )


def _build_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            ("system", EXECUTOR_SYSTEM_PROMPT),
            (
                "human",
                "Original task:\n{task_description}\n\n"
                "Plan (JSON):\n{plan_json}\n\n"
                "Execute every step of the plan and produce the final Markdown answer.",
            ),
            MessagesPlaceholder("agent_scratchpad"),
        ]
    )


async def _emit_tool_calls(task_id: str, intermediate_steps: list[Any]) -> list[dict]:
    """Publish tool-call events to the WebSocket and return a serializable log."""
    events: list[dict] = []
    for action, observation in intermediate_steps:
        tool_name = getattr(action, "tool", "unknown")
        tool_input = getattr(action, "tool_input", None)
        try:
            input_repr = (
                json.dumps(tool_input)
                if not isinstance(tool_input, str)
                else tool_input
            )
        except (TypeError, ValueError):
            input_repr = str(tool_input)
        if len(input_repr) > 500:
            input_repr = input_repr[:500] + "â¦"

        observation_str = str(observation)
        if len(observation_str) > 500:
            observation_str = observation_str[:500] + "â¦"

        event = {
            "type": "agent_tool_call",
            "agent": "executor",
            "tool": tool_name,
            "input": input_repr,
            "output_preview": observation_str,
        }
        events.append(event)
        await publish_task_update(task_id, event)
    return events


async def run_executor(
    plan: dict[str, Any],
    task_id: str,
    task_description: str,
    previous_feedback: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run the Executor agent over the plan. Returns a structured result dict."""
    reset_notebook()

    llm = _build_llm()
    tools = [web_search, code_executor, file_tool]
    prompt = _build_prompt()

    try:
        agent = create_tool_calling_agent(llm, tools, prompt)
    except Exception as exc:
        logger.exception("Failed to build executor agent", task_id=task_id)
        raise AgentExecutionError("Executor initialization failed") from exc

    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=False,
        max_iterations=_MAX_AGENT_ITERATIONS,
        handle_parsing_errors=True,
        return_intermediate_steps=True,
    )

    feedback_text = (
        json.dumps(previous_feedback, indent=2) if previous_feedback else "None"
    )

    started = time.perf_counter()
    try:
        result = await agent_executor.ainvoke(
            {
                "task_description": task_description,
                "plan_json": json.dumps(plan, indent=2),
                "previous_feedback": feedback_text,
            }
        )
    except Exception as exc:
        logger.exception("Executor ainvoke failed", task_id=task_id)
        raise AgentExecutionError("Executor LLM call failed") from exc
    duration_ms = int((time.perf_counter() - started) * 1000)

    output_text: str = str(result.get("output", "")).strip()
    intermediate = result.get("intermediate_steps", []) or []
    tool_events = await _emit_tool_calls(task_id, intermediate)

    # Stream the final answer as one chunk so the frontend can render it live.
    if output_text:
        await publish_task_update(
            task_id,
            {"type": "agent_stream", "agent": "executor", "delta": output_text},
        )

    logger.info(
        "Executor completed",
        task_id=task_id,
        tool_calls=len(tool_events),
        duration_ms=duration_ms,
        output_chars=len(output_text),
    )

    return {
        "formatted_output": output_text,
        "steps_completed": len(plan.get("steps", [])),
        "tool_calls": tool_events,
        "duration_ms": duration_ms,
    }
