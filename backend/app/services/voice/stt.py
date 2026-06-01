from groq import Groq

from app.config.settings import settings


class STT:

    def __init__(self):

        self.client = Groq(
            api_key=settings.GROQ_API_KEY
        )

    def transcribe(
        self,
        audio_path
    ):

        with open(
            audio_path,
            "rb"
        ) as file:

            result = (
                self.client.audio.transcriptions.create(
                    file=file,
                    model="whisper-large-v3"
                )
            )

        return result.text


stt = STT()