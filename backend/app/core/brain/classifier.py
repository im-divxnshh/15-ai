class IntentClassifier:

    def classify(
        self,
        message: str
    ):

        msg = message.lower().strip()

        greetings = [
            "hi",
            "hello",
            "hey",
            "yo",
            "good morning",
            "good afternoon",
            "good evening"
        ]

        technical_words = [
            "code",
            "api",
            "backend",
            "frontend",
            "database",
            "software",
            "python",
            "javascript",
            "react",
            "nextjs",
            "fastapi",
            "bug",
            "error",
            "fix"
        ]

        business_words = [
            "startup",
            "market",
            "pricing",
            "revenue",
            "sales",
            "customer",
            "business"
        ]

        planning_words = [
            "plan",
            "roadmap",
            "strategy",
            "architecture",
            "design",
            "build",
            "create",
            "develop"
        ]

        analysis_words = [
            "analyze",
            "review",
            "audit",
            "evaluate",
            "compare"
        ]

        chat_words = [
            "how are you",
            "what can you do",
            "who are you"
        ]

        if msg in greetings:
            return "greeting"

        if any(
            word in msg
            for word in chat_words
        ):
            return "chat"

        if any(
            word in msg
            for word in technical_words
        ):
            return "technical"

        if any(
            word in msg
            for word in business_words
        ):
            return "business"

        if any(
            word in msg
            for word in planning_words
        ):
            return "planning"

        if any(
            word in msg
            for word in analysis_words
        ):
            return "analysis"

        return "general"


classifier = IntentClassifier()