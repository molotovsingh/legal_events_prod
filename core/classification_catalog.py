"""
Classification Model Catalog (Layer 1.5)

Centralized metadata registry for document classification models.
Mirrors architecture of document_extractor_catalog.py and event_extractor_catalog.py.

Architecture Philosophy:
- Registry pattern for consistent catalog management across all 3 layers
- Dynamic UI generation (no hardcoded model lists)
- Deployment control via enabled flag (no code changes needed)
- Metadata co-location (cost, speed, use cases, prompt pairing)

Usage:
    from core.classification_catalog import get_classification_catalog

    catalog = get_classification_catalog()
    enabled_models = catalog.list_models(enabled=True, recommended_only=True)
"""

from dataclasses import dataclass
from typing import List, Optional, Dict
import logging

logger = logging.getLogger(__name__)


@dataclass
class ClassificationModelEntry:
    """
    Classification model metadata entry (Layer 1.5).

    Mirrors DocExtractorEntry (Layer 1) and EventExtractorEntry (Layer 2) patterns.
    """

    # === Identification ===
    model_id: str  # Full model identifier (e.g., "anthropic/claude-3-haiku")
    display_name: str  # UI-friendly name (e.g., "Claude 3 Haiku")
    provider: str  # API provider ("openrouter", "anthropic", "openai")

    # === Registry Control ===
    enabled: bool = True  # Toggle model availability (deployment control)
    recommended: bool = False  # Highlight in UI as recommended option

    # === Performance Metadata ===
    cost_per_1m: float = 0.0  # Cost per 1M tokens (e.g., 0.25 for Haiku)
    speed: str = "normal"  # "fast" (4.4s), "normal", "slow"

    # === Classification-Specific Metadata ===
    typical_labels_per_doc: str = "1.0-1.5"  # Expected label count (from benchmarks)
    multi_label_rate: str = "5-35%"  # Percentage of docs with multiple labels
    quality_score: str = "10/10"  # Benchmark quality rating

    # === Prompt Pairing (references prompt_registry.py) ===
    recommended_prompt: str = "decisive"  # "comprehensive" or "decisive"

    # === Use Case Mapping ===
    primary_use_case: str = "routing_triage"  # "search_discovery", "routing_triage", "comprehensive_analysis"

    # === Metadata ===
    notes: str = ""  # Special considerations, use cases, limitations
    documentation_url: Optional[str] = None  # Link to model documentation

    # === API Configuration ===
    requires_api_key: bool = True  # Does this model need an API key?
    api_key_env_var: str = "OPENROUTER_API_KEY"  # Environment variable name


# ============================================================================
# CLASSIFICATION MODEL REGISTRY
# ============================================================================
#
# Deployment Configuration:
# - Llama 3.3 70B: Enabled (routing/triage use case)
# - Claude 3 Haiku: Enabled (search/discovery use case)
# - Mistral Large 2411: DISABLED (per deployment requirements)
#
# To re-enable Mistral: Change enabled=True in registry entry below
# ============================================================================

CLASSIFICATION_MODEL_REGISTRY: List[ClassificationModelEntry] = [
    # === PRIMARY MODELS (ENABLED FOR DEPLOYMENT) ===
    # Default order: Llama 3.3 70B (OSS, routing/triage) → Claude 3 Haiku (search/discovery)

    ClassificationModelEntry(
        model_id="meta-llama/llama-3.3-70b-instruct",
        display_name="Llama 3.3 70B",
        provider="openrouter",
        enabled=True,
        recommended=True,  # DEFAULT for routing/triage (OSS)
        cost_per_1m=0.60,
        speed="normal",
        typical_labels_per_doc="1.0-1.5",
        multi_label_rate="5-35%",
        quality_score="10/10",
        recommended_prompt="decisive",  # Single-label V2 for routing
        primary_use_case="routing_triage",
        notes=(
            "Most accurate. Minimal hedging (5% multi-label with decisive prompt). "
            "Best for single-label routing decisions and document triage. "
            "Ranks best for correctness across all test scenarios. "
            "Open source default."
        ),
        documentation_url=None,
        requires_api_key=True,
        api_key_env_var="OPENROUTER_API_KEY"
    ),

    ClassificationModelEntry(
        model_id="anthropic/claude-3-haiku",
        display_name="Claude 3 Haiku",
        provider="openrouter",
        enabled=True,
        recommended=True,  # ALTERNATIVE for search/discovery
        cost_per_1m=0.25,
        speed="fast",  # 4.4s benchmark from classification-findings-2025-10-14.md
        typical_labels_per_doc="1.5-2.0",
        multi_label_rate="35-65%",
        quality_score="10/10",
        recommended_prompt="comprehensive",  # Multi-label V1 for search
        primary_use_case="search_discovery",
        notes=(
            "Best balance: Fast (4.4s), cheap ($0.25/M), 80% recall. "
            "Ideal for multi-label search/tagging workflows. "
            "1.90 labels/doc average with comprehensive prompt."
        ),
        documentation_url="https://docs.anthropic.com/en/api",
        requires_api_key=True,
        api_key_env_var="OPENROUTER_API_KEY"
    ),

    # === DISABLED MODELS (DEPLOYMENT EXCLUSIONS) ===

    ClassificationModelEntry(
        model_id="mistralai/mistral-large-2411",
        display_name="Mistral Large 2411",
        provider="openrouter",
        enabled=False,  # 🔴 DISABLED for deployment
        recommended=False,
        cost_per_1m=0.80,
        speed="normal",
        typical_labels_per_doc="1.5-2.0",
        multi_label_rate="35-70%",
        quality_score="10/10",
        recommended_prompt="comprehensive",
        primary_use_case="comprehensive_analysis",
        notes=(
            "2.05 labels/doc (highest coverage). 70% multi-label rate. "
            "Captures maximum document nuance. "
            "DISABLED for deployment - re-enable by setting enabled=True."
        ),
        documentation_url=None,
        requires_api_key=True,
        api_key_env_var="OPENROUTER_API_KEY"
    ),
]


# ============================================================================
# CLASSIFICATION CATALOG CLASS
# ============================================================================

class ClassificationCatalog:
    """
    Classification model registry with query and metadata utilities.

    Mirrors EventExtractorCatalog and DocumentExtractorCatalog patterns
    for architectural consistency across all 3 pipeline layers.
    """

    def __init__(self, registry: List[ClassificationModelEntry]):
        self._registry = registry
        self._index: Dict[str, ClassificationModelEntry] = {
            entry.model_id: entry for entry in registry
        }

    def get_model(self, model_id: str) -> Optional[ClassificationModelEntry]:
        """
        Get model entry by ID.

        Args:
            model_id: Model identifier (e.g., "anthropic/claude-3-haiku")

        Returns:
            ClassificationModelEntry if found, None otherwise
        """
        return self._index.get(model_id)

    def list_models(
        self,
        enabled: Optional[bool] = None,
        recommended_only: bool = False,
        provider: Optional[str] = None
    ) -> List[ClassificationModelEntry]:
        """
        Query models with filters.

        Args:
            enabled: Filter by enabled status (None = no filter)
            recommended_only: Only return recommended models
            provider: Filter by provider ("openrouter", "anthropic", etc.)

        Returns:
            List of ClassificationModelEntry objects matching all filters
        """
        results = self._registry

        if enabled is not None:
            results = [m for m in results if m.enabled == enabled]

        if recommended_only:
            results = [m for m in results if m.recommended]

        if provider:
            results = [m for m in results if m.provider == provider]

        return results

    def validate_model_id(self, model_id: str) -> bool:
        """
        Check if model ID exists in catalog.

        Args:
            model_id: Model identifier to validate

        Returns:
            True if model exists, False otherwise
        """
        return model_id in self._index

    def get_all_model_ids(self) -> List[str]:
        """Get list of all model IDs in catalog."""
        return list(self._index.keys())

    def get_recommended_prompt(self, model_id: str) -> Optional[str]:
        """
        Get recommended prompt variant for a model.

        Args:
            model_id: Model identifier

        Returns:
            Prompt variant name (e.g., "comprehensive", "decisive") or None
        """
        model = self.get_model(model_id)
        return model.recommended_prompt if model else None

    def get_models_by_use_case(self, use_case: str) -> List[ClassificationModelEntry]:
        """
        Get models optimized for a specific use case.

        Args:
            use_case: Use case name ("search_discovery", "routing_triage", etc.)

        Returns:
            List of models with matching primary_use_case
        """
        return [
            m for m in self._registry
            if m.primary_use_case == use_case and m.enabled
        ]


# ============================================================================
# CONVENIENCE FUNCTIONS (Singleton Pattern)
# ============================================================================

_global_catalog: Optional[ClassificationCatalog] = None


def get_classification_catalog() -> ClassificationCatalog:
    """
    Get the global classification catalog instance (singleton pattern).

    Returns:
        ClassificationCatalog with all registered models
    """
    global _global_catalog
    if _global_catalog is None:
        _global_catalog = ClassificationCatalog(CLASSIFICATION_MODEL_REGISTRY)
    return _global_catalog


def get_classification_model(model_id: str) -> Optional[ClassificationModelEntry]:
    """Convenience function: Get model by ID."""
    return get_classification_catalog().get_model(model_id)


def list_classification_models(**filters) -> List[ClassificationModelEntry]:
    """Convenience function: Query models with filters."""
    return get_classification_catalog().list_models(**filters)


def validate_classification_model(model_id: str) -> bool:
    """Convenience function: Check if model ID is valid."""
    return get_classification_catalog().validate_model_id(model_id)
