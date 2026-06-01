from pydantic import BaseModel

class ConversationMemory(BaseModel):
    user_message: str
    assistant_message: str

class ProjectMemory(BaseModel):
    project_name: str
    data: dict

class DecisionMemory(BaseModel):
    decision: str
    reason: str