"""Builds the pydantic-ai model from Django settings (LLM_* env vars)."""

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from pydantic_ai.models import Model


def build_model() -> Model:
    if not settings.LLM_API_KEY:
        raise ImproperlyConfigured('LLM_API_KEY is not set (see backend/.env.example).')

    if settings.LLM_PROVIDER == 'openai':
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openai import OpenAIProvider

        provider = OpenAIProvider(base_url=settings.LLM_BASE_URL or None, api_key=settings.LLM_API_KEY)
        return OpenAIChatModel(
            settings.LLM_MODEL, provider=provider, settings={'temperature': 0.9, 'max_tokens': 1200}
        )

    if settings.LLM_PROVIDER == 'anthropic':
        from pydantic_ai.models.anthropic import AnthropicModel, AnthropicModelSettings
        from pydantic_ai.providers.anthropic import AnthropicProvider

        # Current Claude models reject sampling params; effort keeps short comedic output cheap and fast.
        model_settings = AnthropicModelSettings(max_tokens=4000, anthropic_effort='low')
        return AnthropicModel(
            settings.LLM_MODEL, provider=AnthropicProvider(api_key=settings.LLM_API_KEY), settings=model_settings
        )

    raise ImproperlyConfigured(f'Unknown LLM_PROVIDER {settings.LLM_PROVIDER!r} (expected openai or anthropic).')
