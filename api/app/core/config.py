"""Application settings, from the environment or the repository .env file."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# api/app/core/config.py -> repository root.
ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / ".env",
        extra="ignore",
        case_sensitive=False,
    )

    # --- App ---
    app_env: str = "dev"  # "production" switches logs to JSON
    log_level: str = "INFO"

    # --- Storage ---
    database_url: str
    redis_url: str
    cache_ttl: int = 3600
    data_dir: Path = ROOT / "data"

    # --- Embeddings (local) ---
    # Must match the model the corpus was embedded with (ingest/config.py).
    embedding_model: str = "BAAI/bge-base-en-v1.5"
    embedding_dim: int = 768
    # bge was trained with this prefix on queries (never on passages).
    query_prefix: str = "Represent this sentence for searching relevant passages: "
    embedding_device: str = "cpu"  # one short question: ~30 ms on CPU

    # --- Gemini (answers) ---
    google_api_key: str = Field(min_length=1)
    # Cheapest tier is enough: answers come from the retrieved passages.
    llm_model: str = "gemini-3.5-flash-lite"
    llm_temperature: float = 0.0  # same question, same (cacheable) answer
    # None keeps the model default: 0 is rejected, 128 was slower.
    llm_thinking_budget: int | None = None

    # --- Retrieval ---
    retrieve_k: int = 6  # passages sent to the model; more adds cost and noise
    # The vector search fetches this many, the reranker keeps the best
    # retrieve_k. The right chunk was in the top 50 for 65% of the golden
    # questions but in the top 6 for only 26%.
    rerank_candidates: int = 20
    # A cross-encoder: reads question and passage together, so it judges
    # "does this answer it" rather than "does this sound similar".
    rerank_model: str = "BAAI/bge-reranker-base"
    # Question + passage tokens the reranker reads. 512 (the model's maximum)
    # took 2.4 s per question on 20 candidates.
    rerank_max_tokens: int = 256
    # HNSW candidates per search: 99% recall@10 at ~12 ms on 1.06M chunks;
    # recall plateaus above it (benchmarks_hnsw/).
    hnsw_ef_search: int = 160

    # --- Cost estimate (USD per 1M tokens) ---
    # https://ai.google.dev/gemini-api/docs/pricing#gemini-3.5-flash-lite
    usd_per_million_input_tokens: float = 0.3
    usd_per_million_output_tokens: float = 2.5

    # --- LangSmith tracing (off by default: sends data to a third party) ---
    langsmith_tracing: bool = False
    langsmith_api_key: str | None = None
    langsmith_project: str = "rag-at-scale"
    langsmith_endpoint: str = "https://api.smith.langchain.com"

    # --- Rate limiting (per client IP, on /chat) ---
    rate_limit: str = "10/minute"

    # --- Web ---
    # Dev frontend only; in production it is same-origin behind nginx.
    cors_origins: list[str] = ["http://localhost:3000"]

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Read the settings once and reuse them."""
    return Settings()


settings = get_settings()
