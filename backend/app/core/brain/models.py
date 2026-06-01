from pydantic import BaseModel
from typing import List

class TaskPlan(BaseModel):
    goal: str
    intent: str
    priority: str
    tasks: List[str]

class RiskReport(BaseModel):
    risks: List[str]

class BrainOutput(BaseModel):
    goal: str
    intent: str
    analysis: str
    execution_plan: str
    risks: List[str]
    response: str