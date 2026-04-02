from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Supabase
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""

    # JWT
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"

    # GitHub
    github_webhook_secret: str = ""

    # AI providers
    ollama_url: str = "http://localhost:11434"
    anthropic_api_key: str = ""
    kimi_api_key: str = ""
    openai_api_key: str = ""

    # RAG / Embedding
    embedding_provider: str = "openai"  # openai | ollama
    embedding_model: str = "text-embedding-3-small"
    embedding_dimension: int = 1536
    rag_max_context_chars: int = 6000
    rag_memory_limit: int = 20

    # Email (Resend)
    resend_api_key: str = ""
    app_url: str = "http://localhost:5173"
    email_from: str = "OPPM <noreply@oppm.dev>"

    # App
    cors_origins: str = "http://localhost:5173,http://localhost:5174,http://localhost:5175"
    debug: bool = True

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
