"""Pydantic schemas for agent state and WebSocket events."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

AgentName = Literal["planner", "executor", "critic"]
EventType = Literal[
    "agent_start",
    "agent_stream",
    "agent_tool_call",
    "agent_done",
    "task_complete",
    "task_failed",
]


class AgentEvent(BaseModel):
    """Envelope broadcast over the WebSocket stream."""

    type: EventType
    agent: AgentName | None = None
    delta: str | None = None
    output: dict[str, Any] | None = None
    tool: str | None = None
    input: str | None = None
    duration_ms: int | None = None
    result: str | None = None
    score: float | None = None
    error: str | None = None


class PlanStep(BaseModel):
    step_id: int
    title: str
    description: str
    tool: str
    tool_input_hint: str
    expected_output: str
    dependencies: list[int] = Field(default_factory=list)
    critical: bool = False


class TaskPlan(BaseModel):
    task_summary: str
    complexity: Literal["low", "medium", "high"]
    estimated_steps: int
    steps: list[PlanStep]
    success_criteria: str


class RubricEntry(BaseModel):
    score: int = Field(ge=0, le=10)
    comment: str


class CriticRubric(BaseModel):
    accuracy: RubricEntry
    completeness: RubricEntry
    clarity: RubricEntry
    relevance: RubricEntry
    depth: RubricEntry


class CriticVerdict(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    rubric: CriticRubric
    strengths: list[str]
    improvements_needed: list[str]
    specific_instructions_for_next_iteration: str
    verdict: Literal["accept", "revise"]
