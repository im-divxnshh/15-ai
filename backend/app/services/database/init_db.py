from app.services.database.base import Base
from app.services.database.database import engine

from app.services.database.models import (
    Conversation,
    ProjectMemory,
    DecisionMemory
)

Base.metadata.create_all(
    bind=engine
)

print(
    "Database Initialized"
)