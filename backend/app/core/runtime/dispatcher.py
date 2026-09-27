"""Dispatcher (M03) — turns brain plans into queued tasks."""
from __future__ import annotations

import logging

from app.core.brain.models import Plan, PlanStep
from app.core.memory.store import new_id
from app.core.runtime.schemas import Task
from app.core.runtime.task_queue import task_queue

log = logging.getLogger("runtime.dispatcher")


class Dispatcher:
    async def dispatch_plan(self, plan: Plan, urgency: int = 1) -> list[str]:
        task_ids = []
        for step in plan.steps:
            task_id = await self.dispatch_step(step, urgency=urgency)
            if task_id:
                task_ids.append(task_id)
        return task_ids

    async def dispatch_step(self, step: PlanStep, urgency: int = 1) -> str | None:
        if not step.action:
            return None
        task = Task(
            id=new_id(),
            title=step.action[:120],
            agent=step.agent if step.agent in ("jarvis",) or step.agent else "jarvis",
            action=step.action,
            tool=step.tool,
            tool_input=step.tool_input,
            priority=max(0, min(3, urgency)),
        )
        await task_queue.submit(task)
        return task.id

    async def dispatch_raw(
        self, title: str, agent: str = "jarvis", action: str | None = None,
        tool: str | None = None, tool_input: dict | None = None, priority: int = 1,
    ) -> str:
        task = Task(
            id=new_id(), title=title, agent=agent, action=action or title,
            tool=tool, tool_input=tool_input or {}, priority=priority,
        )
        await task_queue.submit(task)
        return task.id


dispatcher = Dispatcher()
