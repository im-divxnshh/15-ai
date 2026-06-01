from app.core.memory.manager import memory_manager


class MemoryRetriever:

    def retrieve_context(
        self,
        query: str
    ):

        memories = memory_manager.search_memory(
            query
        )

        if not memories:
            return ""

        context = []

        for memory in memories:

            context.append(
                memory["text"]
            )

        return "\n".join(context)


memory_retriever = MemoryRetriever()