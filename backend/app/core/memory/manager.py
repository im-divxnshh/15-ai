from app.core.memory.conversation import conversation_store
from app.core.memory.project import project_store
from app.core.memory.decisions import decision_store
from app.core.memory.session import session_memory
from app.core.memory.vectors import (
    vector_memory
)

from app.core.memory.search import (
    memory_search
)

class MemoryManager:

    def save_conversation(
        self,
        user_message,
        assistant_message
    ):

        return conversation_store.save(
            user_message,
            assistant_message
        )

    def save_project(
        self,
        project_name,
        data
    ):

        return project_store.save(
            project_name,
            data
        )

    def save_decision(
        self,
        decision,
        reason
    ):

        return decision_store.save(
            decision,
            reason
        )

    def save_session(
        self,
        session_id,
        context
    ):

        return session_memory.save_context(
            session_id,
            context
        )
    

    def get_session(
        self,
        session_id
    ):

        return session_memory.get_context(
            session_id
        )
    
    
    def save_vector_memory(
        self,
        text
    ):

        return vector_memory.save_memory(
            text
        )
        
    def search_memory(
        self,
        query
    ):

        return memory_search.search(
            query
        )


memory_manager = MemoryManager()