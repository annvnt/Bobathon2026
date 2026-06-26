"""Central configuration, loaded from environment / .env file."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_ROOT.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Relational DB
    DATABASE_URL: str = "sqlite:///./ecocomply.db"

    # Vector store
    CHROMA_DIR: str = "./.chroma"

    # LLM
    LLM_PROVIDER: str = "openrouter"  # openrouter | watsonx
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "openai/gpt-4o-mini"
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    WATSONX_API_KEY: str = ""
    WATSONX_PROJECT_ID: str = ""
    WATSONX_URL: str = "https://eu-de.ml.cloud.ibm.com"
    WATSONX_MODEL_ID: str = "ibm/granite-13b-instruct-v2"

    # Alerts
    ALERTS_PROVIDER: str = "mock"  # mock | twilio
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_FROM_NUMBER: str = ""
    TWILIO_TEST_TO_NUMBER: str = ""

    # Scheduler
    ENABLE_SCHEDULER: bool = True
    SYNC_HOUR: int = 0
    SYNC_MINUTE: int = 0

    # CORS
    FRONTEND_ORIGIN: str = "http://localhost:3000"

    # Path to the bundled challenge dataset (used for seeding + mock MCP)
    @property
    def dataset_dir(self) -> Path:
        return REPO_ROOT / "Dataset"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
