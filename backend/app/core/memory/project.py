from app.services.database.database import SessionLocal

from app.services.database.models import ProjectMemory


class ProjectStore:

    def save(
        self,
        project_name,
        data
    ):

        db = SessionLocal()

        project = ProjectMemory(
            project_name=project_name,
            data=str(data)
        )

        db.add(project)

        db.commit()

        db.close()

        return {
            "status": "saved"
        }


project_store = ProjectStore()