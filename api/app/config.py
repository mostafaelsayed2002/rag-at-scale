"""Application settings, from the environment or the repository .env file."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
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

    google_api_key: str = Field(min_length=1)

    # Must match the model the corpus was embedded with.
    embedding_model: str = "models/gemini-embedding-2"
    embedding_dim: int = 768

    # Cheapest tier is enough: answers come from the retrieved passages.
    llm_model: str = "gemini-3.5-flash-lite"

    # Zero, so the same question gives the same (cacheable) answer.
    llm_temperature: float = 0.0

    # None keeps the model default: 0 is rejected, 128 was slower.
    llm_thinking_budget: int | None = None

    # Passages sent to the model. More costs tokens and adds noise.
    retrieve_k: int = 6

    # LangSmith tracing. Off unless explicitly turned on: it sends every
    # question and every answer to a third party, which should be a decision
    # rather than something that happens because a key is present.
    langsmith_tracing: bool = False
    langsmith_api_key: str | None = None
    langsmith_project: str = "rag-at-scale"
    langsmith_endpoint: str = "https://api.smith.langchain.com"

    # Published prices, used to turn real token counts into a cost estimate.
    # Settings rather than constants: a price is not something code can
    # measure, and anything shown from these is labelled an estimate.
    # https://ai.google.dev/gemini-api/docs/pricing#gemini-3.5-flash-lite
    usd_per_million_input_tokens: float = 0.3
    usd_per_million_output_tokens: float = 2.5

    # Required: holds the answer cache and the analytics counters.
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
