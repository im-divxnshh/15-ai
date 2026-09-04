"""Workflow Engine (M14) — simple trigger → steps automations.

A workflow = named list of steps ({tool, input} or {agent, action}) plus a trigger:
- "manual"  : fired from the UI / API
- "schedule": fired by the scheduler every N minutes (checked by a background loop)
- "phrase"  : fired when a chat message contains the phrase
Runs through the normal dispatcher/queue so everything shows up in the office UI.
"""
from __future__ import annotations

import asyncio
import logging

from app.core.events.bus import EVT_SYSTEM, bus as events
from app.core.memory.store import new_id, now_iso, store
from app.core.runtime.dispatcher import dispatcher

log = logging.getLogger("workflow.engine")

COLLECTION = "workflows"
EXECUTIONS = "workflow_executions"


class WorkflowEngine:
    def __init__(self) -> None:
        self._scheduler_task: asyncio.Task | None = None

    # -- definitions -----------------------------------------------------
    def create(self, name: str, steps: list[dict], trigger: dict | None = None) -> dict:
        wf_id = new_id()
        doc = {"id": wf_id, "name": name, "steps": steps,
               "trigger": trigger or {"type": "manual"}, "enabled": True,
               "runs": 0, "created_at": now_iso()}
        store.put(COLLECTION, wf_id, doc)
        return doc

    def list(self) -> list[dict]:
        return store.list(COLLECTION, limit=100)

    def delete(self, wf_id: str) -> bool:
        return store.delete(COLLECTION, wf_id)

    # -- execution ---------------------------------------------------------
    async def run(self, wf_id: str) -> dict:
        wf = store.get(COLLECTION, wf_id)
        if not wf or not wf.get("enabled"):
            return {"error": "workflow not found or disabled"}
        exec_id = new_id()
        task_ids = []
        for i, step in enumerate(wf["steps"]):
            task_id = await dispatcher.dispatch_raw(
                title=f"[{wf['name']} #{i + 1}] {step.get('action') or step.get('tool', '')}",
                agent=step.get("agent", "oracle"),
                action=step.get("action"),
                tool=step.get("tool"),
                tool_input=step.get("input", {}),
            )
            task_ids.append(task_id)
        wf["runs"] = int(wf.get("runs", 0)) + 1
        store.put(COLLECTION, wf_id, wf)
        store.put(EXECUTIONS, exec_id, {
            "workflow_id": wf_id, "name": wf["name"], "tasks": task_ids,
            "created_at": now_iso(),
        })
        await events.publish(EVT_SYSTEM, {"type": "workflow_started", "name": wf["name"]})
        return {"execution_id": exec_id, "tasks": task_ids}

    # -- phrase + schedule triggers --------------------------------------------
    async def check_phrase_triggers(self, message: str) -> int:
        fired = 0
        for wf in self.list():
            trig = wf.get("trigger") or {}
            if trig.get("type") == "phrase" and trig.get("phrase", "").lower() in message.lower():
                await self.run(wf["id"])
                fired += 1
        return fired

    def start_scheduler(self, interval_seconds: int = 60) -> None:
        if self._scheduler_task is None or self._scheduler_task.done():
            self._scheduler_task = asyncio.create_task(self._scheduler_loop(interval_seconds))

    async def stop_scheduler(self) -> None:
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass

    async def _scheduler_loop(self, interval: int) -> None:
        while True:
            try:
                for wf in self.list():
                    trig = wf.get("trigger") or {}
                    if trig.get("type") != "schedule" or not wf.get("enabled"):
                        continue
                    await self.run(wf["id"])
            except Exception:  # noqa: BLE001
                log.exception("scheduler tick failed")
            await asyncio.sleep(interval)


workflow_engine = WorkflowEngine()
