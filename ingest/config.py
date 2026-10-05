"""Settings for the ingestion pipeline.

Values come from the environment or the repository's .env file, with the
defaults below used when neither sets them. Anything here can be overridden
for one run without editing code:

    CHUNK_CHARS=1200 uv run --package rag-ingest python ingest/ingest.py chunk --count-only
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

    # --- Corpus (written by download.py) ---
    corpus_dir: Path = ROOT / "data" / "eurlex"

    # --- Chunking ---
    # Characters, not tokens: ~1,600 characters of legal English is ~360
    # tokens, comfortably under the embedding model's 512-token limit.
    chunk_chars: int = 1600
    overlap_chars: int = 200
    # Documents per shard file. Resuming works shard by shard, so smaller is
    # finer-grained; larger means fewer files.
    shard_docs: int = 500

    # --- Embedding ---
    # Local, free, no quota. Must be the same model the API embeds queries with.
    embedding_model: str = "BAAI/bge-base-en-v1.5"
    embedding_dim: int = 768
    # The model reads at most 512 tokens and silently drops the rest, so
    # chunks longer than this are split again before embedding.
    max_tokens: int = 512
    embed_batch: int = 32

    # The stages' folder under corpus_dir. A second one (WORK_NAME=work_v2)
    # holds a new chunking next to the current one until it proves better.
    work_name: str = "work"

    # Only the load stage needs it, so chunking and counting work without a database.
    database_url: str | None = None

    @property
    def pdf_dir(self) -> Path:
        return self.corpus_dir / "pdf"

    @property
    def acts_file(self) -> Path:
        return self.corpus_dir / "acts.jsonl"

    @property
    def work_dir(self) -> Path:
        """Where the stages hand over to each other: chunks, then vectors."""
        return self.corpus_dir / self.work_name


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Read the settings once and reuse them."""
    return Settings()


settings = get_settings()
