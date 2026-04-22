"""SQLModel database models for AgentForge."""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from sqlmodel import Field, Relationship, SQLModel


class TaskStatus(str, Enum):
    PENDING = "pending"
    PLANNING = "planning"
    EXECUTING = "executing"
    CRITIQUING = "critiquing"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.utcnow()


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: str = Field(default_factory=_uuid, primary_key=True)
    email: str = Field(unique=True, index=True, max_length=255)
    username: str = Field(unique=True, index=True, max_length=64)
    hashed_password: str
    is_active: bool = True
    created_at: datetime = Field(default_factory=_utcnow)

    tasks: list["Task"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class Task(SQLModel, table=True):
    __tablename__ = "tasks"

    id: str = Field(default_factory=_uuid, primary_key=True)
    title: str = Field(max_length=255)
    description: str
    status: TaskStatus = Field(default=TaskStatus.PENDING, index=True)
    category: str | None = Field(default=None, max_length=64)

    user_id: str = Field(foreign_key="users.id", index=True)
    user: User | None = Relationship(back_populates="tasks")

    # Agent outputs stored as JSON strings (schema-free for flexibility)
    planner_output: str | None = None
    executor_output: str | None = None
    critic_output: str | None = None
    final_result: str | None = None

    # Iteration tracking
    iteration_count: int = 0
    critic_score: float | None = None
    error_message: str | None = None

    created_at: datetime = Field(default_factory=_utcnow, index=True)
    updated_at: datetime = Field(default_factory=_utcnow)
    completed_at: datetime | None = None
