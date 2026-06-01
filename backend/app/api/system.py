from fastapi import APIRouter

from app.core.memory.manager import memory_manager
from app.services.llm.groq_client import ask_groq

router = APIRouter()


@router.get("/system-test")
def system_test():

    results = {}

    # PostgreSQL
    try:

        memory_manager.save_conversation(
            "system_test",
            "postgres_ok"
        )

        results["postgres"] = "OK"

    except Exception as e:

        results["postgres"] = str(e)

    # Redis
    try:

        memory_manager.save_session(
            "health",
            "redis_ok"
        )

        value = memory_manager.get_session(
            "health"
        )

        results["redis"] = value

    except Exception as e:

        results["redis"] = str(e)

    # Vector Memory
    try:

        memory_manager.save_vector_memory(
            "FastAPI Test Memory"
        )

        vector_result = (
            memory_manager.search_memory(
                "FastAPI"
            )
        )

        results["vector"] = vector_result

    except Exception as e:

        results["vector"] = str(e)

    # Groq
    try:

        response = ask_groq(
            "You are a test assistant.",
            "Reply with OK"
        )

        results["groq"] = response

    except Exception as e:

        results["groq"] = str(e)

    return {
        "status": "completed",
        "results": results
    }