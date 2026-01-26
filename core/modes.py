"""
Processing Modes Configuration

Maps user-friendly mode names to provider/model configurations.
Configurable via environment variables for easy deployment customization.

This abstracts away technical LLM details from end users (lawyers),
presenting simple "Best / Balanced / Fast" options instead.
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
    icon: str  # "star", "scales", "bolt" - for frontend display
    estimated_speed: str  # e.g., "~30s per page"


def _build_default_modes() -> Dict[str, ProcessingMode]:
    """
    Build default mode configurations.

    Provider/model mappings can be overridden via environment variables:
    - MODE_BEST_PROVIDER, MODE_BEST_MODEL, MODE_BEST_DOC_EXTRACTOR
    - MODE_BALANCED_PROVIDER, MODE_BALANCED_MODEL, MODE_BALANCED_DOC_EXTRACTOR
    - MODE_FAST_PROVIDER, MODE_FAST_MODEL, MODE_FAST_DOC_EXTRACTOR
    """
    return {
        "best": ProcessingMode(
            id="best",
            name="Best Quality",
            description="Highest accuracy for complex legal documents. Takes longer but catches more details.",
            provider=os.getenv("MODE_BEST_PROVIDER", "anthropic"),
            model=os.getenv("MODE_BEST_MODEL", "claude-3-5-sonnet-20241022"),
            doc_extractor=os.getenv("MODE_BEST_DOC_EXTRACTOR", "qwen_vl"),
            icon="star",
            estimated_speed="~45s per page"
        ),
        "balanced": ProcessingMode(
            id="balanced",
            name="Balanced",
            description="Good balance of speed and accuracy. Recommended for most documents.",
            provider=os.getenv("MODE_BALANCED_PROVIDER", "openrouter"),
            model=os.getenv("MODE_BALANCED_MODEL", "meta-llama/llama-3.3-70b-instruct"),
            doc_extractor=os.getenv("MODE_BALANCED_DOC_EXTRACTOR", "docling"),
            icon="scales",
            estimated_speed="~20s per page"
        ),
        "fast": ProcessingMode(
            id="fast",
            name="Fast",
            description="Quickest processing for straightforward documents. Best for clear, well-formatted PDFs.",
            provider=os.getenv("MODE_FAST_PROVIDER", "openrouter"),
            model=os.getenv("MODE_FAST_MODEL", "meta-llama/llama-3.1-8b-instruct"),
            doc_extractor=os.getenv("MODE_FAST_DOC_EXTRACTOR", "docling"),
            icon="bolt",
            estimated_speed="~8s per page"
        )
    }


# Build modes at module load time
DEFAULT_MODES = _build_default_modes()

# Default mode for new users
DEFAULT_MODE_ID = "balanced"


def get_mode(mode_id: str) -> Optional[ProcessingMode]:
    """
    Get mode configuration by ID.

    Args:
        mode_id: Mode identifier ("best", "balanced", "fast")

    Returns:
        ProcessingMode if found, None otherwise
    """
    return DEFAULT_MODES.get(mode_id)


def list_modes() -> List[ProcessingMode]:
    """
    List all available modes in display order.

    Returns:
        List of ProcessingMode instances (best, balanced, fast)
    """
    # Return in specific order for UI display
    order = ["best", "balanced", "fast"]
    return [DEFAULT_MODES[mode_id] for mode_id in order if mode_id in DEFAULT_MODES]


def get_default_mode() -> ProcessingMode:
    """
    Get the default mode (balanced).

    Returns:
        The default ProcessingMode instance
    """
    return DEFAULT_MODES[DEFAULT_MODE_ID]


def get_mode_ids() -> List[str]:
    """
    Get list of valid mode IDs.

    Returns:
        List of mode ID strings
    """
    return list(DEFAULT_MODES.keys())
