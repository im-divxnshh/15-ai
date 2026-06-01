from app.core.brain.brain import (
    brain
)


class TaskExecutor:

    def execute(
        self,
        goal: str
    ):

        return brain.process(
            goal
        )


task_executor = TaskExecutor()