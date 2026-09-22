"""Application settings, from the environment or the repository .env file."""

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / ".env",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: str = "dev"
    log_level: str = "INFO"

    database_url: str = "postgresql://rag:rag@localhost:5432/rag"

    # Queries must be embedded with the model the corpus used: vectors from two
    # different models are not comparable, and the distances would be
    # meaningless rather than obviously wrong.
    google_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("GOOGLE_API_KEY", "GEMINI_API_KEY"),
    )
    embedding_model: str = "models/gemini-embedding-2"
    embedding_dim: int = 768

    # Shared cache. Empty disables it, so the API still runs with no Redis
    # around, just paying for every repeated query.
    redis_url: str = "redis://localhost:6379/0"
    # An hour. The corpus does not change between deployments, so this is a
    # limit on how long a stale answer could survive, not on correctness.
    cache_ttl: int = 3600

    # Where the corpus PDFs live, so the API can serve the file a citation
    # points at. Mounted read-only into the container.
    data_dir: Path = ROOT / "data"

    # 3000 is `npm run dev`, 3100 the preview server used while developing.
    # In production the frontend is same-origin behind nginx, so none apply.
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:3100"]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Read the settings once and reuse them."""
    return Settings()


settings = get_settings()
