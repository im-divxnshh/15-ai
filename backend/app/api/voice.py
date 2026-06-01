from fastapi import APIRouter
from fastapi import UploadFile
from fastapi import File
import tempfile

from app.services.voice.controller import (
    voice_controller
)

router = APIRouter(
    prefix="/voice",
    tags=["Voice"]
)


@router.post("/chat")
async def voice_chat(
    file: UploadFile = File(...)
):

    with tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".wav"
    ) as temp:

        content = await file.read()

        temp.write(content)

        path = temp.name

    return voice_controller.process(
        path
    )