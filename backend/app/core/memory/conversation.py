from app.services.database.database import SessionLocal

from app.services.database.models import Conversation


class ConversationStore:

    def save(
        self,
        user_message,
        assistant_message
    ):

        db = SessionLocal()

        record = Conversation(
            user_message=user_message,
            assistant_message=assistant_message
        )

        db.add(record)

        db.commit()

        db.close()

        return {
            "status": "saved"
        }


conversation_store = ConversationStore()