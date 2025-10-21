"""
Document Extractor Prompts - Named prompts for vision-based document extractors

This module stores model-specific prompts that can be referenced by extractor_id
in the DocumentExtractorCatalog. Allows centralized prompt management and versioning.

Usage:
    from core.doc_extractor_prompts import get_prompt_by_id

    prompt = get_prompt_by_id("qwen_vl_doc")
"""

from typing import Dict

# ============================================================================
# PROMPT REGISTRY
# ============================================================================

QWEN_VL_DOC_PROMPT = """
Transcribe this document completely and accurately, preserving all content and structure.

Pay special attention to:
- All dates in their original format (critical for chronological analysis)
- Legal citations and case references
- Party names and their roles
- Numbered sections, clauses, and sub-clauses
- Tables and schedules (convert to markdown tables)
- Signature blocks and attestation clauses
- Temporal markers and sequences

Return the complete document text in clean markdown format.
If the document has multiple pages, transcribe them in order and maintain continuity.
""".strip()


# Prompt registry mapping prompt IDs to prompt strings
_PROMPT_REGISTRY: Dict[str, str] = {
    "qwen_vl_doc": QWEN_VL_DOC_PROMPT,
}


# ============================================================================
# PUBLIC API
# ============================================================================

def get_prompt_by_id(prompt_id: str) -> str:
    """
    Get a document extractor prompt by ID.

    Args:
        prompt_id: Prompt identifier (e.g., 'qwen_vl_doc')

    Returns:
        Prompt string

    Raises:
        KeyError: If prompt_id not found in registry
    """
    if prompt_id not in _PROMPT_REGISTRY:
        raise KeyError(
            f"Prompt '{prompt_id}' not found. Available prompts: {list(_PROMPT_REGISTRY.keys())}"
        )

    return _PROMPT_REGISTRY[prompt_id]


def list_prompt_ids() -> list[str]:
    """
    Get list of all available prompt IDs.

    Returns:
        List of prompt identifiers
    """
    return list(_PROMPT_REGISTRY.keys())


def register_prompt(prompt_id: str, prompt: str) -> None:
    """
    Register a new prompt in the registry (for dynamic additions).

    Args:
        prompt_id: Unique identifier for the prompt
        prompt: The prompt string

    Raises:
        ValueError: If prompt_id already exists
    """
    if prompt_id in _PROMPT_REGISTRY:
        raise ValueError(
            f"Prompt ID '{prompt_id}' already exists. "
            f"Use a different ID or update the existing prompt directly."
        )

    _PROMPT_REGISTRY[prompt_id] = prompt
