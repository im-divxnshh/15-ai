from app.core.memory.vectors import (
    vector_memory
)


class MemorySearch:

    def search(
        self,
        query
    ):

        results = []

        memories = (
            vector_memory.get_all()
        )

        for memory in memories:

            if query.lower() in (
                memory["text"]
                .lower()
            ):

                results.append(
                    memory
                )

        return results


memory_search = MemorySearch()