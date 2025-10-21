"""
Model Catalog Registry - Single Source of Truth for Model Metadata

This module provides centralized model configuration for the legal event extraction system.
All model metadata (pricing, capabilities, quality scores) is defined here to eliminate
duplication across app.py, constants.py, and adapter files.

Architecture:
- ModelEntry: Complete metadata for a single model (20+ fields)
- ModelCatalog: Registry with query/validation API
- Helper functions: Convenience accessors for common queries

Usage:
    from core.model_catalog import get_model_catalog, ModelTier

    catalog = get_model_catalog()
    model = catalog.get_model("claude-sonnet-4-5")

    ground_truth_models = catalog.list_models(tier=ModelTier.TIER_1)

    capabilities = catalog.get_capabilities("openai/gpt-4o-mini")
    if capabilities["supports_json_mode"]:
        # Use native JSON mode
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class ModelTier(str, Enum):
    """Model tier classification for ground truth workflows"""
    TIER_1 = "tier_1"  # Claude Sonnet 4.5 - Recommended ground truth
    TIER_2 = "tier_2"  # GPT-5, Gemini 2.5 Pro - Alternative ground truth
    TIER_3 = "tier_3"  # Claude Opus 4 - Highest quality (expensive)
    PRODUCTION = "production"  # Production-grade models (fast, affordable)
    BUDGET = "budget"  # Low-cost options


class ModelStatus(str, Enum):
    """Model lifecycle status"""
    STABLE = "stable"  # Production-ready, fully tested
    EXPERIMENTAL = "experimental"  # Available but not fully validated
    DEPRECATED = "deprecated"  # Legacy, scheduled for removal
    PLACEHOLDER = "placeholder"  # Announced but not yet released (e.g., GPT-5)


@dataclass
class ModelEntry:
    """Complete model metadata entry"""

    # === Identification ===
    provider: str  # 'anthropic', 'openai', 'google', 'openrouter', 'deepseek'
    model_id: str  # Backend model identifier (e.g., 'claude-sonnet-4-5', 'openai/gpt-4o-mini')
    display_name: str  # UI display name (e.g., "Claude Sonnet 4.5", "GPT-4o Mini")

    # === Classification ===
    tier: ModelTier  # Ground truth tier or production classification
    category: str  # "Ground Truth", "Production", "Budget"
    status: ModelStatus = ModelStatus.STABLE

    # === Pricing (per million tokens) ===
    cost_input_per_1m: Optional[float] = None  # Input cost in USD
    cost_output_per_1m: Optional[float] = None  # Output cost in USD
    cost_display: str = "$TBD"  # UI display string (e.g., "$3/M", "Free")

    # === Capabilities ===
    context_window: int = 128000  # Max input tokens
    context_display: str = "128K"  # UI display string
    supports_json_mode: bool = False  # Native JSON mode support
    requires_responses_api: bool = False  # GPT-5 Responses API requirement
    supports_vision: bool = False  # Multimodal vision capability
    max_tokens_output: Optional[int] = None  # Max output tokens (if different from default)

    # === Quality Metrics (from Oct 2025 testing) ===
    quality_score: Optional[str] = None  # "10/10", "9/10" from benchmark tests
    extraction_speed_seconds: Optional[float] = None  # Avg extraction time on 15-page PDF

    # === UI Metadata ===
    badges: List[str] = field(default_factory=list)  # ["Tier 1", "Fastest", "Cheapest"]
    recommended: bool = False  # Show in "Recommended" section
    documentation_url: Optional[str] = None  # Provider documentation
    notes: Optional[str] = None  # Testing quirks, limitations, or special guidance


# ============================================================================
# MODEL REGISTRY - Single Source of Truth
# ============================================================================

_MODEL_REGISTRY: List[ModelEntry] = [
    # === GROUND TRUTH MODELS (Tier 1-3) ===

    ModelEntry(
        provider="anthropic",
        model_id="claude-sonnet-4-5",
        display_name="Claude Sonnet 4.5",
        tier=ModelTier.TIER_1,
        category="Ground Truth",
        status=ModelStatus.STABLE,
        cost_input_per_1m=3.0,
        cost_output_per_1m=15.0,
        cost_display="$3/M",
        context_window=200000,
        context_display="200K",
        supports_json_mode=True,
        quality_score="10/10",
        extraction_speed_seconds=4.4,
        badges=["Tier 1", "Recommended"],
        recommended=True,
        documentation_url="https://docs.anthropic.com/en/docs/about-claude/models",
        notes="Best balance of quality, speed, and cost for ground truth datasets."
    ),

    ModelEntry(
        provider="openai",
        model_id="gpt-5",
        display_name="GPT-5",
        tier=ModelTier.TIER_2,
        category="Ground Truth",
        status=ModelStatus.PLACEHOLDER,
        cost_input_per_1m=None,  # TBD
        cost_output_per_1m=None,
        cost_display="$TBD",
        context_window=128000,
        context_display="128K",
        supports_json_mode=False,  # Uses Responses API instead
        requires_responses_api=True,
        quality_score="10/10",
        badges=["Tier 2", "Reasoning"],
        recommended=False,
        documentation_url="https://platform.openai.com/docs/models/gpt-5",
        notes="Requires Responses API for structured output. Non-deterministic reasoning model."
    ),

    ModelEntry(
        provider="google",
        model_id="gemini-2.5-pro",
        display_name="Gemini 2.5 Pro",
        tier=ModelTier.TIER_2,
        category="Ground Truth",
        status=ModelStatus.PLACEHOLDER,
        cost_input_per_1m=None,  # TBD (likely $1.25-2.50)
        cost_output_per_1m=None,
        cost_display="$TBD",
        context_window=2000000,
        context_display="2M",
        supports_json_mode=True,
        quality_score=None,  # Not yet benchmarked
        badges=["Tier 2", "2M Context"],
        recommended=False,
        documentation_url="https://ai.google.dev/gemini-api/docs/models/gemini-v2",
        notes="Pending release. Massive 2M context window for document-heavy cases."
    ),

    ModelEntry(
        provider="google",
        model_id="gemini-2.5-flash",
        display_name="Gemini 2.5 Flash",
        tier=ModelTier.PRODUCTION,
        category="Production",
        status=ModelStatus.STABLE,
        cost_input_per_1m=0.0,  # Free tier (as of June 2025)
        cost_output_per_1m=0.0,
        cost_display="Free",
        context_window=1000000,
        context_display="1M",
        supports_json_mode=True,
        quality_score="9/10",
        badges=["Recommended", "Free", "1M Context"],
        recommended=True,
        documentation_url="https://ai.google.dev/gemini-api/docs/models/gemini-v2",
        notes="Google's recommended model for LangExtract (GA since June 2025). Fast, accurate, budget-friendly."
    ),

    ModelEntry(
        provider="anthropic",
        model_id="claude-opus-4",
        display_name="Claude Opus 4",
        tier=ModelTier.TIER_3,
        category="Ground Truth",
        status=ModelStatus.STABLE,
        cost_input_per_1m=15.0,
        cost_output_per_1m=75.0,
        cost_display="$15/M",
        context_window=200000,
        context_display="200K",
        supports_json_mode=True,
        quality_score="10/10",
        badges=["Tier 3", "Highest Quality"],
        recommended=False,
        documentation_url="https://docs.anthropic.com/en/docs/about-claude/models",
        notes="Highest quality but 5x cost vs Sonnet 4.5. Use for validation only."
    ),

    # === PRODUCTION MODELS (Fast, Affordable, Reliable) ===

    ModelEntry(
        provider="anthropic",
        model_id="claude-3-haiku-20240307",
        display_name="Claude 3 Haiku",
        tier=ModelTier.PRODUCTION,
        category="Production",
        status=ModelStatus.STABLE,
        cost_input_per_1m=0.25,
        cost_output_per_1m=1.25,
        cost_display="$0.25/M",
        context_window=200000,
        context_display="200K",
        supports_json_mode=True,
        quality_score="10/10",
        extraction_speed_seconds=4.4,
        badges=["Fastest", "Production"],
        recommended=True,
        documentation_url="https://docs.anthropic.com/en/docs/about-claude/models",
        notes="Speed champion: 4.4s extractions with 10/10 quality. Best for production."
    ),

    ModelEntry(
        provider="openai",
        model_id="gpt-4o",
        display_name="GPT-4o",
        tier=ModelTier.PRODUCTION,
        category="Production",
        status=ModelStatus.STABLE,
        cost_input_per_1m=2.5,
        cost_output_per_1m=10.0,
        cost_display="$2.50/M",
        context_window=128000,
        context_display="128K",
        supports_json_mode=True,
        supports_vision=True,
        quality_score="10/10",
        badges=["Production", "Multimodal"],
        recommended=True,
        documentation_url="https://platform.openai.com/docs/models/gpt-4o",
        notes="Excellent quality with vision support. Faster than GPT-4 Turbo."
    ),

    ModelEntry(
        provider="openai",
        model_id="gpt-4o-mini",
        display_name="GPT-4o Mini",
        tier=ModelTier.PRODUCTION,
        category="Production",
        status=ModelStatus.STABLE,
        cost_input_per_1m=0.15,
        cost_output_per_1m=0.60,
        cost_display="$0.15/M",
        context_window=128000,
        context_display="128K",
        supports_json_mode=True,
        supports_vision=True,
        quality_score="9/10",
        badges=["Production", "Affordable"],
        recommended=True,
        documentation_url="https://platform.openai.com/docs/models/gpt-4o-mini",
        notes="Recommended starting point: 9/10 quality at excellent cost."
    ),

    ModelEntry(
        provider="google",
        model_id="gemini-2.0-flash",
        display_name="Gemini 2.0 Flash",
        tier=ModelTier.PRODUCTION,
        category="Production",
        status=ModelStatus.STABLE,
        cost_input_per_1m=0.0,
        cost_output_per_1m=0.0,
        cost_display="Free",
        context_window=1000000,
        context_display="1M",
        supports_json_mode=True,
        quality_score="8/10",
        badges=["Free", "1M Context"],
        recommended=True,
        documentation_url="https://ai.google.dev/gemini-api/docs/models/gemini-v2",
        notes="Free tier with generous 1M context. Solid for prototyping."
    ),

    # === BUDGET MODELS (Ultra-low cost) ===

    ModelEntry(
        provider="openrouter",
        model_id="deepseek/deepseek-r1-distill-llama-70b",
        display_name="DeepSeek R1 Distill 70B",
        tier=ModelTier.BUDGET,
        category="Budget",
        status=ModelStatus.STABLE,
        cost_input_per_1m=0.014,
        cost_output_per_1m=0.028,
        cost_display="$0.03/M",
        context_window=128000,
        context_display="128K",
        supports_json_mode=False,  # Uses prompt-based JSON
        quality_score="10/10",
        badges=["Cheapest", "Budget Champion"],
        recommended=True,
        documentation_url="https://openrouter.ai/models/deepseek/deepseek-r1-distill-llama-70b",
        notes="50x cheaper than Claude Sonnet 4.5 with 10/10 quality. Reasoning distilled."
    ),

    ModelEntry(
        provider="openrouter",
        model_id="openai/gpt-oss-120b",
        display_name="GPT-OSS-120B",
        tier=ModelTier.BUDGET,
        category="Budget",
        status=ModelStatus.STABLE,
        cost_input_per_1m=0.27,
        cost_output_per_1m=0.35,
        cost_display="$0.31/M",
        context_window=128000,
        context_display="128K",
        supports_json_mode=False,  # Uses prompt-based JSON
        quality_score="10/10",
        badges=["Open Source", "Privacy Hedge"],
        recommended=False,
        documentation_url="https://openrouter.ai/models/openai/gpt-oss-120b",
        notes="Apache 2.0 licensed. Strategic hedge against vendor lock-in. Can self-host."
    ),

    ModelEntry(
        provider="openrouter",
        model_id="meta-llama/llama-3.3-70b-instruct",
        display_name="Llama 3.3 70B",
        tier=ModelTier.BUDGET,
        category="Budget",
        status=ModelStatus.STABLE,
        cost_input_per_1m=0.35,
        cost_output_per_1m=0.40,
        cost_display="$0.60/M",
        context_window=128000,
        context_display="128K",
        supports_json_mode=True,
        quality_score="10/10",
        badges=["Open Source", "Budget"],
        recommended=False,
        documentation_url="https://openrouter.ai/models/meta-llama/llama-3.3-70b-instruct",
        notes="Meta's flagship open source model. Supports native JSON mode via OpenRouter."
    ),

    ModelEntry(
        provider="openrouter",
        model_id="qwen/qwq-32b",
        display_name="Qwen QwQ 32B",
        tier=ModelTier.BUDGET,
        category="Budget",
        status=ModelStatus.EXPERIMENTAL,
        cost_input_per_1m=0.09,
        cost_output_per_1m=0.14,
        cost_display="$0.115/M",
        context_window=128000,
        context_display="128K",
        supports_json_mode=False,  # Uses prompt-based JSON
        quality_score="7/10",
        badges=["Ultra-Budget"],
        recommended=False,
        documentation_url="https://openrouter.ai/models/qwen/qwq-32b",
        notes="⚠️ May miss events on complex docs. Best for simple document types."
    ),

    ModelEntry(
        provider="openrouter",
        model_id="mistralai/mistral-large-2411",
        display_name="Mistral Large 2411",
        tier=ModelTier.PRODUCTION,
        category="Production",
        status=ModelStatus.STABLE,
        cost_input_per_1m=2.0,
        cost_output_per_1m=6.0,
        cost_display="$2/M",
        context_window=128000,
        context_display="128K",
        supports_json_mode=True,
        quality_score="9/10",
        badges=["Production", "EU Hosting"],
        recommended=False,
        documentation_url="https://openrouter.ai/models/mistralai/mistral-large-2411",
        notes="European alternative to US providers. Good GDPR compliance story."
    ),

    # === GEMINI MODELS VIA OPENROUTER ===

    ModelEntry(
        provider="openrouter",
        model_id="google/gemini-2.5-pro",
        display_name="Gemini 2.5 Pro (OpenRouter)",
        tier=ModelTier.TIER_2,
        category="Ground Truth",
        status=ModelStatus.PLACEHOLDER,
        cost_input_per_1m=None,  # TBD - pricing not yet announced
        cost_output_per_1m=None,
        cost_display="$TBD",
        context_window=2000000,
        context_display="2M",
        supports_json_mode=True,
        quality_score=None,  # Not yet benchmarked
        badges=["Tier 2", "2M Context"],
        recommended=False,
        documentation_url="https://openrouter.ai/models/google/gemini-2.5-pro",
        notes="Gemini 2.5 Pro via OpenRouter unified API. Alternative to direct Google/LangExtract."
    ),

    ModelEntry(
        provider="openrouter",
        model_id="google/gemini-2.0-flash",
        display_name="Gemini 2.0 Flash (OpenRouter)",
        tier=ModelTier.PRODUCTION,
        category="Production",
        status=ModelStatus.STABLE,
        cost_input_per_1m=0.0,  # Free tier via OpenRouter
        cost_output_per_1m=0.0,
        cost_display="Free",
        context_window=1000000,
        context_display="1M",
        supports_json_mode=True,
        quality_score="8/10",
        badges=["Free", "1M Context"],
        recommended=True,
        documentation_url="https://openrouter.ai/models/google/gemini-2.0-flash",
        notes="Free Gemini via OpenRouter. Good for high-volume prototyping."
    ),

    # === DIRECT PROVIDER APIs ===

    ModelEntry(
        provider="deepseek",
        model_id="deepseek-chat",
        display_name="DeepSeek Chat",
        tier=ModelTier.PRODUCTION,
        category="Production",
        status=ModelStatus.STABLE,
        cost_input_per_1m=0.14,
        cost_output_per_1m=0.28,
        cost_display="$0.14/M",
        context_window=64000,
        context_display="64K",
        supports_json_mode=True,
        quality_score="9/10",
        badges=["Production", "Affordable"],
        recommended=False,
        documentation_url="https://platform.deepseek.com/api-docs/",
        notes="Direct API access. Lower cost than OpenRouter for DeepSeek models."
    ),
]


# ============================================================================
# MODEL CATALOG CLASS
# ============================================================================

class ModelCatalog:
    """
    Model registry with query and validation utilities.

    Provides centralized access to model metadata with filtering,
    validation, and convenience methods for common operations.
    """

    def __init__(self, registry: List[ModelEntry]):
        self._registry = registry
        self._index: Dict[str, ModelEntry] = {
            model.model_id: model for model in registry
        }

    def get_model(self, model_id: str) -> Optional[ModelEntry]:
        """
        Get model entry by ID.

        Args:
            model_id: Model identifier (e.g., 'claude-sonnet-4-5', 'openai/gpt-4o-mini')

        Returns:
            ModelEntry if found, None otherwise
        """
        return self._index.get(model_id)

    def list_models(
        self,
        provider: Optional[str] = None,
        category: Optional[str] = None,
        tier: Optional[ModelTier] = None,
        status: Optional[ModelStatus] = None,
        min_context: Optional[int] = None,
        recommended_only: bool = False
    ) -> List[ModelEntry]:
        """
        Query models with filters.

        Args:
            provider: Filter by provider name ('anthropic', 'openai', etc.)
            category: Filter by category ("Ground Truth", "Production", "Budget")
            tier: Filter by tier (ModelTier.TIER_1, etc.)
            status: Filter by status (ModelStatus.STABLE, etc.)
            min_context: Filter by minimum context window size
            recommended_only: Only return models marked as recommended

        Returns:
            List of ModelEntry objects matching all filters
        """
        results = self._registry

        if provider:
            results = [m for m in results if m.provider == provider]

        if category:
            results = [m for m in results if m.category == category]

        if tier:
            results = [m for m in results if m.tier == tier]

        if status:
            results = [m for m in results if m.status == status]

        if min_context:
            results = [m for m in results if m.context_window >= min_context]

        if recommended_only:
            results = [m for m in results if m.recommended]

        return results

    def get_capabilities(self, model_id: str) -> Dict[str, bool]:
        """
        Get model capability flags.

        Args:
            model_id: Model identifier

        Returns:
            Dict with capability flags:
            {
                "supports_json_mode": bool,
                "requires_responses_api": bool,
                "supports_vision": bool
            }

            Returns empty dict if model not found.
        """
        model = self.get_model(model_id)
        if not model:
            return {}

        return {
            "supports_json_mode": model.supports_json_mode,
            "requires_responses_api": model.requires_responses_api,
            "supports_vision": model.supports_vision,
        }

    def get_pricing(self, model_id: str) -> Optional[Dict[str, float]]:
        """
        Get pricing information for cost estimation.

        Args:
            model_id: Model identifier

        Returns:
            Dict with pricing data:
            {
                "cost_input_per_1m": float,
                "cost_output_per_1m": float
            }

            Returns None if model not found or pricing unavailable.
        """
        model = self.get_model(model_id)
        if not model or model.cost_input_per_1m is None:
            return None

        return {
            "cost_input_per_1m": model.cost_input_per_1m,
            "cost_output_per_1m": model.cost_output_per_1m,
        }

    def validate_model_id(self, model_id: str) -> bool:
        """
        Check if model ID exists in catalog.

        Args:
            model_id: Model identifier to validate

        Returns:
            True if model exists, False otherwise
        """
        return model_id in self._index

    def resolve_runtime_model(
        self,
        provider: str,
        runtime_model: Optional[str],
        env_defaults: Dict[str, str]
    ) -> str:
        """
        Resolve final model using precedence chain.

        Precedence (highest to lowest):
        1. runtime_model (UI selection)
        2. Environment variable (env_defaults)
        3. First model in catalog for provider

        Args:
            provider: Provider name ('anthropic', 'openai', etc.)
            runtime_model: Runtime model override from UI
            env_defaults: Dict mapping provider to env var default

        Returns:
            Final model identifier

        Raises:
            ValueError: If no models found for provider
        """
        # Precedence 1: Runtime model (UI selection)
        if runtime_model:
            return runtime_model

        # Precedence 2: Environment variable
        if provider in env_defaults and env_defaults[provider]:
            return env_defaults[provider]

        # Precedence 3: First model in catalog for provider
        provider_models = self.list_models(provider=provider)
        if not provider_models:
            raise ValueError(f"No models found for provider: {provider}")

        return provider_models[0].model_id

    def get_all_model_ids(self) -> List[str]:
        """Get list of all model IDs in catalog."""
        return list(self._index.keys())

    def get_ground_truth_models(self) -> List[ModelEntry]:
        """Get all ground truth models (Tier 1-3)."""
        return [
            m for m in self._registry
            if m.tier in [ModelTier.TIER_1, ModelTier.TIER_2, ModelTier.TIER_3]
        ]

    def get_recommended_models(self) -> List[ModelEntry]:
        """Get all recommended models for production use."""
        return [m for m in self._registry if m.recommended]


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

_global_catalog: Optional[ModelCatalog] = None


def get_model_catalog() -> ModelCatalog:
    """
    Get the global model catalog instance (singleton pattern).

    Returns:
        ModelCatalog with all registered models
    """
    global _global_catalog
    if _global_catalog is None:
        _global_catalog = ModelCatalog(_MODEL_REGISTRY)
    return _global_catalog


def get_model(model_id: str) -> Optional[ModelEntry]:
    """Convenience function: Get model by ID."""
    return get_model_catalog().get_model(model_id)


def list_models(**filters) -> List[ModelEntry]:
    """Convenience function: Query models with filters."""
    return get_model_catalog().list_models(**filters)


def get_capabilities(model_id: str) -> Dict[str, bool]:
    """Convenience function: Get model capabilities."""
    return get_model_catalog().get_capabilities(model_id)


def get_pricing(model_id: str) -> Optional[Dict[str, float]]:
    """Convenience function: Get model pricing."""
    return get_model_catalog().get_pricing(model_id)


def validate_model_id(model_id: str) -> bool:
    """Convenience function: Validate model ID."""
    return get_model_catalog().validate_model_id(model_id)


# ============================================================================
# MIGRATION HELPERS (for app.py refactoring)
# ============================================================================

def get_ui_model_config_list() -> List:
    """
    Get model list formatted for UI dropdowns (app.py compatibility).

    Returns list of objects supporting attribute access matching the old ModelConfig dataclass:
    - m.provider
    - m.model_id
    - m.display_name
    - m.category
    - m.cost_per_1m
    - m.context_window
    - m.quality_score
    - m.badges

    Example:
        models = get_ui_model_config_list()
        for m in models:
            print(f"{m.display_name}: {m.cost_per_1m}")
    """
    from types import SimpleNamespace

    catalog = get_model_catalog()

    class UILegacyModelConfig(SimpleNamespace):
        """Compatibility shim matching legacy ModelConfig API used in app.py."""

        def format_inline(self) -> str:
            parts: List[str] = []
            quality = getattr(self, "quality_score", None)
            if quality:
                parts.append(quality)

            cost = getattr(self, "cost_per_1m", None)
            if cost:
                parts.append(cost)

            context = getattr(self, "context_window", None)
            if context:
                parts.append(context)

            badges = getattr(self, "badges", None) or []
            parts.extend(badges)

            return " • ".join(parts)

    return [
        UILegacyModelConfig(
            provider=model.provider,
            model_id=model.model_id,
            display_name=model.display_name,
            category=model.category,
            cost_per_1m=model.cost_display,
            context_window=model.context_display,
            quality_score=model.quality_score or "",
            badges=model.badges,
        )
        for model in catalog._registry
    ]
