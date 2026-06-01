from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy import DateTime

from datetime import datetime

from app.services.database.base import Base


class Conversation(Base):

    __tablename__ = "conversations"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    user_message = Column(Text)

    assistant_message = Column(Text)

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )


class ProjectMemory(Base):

    __tablename__ = "project_memories"

    id = Column(
        Integer,
        primary_key=True
    )

    project_name = Column(
        String(255)
    )

    data = Column(Text)


class DecisionMemory(Base):

    __tablename__ = "decision_memories"

    id = Column(
        Integer,
        primary_key=True
    )

    decision = Column(Text)

    reason = Column(Text)
 
class TaskRecord(Base):

    __tablename__ = "tasks"

    id = Column(
        String,
        primary_key=True
    )

    goal = Column(Text)

    status = Column(
        String(50)
    )

    result = Column(Text)

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )    