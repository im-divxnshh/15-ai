from fastapi import APIRouter
from pydantic import BaseModel

from app.core.brain.brain import brain

router = APIRouter()


class ChatRequest(BaseModel):
    message: str


@router.post("/chat")
def chat(req: ChatRequest):

    result = brain.process(
        req.message
    )

    return {
        "message":
        result.response
    }