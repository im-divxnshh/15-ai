"""JARVIS's Brain (M01) — the full pipeline.

User message
  → Classifier (intent / language / urgency)
  → Memory retrieval (relevant context)
  → Planner (agent/tool steps)
  → Risk Engine (approval gate)
  → Reasoner (thinking pass)
  → Tool execution (if planned)
  → Response Builder → reply

Every stage emits events to the bus so the 2D office UI shows live activity.
"""
from __future__ import annotations

import logging
from typing import Any

from app.core.brain.classifier import classifier
from app.core.brain.llm_router import llm_router
from app.core.brain.models import BrainResponse, Classification, Intent, Plan
from app.core.brain.planner import planner
from app.core.brain.reasoner import reasoner
from app.core.brain.response_builder import response_builder
from app.core.brain.risk_engine import risk_engine
from app.core.events.bus import (
    EVT_AGENT_FINISHED,
    EVT_AGENT_STARTED,
    EVT_AGENT_THINKING,
    bus as events,
)

log = logging.getLogger("brain")


class Brain:
    def __init__(self) -> None:
        self._tools_executor = None  # lazy — set after tools module loads
        self._memory = None          # lazy — set after memory module loads

    def wire(self, memory, tools_executor) -> None:
        """Late wiring to avoid circular imports."""
        self._memory = memory
        self._tools_executor = tools_executor

    async def process(
        self,
        text: str,
        history: list[dict] | None = None,
        direct_agent: str | None = None,
    ) -> BrainResponse:
        # 1. CLASSIFY ------------------------------------------------------
        cls = await classifier.classify(text)
        await events.publish(EVT_AGENT_THINKING, {"agent": "jarvis", "stage": "classify", "detail": cls.intent.value})

        # 2. MEMORY RETRIEVAL ----------------------------------------------
        memory_hits: list[str] = []
        memory_context = ""
        if self._memory is not None:
            try:
                memory_context, memory_hits = await self._memory.recall_context(text)
            except Exception:  # noqa: BLE001
                log.exception("memory recall failed")

        # 3. PLAN -----------------------------------------------------------
        plan: Plan | None = None
        if direct_agent and direct_agent != "jarvis":
            plan = Plan(goal=text, respond_directly=False)
            from app.core.brain.models import PlanStep

            plan.steps = [PlanStep(step=1, agent=direct_agent, action=f"handle: {text}")]
        else:
            plan = await planner.plan(text, cls, context=memory_context)
        await events.publish(EVT_AGENT_THINKING, {"agent": "jarvis", "stage": "plan", "detail": plan.goal})

        # 4. RISK -----------------------------------------------------------
        risk = await risk_engine.assess(plan)
        if risk.needs_approval:
            # answer with an approval request instead of executing
            ask = (
                f"⚠️ Boss, ye plan thoda risky lag raha hai — pehle confirm kar do:\n"
                + "\n".join(f"  {s.step}. {s.action}" for s in plan.steps)
                + "\n\nBolo **haan karo** ya **nahi, ruk jao**. 👀"
            )
            return BrainResponse(
                text=ask, intent=cls.intent, classification=cls, plan=plan,
                risk=risk, memory_used=memory_hits,
            )

        # 5. EXECUTE TOOLS ---------------------------------------------------
        tool_results: list[dict[str, Any]] = []
        agents_involved = {s.agent for s in plan.steps} or {"jarvis"}
        if not plan.respond_directly and self._tools_executor is not None:
            for step in plan.steps:
                if not step.tool:
                    continue
                await events.publish(EVT_AGENT_STARTED, {"agent": step.agent, "action": step.action, "tool": step.tool})
                try:
                    result = await self._tools_executor.execute(step.tool, step.tool_input, agent=step.agent)
                    tool_results.append({"tool": step.tool, "input": step.tool_input, "result": result})
                except Exception as exc:  # noqa: BLE001
                    log.exception("tool %s failed", step.tool)
                    tool_results.append({"tool": step.tool, "input": step.tool_input, "error": str(exc)})
                await events.publish(EVT_AGENT_FINISHED, {"agent": step.agent, "action": step.action})

        # 6. REASON -----------------------------------------------------------
        reasoning = None
        if not plan.respond_directly or tool_results:
            reasoning = await reasoner.reason(text, plan, tool_results, memory_context)

        # 7. BUILD RESPONSE ----------------------------------------------------
        agent_id = next(iter(agents_involved)) if not plan.respond_directly else "jarvis"
        agent_name, agent_prompt = "JARVIS", None
        try:
            from app.core.registry.agents import AGENTS

            if agent_id in AGENTS:
                agent_name, agent_prompt = AGENTS[agent_id].name, AGENTS[agent_id].prompt
        except Exception:  # noqa: BLE001
            pass

        if agent_prompt:
            final_text = await response_builder.build(
                text, cls, plan, reasoning, tool_results, memory_context, history,
                agent_name=agent_name, agent_prompt=agent_prompt,
            )
        else:
            final_text = await response_builder.build(
                text, cls, plan, reasoning, tool_results, memory_context, history
            )

        # 8. SAVE TO MEMORY ----------------------------------------------------
        if self._memory is not None:
            try:
                await self._memory.save_conversation_turn("user", text)
                await self._memory.save_conversation_turn("jarvis", final_text)
                if cls.intent in (Intent.TASK, Intent.EMOTIONAL) or len(text) > 80:
                    await self._memory.remember(text, kind=cls.intent.value)
            except Exception:  # noqa: BLE001
                log.exception("memory save failed")

        return BrainResponse(
            text=final_text,
            intent=cls.intent,
            agent=agent_id,
            classification=cls,
            plan=plan,
            reasoning=reasoning,
            risk=risk,
            tool_results=tool_results,
            memory_used=memory_hits,
        )


brain = Brain()
