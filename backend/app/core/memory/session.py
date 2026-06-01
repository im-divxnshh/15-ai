from app.core.memory.cache import cache


class SessionMemory:

    def save_context(
        self,
        session_id,
        context
    ):

        cache.set(
            f"session:{session_id}",
            context
        )

    def get_context(
        self,
        session_id
    ):

        return cache.get(
            f"session:{session_id}"
        )


session_memory = SessionMemory()