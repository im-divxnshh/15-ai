"""Runtime schemas (M03)."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TaskState(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    WAITING_APPROVAL = "waiting_approval"
    CANCELLED = "cancelled"


class Task(BaseModel):
    id: str
    title: str
    agent: str = "jarvis"
    action: str = ""
    tool: str | None = None
    tool_input: dict[str, Any] = Field(default_factory=dict)
    priority: int = 1          # 0 low .. 3 critical
    state: TaskState = TaskState.QUEUED
    attempts: int = 0
    max_attempts: int = 2
    result: Any = None
    error: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    finished_at: datetime | None = None

    class Config:
        json_encoders = {datetime: lambda d: d.isoformat()}


class DispatchResult(BaseModel):
    task_id: str
    accepted: bool
    reason: str | None = None
