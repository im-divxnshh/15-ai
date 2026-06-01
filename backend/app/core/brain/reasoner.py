class Reasoner:

    def analyze(self, plan):

        return f"""
Goal:
{plan.goal}

Intent:
{plan.intent}

Tasks:
{", ".join(plan.tasks)}
"""

reasoner = Reasoner()