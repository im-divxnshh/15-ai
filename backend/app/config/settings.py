from dotenv import load_dotenv
import os

load_dotenv()


class Settings:

    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY")
    DATABASE_URL: str = os.getenv("DATABASE_URL")
    UPSTASH_REDIS_REST_URL: str = os.getenv("UPSTASH_REDIS_REST_URL")
    UPSTASH_REDIS_REST_TOKEN: str = os.getenv("UPSTASH_REDIS_REST_TOKEN")


settings = Settings()