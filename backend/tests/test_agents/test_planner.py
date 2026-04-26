"""Planner tests with the LLM stubbed via _build_llm."""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any

import pytest

from app.agents import planner as planner_module
from app.core.exceptions import AgentExecutionError


VALID_PLAN = {
    "task_summary": "Compare three open-source vector databases.",
    "complexity": "medium",
    "estimated_steps": 2,
    "steps": [
        {
            "step_id": 1,
            "title": "Research candidates",
            "description": "Find three production-grade open source vector DBs.",
            "tool": "web_search",
            "tool_input_hint": "open source vector database 2026",
            "expected_output": "List of three.",
            "dependencies": [],
            "critical": True,
        },
        {
            "step_id": 2,
            "title": "Compose comparison",
            "description": "Write up pros and cons for each.",
            "tool": "reasoning",
            "tool_input_hint": "synthesize",
            "expected_output": "Markdown comparison.",
            "dependencies": [1],
            "critical": True,
        },
    ],
    "success_criteria": "Three DBs with pros/cons each.",
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
    """Replace `_build_llm` so `prompt | llm` yields our fake stream."""

    class _FakeLLM:
        def __or__(self, _other: Any) -> "_FakeLLM":
            return self

    # Patch the prompt-pipe pattern: ChatPromptTemplate | llm. The simplest
    # interception is to patch the chain returned by `prompt | llm` — we
    # instead monkeypatch ChatPromptTemplate.from_messages's __or__ result via
    # patching the module's _build_llm and having `|` produce our chain.
    fake_chain = _FakeChain([payload])

    class _FakePrompt:
        def __or__(self, _other: Any) -> _FakeChain:
            return fake_chain

    monkeypatch.setattr(planner_module, "_build_llm", lambda: _FakeLLM())
    monkeypatch.setattr(
        planner_module, "ChatPromptTemplate", SimpleNamespace(from_messages=lambda _: _FakePrompt())
    )


@pytest.mark.asyncio
async def test_planner_returns_validated_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_llm(monkeypatch, json.dumps(VALID_PLAN))
    plan = await planner_module.run_planner("Compare vector DBs", "task-1")
    assert plan["complexity"] == "medium"
    assert len(plan["steps"]) == 2


@pytest.mark.asyncio
async def test_planner_strips_code_fences(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fenced = "```json\n" + json.dumps(VALID_PLAN) + "\n```"
    _patch_llm(monkeypatch, fenced)
    plan = await planner_module.run_planner("x", "task-2")
    assert plan["task_summary"].startswith("Compare")


@pytest.mark.asyncio
async def test_planner_rejects_empty_description(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(AgentExecutionError):
        await planner_module.run_planner("   ", "task-3")


@pytest.mark.asyncio
async def test_planner_rejects_malformed_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_llm(monkeypatch, "this is not json at all")
    with pytest.raises(AgentExecutionError):
        await planner_module.run_planner("real task", "task-4")


@pytest.mark.asyncio
async def test_planner_rejects_invalid_schema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_llm(monkeypatch, json.dumps({"complexity": "extreme"}))
    with pytest.raises(AgentExecutionError):
        await planner_module.run_planner("real task", "task-5")


def test_strip_fences_handles_plain_text() -> None:
    assert planner_module._strip_fences("hello") == "hello"


def test_strip_fences_handles_fenced() -> None:
    assert planner_module._strip_fences("```json\n{}\n```") == "{}"
