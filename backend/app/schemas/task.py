"""Pydantic schemas for task endpoints."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.db.models import TaskStatus


class TaskCreate(BaseModel):
    title: str = Field(min_length=3, max_length=255)
    description: str = Field(min_length=10, max_length=10_000)
    category: str | None = Field(default=None, max_length=64)

    @field_validator("title", "description")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


class TaskListRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    status: TaskStatus
    category: str | None = None
    critic_score: float | None = None
    iteration_count: int
    created_at: datetime
    completed_at: datetime | None = None


class TaskRead(BaseModel):
    """Full task detail. JSON-string columns are parsed back into dicts."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    description: str
    status: TaskStatus
    category: str | None = None

    planner_output: dict[str, Any] | None = None
    executor_output: dict[str, Any] | None = None
    critic_output: dict[str, Any] | None = None
    final_result: str | None = None

    iteration_count: int
    critic_score: float | None = None
    error_message: str | None = None

    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None

    @field_validator(
        "planner_output", "executor_output", "critic_output", mode="before"
    )
    @classmethod
    def _parse_json(cls, v: object) -> object:
        if v is None or isinstance(v, dict):
            return v
        if isinstance(v, str):
            stripped = v.strip()
            if not stripped:
                return None
            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                return {"raw": stripped}
        return v
