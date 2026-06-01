from app.core.runtime.task_registry import (
    task_registry
)

from app.core.runtime.dispatcher import (
    dispatcher
)

from app.core.runtime.lifecycle import (
    lifecycle
)


class Orchestrator:

    def run(
        self,
        goal: str
    ):

        task = (
            task_registry.create_task(
                goal
            )
        )

        lifecycle.start(task)

        try:

            result = dispatcher.dispatch(
                goal
            )

            lifecycle.complete(
                task,
                str(result)
            )

        except Exception:

            lifecycle.fail(task)

        return task


orchestrator = Orchestrator()