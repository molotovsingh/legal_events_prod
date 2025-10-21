"""
Event Extractor Prompts - Named prompt registry with versioning

Provides centralized prompt management for event extractors with:
- Named prompt IDs for catalog references
- Versioning and changelog tracking
- Provider-specific prompt optimization
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class PromptEntry:
    """Named prompt with metadata"""

    prompt_id: str  # Unique identifier (e.g., 'legal_events_v1', 'legal_events_concise')
    prompt_text: str  # Full prompt content
    version: str = "1.0"
    description: str = ""  # Usage notes, optimization tips
    changelog: str = ""  # Version history
    recommended_providers: List[str] = field(default_factory=list)  # ['openrouter', 'openai'] etc.


# ============================================================================
# PROMPT REGISTRY
# ============================================================================

_PROMPT_REGISTRY: Dict[str, PromptEntry] = {
    "legal_events_v1": PromptEntry(
        prompt_id="legal_events_v1",
        prompt_text="""Extract all legally significant events from the following document.
For each event, provide:
- event_particulars: A clear 2-8 sentence description of what happened
- citation: Legal reference if explicitly stated (or empty string if none)
- date: Specific date if mentioned (or empty string if none)

Return a JSON array of events.""",
        version="1.0",
        description="Baseline legal events extraction prompt",
        changelog="2025-02-15: Initial version",
        recommended_providers=['langextract', 'openrouter', 'openai', 'anthropic']
    ),

    "legal_events_concise": PromptEntry(
        prompt_id="legal_events_concise",
        prompt_text="""Extract key legal events. For each event:
- event_particulars: 1-2 sentence summary
- citation: Legal reference (empty if none)
- date: Date if stated (empty if none)

Return JSON array.""",
        version="1.0",
        description="Concise prompt for budget models (shorter context window)",
        changelog="2025-02-15: Created for budget models",
        recommended_providers=['deepseek', 'qwen']
    ),

    # Future: Add more specialized prompts
    # "contract_milestones": For contract-specific event extraction
    # "litigation_timeline": For court case timeline extraction
    # "regulatory_compliance": For compliance event extraction
}


# ============================================================================
# PROMPT REGISTRY ACCESS
# ============================================================================

def get_prompt_by_id(prompt_id: str) -> Optional[str]:
    """
    Get prompt text by ID.

    Args:
        prompt_id: Prompt identifier

    Returns:
        Prompt text if found, None otherwise
    """
    entry = _PROMPT_REGISTRY.get(prompt_id)
    if entry:
        return entry.prompt_text

    logger.warning(f"Prompt ID '{prompt_id}' not found in registry")
    return None


def get_prompt_entry(prompt_id: str) -> Optional[PromptEntry]:
    """Get full prompt entry with metadata"""
    return _PROMPT_REGISTRY.get(prompt_id)


def list_prompts(provider: Optional[str] = None) -> List[PromptEntry]:
    """
    List available prompts, optionally filtered by provider.

    Args:
        provider: Filter by recommended provider (e.g., 'openrouter')

    Returns:
        List of PromptEntry objects
    """
    prompts = list(_PROMPT_REGISTRY.values())

    if provider:
        prompts = [
            p for p in prompts
            if provider in p.recommended_providers or not p.recommended_providers
        ]

    return prompts


def get_all_prompt_ids() -> List[str]:
    """Get list of all prompt IDs"""
    return list(_PROMPT_REGISTRY.keys())
