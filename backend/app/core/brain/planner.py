from app.core.brain.models import TaskPlan

class Planner:

    def create_plan(
        self,
        goal: str,
        intent: str
    ):

        return TaskPlan(
            goal=goal,
            intent=intent,
            priority="high",
            tasks=[
                f"Analyze request: {goal}",
                "Generate execution strategy",
                "Validate solution"
            ]
        )

planner = Planner()