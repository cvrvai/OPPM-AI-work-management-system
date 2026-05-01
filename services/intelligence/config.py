"""Intelligence service configuration."""

from shared.config import SharedSettings


class IntelligenceSettings(SharedSettings):
    """Intelligence-service-specific settings."""
    # OpenAI (for embeddings + optional LLM)
    openai_api_key: str = ""

    # Ollama
    ollama_url: str = "http://localhost:11434"

    # Anthropic
    anthropic_api_key: str = ""

    # Kimi
    kimi_api_key: str = ""

    # DeepSeek
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"

    model_config = {"env_file": ".env", "extra": "ignore"}


_settings = None


def get_settings() -> IntelligenceSettings:
    global _settings
    if _settings is None:
        _settings = IntelligenceSettings()
    return _settings
