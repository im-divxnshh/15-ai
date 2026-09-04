"""Shared data models for the brain pipeline."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Intent(str, Enum):
    CHAT = "chat"                # casual conversation / questions
    TASK = "task"                # something to DO (remind, research, write, build)
    QUESTION = "question"        # knowledge question (may need search)
    COMMAND = "command"          # system command (show tasks, agent status)
    APPROVAL = "approval"        # user approving/rejecting a pending action
    EMOTIONAL = "emotional"      # venting, reflection, mood


class Priority(int, Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


class Classification(BaseModel):
    intent: Intent = Intent.CHAT
    language: str = "hinglish"   # hinglish | hindi | english
    sentiment: str = "neutral"   # positive | neutral | negative
    urgency: Priority = Priority.NORMAL
    confidence: float = 0.7


class PlanStep(BaseModel):
    step: int
    agent: str = "jarvis"        # agent id that should execute
    action: str                  # what to do
    tool: str | None = None      # tool name if a tool is needed
    tool_input: dict[str, Any] = Field(default_factory=dict)
    needs_approval: bool = False


class Plan(BaseModel):
    goal: str
    steps: list[PlanStep] = Field(default_factory=list)
    respond_directly: bool = True  # smalltalk / simple Q&A — no agents needed


class Reasoning(BaseModel):
    thinking: str = ""
    key_points: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


class RiskAssessment(BaseModel):
    score: int = 0               # 0 (safe) .. 100 (danger)
    level: str = "safe"          # safe | low | medium | high
    reasons: list[str] = Field(default_factory=list)
    needs_approval: bool = False


class BrainResponse(BaseModel):
    text: str
    intent: Intent = Intent.CHAT
    agent: str = "jarvis"
    classification: Classification = Field(default_factory=Classification)
    plan: Plan | None = None
    reasoning: Reasoning | None = None
    risk: RiskAssessment | None = None
    tool_results: list[dict[str, Any]] = Field(default_factory=list)
    memory_used: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
