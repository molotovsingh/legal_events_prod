"""
Processing Modes Configuration

Maps user-friendly mode names to provider/model configurations.
Configurable via environment variables for easy deployment customization.

This abstracts away technical LLM details from end users (lawyers),
presenting simple "Best / Balanced / Budget" options instead.

Developer modes (gpt5, opus, deepseek, budget) are also available for testing.
"""

from dataclasses import dataclass
from typing import Dict, Optional, List
import os


@dataclass
class ProcessingMode:
    """A user-facing processing mode that maps to specific provider/model config."""
    id: str
    name: str
    description: str
    provider: str
    model: str
    doc_extractor: str
    icon: str  # "star", "scales", "dollar", "flask" - for frontend display
    estimated_speed: str  # e.g., "~30s per page"
    is_developer_mode: bool = False  # Hidden from regular users


# Environment variable overrides for per-mode model selection
MODE_BEST_MODEL = os.getenv("MODE_BEST_MODEL", "anthropic/claude-sonnet-4.5")
MODE_BALANCED_MODEL = os.getenv("MODE_BALANCED_MODEL", "anthropic/claude-haiku-4.5")
MODE_MEDIUM_MODEL = os.getenv("MODE_MEDIUM_MODEL", "google/gemini-2.5-flash-preview-05-20")
MODE_GPT5_MODEL = os.getenv("MODE_GPT5_MODEL", "openai/gpt-5.2")
MODE_OPUS_MODEL = os.getenv("MODE_OPUS_MODEL", "anthropic/claude-opus-4.5")
MODE_DEEPSEEK_MODEL = os.getenv("MODE_DEEPSEEK_MODEL", "deepseek/deepseek-r1")
MODE_BUDGET_MODEL = os.getenv("MODE_BUDGET_MODEL", "meta-llama/llama-3.3-70b-instruct")


def _build_default_modes() -> Dict[str, ProcessingMode]:
    """
    Build default mode configurations.

    Provider/model mappings can be overridden via environment variables:
    - MODE_BEST_MODEL, MODE_BALANCED_MODEL, MODE_MEDIUM_MODEL
    - MODE_GPT5_MODEL, MODE_OPUS_MODEL, MODE_DEEPSEEK_MODEL, MODE_BUDGET_MODEL

    Model categorization (verified via OpenRouter smoke test Jan 2026):
    - Best: anthropic/claude-sonnet-4.5 - 10/10 quality, $3/M, 6.7s latency
    - Balanced: anthropic/claude-haiku-4.5 - 10/10 quality, $1/M, 4.0s latency
    - Medium: google/gemini-2.5-flash - 9/10 quality, $0.15/M, 2.6s latency

    Developer modes:
    - gpt5: openai/gpt-5.2 - Latest GPT-5, $2.5/M, 6.9s latency
    - opus: anthropic/claude-opus-4.5 - Highest quality, $5/M, 7.1s latency
    - deepseek: deepseek/deepseek-r1 - Reasoning model, $0.55/M, 70.9s latency
    - budget: meta-llama/llama-3.3-70b-instruct - Cheapest, $0.10/M, 5.4s latency
    """
    return {
        # === USER-FACING MODES ===
        "best": ProcessingMode(
            id="best",
            name="Best Quality",
            description="Highest accuracy for critical legal matters. Claude Sonnet 4.5 - $3/M.",
            provider=os.getenv("MODE_BEST_PROVIDER", "openrouter"),
            model=MODE_BEST_MODEL,
            doc_extractor=os.getenv("MODE_BEST_DOC_EXTRACTOR", "docling"),
            icon="star",
            estimated_speed="~7s per page"
        ),
        "balanced": ProcessingMode(
            id="balanced",
            name="Balanced",
            description="Excellent quality at low cost. Claude Haiku 4.5 - $1/M, fast.",
            provider=os.getenv("MODE_BALANCED_PROVIDER", "openrouter"),
            model=MODE_BALANCED_MODEL,
            doc_extractor=os.getenv("MODE_BALANCED_DOC_EXTRACTOR", "docling"),
            icon="scales",
            estimated_speed="~4s per page"
        ),
        "medium": ProcessingMode(
            id="medium",
            name="Budget",
            description="Cost-effective for high-volume. Gemini 2.5 Flash - $0.15/M, fastest.",
            provider=os.getenv("MODE_MEDIUM_PROVIDER", "openrouter"),
            model=MODE_MEDIUM_MODEL,
            doc_extractor=os.getenv("MODE_MEDIUM_DOC_EXTRACTOR", "docling"),
            icon="dollar",
            estimated_speed="~3s per page"
        ),

        # === DEVELOPER/TESTING MODES ===
        "gpt5": ProcessingMode(
            id="gpt5",
            name="GPT-5.2 (Dev)",
            description="Latest OpenAI model. GPT-5.2 - $2.5/M, agentic capabilities.",
            provider="openrouter",
            model=MODE_GPT5_MODEL,
            doc_extractor="docling",
            icon="flask",
            estimated_speed="~7s per page",
            is_developer_mode=True
        ),
        "opus": ProcessingMode(
            id="opus",
            name="Claude Opus 4.5 (Dev)",
            description="Highest quality model. Claude Opus 4.5 - $5/M, ground truth.",
            provider="openrouter",
            model=MODE_OPUS_MODEL,
            doc_extractor="docling",
            icon="flask",
            estimated_speed="~7s per page",
            is_developer_mode=True
        ),
        "deepseek": ProcessingMode(
            id="deepseek",
            name="DeepSeek R1 (Dev)",
            description="Reasoning specialist. DeepSeek R1 - $0.55/M, slow but thorough.",
            provider="openrouter",
            model=MODE_DEEPSEEK_MODEL,
            doc_extractor="docling",
            icon="flask",
            estimated_speed="~70s per page",
            is_developer_mode=True
        ),
        "budget": ProcessingMode(
            id="budget",
            name="Llama 3.3 70B (Dev)",
            description="Cheapest model. Llama 3.3 70B - $0.10/M, excellent value.",
            provider="openrouter",
            model=MODE_BUDGET_MODEL,
            doc_extractor="docling",
            icon="flask",
            estimated_speed="~5s per page",
            is_developer_mode=True
        ),
    }


# Build modes at module load time
DEFAULT_MODES = _build_default_modes()

# Default mode for new users
DEFAULT_MODE_ID = "balanced"


def get_mode(mode_id: str) -> Optional[ProcessingMode]:
    """
    Get mode configuration by ID.

    Args:
        mode_id: Mode identifier ("best", "balanced", "medium")

    Returns:
        ProcessingMode if found, None otherwise
    """
    return DEFAULT_MODES.get(mode_id)


def list_modes(include_developer: bool = False) -> List[ProcessingMode]:
    """
    List all available modes in display order.

    Args:
        include_developer: If True, include developer/testing modes

    Returns:
        List of ProcessingMode instances
    """
    # User-facing modes in specific order
    user_order = ["best", "balanced", "medium"]
    # Developer modes
    dev_order = ["gpt5", "opus", "deepseek", "budget"]

    modes = [DEFAULT_MODES[mode_id] for mode_id in user_order if mode_id in DEFAULT_MODES]

    if include_developer:
        modes.extend([DEFAULT_MODES[mode_id] for mode_id in dev_order if mode_id in DEFAULT_MODES])

    return modes


def get_default_mode() -> ProcessingMode:
    """
    Get the default mode (balanced).

    Returns:
        The default ProcessingMode instance
    """
    return DEFAULT_MODES[DEFAULT_MODE_ID]


def get_mode_ids(include_developer: bool = False) -> List[str]:
    """
    Get list of valid mode IDs.

    Args:
        include_developer: If True, include developer/testing mode IDs

    Returns:
        List of mode ID strings
    """
    if include_developer:
        return list(DEFAULT_MODES.keys())
    else:
        return [mode_id for mode_id, mode in DEFAULT_MODES.items() if not mode.is_developer_mode]


def is_developer_mode(mode_id: str) -> bool:
    """Check if a mode ID is a developer mode."""
    mode = DEFAULT_MODES.get(mode_id)
    return mode.is_developer_mode if mode else False
