"""
Extractor Factory - Creates document and event extractors based on configuration
Supports environment variable overrides for different implementations
"""

import logging
import importlib
from typing import Tuple, Callable, Dict, Any, Optional

from .interfaces import DocumentExtractor, EventExtractor
from .config import (
    DoclingConfig, LangExtractConfig, ExtractorConfig,
    OpenRouterConfig, OpenCodeZenConfig, OpenAIConfig, AnthropicConfig, DeepSeekConfig,
    load_config, load_provider_config
)
from .docling_adapter import DoclingDocumentExtractor
from .qwen_vl_doc_adapter import Qwen3VLDocumentExtractor
from .langextract_adapter import LangExtractEventExtractor
from .openrouter_adapter import OpenRouterEventExtractor
from .opencode_zen_adapter import OpenCodeZenEventExtractor
from .openai_adapter import OpenAIEventExtractor
from .anthropic_adapter import AnthropicEventExtractor
from .deepseek_adapter import DeepSeekEventExtractor

logger = logging.getLogger(__name__)


class ExtractorConfigurationError(ValueError):
    """Raised when extractor provider configuration is invalid."""


# Document Extractor Factories

def _create_docling_document_extractor(
    doc_config: DoclingConfig,
    _event_config: Any,
    _extractor_config: ExtractorConfig
) -> DocumentExtractor:
    """Factory for the Docling document extractor (local PDF processing)."""
    return DoclingDocumentExtractor(doc_config)


def _create_qwen_vl_document_extractor(
    _doc_config: DoclingConfig,
    _event_config: Any,
    _extractor_config: ExtractorConfig
) -> DocumentExtractor:
    """Factory for the Qwen3-VL document extractor (budget vision via OpenRouter)."""
    import os
    from .document_extractor_catalog import get_doc_extractor_catalog

    openrouter_api_key = os.getenv("OPENROUTER_API_KEY", "")

    # Inject prompt from catalog if configured
    catalog = get_doc_extractor_catalog()
    prompt = catalog.get_prompt("qwen_vl")

    return Qwen3VLDocumentExtractor(api_key=openrouter_api_key, prompt=prompt)


# Whitelist of allowed import paths for dynamic factory loading (security)
_FACTORY_IMPORT_WHITELIST = ["src.core"]


def _build_doc_provider_registry() -> Dict[str, Callable[[DoclingConfig, Any, ExtractorConfig], DocumentExtractor]]:
    """
    Build document provider registry dynamically from catalog entries.

    This function reads factory_callable strings from the catalog and dynamically
    imports them to build the registry. Only whitelisted import paths are allowed.

    Returns:
        Dict mapping extractor_id to factory function
    """
    from .document_extractor_catalog import get_doc_extractor_catalog

    catalog = get_doc_extractor_catalog()
    registry = {}

    # Get all enabled extractors with factory callables
    for entry in catalog.list_extractors(enabled=True):
        if not entry.factory_callable:
            logger.debug(f"Skipping {entry.extractor_id}: no factory_callable defined")
            continue

        try:
            # Security: Validate import path is whitelisted
            module_path = entry.factory_callable.rsplit('.', 1)[0]
            if not any(module_path.startswith(prefix) for prefix in _FACTORY_IMPORT_WHITELIST):
                logger.warning(
                    f"Skipping {entry.extractor_id}: factory_callable '{entry.factory_callable}' "
                    f"not in whitelist {_FACTORY_IMPORT_WHITELIST}"
                )
                continue

            # Dynamically import factory function
            module_name, func_name = entry.factory_callable.rsplit('.', 1)
            module = importlib.import_module(module_name)
            factory_func = getattr(module, func_name)

            registry[entry.extractor_id] = factory_func
            logger.debug(f"✅ Registered {entry.extractor_id} → {entry.factory_callable}")

        except (ImportError, AttributeError, ValueError) as e:
            logger.warning(
                f"Failed to load factory for {entry.extractor_id} "
                f"from '{entry.factory_callable}': {e}. Skipping."
            )
            continue

    # Fallback: Ensure Docling is available as safe default
    if "docling" not in registry:
        logger.warning("Docling not found in dynamic registry, adding fallback")
        registry["docling"] = _create_docling_document_extractor

    logger.info(f"🏭 Built document provider registry with {len(registry)} extractors: {list(registry.keys())}")
    return registry


# Build registry dynamically from catalog at module load time
DOC_PROVIDER_REGISTRY = _build_doc_provider_registry()


# Event Extractor Factories

def _create_langextract_event_extractor(
    _doc_config: DoclingConfig,
    event_config: Any,
    _extractor_config: ExtractorConfig
) -> EventExtractor:
    """Factory for the default LangExtract adapter."""
    return LangExtractEventExtractor(event_config)


def _create_openrouter_event_extractor(
    _doc_config: DoclingConfig,
    event_config: Any,
    _extractor_config: ExtractorConfig
) -> EventExtractor:
    """Factory for the OpenRouter adapter."""
    return OpenRouterEventExtractor(event_config)


def _create_opencode_zen_event_extractor(
    _doc_config: DoclingConfig,
    event_config: Any,
    _extractor_config: ExtractorConfig
) -> EventExtractor:
    """Factory for the OpenCode Zen adapter."""
    return OpenCodeZenEventExtractor(event_config)


def _create_openai_event_extractor(
    _doc_config: DoclingConfig,
    event_config: Any,
    _extractor_config: ExtractorConfig
) -> EventExtractor:
    """Factory for the OpenAI adapter."""
    return OpenAIEventExtractor(event_config)


def _create_anthropic_event_extractor(
    _doc_config: DoclingConfig,
    event_config: Any,
    _extractor_config: ExtractorConfig
) -> EventExtractor:
    """Factory for the Anthropic adapter."""
    return AnthropicEventExtractor(event_config)


def _create_deepseek_event_extractor(
    _doc_config: DoclingConfig,
    event_config: Any,
    _extractor_config: ExtractorConfig
) -> EventExtractor:
    """Factory for the DeepSeek adapter."""
    return DeepSeekEventExtractor(event_config)


def _create_google_event_extractor(
    _doc_config: DoclingConfig,
    event_config: Any,
    _extractor_config: ExtractorConfig
) -> EventExtractor:
    """Factory for the direct Google Gemini adapter."""
    from .gemini_adapter import GeminiEventExtractor
    return GeminiEventExtractor(event_config)


def _build_event_provider_registry() -> Dict[str, Callable[[DoclingConfig, Any, ExtractorConfig], EventExtractor]]:
    """
    Build event provider registry dynamically from catalog entries.

    This function reads factory_callable strings from the catalog and dynamically
    imports them to build the registry. Only whitelisted import paths are allowed.

    Returns:
        Dict mapping provider_id to factory function
    """
    from .event_extractor_catalog import get_event_extractor_catalog

    catalog = get_event_extractor_catalog()
    registry = {}

    # Get all enabled extractors with factory callables
    for entry in catalog.list_extractors(enabled=True):
        if not entry.factory_callable:
            logger.debug(f"Skipping {entry.provider_id}: no factory_callable defined")
            continue

        try:
            # Security: Validate import path is whitelisted
            module_path = entry.factory_callable.rsplit('.', 1)[0]
            if not any(module_path.startswith(prefix) for prefix in _FACTORY_IMPORT_WHITELIST):
                logger.warning(
                    f"Skipping {entry.provider_id}: factory_callable '{entry.factory_callable}' "
                    f"not in whitelist {_FACTORY_IMPORT_WHITELIST}"
                )
                continue

            # Dynamically import factory function
            module_name, func_name = entry.factory_callable.rsplit('.', 1)
            module = importlib.import_module(module_name)
            factory_func = getattr(module, func_name)

            registry[entry.provider_id] = factory_func
            logger.debug(f"✅ Registered {entry.provider_id} → {entry.factory_callable}")

        except (ImportError, AttributeError, ValueError) as e:
            logger.warning(
                f"Failed to load factory for {entry.provider_id} "
                f"from '{entry.factory_callable}': {e}. Skipping."
            )
            continue

    # Fallback: Ensure LangExtract is available as safe default
    if "langextract" not in registry:
        logger.warning("LangExtract not found in dynamic registry, adding fallback")
        registry["langextract"] = _create_langextract_event_extractor

    logger.info(f"🏭 Built event provider registry with {len(registry)} extractors: {list(registry.keys())}")
    return registry


# Build registry dynamically from catalog at module load time
EVENT_PROVIDER_REGISTRY = _build_event_provider_registry()


def build_extractors(
    docling_config: DoclingConfig,
    event_config: Any,
    extractor_config: ExtractorConfig
) -> Tuple[DocumentExtractor, EventExtractor]:
    """
    Build document and event extractors based on configuration

    Args:
        docling_config: Configuration for document processing
        event_config: Provider-specific configuration for event extraction
        extractor_config: Configuration for extractor selection

    Returns:
        Tuple of (DocumentExtractor, EventExtractor) instances

    Raises:
        ValueError: If an unsupported document extractor is requested.
        ExtractorConfigurationError: If the event extractor provider is not registered.
    """
    # Get extractor types from config
    doc_extractor_type = extractor_config.doc_extractor.lower()
    event_extractor_type = extractor_config.event_extractor.lower()

    logger.info(f"🏭 Building extractors: DOC={doc_extractor_type}, EVENT={event_extractor_type}")

    # Validate document extractor exists in catalog and is enabled
    from .document_extractor_catalog import get_doc_extractor_catalog
    catalog = get_doc_extractor_catalog()
    catalog_entry = catalog.get_extractor(doc_extractor_type)

    if not catalog_entry:
        available_ids = catalog.get_all_extractor_ids()
        available = ", ".join(sorted(available_ids)) or "none"
        logger.error(f"❌ Document extractor '{doc_extractor_type}' not found in catalog")
        raise ExtractorConfigurationError(
            f"Document extractor '{doc_extractor_type}' not found in catalog. Available extractors: {available}"
        )

    if not catalog_entry.enabled:
        logger.error(f"❌ Document extractor '{doc_extractor_type}' is disabled in catalog")
        raise ExtractorConfigurationError(
            f"Document extractor '{doc_extractor_type}' is disabled in catalog. "
            f"Enable it in document_extractor_catalog.py or choose a different extractor."
        )

    logger.info(f"✅ Doc catalog validated: {catalog_entry.display_name} (enabled)")

    # Create document extractor
    doc_factory = DOC_PROVIDER_REGISTRY.get(doc_extractor_type)
    if not doc_factory:
        available = ", ".join(sorted(DOC_PROVIDER_REGISTRY)) or "none"
        logger.error(f"❌ Unsupported document extractor type: {doc_extractor_type}")
        raise ExtractorConfigurationError(
            f"Unsupported document extractor type: {doc_extractor_type}. Available providers: {available}"
        )
    doc_extractor = doc_factory(docling_config, None, extractor_config)
    logger.info(f"✅ Created {doc_extractor.__class__.__name__}")

    # Validate event extractor exists in catalog and is enabled
    from .event_extractor_catalog import get_event_extractor_catalog
    event_catalog = get_event_extractor_catalog()
    event_catalog_entry = event_catalog.get_extractor(event_extractor_type)

    if not event_catalog_entry:
        available_ids = event_catalog.get_all_provider_ids()
        available = ", ".join(sorted(available_ids)) or "none"
        logger.error(f"❌ Event extractor '{event_extractor_type}' not found in catalog")
        raise ExtractorConfigurationError(
            f"Event extractor '{event_extractor_type}' not found in catalog. Available providers: {available}"
        )

    if not event_catalog_entry.enabled:
        logger.error(f"❌ Event extractor '{event_extractor_type}' is disabled in catalog")
        raise ExtractorConfigurationError(
            f"Event extractor '{event_extractor_type}' is disabled in catalog. "
            f"Enable it in event_extractor_catalog.py or choose a different provider."
        )

    logger.info(f"✅ Event catalog validated: {event_catalog_entry.display_name} (enabled)")

    # Create event extractor
    event_factory = EVENT_PROVIDER_REGISTRY.get(event_extractor_type)
    if not event_factory:
        available = ", ".join(sorted(EVENT_PROVIDER_REGISTRY)) or "none"
        logger.error(f"❌ Unsupported event extractor type: {event_extractor_type}")
        raise ExtractorConfigurationError(
            f"Unsupported event extractor type: {event_extractor_type}. Available providers: {available}"
        )
    event_extractor = event_factory(docling_config, event_config, extractor_config)
    logger.info(f"✅ Created {event_extractor.__class__.__name__}")

    return doc_extractor, event_extractor


def create_default_extractors(
    event_extractor_override: Optional[str] = None,
    runtime_model: Optional[str] = None,
    doc_extractor_override: Optional[str] = None
) -> Tuple[DocumentExtractor, EventExtractor]:
    """
    Create extractors with default configuration from environment

    Args:
        event_extractor_override: Override the event extractor provider from environment
        runtime_model: Runtime model selection (for OpenRouter multi-model support)
        doc_extractor_override: Override the document extractor provider from environment

    Returns:
        Tuple of (DocumentExtractor, EventExtractor) instances
    """
    # First load base config to determine the event extractor type
    docling_config, _, extractor_config = load_config()

    if event_extractor_override:
        extractor_config.event_extractor = event_extractor_override

    if doc_extractor_override:
        extractor_config.doc_extractor = doc_extractor_override

    # Load provider-specific configuration based on the event extractor type
    docling_config, event_config, extractor_config = load_provider_config(
        extractor_config.event_extractor,
        docling_config=docling_config,
        extractor_config=extractor_config,
        runtime_model=runtime_model
    )

    return build_extractors(docling_config, event_config, extractor_config)


def validate_extractors(doc_extractor: DocumentExtractor, event_extractor: EventExtractor) -> bool:
    """
    Validate that extractors are properly configured

    Args:
        doc_extractor: Document extractor to validate
        event_extractor: Event extractor to validate

    Returns:
        True if both extractors are valid, False otherwise
    """
    try:
        # Check document extractor
        supported_types = doc_extractor.get_supported_types()
        if not supported_types:
            logger.error("❌ Document extractor supports no file types")
            return False

        # Check event extractor
        if not event_extractor.is_available():
            logger.error("❌ Event extractor is not available")
            return False

        logger.info(f"✅ Extractors validated: {len(supported_types)} file types supported")
        return True

    except Exception as e:
        logger.error(f"❌ Extractor validation failed: {e}")
        return False
