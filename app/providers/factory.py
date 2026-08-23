"""
Provider Factory for Initializing Active LLM Backend
"""

from typing import Optional
from app.config import ProviderConfig
from app.providers.anthropic_provider import AnthropicProvider
from app.providers.base import BaseLLMProvider
from app.providers.gemini_provider import GeminiProvider
from app.providers.ollama_provider import OllamaProvider
from app.providers.openai_provider import OpenAIProvider


def create_provider(config: Optional[ProviderConfig] = None) -> BaseLLMProvider:
    """Instantiate and return the configured LLM provider."""
    if config is None:
        config = ProviderConfig()

    provider_name = config.provider.lower().strip()

    if provider_name == "ollama":
        return OllamaProvider(
            api_key=config.api_key,
            model=config.model,
            base_url=config.base_url,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            timeout_seconds=config.timeout_seconds,
        )
    elif provider_name in ("openai", "openrouter", "local"):
        return OpenAIProvider(
            api_key=config.api_key,
            model=config.model,
            base_url=config.base_url,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            timeout_seconds=config.timeout_seconds,
        )
    elif provider_name == "anthropic":
        return AnthropicProvider(
            api_key=config.api_key,
            model=config.model,
            base_url=config.base_url,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            timeout_seconds=config.timeout_seconds,
        )
    elif provider_name == "gemini":
        return GeminiProvider(
            api_key=config.api_key,
            model=config.model,
            base_url=config.base_url,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            timeout_seconds=config.timeout_seconds,
        )
    else:
        raise ValueError(
            f"Unsupported provider '{config.provider}'. Choose from: 'ollama', 'gemini', 'openai', 'anthropic', 'local'."
        )


def create_role_provider(config: Optional[ProviderConfig], role: str) -> BaseLLMProvider:
    """Create a provider specifically tuned for a specialist agent role (Directive v10)."""
    if config is None:
        config = ProviderConfig()

    role_lower = role.lower()
    if any(k in role_lower for k in ["doc", "document", "generation", "writer", "synthesis", "content"]):
        target_model = config.content_generation_model or config.model
        # Document generation needs extended timeout for model swap + long-form output on local GPU
        timeout = max(config.timeout_seconds, 600)
    else:
        target_model = config.orchestration_model or config.model
        timeout = config.timeout_seconds

    cfg_copy = config.model_copy()
    cfg_copy.model = target_model
    cfg_copy.timeout_seconds = timeout
    return create_provider(cfg_copy)

