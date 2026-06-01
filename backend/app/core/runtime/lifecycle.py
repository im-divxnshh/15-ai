from loguru import logger

from app.core.runtime.models import (
    TaskStatus
)

from app.core.runtime.persistence import (
    task_persistence
)


class Lifecycle:

    def start(
        self,
        task
    ):

        task.status = (
            TaskStatus.RUNNING
        )

        task_persistence.save(
            task
        )

        logger.info(
            f"Task Started: {task.id}"
        )

    def complete(
        self,
        task,
        result
    ):

        task.status = (
            TaskStatus.COMPLETED
        )

        task.result = str(
            result
        )

        task_persistence.save(
            task
        )

        logger.info(
            f"Task Completed: {task.id}"
        )

    def fail(
        self,
        task,
        error=None
    ):

        task.status = (
            TaskStatus.FAILED
        )

        if error:

            task.result = str(
                error
            )

        task_persistence.save(
            task
        )

        logger.error(
            f"Task Failed: {task.id}"
        )


lifecycle = Lifecycle()