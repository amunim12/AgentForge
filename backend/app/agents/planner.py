"""Planner agent â decomposes a user task into a structured plan."""
from __future__ import annotations

import json
import re
from typing import Any

import structlog
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from app.agents.prompts.planner import PLANNER_SYSTEM_PROMPT
from app.core.config import settings
from app.core.exceptions import AgentExecutionError
from app.queue.redis_client import publish_task_update
from app.schemas.agent import TaskPlan

logger = structlog.get_logger()

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)


def _strip_fences(text: str) -> str:
    """Drop ```json ... ``` fences if the LLM wrapped its output."""
    return _FENCE_RE.sub("", text.strip()).strip()


def _build_llm() -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model="gemini-1.5-flash",
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=0.1,
        max_output_tokens=settings.MAX_TOKENS_PER_AGENT,
    )


async def run_planner(task_description: str, task_id: str) -> dict[str, Any]:
    """Stream the planner's reasoning to the WebSocket and return a parsed plan.

    Raises:
        AgentExecutionError: if the LLM output cannot be parsed as a TaskPlan.
    """
    if not task_description or not task_description.strip():
        raise AgentExecutionError("Planner received empty task description")

    llm = _build_llm()
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", PLANNER_SYSTEM_PROMPT),
            ("human", "Task to plan:\n{task_description}"),
        ]
    )
    chain = prompt | llm

    full_text = ""
    try:
        async for chunk in chain.astream({"task_description": task_description}):
            delta = getattr(chunk, "content", None)
            if not delta:
                continue
            full_text += delta
            await publish_task_update(
                task_id,
                {"type": "agent_stream", "agent": "planner", "delta": delta},
            )
    except Exception as exc:
        logger.exception("Planner streaming failed", task_id=task_id)
        raise AgentExecutionError("Planner LLM call failed") from exc

    # Try strict JSON parse first; fall back to the tolerant LangChain parser.
    cleaned = _strip_fences(full_text)
    try:
        parsed: dict[str, Any] = json.loads(cleaned)
    except json.JSONDecodeError:
        try:
            parser = JsonOutputParser(pydantic_object=TaskPlan)
            parsed = parser.parse(cleaned)
        except Exception as exc:
            logger.warning(
                "Planner output was not valid JSON",
                task_id=task_id,
                sample=cleaned[:200],
            )
            raise AgentExecutionError("Planner returned malformed JSON") from exc

    # Validate against the Pydantic schema â normalize + enforce structure.
    try:
        plan = TaskPlan.model_validate(parsed)
    except Exception as exc:
        logger.warning(
            "Planner output failed schema validation",
            task_id=task_id,
            error=str(exc),
        )
        raise AgentExecutionError("Planner output failed schema validation") from exc

    logger.info(
        "Planner produced plan",
        task_id=task_id,
        steps=len(plan.steps),
        complexity=plan.complexity,
    )
    return plan.model_dump()
