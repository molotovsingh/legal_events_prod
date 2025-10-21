"""
Document Extractor Catalog - Centralized pricing and metadata for document extraction layer

This module provides document extractor metadata (Layer 1 / pre-processing costs)
separate from LLM model costs (Layer 2 / event extraction).

Architecture mirrors ModelCatalog for consistency.

Usage:
    from core.document_extractor_catalog import get_doc_extractor_catalog

    catalog = get_doc_extractor_catalog()
    pricing = catalog.get_pricing('qwen_vl')
    # Returns: {'cost_per_page': 0.00512, 'cost_display': '$0.077 per 15-page doc'}
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class DocExtractorEntry:
    """Document extractor metadata entry"""

    # === Identification ===
    extractor_id: str  # 'docling', 'qwen_vl', 'gemini'
    display_name: str  # UI display name
    provider: str  # 'local', 'openrouter', 'google'

    # === Pricing (per page/image) ===
    cost_per_page: float  # Cost per page/image in USD
    cost_display: str  # UI display string (e.g., "$0.077 per 15 pages", "FREE")

    # === Capabilities ===
    supports_pdf: bool = True
    supports_docx: bool = False
    supports_images: bool = False
    supports_vision: bool = False  # Multimodal vision understanding

    # === Quality/Performance ===
    processing_speed: str = "medium"  # 'fast', 'medium', 'slow'
    ocr_quality: str = "medium"  # 'high', 'medium', 'low', 'n/a'

    # === Metadata ===
    notes: str = ""  # Special considerations, limitations
    documentation_url: Optional[str] = None
    recommended: bool = False

    # === Registry Control ===
    enabled: bool = True  # Toggle extractor availability in UI/CLI
    prompt_id: Optional[str] = None  # Reference to named prompt in prompts module
    prompt_override: Optional[str] = None  # Inline prompt override (takes precedence over prompt_id)
    factory_callable: Optional[str] = None  # Fully-qualified import path to factory function (e.g., "src.core.extractor_factory._create_docling_document_extractor")


# ============================================================================
# DOCUMENT EXTRACTOR REGISTRY
# ============================================================================

_DOC_EXTRACTOR_REGISTRY: List[DocExtractorEntry] = [
    # === LOCAL EXTRACTORS (Free) ===

    DocExtractorEntry(
        extractor_id="docling",
        display_name="Docling (Local OCR)",
        provider="local",
        cost_per_page=0.0,
        cost_display="FREE",
        supports_pdf=True,
        supports_docx=True,
        supports_images=True,
        supports_vision=False,
        processing_speed="fast",
        ocr_quality="high",
        recommended=True,
        notes="Local Tesseract OCR. Fast, free, production-ready. Use for most documents.",
        documentation_url="https://github.com/DS4SD/docling",
        enabled=True,
        prompt_id=None,  # No prompt needed (uses Tesseract OCR)
        prompt_override=None,
        factory_callable="src.core.extractor_factory._create_docling_document_extractor"
    ),

    # === VISION EXTRACTORS (Paid) ===

    DocExtractorEntry(
        extractor_id="qwen_vl",
        display_name="Qwen3-VL (Budget Vision)",
        provider="openrouter",
        cost_per_page=0.00512,  # $0.00512 per image (verified Oct 16, 2025)
        cost_display="$0.077 per 15-page doc",
        supports_pdf=True,
        supports_docx=False,
        supports_images=True,
        supports_vision=True,
        processing_speed="medium",
        ocr_quality="high",
        recommended=False,
        notes=(
            "Budget vision API for multimodal parsing. "
            "256K context. Use when Docling OCR fails on poor scans."
        ),
        documentation_url="https://openrouter.ai/models/qwen/qwen3-vl-8b-instruct",
        enabled=True,
        prompt_id="qwen_vl_doc",  # References doc_extractor_prompts.QWEN_VL_DOC_PROMPT
        prompt_override=None,
        factory_callable="src.core.extractor_factory._create_qwen_vl_document_extractor"
    ),
]


# ============================================================================
# DOCUMENT EXTRACTOR CATALOG CLASS
# ============================================================================

class DocumentExtractorCatalog:
    """
    Document extractor registry with query and pricing utilities.

    Provides centralized access to Layer 1 (document extraction) pricing and metadata.
    """

    def __init__(self, registry: List[DocExtractorEntry]):
        self._registry = registry
        self._index: Dict[str, DocExtractorEntry] = {
            extractor.extractor_id: extractor for extractor in registry
        }

    def get_extractor(self, extractor_id: str) -> Optional[DocExtractorEntry]:
        """
        Get extractor entry by ID.

        Args:
            extractor_id: Extractor identifier ('docling', 'qwen_vl', 'gemini')

        Returns:
            DocExtractorEntry if found, None otherwise
        """
        return self._index.get(extractor_id)

    def list_extractors(
        self,
        provider: Optional[str] = None,
        supports_pdf: Optional[bool] = None,
        supports_vision: Optional[bool] = None,
        recommended_only: bool = False,
        free_only: bool = False,
        enabled: Optional[bool] = None
    ) -> List[DocExtractorEntry]:
        """
        Query extractors with filters.

        Args:
            provider: Filter by provider ('local', 'openrouter', 'google')
            supports_pdf: Filter by PDF support
            supports_vision: Filter by vision capability
            recommended_only: Only return recommended extractors
            free_only: Only return zero-cost extractors
            enabled: Filter by enabled status (None = no filter, True = enabled only, False = disabled only)

        Returns:
            List of DocExtractorEntry objects matching all filters
        """
        results = self._registry

        if provider:
            results = [e for e in results if e.provider == provider]

        if supports_pdf is not None:
            results = [e for e in results if e.supports_pdf == supports_pdf]

        if supports_vision is not None:
            results = [e for e in results if e.supports_vision == supports_vision]

        if recommended_only:
            results = [e for e in results if e.recommended]

        if free_only:
            results = [e for e in results if e.cost_per_page == 0.0]

        if enabled is not None:
            results = [e for e in results if e.enabled == enabled]

        return results

    def get_pricing(self, extractor_id: str) -> Optional[Dict[str, float]]:
        """
        Get pricing information for cost estimation.

        Args:
            extractor_id: Extractor identifier

        Returns:
            Dict with pricing data:
            {
                "cost_per_page": float,
                "cost_display": str
            }

            Returns None if extractor not found.
        """
        extractor = self.get_extractor(extractor_id)
        if not extractor:
            return None

        return {
            "cost_per_page": extractor.cost_per_page,
            "cost_display": extractor.cost_display,
        }

    def estimate_cost(
        self,
        extractor_id: str,
        page_count: int
    ) -> Dict[str, any]:
        """
        Estimate document extraction cost.

        Args:
            extractor_id: Extractor identifier
            page_count: Number of pages to process

        Returns:
            Dict with cost estimate:
            {
                "extractor_id": str,
                "display_name": str,
                "page_count": int,
                "cost_per_page": float,
                "cost_usd": float,
                "cost_display": str,
                "pricing_available": bool
            }
        """
        extractor = self.get_extractor(extractor_id)

        if not extractor:
            logger.warning(f"Document extractor '{extractor_id}' not found in catalog")
            return {
                "extractor_id": extractor_id,
                "display_name": extractor_id,
                "page_count": page_count,
                "cost_per_page": 0.0,
                "cost_usd": 0.0,
                "cost_display": "Unknown extractor",
                "pricing_available": False
            }

        cost_usd = page_count * extractor.cost_per_page

        return {
            "extractor_id": extractor_id,
            "display_name": extractor.display_name,
            "page_count": page_count,
            "cost_per_page": extractor.cost_per_page,
            "cost_usd": cost_usd,
            "cost_display": f"${cost_usd:.4f}" if cost_usd > 0 else "FREE",
            "pricing_available": True
        }

    def validate_extractor_id(self, extractor_id: str) -> bool:
        """
        Check if extractor ID exists in catalog.

        Args:
            extractor_id: Extractor identifier to validate

        Returns:
            True if extractor exists, False otherwise
        """
        return extractor_id in self._index

    def get_all_extractor_ids(self) -> List[str]:
        """Get list of all extractor IDs in catalog."""
        return list(self._index.keys())

    def get_prompt(self, extractor_id: str) -> Optional[str]:
        """
        Get document extraction prompt for a specific extractor.

        Prompt resolution priority:
        1. prompt_override (inline override if specified)
        2. prompt_id (lookup in prompts module)
        3. None (extractor uses default behavior)

        Args:
            extractor_id: Extractor identifier

        Returns:
            Prompt string if found, None if no prompt configured
        """
        extractor = self.get_extractor(extractor_id)
        if not extractor:
            return None

        # Priority 1: Inline override
        if extractor.prompt_override:
            return extractor.prompt_override

        # Priority 2: Prompt ID reference
        if extractor.prompt_id:
            try:
                from .doc_extractor_prompts import get_prompt_by_id
                return get_prompt_by_id(extractor.prompt_id)
            except (ImportError, KeyError) as e:
                logger.warning(
                    f"Failed to load prompt '{extractor.prompt_id}' for {extractor_id}: {e}"
                )
                return None

        # Priority 3: No prompt configured
        return None


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

_global_catalog: Optional[DocumentExtractorCatalog] = None


def get_doc_extractor_catalog() -> DocumentExtractorCatalog:
    """
    Get the global document extractor catalog instance (singleton pattern).

    Returns:
        DocumentExtractorCatalog with all registered extractors
    """
    global _global_catalog
    if _global_catalog is None:
        _global_catalog = DocumentExtractorCatalog(_DOC_EXTRACTOR_REGISTRY)
    return _global_catalog


def get_doc_extractor(extractor_id: str) -> Optional[DocExtractorEntry]:
    """Convenience function: Get extractor by ID."""
    return get_doc_extractor_catalog().get_extractor(extractor_id)


def list_doc_extractors(**filters) -> List[DocExtractorEntry]:
    """Convenience function: Query extractors with filters."""
    return get_doc_extractor_catalog().list_extractors(**filters)


def get_doc_pricing(extractor_id: str) -> Optional[Dict[str, float]]:
    """Convenience function: Get extractor pricing."""
    return get_doc_extractor_catalog().get_pricing(extractor_id)


def estimate_doc_cost(extractor_id: str, page_count: int) -> Dict[str, any]:
    """Convenience function: Estimate document extraction cost."""
    return get_doc_extractor_catalog().estimate_cost(extractor_id, page_count)
