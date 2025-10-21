"""
Classification Factory - Creates classification adapters

Mirrors extractor_factory.py (Layer 2) pattern for consistency.
Routes to appropriate classifier adapter based on provider.

Usage:
    from core.classification_factory import create_classifier

    classifier = create_classifier(
        model_id="anthropic/claude-3-haiku",
        prompt_variant="comprehensive"
    )

    result = classifier.classify(document_text)
    # Returns: {"primary": "Court Order/Judgment", "classes": [...], "confidence": 0.92}
"""

from typing import Optional
import logging

from core.classification_catalog import get_classification_catalog
from core.prompt_registry import get_prompt_variant

logger = logging.getLogger(__name__)


def create_classifier(
    model_id: str,
    prompt_variant: Optional[str] = None
):
    """
    Create classification adapter for a model.

    Factory pattern that:
    1. Validates model exists in catalog
    2. Checks model is enabled
    3. Resolves prompt variant (uses recommended if not specified)
    4. Routes to appropriate adapter based on provider

    Args:
        model_id: Model identifier from classification_catalog (e.g., "anthropic/claude-3-haiku")
        prompt_variant: Prompt variant name (from prompt_registry: "comprehensive", "decisive")
                        If None, uses model's recommended_prompt from catalog

    Returns:
        ClassificationAdapter instance ready to classify documents

    Raises:
        ValueError: If model not found, disabled, or invalid prompt variant
        RuntimeError: If provider not supported or adapter creation fails

    Example:
        >>> classifier = create_classifier("anthropic/claude-3-haiku")
        >>> result = classifier.classify("This is a court order...")
        >>> print(result["primary"])
        "Court Order/Judgment"
    """
    # Get catalog and validate model
    catalog = get_classification_catalog()
    model_entry = catalog.get_model(model_id)

    if not model_entry:
        available_models = catalog.get_all_model_ids()
        raise ValueError(
            f"Unknown classification model: '{model_id}'. "
            f"Available models: {', '.join(available_models)}"
        )

    if not model_entry.enabled:
        raise ValueError(
            f"Classification model '{model_id}' is disabled in catalog. "
            f"Enable it by setting enabled=True in classification_catalog.py"
        )

    # Resolve prompt variant
    if prompt_variant is None:
        prompt_variant = model_entry.recommended_prompt
        logger.info(
            f"Using recommended prompt '{prompt_variant}' for model '{model_id}'"
        )

    # Validate prompt variant exists
    try:
        prompt = get_prompt_variant(prompt_variant)
    except KeyError as e:
        raise ValueError(
            f"Invalid prompt variant: '{prompt_variant}'. "
            f"Check prompt_registry.py for available variants."
        ) from e

    logger.info(
        f"Creating classifier: model={model_id}, prompt={prompt_variant}, "
        f"provider={model_entry.provider}"
    )

    # Route to appropriate adapter based on provider
    if model_entry.provider == "openrouter":
        from core.openrouter_classifier import OpenRouterClassifier
        return OpenRouterClassifier(
            model_id=model_id,
            prompt_variant=prompt,
            cost_per_1m=model_entry.cost_per_1m
        )

    elif model_entry.provider == "anthropic":
        # Direct Anthropic API (future support)
        from core.anthropic_classifier import AnthropicClassifier
        return AnthropicClassifier(
            model_id=model_id,
            prompt_variant=prompt,
            cost_per_1m=model_entry.cost_per_1m
        )

    elif model_entry.provider == "openai":
        # Direct OpenAI API (future support)
        from core.openai_classifier import OpenAIClassifier
        return OpenAIClassifier(
            model_id=model_id,
            prompt_variant=prompt,
            cost_per_1m=model_entry.cost_per_1m
        )

    else:
        raise RuntimeError(
            f"Unsupported provider: '{model_entry.provider}' for model '{model_id}'. "
            f"Supported providers: openrouter, anthropic, openai"
        )


def get_classifier_for_use_case(
    use_case: str,
    prompt_variant: Optional[str] = None
):
    """
    Convenience function: Create classifier optimized for a use case.

    Automatically selects the best model for the use case from catalog.

    Args:
        use_case: Use case name ("search_discovery", "routing_triage", "comprehensive_analysis")
        prompt_variant: Optional prompt override (defaults to model's recommended prompt)

    Returns:
        ClassificationAdapter instance

    Example:
        >>> # Get classifier optimized for search/discovery
        >>> classifier = get_classifier_for_use_case("search_discovery")
        >>> # Returns Claude 3 Haiku with "comprehensive" prompt
    """
    catalog = get_classification_catalog()
    models = catalog.get_models_by_use_case(use_case)

    if not models:
        raise ValueError(
            f"No models found for use case: '{use_case}'. "
            f"Check classification_catalog.py registry."
        )

    # Use first recommended model for the use case
    recommended = [m for m in models if m.recommended]
    model = recommended[0] if recommended else models[0]

    logger.info(f"Selected model '{model.model_id}' for use case '{use_case}'")

    return create_classifier(
        model_id=model.model_id,
        prompt_variant=prompt_variant
    )
