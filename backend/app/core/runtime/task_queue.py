"""Task Queue (M08) — asyncio background queue with priorities + retries.

Deliberately Redis-free: priorities are just queue lanes, retries are
bounded, and everything is visible in the doc store for the UI.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from app.core.events.bus import (
    EVT_AGENT_FINISHED,
    EVT_AGENT_STARTED,
    EVT_TASK_COMPLETED,
    EVT_TASK_CREATED,
    EVT_TASK_FAILED,
    bus as events,
)
from app.core.memory.store import store
from app.core.registry import registry
from app.core.runtime.schemas import Task, TaskState

log = logging.getLogger("runtime.queue")

QUEUES: list[asyncio.Queue] = []  # one lane per priority (0..3), index = priority


def _persist(task: Task) -> None:
    store.put("runtime_tasks", task.id, task.model_dump(mode="json"))


class TaskQueue:
    def __init__(self, workers_per_lane: int = 1) -> None:
        self.workers_per_lane = workers_per_lane
        self._workers: list[asyncio.Task] = []
        self._executor = None

    def wire(self, executor) -> None:
        self._executor = executor

    # -- lifecycle -----------------------------------------------------------
    def start(self) -> None:
        global QUEUES
        QUEUES = [asyncio.Queue() for _ in range(4)]
        for prio, lane in enumerate(QUEUES):
            for i in range(self.workers_per_lane):
                self._workers.append(asyncio.create_task(self._worker(lane, prio, i)))
        log.info("task queue started (4 lanes x %s workers)", self.workers_per_lane)

    async def stop(self) -> None:
        for w in self._workers:
            w.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()

    # -- api ---------------------------------------------------------------
    async def submit(self, task: Task) -> bool:
        if not QUEUES:
            self.start()
        _persist(task)
        await events.publish(EVT_TASK_CREATED, {"task_id": task.id, "title": task.title, "agent": task.agent})
        lane = QUEUES[min(task.priority, 3)]
        await lane.put(task)
        return True

    def stats(self) -> dict:
        lanes = {str(p): q.qsize() for p, q in enumerate(QUEUES)} if QUEUES else {}
        return {"lanes": lanes, "workers": len(self._workers)}

    # -- worker --------------------------------------------------------------
    async def _worker(self, lane: asyncio.Queue, prio: int, idx: int) -> None:
        while True:
            task = await lane.get()
            try:
                if task.state == TaskState.CANCELLED:
                    continue
                await self._run(task)
            except Exception:  # noqa: BLE001
                log.exception("worker %s-%s crashed on task %s", prio, idx, task.id)
            finally:
                lane.task_done()

    async def _run(self, task: Task) -> None:
        task.state = TaskState.RUNNING
        task.attempts += 1
        task.started_at = datetime.now(timezone.utc)
        _persist(task)
        registry.set_status(task.agent, "working", task.title)
        await events.publish(EVT_AGENT_STARTED, {"agent": task.agent, "task_id": task.id, "action": task.title})

        result, error = None, None
        try:
            if self._executor is not None:
                result = await self._executor.execute(task)
            else:
                error = "no executor wired"
        except Exception as exc:  # noqa: BLE001
            error = str(exc)

        if error and task.attempts < task.max_attempts:
            log.warning("task %s failed (%s), retrying", task.id, error)
            retry = task.model_copy(update={"state": TaskState.QUEUED, "error": error})
            _persist(retry)
            await QUEUES[min(retry.priority, 3)].put(retry)
            registry.set_status(task.agent, "idle")
            return

        task.result = result
        task.error = error
        task.state = TaskState.FAILED if error else TaskState.DONE
        task.finished_at = datetime.now(timezone.utc)
        _persist(task)
        registry.set_status(task.agent, "finished")
        if task.state == TaskState.DONE:
            await events.publish(EVT_TASK_COMPLETED, {"task_id": task.id, "title": task.title, "agent": task.agent})
        else:
            await events.publish(EVT_TASK_FAILED, {"task_id": task.id, "title": task.title, "agent": task.agent, "error": error})
        await events.publish(EVT_AGENT_FINISHED, {"agent": task.agent, "task_id": task.id})


task_queue = TaskQueue()
