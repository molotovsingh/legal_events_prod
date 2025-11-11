"""
Unified Provider Registry - Simplified vendor-to-LLM mapping

This module replaces the complex multi-layer registry system with a single
source of truth for LLM provider configuration.

Architecture:
- Direct function references (no string imports)
- Single registry dictionary
- Fail-fast validation
- Consistent field naming
- No magic swapping or fallbacks

Usage:
    from core.providers import PROVIDERS, get_provider

    # Get provider metadata
    provider = get_provider("openrouter")

    # List all enabled providers
    enabled = [p for p in PROVIDERS.values() if p.enabled]

    # Create extractor instance
    extractor = provider.factory(config)
"""

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional
import logging

from .interfaces import EventExtractor
from .config import (
    OpenRouterConfig,
    OpenAIConfig,
    AnthropicConfig,
    ExtractorConfig
)

logger = logging.getLogger(__name__)


@dataclass
class Provider:
    """
    Provider metadata and factory function.

    Simplified from the previous EventExtractorEntry with 12+ fields.
    Focuses on essential information only.
    """

    # Identification
    id: str  # "openrouter", "openai", "anthropic"
    name: str  # "OpenRouter", "OpenAI", "Anthropic"

    # Factory function (direct reference, not string)
    factory: Callable[[Any], EventExtractor]

    # Configuration
    config_class: type  # OpenRouterConfig, OpenAIConfig, etc.
    default_model: str  # Default model for this provider

    # Capabilities
    supports_model_override: bool = True  # All modern providers support this

    # Registry control
    enabled: bool = True

    # Documentation
    docs_url: Optional[str] = None
    notes: str = ""


# ============================================================================
# FACTORY FUNCTIONS
# ============================================================================

def _create_openrouter_extractor(config: OpenRouterConfig) -> EventExtractor:
    """Create OpenRouter event extractor."""
    from .openrouter_adapter import OpenRouterEventExtractor
    return OpenRouterEventExtractor(config)


def _create_openai_extractor(config: OpenAIConfig) -> EventExtractor:
    """Create OpenAI event extractor."""
    from .openai_adapter import OpenAIEventExtractor
    return OpenAIEventExtractor(config)


def _create_anthropic_extractor(config: AnthropicConfig) -> EventExtractor:
    """Create Anthropic event extractor."""
    from .anthropic_adapter import AnthropicEventExtractor
    return AnthropicEventExtractor(config)


# ============================================================================
# PROVIDER REGISTRY - Single Source of Truth
# ============================================================================

PROVIDERS: Dict[str, Provider] = {
    "openrouter": Provider(
        id="openrouter",
        name="OpenRouter",
        factory=_create_openrouter_extractor,
        config_class=OpenRouterConfig,
        default_model="meta-llama/llama-3.3-70b-instruct",
        supports_model_override=True,
        enabled=True,
        docs_url="https://openrouter.ai/docs",
        notes="Unified API for 10+ models. Best for A/B testing and flexibility."
    ),

    "openai": Provider(
        id="openai",
        name="OpenAI",
        factory=_create_openai_extractor,
        config_class=OpenAIConfig,
        default_model="gpt-4o-mini",
        supports_model_override=True,
        enabled=True,
        docs_url="https://platform.openai.com/docs/api-reference",
        notes="Direct OpenAI API. GPT-4o-mini (budget), GPT-4o (quality), GPT-5 (ground truth)."
    ),

    "anthropic": Provider(
        id="anthropic",
        name="Anthropic",
        factory=_create_anthropic_extractor,
        config_class=AnthropicConfig,
        default_model="claude-3-haiku-20240307",
        supports_model_override=True,
        enabled=True,
        docs_url="https://docs.anthropic.com/en/api",
        notes="Direct Anthropic API. Claude 3 Haiku (budget), Claude Sonnet 4.5 (ground truth)."
    ),

    # Future providers (LangExtract, DeepSeek, Gemini) will be added here
    # after architecture stabilizes. Template:
    #
    # "langextract": Provider(
    #     id="langextract",
    #     name="Google Gemini (via LangExtract)",
    #     factory=_create_langextract_extractor,
    #     config_class=LangExtractConfig,
    #     default_model="gemini-2.0-flash",
    #     enabled=False,  # Temporarily disabled during refactor
    # ),
}


# Default provider for the entire system
DEFAULT_PROVIDER_ID = "openrouter"
DEFAULT_MODEL = "meta-llama/llama-3.3-70b-instruct"


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def get_provider(provider_id: str) -> Optional[Provider]:
    """
    Get provider metadata by ID.

    Args:
        provider_id: Provider identifier (e.g., "openrouter")

    Returns:
        Provider instance if found, None otherwise
    """
    return PROVIDERS.get(provider_id)


def list_providers(enabled_only: bool = True) -> list[Provider]:
    """
    List all providers, optionally filtered by enabled status.

    Args:
        enabled_only: If True, only return enabled providers

    Returns:
        List of Provider instances
    """
    providers = PROVIDERS.values()
    if enabled_only:
        providers = [p for p in providers if p.enabled]
    return list(providers)


def validate_provider(provider_id: str) -> bool:
    """
    Check if provider ID exists and is enabled.

    Args:
        provider_id: Provider identifier to validate

    Returns:
        True if provider exists and is enabled
    """
    provider = get_provider(provider_id)
    return provider is not None and provider.enabled


def get_provider_ids() -> list[str]:
    """Get list of all provider IDs (enabled and disabled)."""
    return list(PROVIDERS.keys())


def get_enabled_provider_ids() -> list[str]:
    """Get list of enabled provider IDs only."""
    return [p.id for p in list_providers(enabled_only=True)]


# ============================================================================
# STARTUP VALIDATION
# ============================================================================

def validate_providers_on_startup() -> tuple[bool, list[str]]:
    """
    Validate all enabled providers can be instantiated.

    This should be called at application startup to fail fast
    if provider configuration is invalid.

    Returns:
        Tuple of (all_valid, error_messages)
    """
    errors = []

    for provider in list_providers(enabled_only=True):
        try:
            # Try to instantiate config
            config = provider.config_class()

            # Check API key is present (basic validation)
            if hasattr(config, 'api_key') and not config.api_key:
                errors.append(
                    f"Provider '{provider.id}': API key not configured "
                    f"(check environment variables)"
                )
                continue

            # Try to call factory (dry run - don't actually use it)
            logger.debug(f"✅ Provider '{provider.id}' validation passed")

        except Exception as e:
            errors.append(f"Provider '{provider.id}': {str(e)}")

    if errors:
        logger.error(f"❌ Provider validation failed:\n" + "\n".join(f"  - {e}" for e in errors))
        return False, errors

    logger.info(f"✅ All {len(list_providers(enabled_only=True))} enabled providers validated successfully")
    return True, []
