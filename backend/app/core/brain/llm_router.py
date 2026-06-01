from app.services.llm.groq_client import ask_groq

class LLMRouter:

    def generate(
        self,
        system_prompt,
        user_prompt
    ):

        return ask_groq(
            system_prompt,
            user_prompt
        )

llm_router = LLMRouter()