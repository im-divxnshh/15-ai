from app.services.database.database import SessionLocal

from app.services.database.models import DecisionMemory


class DecisionStore:

    def save(
        self,
        decision,
        reason
    ):

        db = SessionLocal()

        record = DecisionMemory(
            decision=decision,
            reason=reason
        )

        db.add(record)

        db.commit()

        db.close()

        return {
            "status": "saved"
        }


decision_store = DecisionStore()