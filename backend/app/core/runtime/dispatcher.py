from app.core.runtime.task_executor import (
    task_executor
)


class Dispatcher:

    def dispatch(
        self,
        goal: str
    ):

        return task_executor.execute(
            goal
        )


dispatcher = Dispatcher()