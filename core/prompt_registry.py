"""
Classification Prompt Registry

Manages multiple classification prompt strategies with documented characteristics.
Enables use-case-specific optimization without forced trade-offs.

Design Philosophy:
- Different use cases need different prompt behaviors
- Maintain multiple prompts with clear documentation
- User selects based on workflow needs (search vs routing vs comprehensive analysis)
- No one-size-fits-all approach
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from core.constants import (
    LEGAL_CLASSIFICATION_MULTILABEL_PROMPT,
    LEGAL_CLASSIFICATION_MULTILABEL_PROMPT_V2,
)


@dataclass
class PromptCharacteristics:
    """Documented characteristics of a classification prompt strategy."""

    recall_priority: str  # "high", "moderate", "low"
    precision_priority: str  # "high", "moderate", "low"
    decisiveness: str  # "high", "moderate", "low", "maximum"
    typical_labels_per_doc: str  # e.g., "1.5-2.0", "1.0-1.5"
    multi_label_rate: str  # e.g., "35-70%", "0-33%"


@dataclass
class PromptVariant:
    """A classification prompt variant with metadata."""

    name: str
    prompt_text: str
    use_cases: List[str]
    characteristics: PromptCharacteristics
    recommended_models: List[str]
    description: str
    version: str  # e.g., "multilabel-v1", "multilabel-v2"
    output_directory: str  # Where to save classification results

    # Authorship and versioning metadata
    author: str  # Author or team responsible for this variant
    created_date: str  # ISO format: "YYYY-MM-DD"
    modified_date: str  # ISO format: "YYYY-MM-DD"
    changelog: Optional[str] = None  # Brief description of changes from previous version


# ============================================================================
# PROMPT REGISTRY - Add new prompt variants here
# ============================================================================

CLASSIFICATION_PROMPT_REGISTRY: Dict[str, PromptVariant] = {
    "comprehensive": PromptVariant(
        name="Comprehensive Multi-Label (V1)",
        prompt_text=LEGAL_CLASSIFICATION_MULTILABEL_PROMPT,
        use_cases=[
            "search",
            "tagging",
            "comprehensive_analysis",
            "document_discovery",
            "multi-tag_recommendation",
        ],
        characteristics=PromptCharacteristics(
            recall_priority="high",
            precision_priority="moderate",
            decisiveness="low",
            typical_labels_per_doc="1.5-2.0",
            multi_label_rate="35-70%",
        ),
        recommended_models=[
            "anthropic/claude-3-haiku",  # 1.90 labels/doc, 80% recall
            "mistralai/mistral-large-2411",  # 2.05 labels/doc, most comprehensive
            "openai/gpt-oss-120b",  # 1.82 labels/doc, 100% recall
        ],
        description=(
            "Captures all possible document functions. Use when you need high recall "
            "for search/tagging systems. Models are encouraged to include all relevant "
            "labels, not just the primary one. Best for workflows where finding ALL "
            "documents with a particular function is more important than decisiveness."
        ),
        version="multilabel-v1",
        output_directory="output/classification_multilabel",
        author="User Preference (Primary Research)",
        created_date="2025-10-14",
        modified_date="2025-10-14",
        changelog="Initial baseline prompt for comprehensive multi-label classification. "
                 "Optimized for high recall in search/tagging workflows. Tested on 5 models "
                 "with 20 documents. Avg 1.5-2.0 labels/doc, 35-70% multi-label rate.",
    ),

    "decisive": PromptVariant(
        name="Decisive Single-Label Default (V2)",
        prompt_text=LEGAL_CLASSIFICATION_MULTILABEL_PROMPT_V2,
        use_cases=[
            "routing",
            "triage",
            "primary_classification",
            "workflow_automation",
            "document_type_detection",
        ],
        characteristics=PromptCharacteristics(
            recall_priority="moderate",
            precision_priority="high",
            decisiveness="high",
            typical_labels_per_doc="1.0-1.5",
            multi_label_rate="0-33%",
        ),
        recommended_models=[
            "openai/gpt-oss-120b",  # 1.00 labels/doc, 0% multi-label
            "meta-llama/llama-3.3-70b-instruct",  # 1.05 labels/doc, 5% multi-label
            "openai/gpt-4o-mini",  # 1.05 labels/doc, 5% multi-label
        ],
        description=(
            "Commits to single primary label by default. Use when you need decisive "
            "routing/triage decisions. Multi-labels only used when explicitly justified. "
            "Reduces hedging by 37.6% average across models. Best for workflows where "
            "one clear decision is needed (e.g., 'which folder does this go in?')."
        ),
        version="multilabel-v2",
        output_directory="output/classification_multilabel_v2",
        author="Optimization Research Team",
        created_date="2025-10-14",
        modified_date="2025-10-14",
        changelog="Optimized V2 prompt with explicit 'DEFAULT TO SINGLE-LABEL' guidance. "
                 "Reduces hedging by 37.6% average across 5 models while maintaining quality. "
                 "Improved cross-model consistency (variance reduced by 1.7%). Best for routing/triage workflows.",
    ),
}


# ============================================================================
# REGISTRY FUNCTIONS
# ============================================================================

def get_prompt_variant(variant_name: str) -> PromptVariant:
    """
    Get a prompt variant by name.

    Args:
        variant_name: Name of the variant ("comprehensive", "decisive", etc.)

    Returns:
        PromptVariant object with prompt text and metadata

    Raises:
        KeyError: If variant_name not found in registry
    """
    if variant_name not in CLASSIFICATION_PROMPT_REGISTRY:
        available = ", ".join(CLASSIFICATION_PROMPT_REGISTRY.keys())
        raise KeyError(
            f"Unknown prompt variant: '{variant_name}'. "
            f"Available variants: {available}"
        )

    return CLASSIFICATION_PROMPT_REGISTRY[variant_name]


def list_prompt_variants() -> List[str]:
    """Get list of all available prompt variant names."""
    return list(CLASSIFICATION_PROMPT_REGISTRY.keys())


def get_default_variant() -> str:
    """
    Get the default prompt variant name.

    Returns "comprehensive" (V1) as default to preserve existing behavior.
    User's preference: comprehensive multi-label classification.
    """
    return "comprehensive"


def get_prompt_text(variant_name: Optional[str] = None) -> str:
    """
    Get prompt text for a variant.

    Args:
        variant_name: Name of variant, or None for default

    Returns:
        Prompt text string
    """
    if variant_name is None:
        variant_name = get_default_variant()

    variant = get_prompt_variant(variant_name)
    return variant.prompt_text


def get_output_directory(variant_name: Optional[str] = None) -> str:
    """
    Get output directory for a variant.

    Args:
        variant_name: Name of variant, or None for default

    Returns:
        Output directory path string
    """
    if variant_name is None:
        variant_name = get_default_variant()

    variant = get_prompt_variant(variant_name)
    return variant.output_directory


def get_prompt_version(variant_name: Optional[str] = None) -> str:
    """
    Get version identifier for a variant (used in output JSON metadata).

    Args:
        variant_name: Name of variant, or None for default

    Returns:
        Version string like "multilabel-v1" or "multilabel-v2"
    """
    if variant_name is None:
        variant_name = get_default_variant()

    variant = get_prompt_variant(variant_name)
    return variant.version


def print_variant_info(variant_name: str) -> None:
    """Print detailed information about a prompt variant."""
    variant = get_prompt_variant(variant_name)

    print(f"\n{'=' * 80}")
    print(f"Prompt Variant: {variant.name}")
    print(f"{'=' * 80}")
    print(f"\nDescription: {variant.description}")
    print(f"\nUse Cases:")
    for use_case in variant.use_cases:
        print(f"  - {use_case}")
    print(f"\nCharacteristics:")
    print(f"  Recall Priority: {variant.characteristics.recall_priority}")
    print(f"  Precision Priority: {variant.characteristics.precision_priority}")
    print(f"  Decisiveness: {variant.characteristics.decisiveness}")
    print(f"  Typical Labels/Doc: {variant.characteristics.typical_labels_per_doc}")
    print(f"  Multi-Label Rate: {variant.characteristics.multi_label_rate}")
    print(f"\nRecommended Models:")
    for model in variant.recommended_models:
        print(f"  - {model}")
    print(f"\nMetadata:")
    print(f"  Version: {variant.version}")
    print(f"  Author: {variant.author}")
    print(f"  Created: {variant.created_date}")
    print(f"  Modified: {variant.modified_date}")
    if variant.changelog:
        print(f"\nChangelog:")
        print(f"  {variant.changelog}")
    print(f"\nOutput Directory: {variant.output_directory}")
    print(f"{'=' * 80}\n")


def print_all_variants() -> None:
    """Print summary of all available prompt variants."""
    print(f"\n{'=' * 80}")
    print("Available Classification Prompt Variants")
    print(f"{'=' * 80}\n")

    for variant_name in list_prompt_variants():
        variant = get_prompt_variant(variant_name)
        print(f"📋 {variant_name}: {variant.name}")
        print(f"   {variant.description[:100]}...")
        print(f"   Use cases: {', '.join(variant.use_cases[:3])}")
        print(f"   Labels/doc: {variant.characteristics.typical_labels_per_doc}, "
              f"Multi-label rate: {variant.characteristics.multi_label_rate}")
        print()

    print(f"Default variant: {get_default_variant()}")
    print(f"\nTo see detailed info: --show-prompt-info <variant_name>")
    print(f"{'=' * 80}\n")


# ============================================================================
# BACKWARD COMPATIBILITY
# ============================================================================

def get_prompt_for_v1_v2_flag(prompt_variant: Optional[str]) -> str:
    """
    Backward compatibility for existing --prompt-variant v1/v2 flags.

    Maps old flags to new registry names:
    - "v1" or "multilabel-v1" → "comprehensive"
    - "v2" or "multilabel-v2" → "decisive"
    - None → default ("comprehensive")

    Args:
        prompt_variant: Old-style flag value or None

    Returns:
        Registry variant name
    """
    if prompt_variant is None:
        return get_default_variant()

    # Map old flags to new registry names
    mapping = {
        "v1": "comprehensive",
        "multilabel-v1": "comprehensive",
        "v2": "decisive",
        "multilabel-v2": "decisive",
    }

    # If it's already a registry name, return as-is
    if prompt_variant in CLASSIFICATION_PROMPT_REGISTRY:
        return prompt_variant

    # If it's an old flag, map it
    if prompt_variant in mapping:
        return mapping[prompt_variant]

    # Unknown value
    available = ", ".join(list_prompt_variants())
    raise ValueError(
        f"Unknown prompt variant: '{prompt_variant}'. "
        f"Available: {available}"
    )
