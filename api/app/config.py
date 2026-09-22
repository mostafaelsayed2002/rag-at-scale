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

    # The answer is written from the retrieved passages, not from what the
    # model remembers, so the cheapest tier is the right default. Kept as a
    # setting so a better model is one line, not a code change.
    llm_model: str = "gemini-3.5-flash-lite"
    # Zero, so the same question gives the same answer. That is what makes a
    # cached answer honest rather than merely similar to a fresh one.
    llm_temperature: float = 0.0
    # Tokens the model may spend reasoning before it answers. None leaves the
    # model's own default alone, which is what we use: this model rejects a
    # budget of 0 outright, and a measured budget of 128 was slower than the
    # default rather than faster.
    llm_thinking_budget: int | None = None
    # Passages sent to the model. More context is not better: it costs tokens
    # and buries the relevant passage among near misses.
    retrieve_k: int = 6

    # Published prices, used to turn real token counts into a cost estimate.
    # Settings rather than constants: a price is not something code can
    # measure, and anything shown from these is labelled an estimate.
    usd_per_million_input_tokens: float = 0.10
    usd_per_million_output_tokens: float = 0.40

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
