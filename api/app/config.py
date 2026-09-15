from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # openai_api_key: str
    OWNER: str

    model_config = {
        "env_file": ROOT / ".env",
        "extra": "ignore",
    }

    @property
    def is_production(self) -> bool:
        return self.env == "production"


@lru_cache
def get_settings() -> Settings:
    """Cache settings instance - loaded once, reused everywhere."""
    return Settings()
