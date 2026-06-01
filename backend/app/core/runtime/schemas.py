from pydantic import BaseModel

from app.core.runtime.models import (
    TaskStatus
)


class Task(BaseModel):

    id: str

    goal: str

    status: TaskStatus

    result: str | None = None