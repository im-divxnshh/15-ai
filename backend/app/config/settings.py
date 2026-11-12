"""Central configuration for the 15-AI system.

Everything is env-driven and every external service is OPTIONAL.
If a service is not configured the system degrades gracefully to
local in-process / on-disk fallbacks so the whole thing ALWAYS runs.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")


class Settings(BaseSettings):
    # ---- Groq is the only model provider ----
    groq_api_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model: str = "openai/gpt-oss-20b"
    nova_llm_model: str = "openai/gpt-oss-120b"
    default_agent_model: str = "openai/gpt-oss-20b"

    # ---- Embeddings ----
    embeddings_provider: str = "local"  # local only
    embeddings_model: str = "embedding-3"

    # ---- Firebase ----
    firebase_credentials: str = ""  # one-line JSON string
    firebase_project_id: str = ""

    # ---- Neon Postgres (pgvector) ----
    neon_url: str = ""

    # ---- Cloudflare R2 ----
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket: str = ""

    # ---- App ----
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: str = "http://localhost:3000"
    user_name: str = "Boss"

    # ---- Derived flags ----
    @property
    def llm_ready(self) -> bool:
        return bool(self.groq_api_key)

    @property
    def firebase_ready(self) -> bool:
        return bool(self.firebase_credentials or self.firebase_project_id)

    @property
    def neon_ready(self) -> bool:
        return bool(self.neon_url)

    @property
    def r2_ready(self) -> bool:
        return bool(self.r2_account_id and self.r2_access_key_id and self.r2_secret_access_key and self.r2_bucket)

    @property
    def search_ready(self) -> bool:
        return self.llm_ready  # tool integration remains to be verified

    def firebase_credentials_dict(self) -> dict | None:
        """Parse the FIREBASE_CREDENTIALS env var (one-line JSON) into a dict."""
        if not self.firebase_credentials:
            return None
        try:
            return json.loads(self.firebase_credentials)
        except json.JSONDecodeError:
            return None


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
