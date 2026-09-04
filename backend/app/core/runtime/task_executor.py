"""Task Executor (M03) — runs a task: tool call, agent LLM work, or workflow step."""
from __future__ import annotations

import logging
from typing import Any

from app.core.brain.llm_router import llm_router
from app.core.brain.prompts import system_prompt
from app.core.memory.manager import memory
from app.core.registry.agents import AGENTS
from app.core.runtime.schemas import Task
from app.services.tools.registry import tool_registry

log = logging.getLogger("runtime.executor")


class TaskExecutor:
    async def execute(self, task: Task) -> Any:
        # 1. tool task → run the tool
        if task.tool:
            return await tool_registry.execute(task.tool, task.tool_input, agent=task.agent)

        # 2. agent work task → let the agent think about the action
        agent = AGENTS.get(task.agent)
        if agent is None:
            return {"error": f"unknown agent '{task.agent}'"}

        context, _ = await memory.recall_context(task.action)
        messages = [
            {"role": "system", "content": system_prompt(agent.name, agent.prompt)},
            {
                "role": "user",
                "content": (
                    f"Complete this task and return the useful output (no fluff):\n{task.action}"
                    + (f"\n\nRelevant memory:\n{context}" if context else "")
                ),
            },
        ]
        text = await llm_router.chat(messages, temperature=0.6)
        await memory.save_conversation_turn(task.agent, text, agent=task.agent)
        return {"output": text}


task_executor = TaskExecutor()
