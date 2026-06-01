from loguru import logger

from app.core.brain.classifier import classifier
from app.core.brain.planner import planner
from app.core.brain.reasoner import reasoner
from app.core.brain.risk_engine import risk_engine
from app.core.brain.llm_router import llm_router
from app.core.brain.response_builder import response_builder
from app.core.brain.prompts import JARVIS_SYSTEM_PROMPT

from app.core.memory.manager import (
    memory_manager
)

from app.core.memory.retriever import (
    memory_retriever
)


class Brain:

    def process(
        self,
        goal: str
    ):

        logger.info(
            f"New Goal Received: {goal}"
        )

        # ---------------------------
        # Intent Classification
        # ---------------------------

        intent = classifier.classify(
            goal
        )

        logger.info(
            f"Intent Detected: {intent}"
        )

        # ---------------------------
        # Memory Retrieval
        # ---------------------------

        try:

            memory_context = (
                memory_retriever.retrieve_context(
                    goal
                )
            )

        except Exception as e:

            logger.error(
                f"Memory Retrieval Failed: {str(e)}"
            )

            memory_context = ""

        # ===================================================
        # CHAT MODE
        # ===================================================

        if intent in [
            "greeting",
            "chat",
            "general"
        ]:

            prompt = f"""
Memory Context:
{memory_context}

User Message:
{goal}
"""

            llm_response = (
                llm_router.generate(
                    system_prompt=
                    JARVIS_SYSTEM_PROMPT,
                    user_prompt=prompt
                )
            )

            try:

                memory_manager.save_conversation(
                    user_message=goal,
                    assistant_message=llm_response
                )

                memory_manager.save_vector_memory(
                    text=goal
                )

            except Exception as e:

                logger.error(
                    f"Memory Save Failed: {str(e)}"
                )

            return response_builder.build(
                goal=goal,
                intent=intent,
                analysis="",
                risks=[],
                llm_response=llm_response
            )

        # ===================================================
        # AGENT MODE
        # ===================================================

        logger.info(
            "Entering Agent Mode"
        )

        plan = planner.create_plan(
            goal=goal,
            intent=intent
        )

        analysis = reasoner.analyze(
            plan
        )

        risks = risk_engine.evaluate(
            plan
        )

        prompt = f"""
Memory Context:
{memory_context}

Goal:
{goal}

Intent:
{intent}

Plan:
{plan}

Analysis:
{analysis}

Risks:
{risks}
"""

        llm_response = (
            llm_router.generate(
                system_prompt=
                JARVIS_SYSTEM_PROMPT,
                user_prompt=prompt
            )
        )

        try:

            memory_manager.save_conversation(
                user_message=goal,
                assistant_message=llm_response
            )

            memory_manager.save_vector_memory(
                text=goal
            )

            memory_manager.save_session(
                session_id="default",
                context=goal
            )

        except Exception as e:

            logger.error(
                f"Memory Save Failed: {str(e)}"
            )

        return response_builder.build(
            goal=goal,
            intent=intent,
            analysis=analysis,
            risks=risks,
            llm_response=llm_response
        )


brain = Brain()