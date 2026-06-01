from app.core.brain.models import BrainOutput

class ResponseBuilder:

    def build(
        self,
        goal,
        intent,
        analysis,
        risks,
        llm_response
    ):

        return BrainOutput(
            goal=goal,
            intent=intent,
            analysis=analysis,
            execution_plan=llm_response,
            risks=risks,
            response=llm_response
        )

response_builder = ResponseBuilder()