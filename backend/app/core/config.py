"""
Application configuration.

All values are sourced from environment variables (see .env.example).
Nothing here is hardcoded secrets — only defaults safe to commit.
"""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=["../.env", ".env"], extra="ignore")

    # --- LLM provider ---
    # "groq" (default, free-tier, zero local setup risk) or "ollama" (local, free, zero cost)
    llm_provider: str = "groq"
    llm_model: str = "openai/gpt-oss-20b"
    groq_api_key: str = ""
    auth_secret: str = "omnicare-assessment-dev-secret-change-me"
    ollama_base_url: str = "http://localhost:11434"

    # --- Data locations ---
    # Resolved relative to the repo root so it works both locally and in Docker.
    data_dir: Path = Path(__file__).resolve().parents[3] / "data"
    policy_doc_path: Path = data_dir / "sample_policy.md"
    claims_db_path: Path = data_dir / "mock_claims.json"

    # --- RAG ---
    chunk_size: int = 500          # characters per chunk; policy doc is short, keep chunks small
    chunk_overlap: int = 50
    rag_top_k: int = 3             # retrieve only the most relevant chunks (token efficiency)
    rag_min_relevance: float = 0.25 # below this, we say "not found" instead of guessing

    # --- Safety / loop protection ---
    max_tool_calls_per_turn: int = 2
    max_agent_steps: int = 4
    llm_timeout_seconds: int = 20

    # --- App ---
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Cached so we parse the environment once per process."""
    return Settings()
