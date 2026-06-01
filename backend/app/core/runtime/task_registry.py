import uuid

from app.core.runtime.schemas import (
    Task
)

from app.core.runtime.models import (
    TaskStatus
)


class TaskRegistry:

    def __init__(self):

        self.tasks = {}

    def create_task(
        self,
        goal: str
    ):

        task = Task(
            id=str(uuid.uuid4()),
            goal=goal,
            status=TaskStatus.PENDING
        )

        self.tasks[
            task.id
        ] = task

        return task

    def get_task(
        self,
        task_id: str
    ):

        return self.tasks.get(
            task_id
        )


task_registry = TaskRegistry()