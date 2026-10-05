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
    # Semantic cache: a new question this similar to an answered one gets that
    # answer. Measured on bge-base: real paraphrases score 0.66-0.95 and
    # different legal questions up to 0.93 ("minimum wage in 2026" vs "in
    # 2025"), so only near-identical rewordings are safe to reuse.
    semantic_cache_threshold: float = 0.95
    # Questions kept for the semantic cache. Every lookup reads them all
    # (~2 KB each), so it stays small.
    semantic_cache_size: int = 2000
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
    # retrieve_k. The right chunk was among the top 100 for 94% of the golden
    # questions but in the top 6 for only 39%.
    rerank_candidates: int = 100
    # Recitals ("this Regulation aims to...") sound like questions and push the
    # articles with the rules out of the candidates: at most this many.
    # Hit@6 with Voyage: 0.80 with the cap, 0.77 without.
    max_recitals: int = 1
    # Voyage AI's reranker, an API: reads question and passage together, so it
    # judges "does this answer it" rather than "does this sound similar".
    # Hit@6 0.80 vs 0.56 for bge-reranker-base on CPU; ~0.7 s per question,
    # ~$0.002 per question at 100 candidates.
    rerank_model: str = "rerank-2.5"
    voyage_api_key: str = Field(min_length=1)
    # HNSW candidates per search. Must be at least the rows asked for (the
    # candidates, plus the recitals skipped), or the index returns fewer.
    hnsw_ef_search: int = 400

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
