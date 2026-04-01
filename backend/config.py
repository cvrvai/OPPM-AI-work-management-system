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

    # App
    cors_origins: str = "http://localhost:5173,http://localhost:5174,http://localhost:5175"
    debug: bool = True

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
