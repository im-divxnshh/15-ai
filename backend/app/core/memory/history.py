class ConversationHistory:

    def build_context(
        self,
        messages
    ):

        return "\n".join(messages)