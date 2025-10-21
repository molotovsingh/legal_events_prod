"""
Event Extractor Catalog - Centralized metadata for event extraction layer

This module provides event extractor metadata (Layer 2 / event extraction providers)
separate from per-model pricing (Model Catalog).

Architecture mirrors DocumentExtractorCatalog for consistency.

Usage:
    from core.event_extractor_catalog import get_event_extractor_catalog

    catalog = get_event_extractor_catalog()
    providers = catalog.list_extractors(enabled=True)
    # Returns: List of enabled EventExtractorEntry objects
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class EventExtractorEntry:
    """Event extractor metadata entry"""

    # === Identification ===
    provider_id: str  # 'langextract', 'openrouter', 'openai', etc.
    display_name: str  # UI display name ('Gemini', 'OpenRouter', etc.)

    # === Registry Control ===
    enabled: bool = True  # Toggle provider availability in UI/CLI/factory
    factory_callable: Optional[str] = None  # Fully-qualified import path (e.g., "src.core.extractor_factory._create_openrouter_event_extractor")
    prompt_id: Optional[str] = None  # Reference to named prompt in prompts module
    prompt_override: Optional[str] = None  # Inline prompt override (takes precedence over prompt_id)

    # === Capabilities ===
    supports_runtime_model: bool = False  # True for providers with multi-model selection (OpenRouter, OpenAI, Anthropic, Gemini)

    # === Metadata ===
    notes: str = ""  # Special considerations, use cases, limitations
    documentation_url: Optional[str] = None
    recommended: bool = False  # Highlight in UI as recommended provider


# ============================================================================
# EVENT EXTRACTOR REGISTRY
# ============================================================================

_EVENT_EXTRACTOR_REGISTRY: List[EventExtractorEntry] = [
    # === PRIMARY PROVIDERS ===

    EventExtractorEntry(
        provider_id="langextract",
        display_name="Gemini",
        enabled=True,
        factory_callable="src.core.extractor_factory._create_langextract_event_extractor",
        supports_runtime_model=True,  # Supports model_id override (gemini-2.0-flash, gemini-2.5-pro)
        recommended=True,
        notes="Google Gemini 2.0 Flash. Default provider. Fast, accurate, budget-friendly.",
        documentation_url="https://ai.google.dev/gemini-api/docs",
    ),

    EventExtractorEntry(
        provider_id="openrouter",
        display_name="OpenRouter",
        enabled=True,
        factory_callable="src.core.extractor_factory._create_openrouter_event_extractor",
        supports_runtime_model=True,  # Supports runtime model selection (10+ curated models)
        recommended=True,
        notes="Unified API for 10+ curated models (OpenAI, Anthropic, DeepSeek, Meta, Mistral). Best for A/B testing.",
        documentation_url="https://openrouter.ai/docs",
    ),

    EventExtractorEntry(
        provider_id="openai",
        display_name="OpenAI",
        enabled=True,
        factory_callable="src.core.extractor_factory._create_openai_event_extractor",
        supports_runtime_model=True,  # Supports model override (gpt-4o-mini, gpt-4o, gpt-5)
        recommended=False,
        notes="Direct OpenAI API. GPT-4o-mini (budget), GPT-4o (quality), GPT-5 (ground truth).",
        documentation_url="https://platform.openai.com/docs/api-reference",
    ),

    # === DIRECT PROVIDER APIs (Advanced) ===

    EventExtractorEntry(
        provider_id="anthropic",
        display_name="Anthropic",
        enabled=True,
        factory_callable="src.core.extractor_factory._create_anthropic_event_extractor",
        supports_runtime_model=True,  # Supports model override (claude-3-haiku, claude-sonnet-4-5, claude-opus-4)
        recommended=False,
        notes="Direct Anthropic API. Claude 3 Haiku (budget), Claude Sonnet 4.5 (ground truth), Claude Opus 4 (premium).",
        documentation_url="https://docs.anthropic.com/en/api",
    ),

    EventExtractorEntry(
        provider_id="deepseek",
        display_name="DeepSeek",
        enabled=True,
        factory_callable="src.core.extractor_factory._create_deepseek_event_extractor",
        supports_runtime_model=False,  # Single model: deepseek-chat
        recommended=False,
        notes="DeepSeek R1. Budget reasoning model via OpenAI-compatible API.",
        documentation_url="https://platform.deepseek.com/api-docs",
    ),

    EventExtractorEntry(
        provider_id="google",
        display_name="Google Gemini (Direct API)",
        enabled=True,  # Enabled for internal use (adapter switching from langextract)
        factory_callable="src.core.extractor_factory._create_google_event_extractor",
        supports_runtime_model=True,  # Supports model_id override (gemini-2.0-flash, gemini-2.5-flash, gemini-2.5-pro)
        recommended=False,  # Not recommended in UI - use 'Gemini' provider instead
        notes="Direct Google Gemini API (internal adapter). Access via 'Gemini' provider with model selector.",
        documentation_url="https://ai.google.dev/gemini-api/docs",
    ),

    EventExtractorEntry(
        provider_id="opencode_zen",
        display_name="OpenCode Zen",
        enabled=True,
        factory_callable="src.core.extractor_factory._create_opencode_zen_event_extractor",
        supports_runtime_model=False,  # Single specialized model
        recommended=False,
        notes="Legal AI specialized extraction. Premium legal-focused model.",
        documentation_url=None,  # Private API
    ),
]


# ============================================================================
# EVENT EXTRACTOR CATALOG CLASS
# ============================================================================

class EventExtractorCatalog:
    """
    Event extractor registry with query and metadata utilities.

    Provides centralized access to Layer 2 (event extraction) provider metadata.
    """

    def __init__(self, registry: List[EventExtractorEntry]):
        self._registry = registry
        self._index: Dict[str, EventExtractorEntry] = {
            entry.provider_id: entry for entry in registry
        }

    def get_extractor(self, provider_id: str) -> Optional[EventExtractorEntry]:
        """
        Get extractor entry by provider ID.

        Args:
            provider_id: Provider identifier ('langextract', 'openrouter', 'openai', etc.)

        Returns:
            EventExtractorEntry if found, None otherwise
        """
        return self._index.get(provider_id)

    def list_extractors(
        self,
        enabled: Optional[bool] = None,
        supports_runtime_model: Optional[bool] = None,
        recommended_only: bool = False
    ) -> List[EventExtractorEntry]:
        """
        Query extractors with filters.

        Args:
            enabled: Filter by enabled status (None = no filter, True = enabled only, False = disabled only)
            supports_runtime_model: Filter by runtime model support
            recommended_only: Only return recommended extractors

        Returns:
            List of EventExtractorEntry objects matching all filters
        """
        results = self._registry

        if enabled is not None:
            results = [e for e in results if e.enabled == enabled]

        if supports_runtime_model is not None:
            results = [e for e in results if e.supports_runtime_model == supports_runtime_model]

        if recommended_only:
            results = [e for e in results if e.recommended]

        return results

    def validate_provider_id(self, provider_id: str) -> bool:
        """
        Check if provider ID exists in catalog.

        Args:
            provider_id: Provider identifier to validate

        Returns:
            True if provider exists, False otherwise
        """
        return provider_id in self._index

    def get_all_provider_ids(self) -> List[str]:
        """Get list of all provider IDs in catalog."""
        return list(self._index.keys())

    def get_prompt(self, provider_id: str) -> Optional[str]:
        """
        Get event extraction prompt for a specific provider.

        Prompt resolution priority:
        1. prompt_override (inline override if specified)
        2. prompt_id (lookup in prompts module)
        3. None (provider uses default LEGAL_EVENTS_PROMPT from constants.py)

        Args:
            provider_id: Provider identifier

        Returns:
            Prompt string if found, None if no prompt configured (uses default)
        """
        extractor = self.get_extractor(provider_id)
        if not extractor:
            return None

        # Priority 1: Inline override
        if extractor.prompt_override:
            return extractor.prompt_override

        # Priority 2: Prompt ID reference
        if extractor.prompt_id:
            try:
                from .event_extractor_prompts import get_prompt_by_id
                prompt = get_prompt_by_id(extractor.prompt_id)

                if prompt:
                    return prompt
                else:
                    logger.warning(
                        f"Prompt ID '{extractor.prompt_id}' not found for {provider_id}. "
                        "Using default LEGAL_EVENTS_PROMPT."
                    )
                    return None
            except (ImportError, KeyError) as e:
                logger.warning(
                    f"Failed to load prompt '{extractor.prompt_id}' for {provider_id}: {e}"
                )
                return None

        # Priority 3: No prompt configured (use default LEGAL_EVENTS_PROMPT)
        return None


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

_global_catalog: Optional[EventExtractorCatalog] = None


def get_event_extractor_catalog() -> EventExtractorCatalog:
    """
    Get the global event extractor catalog instance (singleton pattern).

    Returns:
        EventExtractorCatalog with all registered extractors
    """
    global _global_catalog
    if _global_catalog is None:
        _global_catalog = EventExtractorCatalog(_EVENT_EXTRACTOR_REGISTRY)
    return _global_catalog


def get_event_extractor(provider_id: str) -> Optional[EventExtractorEntry]:
    """Convenience function: Get extractor by provider ID."""
    return get_event_extractor_catalog().get_extractor(provider_id)


def list_event_extractors(**filters) -> List[EventExtractorEntry]:
    """Convenience function: Query extractors with filters."""
    return get_event_extractor_catalog().list_extractors(**filters)


def validate_event_provider(provider_id: str) -> bool:
    """Convenience function: Check if provider ID is valid."""
    return get_event_extractor_catalog().validate_provider_id(provider_id)
