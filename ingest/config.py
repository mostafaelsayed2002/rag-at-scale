"""Settings for the ingestion pipeline.

Values come from the environment or the repository's .env file, with the
defaults below used when neither sets them. Anything here can be overridden
for one run without editing code:

    EMBED_TEXTS_PER_MINUTE=2000 uv run python ingest/ingest.py
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Anchored to the repository, so it loads from any working directory.
        env_file=ROOT / ".env",
        extra="ignore",
        case_sensitive=False,
    )

    # Optional here: only the embedding step needs it, and it checks on first use.
    google_api_key: str | None = None

    # Google's cheapest embedding model: $0.20 per million text tokens, with a
    # free tier. Reads up to 8,192 tokens per text.
    embedding_model: str = "models/gemini-embedding-2"

    # Gemini can return any size from 128 to 3072; 768 is the smallest
    # recommended one. Must match the vector column in db/migrations.
    embedding_dim: int = 768

    # Texts per API call. The API's own maximum is 100.
    embed_batch: int = 100

    # Free-tier quota is about 100 texts a minute. Raise this once billing is
    # enabled on the project, or the corpus takes hours.
    embed_texts_per_minute: int = 90

    database_url: str

    data_dir: Path = ROOT / "data"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Read the settings once and reuse them."""
    return Settings()


settings = get_settings()
