from app.services.voice.stt import stt
from app.core.brain.brain import brain


class VoiceController:

    def process(
        self,
        audio_path
    ):

        text = stt.transcribe(
            audio_path
        )

        response = brain.process(
            text
        )

        return {
            "speech": text,
            "response": response
        }


voice_controller = VoiceController()