from typing import Optional
from app.config import LLM_PROVIDER
from app.core.llm.base import BaseLLMProvider
from app.core.llm.gemini import GeminiProvider
from app.core.llm.openai import OpenAIProvider
from app.core.llm.anthropic import AnthropicProvider

def get_llm_provider(provider_name: Optional[str] = None) -> BaseLLMProvider:
    """
    Factory function to retrieve initialized LLM provider instance.
    Looks up database settings 'llm_provider' first, falls back to environment variable,
    and defaults to 'gemini'.
    """
    if not provider_name:
        from app.models.db import get_setting
        provider_name = get_setting("llm_provider") or LLM_PROVIDER or "gemini"

    provider_name = provider_name.lower()
    if provider_name == "gemini":
        return GeminiProvider()
    elif provider_name == "openai":
        return OpenAIProvider()
    elif provider_name == "anthropic":
        return AnthropicProvider()
    else:
        raise ValueError(f"Unsupported LLM provider: {provider_name}")
