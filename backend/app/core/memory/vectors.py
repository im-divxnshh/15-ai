import json
import os

VECTOR_FILE = "vector_memory.json"


class VectorMemory:

    def __init__(self):

        if not os.path.exists(VECTOR_FILE):

            with open(
                VECTOR_FILE,
                "w"
            ) as f:

                json.dump(
                    [],
                    f
                )

    def save_memory(
        self,
        text
    ):

        with open(
            VECTOR_FILE,
            "r"
        ) as f:

            data = json.load(f)

        data.append(
            {
                "text": text
            }
        )

        with open(
            VECTOR_FILE,
            "w"
        ) as f:

            json.dump(
                data,
                f,
                indent=4
            )

    def get_all(self):

        with open(
            VECTOR_FILE,
            "r"
        ) as f:

            return json.load(f)


vector_memory = VectorMemory()