"""Critic agent â scores executor output against a rubric."""
from __future__ import annotations

import json
import re
from typing import Any

import structlog
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from app.agents.prompts.critic import CRITIC_SYSTEM_PROMPT
from app.core.config import settings
from app.core.exceptions import AgentExecutionError
from app.queue.redis_client import publish_task_update
from app.schemas.agent import CriticVerdict

logger = structlog.get_logger()

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)


def _strip_fences(text: str) -> str:
    return _FENCE_RE.sub("", text.strip()).strip()


def _build_llm() -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model="gemini-1.5-pro",
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=0.0,
        max_output_tokens=2048,
    )


async def run_critic(
    original_task: str,
    plan: dict[str, Any],
    execution_result: dict[str, Any],
    task_id: str,
    iteration: int,
) -> dict[str, Any]:
    """Evaluate the executor's output and return a verdict dict."""
    output_text = (execution_result or {}).get("formatted_output", "") or ""
    if not output_text.strip():
        raise AgentExecutionError("Critic received empty executor output")

    llm = _build_llm()
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", CRITIC_SYSTEM_PROMPT),
            (
                "human",
                "Original task:\n{original_task}\n\n"
                "Plan (JSON):\n{plan_json}\n\n"
                "Executor output (iteration {iteration}):\n{execution_output}\n\n"
                "Evaluate strictly per the rubric and return JSON only.",
            ),
        ]
    )
    chain = prompt | llm

    full_text = ""
    try:
        async for chunk in chain.astream(
            {
                "original_task": original_task,
                "plan_json": json.dumps(plan, indent=2),
                "execution_output": output_text,
                "iteration": iteration,
            }
        ):
            delta = getattr(chunk, "content", None)
            if not delta:
                continue
            full_text += delta
            await publish_task_update(
                task_id,
                {"type": "agent_stream", "agent": "critic", "delta": delta},
            )
    except Exception as exc:
        logger.exception("Critic streaming failed", task_id=task_id)
        raise AgentExecutionError("Critic LLM call failed") from exc

    cleaned = _strip_fences(full_text)
    try:
        parsed: dict[str, Any] = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.warning(
            "Critic output was not valid JSON",
            task_id=task_id,
            sample=cleaned[:200],
        )
        raise AgentExecutionError("Critic returned malformed JSON") from exc

    try:
        verdict = CriticVerdict.model_validate(parsed)
    except Exception as exc:
        logger.warning(
            "Critic output failed schema validation",
            task_id=task_id,
            error=str(exc),
        )
        raise AgentExecutionError("Critic output failed schema validation") from exc

    logger.info(
        "Critic evaluation complete",
        task_id=task_id,
        score=verdict.score,
        verdict=verdict.verdict,
        iteration=iteration,
    )
    return verdict.model_dump()
