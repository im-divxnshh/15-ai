class TTS:

    def speak(
        self,
        text: str
    ):

        return {
            "audio": None,
            "text": text
        }


tts = TTS()