"""Critic tests with the Gemini LLM stubbed via _build_llm."""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any

import pytest

from app.agents import critic as critic_module
from app.core.exceptions import AgentExecutionError


def _rubric_entry(score: int, comment: str = "ok") -> dict[str, Any]:
    return {"score": score, "comment": comment}


VALID_VERDICT = {
    "score": 0.85,
    "rubric": {
        "accuracy": _rubric_entry(9),
        "completeness": _rubric_entry(8),
        "clarity": _rubric_entry(9),
        "relevance": _rubric_entry(9),
        "depth": _rubric_entry(8),
    },
    "strengths": ["clear comparison", "well sourced"],
    "improvements_needed": [],
    "specific_instructions_for_next_iteration": "n/a",
    "verdict": "accept",
}


class _FakeChunk:
    def __init__(self, text: str) -> None:
        self.content = text


class _FakeChain:
    def __init__(self, chunks: list[str]) -> None:
        self._chunks = chunks

    async def astream(self, _inputs: dict[str, Any]) -> AsyncIterator[_FakeChunk]:
        for c in self._chunks:
            yield _FakeChunk(c)


def _patch_llm(monkeypatch: pytest.MonkeyPatch, payload: str) -> None:
    fake_chain = _FakeChain([payload])

    class _FakeLLM:
        def __or__(self, _other: Any) -> "_FakeLLM":
            return self

    class _FakePrompt:
        def __or__(self, _other: Any) -> _FakeChain:
            return fake_chain

    monkeypatch.setattr(critic_module, "_build_llm", lambda: _FakeLLM())
    monkeypatch.setattr(
        critic_module,
        "ChatPromptTemplate",
        SimpleNamespace(from_messages=lambda _: _FakePrompt()),
    )


@pytest.mark.asyncio
async def test_critic_returns_verdict(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_llm(monkeypatch, json.dumps(VALID_VERDICT))
    verdict = await critic_module.run_critic(
        original_task="Compare DBs",
        plan={"steps": []},
        execution_result={"formatted_output": "## Comparison\n..."},
        task_id="task-1",
        iteration=0,
    )
    assert verdict["score"] == 0.85
    assert verdict["verdict"] == "accept"


@pytest.mark.asyncio
async def test_critic_strips_code_fences(monkeypatch: pytest.MonkeyPatch) -> None:
    fenced = "```json\n" + json.dumps(VALID_VERDICT) + "\n```"
    _patch_llm(monkeypatch, fenced)
    verdict = await critic_module.run_critic(
        "task",
        {"steps": []},
        {"formatted_output": "non-empty"},
        "task-2",
        0,
    )
    assert verdict["verdict"] == "accept"


@pytest.mark.asyncio
async def test_critic_rejects_empty_executor_output() -> None:
    with pytest.raises(AgentExecutionError):
        await critic_module.run_critic(
            "task",
            {"steps": []},
            {"formatted_output": "   "},
            "task-3",
            0,
        )


@pytest.mark.asyncio
async def test_critic_rejects_malformed_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_llm(monkeypatch, "I think the answer is great")
    with pytest.raises(AgentExecutionError):
        await critic_module.run_critic(
            "task",
            {"steps": []},
            {"formatted_output": "non-empty"},
            "task-4",
            0,
        )


@pytest.mark.asyncio
async def test_critic_rejects_invalid_schema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bad = {"score": 5.0, "verdict": "maybe"}  # score >1, missing rubric
    _patch_llm(monkeypatch, json.dumps(bad))
    with pytest.raises(AgentExecutionError):
        await critic_module.run_critic(
            "task",
            {"steps": []},
            {"formatted_output": "non-empty"},
            "task-5",
            0,
        )


def test_strip_fences_idempotent_on_plain() -> None:
    assert critic_module._strip_fences("{}") == "{}"


def test_strip_fences_removes_json_fence() -> None:
    assert critic_module._strip_fences("```json\n{\"a\":1}\n```") == '{"a":1}'
