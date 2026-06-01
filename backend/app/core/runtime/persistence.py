from app.services.database.database import SessionLocal
from app.services.database.models import TaskRecord


class TaskPersistence:

    def save(
        self,
        task
    ):

        db = SessionLocal()

        record = TaskRecord(
            id=task.id,
            goal=task.goal,
            status=task.status,
            result=task.result
        )

        db.merge(record)

        db.commit()

        db.close()


task_persistence = TaskPersistence()