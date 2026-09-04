"""Lifecycle (M03) — startup/shutdown wiring of the whole runtime."""
from __future__ import annotations

import logging

from app.core.brain.brain import brain
from app.core.runtime.task_executor import task_executor
from app.core.runtime.task_queue import task_queue
from app.services.tools.registry import tool_registry

log = logging.getLogger("runtime.lifecycle")


async def startup() -> None:
    """Wire everything together (avoids circular imports) and start the queue."""
    from app.core.memory.manager import memory

    brain.wire(memory=memory, tools_executor=tool_registry)
    task_queue.wire(task_executor)
    task_queue.start()
    log.info("runtime started — brain wired, queue running")


async def shutdown() -> None:
    await task_queue.stop()
    log.info("runtime stopped")
