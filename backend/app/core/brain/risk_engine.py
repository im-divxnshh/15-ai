class RiskEngine:

    def evaluate(self, plan):

        risks = []

        if plan.intent == "technical":
            risks.append(
                "Implementation complexity may increase."
            )

        if plan.intent == "business":
            risks.append(
                "Market assumptions require validation."
            )

        return risks

risk_engine = RiskEngine()