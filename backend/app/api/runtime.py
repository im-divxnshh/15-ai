from fastapi import APIRouter

from app.core.runtime.orchestrator import (
    orchestrator
)

from app.core.runtime.task_registry import (
    task_registry
)

router = APIRouter(
    prefix="/runtime",
    tags=["Runtime"]
)


@router.post("/task")
def create_task(
    payload: dict
):

    goal = payload.get(
        "goal"
    )

    task = orchestrator.run(
        goal
    )

    return task


@router.get("/task/{task_id}")
def get_task(
    task_id: str
):

    return task_registry.get_task(
        task_id
    )


@router.get("/tasks")
def get_tasks():

    return task_registry.tasks