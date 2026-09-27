"""Orchestrator (M03) — the top-level "run the office" entrypoint.

Chat path  : user message → brain pipeline → reply (+ background tasks)
Task path  : brain plan → dispatcher → queue → executor → events
"""
from __future__ import annotations

import logging

from app.core.brain.brain import brain
from app.core.brain.models import BrainResponse
from app.core.events.bus import EVT_CHAT_MESSAGE, bus as events
from app.core.memory.manager import memory
from app.core.runtime.dispatcher import dispatcher

log = logging.getLogger("runtime.orchestrator")


class Orchestrator:
    async def chat(self, text: str, direct_agent: str | None = None) -> BrainResponse:
        """Full chat turn with the office. Emits events + fires background tasks."""
        await events.publish(EVT_CHAT_MESSAGE, {"role": "user", "text": text})
        history = memory.get_history()
        response = await brain.process(text, history=history, direct_agent=direct_agent)

        # risky plans were not executed — the response asks the user to approve
        if response.risk and response.risk.needs_approval:
            await events.publish(EVT_CHAT_MESSAGE, {"role": "jarvis", "text": response.text})
            return response

        # non-trivial plans → also run the steps as background tasks for the office UI
        if response.plan and response.plan.steps and not response.plan.respond_directly:
            for step in response.plan.steps:
                if step.action:
                    await dispatcher.dispatch_step(step, urgency=response.classification.urgency.value)

        await events.publish(EVT_CHAT_MESSAGE, {"role": "jarvis", "text": response.text})
        return response


orchestrator = Orchestrator()
