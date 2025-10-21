"""
Pipeline Metadata Module - Stealth ID Generation & DB-Ready Schema

Provides cryptic pipeline identifiers and comprehensive metadata capture
for parser-extractor matrix testing with zero-friction migration to database.
"""

from __future__ import annotations

import os
import socket
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .legal_pipeline_refactored import LegalEventsPipeline

# Provider code mappings (obfuscated)
PROVIDER_CODES = {
    'langextract': 'LE1',
    'openrouter': 'OR4',
    'opencode_zen': 'OZ5',
    'openai': 'OA2',
    'anthropic': 'AN3'
}

# OCR engine code mappings
OCR_CODES = {
    'tesseract': 'TS1',
    'easyocr': 'EO2',
    'ocrmac': 'OM3',
    'rapidocr': 'RO4',
    'none': 'XX0'
}

# Parser code mappings
PARSER_CODES = {
    'docling': 'DL2'
}


def _get_environment() -> str:
    """
    Auto-detect execution environment (hostname)

    Returns:
        Hostname for machine tracking (e.g., 'MacBook-Pro.local', 'aws-instance-i-123')
    """
    try:
        return socket.gethostname()
    except Exception:
        return 'unknown'


def generate_pipeline_id(
    parser: str,
    provider: str,
    ocr: Optional[str],
    table_mode: Optional[str],
    timestamp: datetime
) -> str:
    """
    Generate cryptic pipeline identifier

    Format: DL2-OR4-TS1-F-20251004143022

    Args:
        parser: Parser name ('docling')
        provider: Provider name ('openrouter', 'langextract', etc.)
        ocr: OCR engine name or None
        table_mode: Table extraction mode ('FAST', 'ACCURATE', or None)
        timestamp: Processing timestamp

    Returns:
        Cryptic pipeline ID string
    """
    # Safe lookups with fallbacks
    parser_code = PARSER_CODES.get(parser, 'XX0')
    provider_code = PROVIDER_CODES.get(provider, 'XX0')
    ocr_code = OCR_CODES.get(ocr or 'none', 'XX0')

    # Table mode: first character or X
    mode_code = (table_mode or 'UNKNOWN')[0] if table_mode else 'X'

    # Timestamp: compact format
    ts = timestamp.strftime('%Y%m%d%H%M%S')

    return f"{parser_code}-{provider_code}-{ocr_code}-{mode_code}-{ts}"


@dataclass
class PipelineMetadata:
    """
    Complete pipeline execution metadata (maps 1:1 to future database schema)

    This dataclass captures everything needed for:
    - Experiment tracking
    - Performance benchmarking
    - Cost analysis
    - Quality comparison
    - Exact reproducibility
    """

    # Primary key
    run_id: str
    timestamp: datetime

    # Configuration (what defines the experiment)
    parser_name: str
    parser_version: Optional[str] = None
    provider_name: str = 'langextract'
    provider_model: Optional[str] = None  # e.g., 'openai/gpt-4o-mini', 'gemini-2.0-flash'
    ocr_engine: Optional[str] = None
    table_mode: Optional[str] = None

    # Environment tracking (auto-captured, zero config)
    environment: str = field(default_factory=_get_environment)
    session_label: Optional[str] = field(default_factory=lambda: os.getenv('PIPELINE_SESSION_LABEL'))

    # Input metadata
    input_filename: str = 'unknown'
    input_size_bytes: Optional[int] = None
    input_pages: Optional[int] = None

    # Output location
    output_path: Optional[str] = None

    # Performance metrics (captured during processing)
    docling_seconds: Optional[float] = None
    extractor_seconds: Optional[float] = None
    total_seconds: Optional[float] = None

    # Quality metrics (calculated from results)
    events_extracted: Optional[int] = None
    citations_found: Optional[int] = None
    avg_detail_length: Optional[float] = None

    # Status tracking
    status: str = 'pending'  # 'success', 'failed', 'partial'
    error_message: Optional[str] = None

    # Full config snapshot (for exact reproducibility)
    config_snapshot: Dict[str, Any] = field(default_factory=dict)

    # Cost tracking (provider-specific, populated if available)
    cost_usd: Optional[float] = None
    tokens_input: Optional[int] = None
    tokens_output: Optional[int] = None

    @classmethod
    def from_pipeline(
        cls,
        pipeline: 'LegalEventsPipeline',
        input_file: Optional[Any] = None,
        timestamp: Optional[datetime] = None
    ) -> 'PipelineMetadata':
        """
        Extract metadata from LegalEventsPipeline instance

        Args:
            pipeline: LegalEventsPipeline instance
            input_file: Uploaded file object (optional, for size extraction)
            timestamp: Override timestamp (default: now)

        Returns:
            PipelineMetadata with all extractable fields populated
        """
        timestamp = timestamp or datetime.now()

        # Parser info
        parser_name = 'docling'  # Hardcoded for current implementation
        parser_version = None
        try:
            import docling
            parser_version = docling.__version__
        except Exception:
            pass

        # Provider info
        provider_name = getattr(pipeline, 'provider', 'langextract')

        # Provider model - extract from adapter with proper config access
        # This supports runtime model overrides (UI selections) over environment defaults
        provider_model = None
        try:
            if hasattr(pipeline, 'event_extractor'):
                extractor = pipeline.event_extractor

                # Strategy 1: config.active_model (OpenRouter pattern with runtime override support)
                # OpenRouter uses a @property that returns runtime_model if set, else env default
                if hasattr(extractor, 'config') and hasattr(extractor.config, 'active_model'):
                    provider_model = extractor.config.active_model

                # Strategy 2: config.model (OpenAI/Anthropic/DeepSeek pattern)
                # These providers store the model in config.model (includes runtime overrides)
                elif hasattr(extractor, 'config') and hasattr(extractor.config, 'model'):
                    provider_model = extractor.config.model

                # Strategy 3: config.model_id (LangExtract/Gemini pattern)
                # LangExtract uses model_id instead of model for Gemini model identifiers
                elif hasattr(extractor, 'config') and hasattr(extractor.config, 'model_id'):
                    provider_model = extractor.config.model_id

                # Fallback: Try direct properties (backward compatibility for old adapters)
                elif hasattr(extractor, 'model_id'):
                    provider_model = extractor.model_id
                elif hasattr(extractor, 'model'):
                    provider_model = extractor.model

            # Final fallback to environment variables (only if no adapter config found)
            if not provider_model:
                if provider_name == 'openrouter':
                    provider_model = os.getenv('OPENROUTER_MODEL', 'openai/gpt-4o-mini')
                elif provider_name == 'openai':
                    provider_model = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
                elif provider_name == 'langextract':
                    provider_model = os.getenv('GEMINI_MODEL_ID', 'gemini-2.0-flash')
                elif provider_name == 'anthropic':
                    # Fixed: Match config.py default (claude-3-haiku-20240307)
                    provider_model = os.getenv('ANTHROPIC_MODEL', 'claude-3-haiku-20240307')
                elif provider_name == 'opencode_zen':
                    provider_model = os.getenv('OPENCODEZEN_MODEL', 'default')
        except Exception:
            pass

        # OCR info (defensive extraction from document extractor config)
        ocr_engine = None
        table_mode = None
        try:
            if hasattr(pipeline, 'document_extractor'):
                extractor = pipeline.document_extractor
                if hasattr(extractor, 'config'):
                    config = extractor.config
                    if hasattr(config, 'ocr_engine'):
                        ocr_engine = config.ocr_engine
                    if hasattr(config, 'table_mode'):
                        # Handle enum or string
                        table_mode = str(config.table_mode) if config.table_mode else None
                        # Extract just the name if it's an enum (e.g., "TableMode.FAST" -> "FAST")
                        if table_mode and '.' in table_mode:
                            table_mode = table_mode.split('.')[-1]
        except Exception:
            pass

        # Input file info
        input_filename = 'unknown'
        input_size_bytes = None
        if input_file:
            try:
                input_filename = input_file.name
                # Try to get file size
                input_file.seek(0, 2)  # Seek to end
                input_size_bytes = input_file.tell()
                input_file.seek(0)  # Reset to beginning
            except Exception:
                pass

        # Generate cryptic run_id
        run_id = generate_pipeline_id(parser_name, provider_name, ocr_engine, table_mode, timestamp)

        # Config snapshot (for exact reproducibility)
        config_snapshot = {
            'parser': parser_name,
            'parser_version': parser_version,
            'provider': provider_name,
            'provider_model': provider_model,
            'ocr_engine': ocr_engine,
            'table_mode': table_mode,
            'environment': _get_environment(),
            'session_label': os.getenv('PIPELINE_SESSION_LABEL'),
        }

        return cls(
            run_id=run_id,
            timestamp=timestamp,
            parser_name=parser_name,
            parser_version=parser_version,
            provider_name=provider_name,
            provider_model=provider_model,
            ocr_engine=ocr_engine,
            table_mode=table_mode,
            input_filename=input_filename,
            input_size_bytes=input_size_bytes,
            config_snapshot=config_snapshot
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for JSON serialization

        Returns:
            Dictionary with all fields (datetime converted to ISO string)
        """
        data = asdict(self)
        # Convert datetime to ISO format string
        if isinstance(data.get('timestamp'), datetime):
            data['timestamp'] = data['timestamp'].isoformat()
        return data
