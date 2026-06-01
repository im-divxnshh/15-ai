from app.core.runtime.task_registry import (
    task_registry
)


class RuntimeAnalytics:

    def total_tasks(self):

        return len(
            task_registry.tasks
        )


analytics = RuntimeAnalytics()