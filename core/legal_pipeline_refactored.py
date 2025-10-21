"""
Refactored Legal Events Pipeline - GUARANTEES five-column output
Uses centralized components and ALWAYS produces table even on failures
Includes intelligent document extraction caching to avoid re-processing same files
"""

import pandas as pd
import tempfile
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Optional

try:
    import streamlit as st
    STREAMLIT_AVAILABLE = True
except ImportError:
    STREAMLIT_AVAILABLE = False

from ..utils.file_handler import FileHandler
from ..core.table_formatter import TableFormatter
from ..core.constants import FIVE_COLUMN_HEADERS, DEFAULT_NO_DATE
from ..core.extractor_factory import create_default_extractors, validate_extractors
from ..core.interfaces import DocumentExtractor, EventExtractor
from ..core.pipeline_metadata import PipelineMetadata

logger = logging.getLogger(__name__)


class LegalEventsPipeline:
    """
    Modular legal events pipeline with GUARANTEED five-column output
    Uses pluggable adapters for document processing and event extraction
    NEVER fails to produce a table - creates fallback records when needed
    """

    # Provider-specific credential requirements mapping
    PROVIDER_CREDENTIALS = {
        'langextract': {
            'env_vars': ['GEMINI_API_KEY', 'GOOGLE_API_KEY'],  # Either one is acceptable
            'primary_key': 'GEMINI_API_KEY',
            'description': 'Google Gemini API for LangExtract'
        },
        'openrouter': {
            'env_vars': ['OPENROUTER_API_KEY'],
            'primary_key': 'OPENROUTER_API_KEY',
            'description': 'OpenRouter unified API'
        },
        'opencode_zen': {
            'env_vars': ['OPENCODEZEN_API_KEY'],
            'primary_key': 'OPENCODEZEN_API_KEY',
            'description': 'OpenCode Zen legal extraction service'
        },
        'openai': {
            'env_vars': ['OPENAI_API_KEY'],
            'primary_key': 'OPENAI_API_KEY',
            'description': 'OpenAI API for GPT models'
        },
        'anthropic': {
            'env_vars': ['ANTHROPIC_API_KEY'],
            'primary_key': 'ANTHROPIC_API_KEY',
            'description': 'Anthropic API for Claude models'
        },
        'deepseek': {
            'env_vars': ['DEEPSEEK_API_KEY'],
            'primary_key': 'DEEPSEEK_API_KEY',
            'description': 'DeepSeek API for DeepSeek-Chat models'
        }
    }

    # Cache configuration
    CACHE_MAX_FILES = 10  # Maximum number of files to keep in cache

    def __init__(self, event_extractor: Optional[str] = None, runtime_model: Optional[str] = None, doc_extractor: Optional[str] = None):
        # Track requested event extractor (default to env)
        requested_provider = event_extractor or os.getenv("EVENT_EXTRACTOR") or "langextract"
        self.event_extractor_type = requested_provider.strip().lower()

        # Track requested document extractor (default to env)
        requested_doc_extractor = doc_extractor or os.getenv("DOC_EXTRACTOR") or "docling"
        self.doc_extractor_type = requested_doc_extractor.strip().lower()

        # Store provider and runtime model for metadata tracking
        self.provider = self.event_extractor_type
        self.runtime_model = runtime_model

        # Initialize document extraction cache (session-level caching)
        self._init_document_cache()

        # Validate environment with provider-aware checks
        self._validate_environment()

        # Initialize pluggable extractors with runtime model override
        self.document_extractor, self.event_extractor = create_default_extractors(
            self.event_extractor_type,
            runtime_model=runtime_model,
            doc_extractor_override=self.doc_extractor_type
        )
        self.file_handler = FileHandler()

        # Validate extractors are properly configured
        if not validate_extractors(self.document_extractor, self.event_extractor):
            logger.warning("⚠️ Extractor validation failed - pipeline may have limited functionality")

        logger.info(
            "✅ Modular legal events pipeline initialized with pluggable adapters (doc:%s, event:%s)",
            self.document_extractor.__class__.__name__,
            self.event_extractor.__class__.__name__
        )

    def _init_document_cache(self):
        """
        Initialize document extraction cache in Streamlit session state

        Cache key format: {filename}:{file_size}:{doc_extractor_type}
        Stores extracted document results to avoid re-processing same files
        when switching between different LLM providers
        """
        if STREAMLIT_AVAILABLE and hasattr(st, 'session_state'):
            if 'doc_extraction_cache' not in st.session_state:
                st.session_state['doc_extraction_cache'] = {}
                logger.debug("💾 Initialized document extraction cache")

    def _get_cache_key(self, uploaded_file, doc_extractor_type: str) -> str:
        """
        Generate cache key for a file

        Args:
            uploaded_file: Streamlit uploaded file object
            doc_extractor_type: Type of document extractor (e.g., 'docling', 'gemini')

        Returns:
            Cache key string
        """
        # Get file size from buffer
        file_size = len(uploaded_file.getbuffer())
        # Format: filename:size:extractor_type
        return f"{uploaded_file.name}:{file_size}:{doc_extractor_type}"

    def _evict_old_cache_entries(self):
        """
        Evict oldest cache entries if cache exceeds max size
        Keeps most recent CACHE_MAX_FILES files
        """
        if not STREAMLIT_AVAILABLE or not hasattr(st, 'session_state'):
            return

        cache = st.session_state.get('doc_extraction_cache', {})
        if len(cache) > self.CACHE_MAX_FILES:
            # Remove oldest entries (Python 3.7+ dicts maintain insertion order)
            num_to_remove = len(cache) - self.CACHE_MAX_FILES
            for _ in range(num_to_remove):
                oldest_key = next(iter(cache))
                del cache[oldest_key]
                logger.debug(f"💾 Evicted cache entry: {oldest_key}")

    def _validate_environment(self):
        """
        Validate provider-specific API credentials

        Checks the appropriate API key based on the selected provider:
        - LangExtract: GEMINI_API_KEY or GOOGLE_API_KEY
        - OpenRouter: OPENROUTER_API_KEY
        - OpenCode Zen: OPENCODEZEN_API_KEY

        Raises:
            ValueError: If required API key is missing for the selected provider
        """
        provider = self.event_extractor_type

        # Get credential requirements for this provider
        if provider not in self.PROVIDER_CREDENTIALS:
            logger.warning(f"⚠️ Unknown provider '{provider}', defaulting to LangExtract validation")
            provider = 'langextract'

        cred_config = self.PROVIDER_CREDENTIALS[provider]
        env_vars = cred_config['env_vars']
        primary_key = cred_config['primary_key']
        description = cred_config['description']

        # Check if at least one of the required env vars is set
        api_key = None
        for env_var in env_vars:
            api_key = os.getenv(env_var)
            if api_key and api_key.strip():
                logger.info(f"✅ {primary_key} validated for provider: {provider}")
                return

        # No valid API key found - raise detailed error
        if len(env_vars) == 1:
            error_msg = f"{primary_key} required for {description}"
        else:
            env_vars_str = " or ".join(env_vars)
            error_msg = f"One of [{env_vars_str}] required for {description}"

        logger.error(f"🚨 {error_msg}")
        raise ValueError(error_msg)

    def process_documents_for_legal_events(self, uploaded_files: List) -> Tuple[pd.DataFrame, Optional[str]]:
        """
        Process documents with GUARANTEED five-column table output
        Generates comprehensive metadata for tracking and future database migration

        Args:
            uploaded_files: List of Streamlit uploaded file objects

        Returns:
            Tuple of (GUARANTEED DataFrame with metadata, optional warning message)
        """
        # Generate metadata at start (captures config snapshot)
        timestamp = datetime.now()
        first_file = uploaded_files[0] if uploaded_files else None
        metadata = PipelineMetadata.from_pipeline(
            pipeline=self,
            input_file=first_file,
            timestamp=timestamp
        )

        try:
            # Validate files
            supported_files, unsupported_files = self.file_handler.validate_uploaded_files(uploaded_files)

            warning_message = None
            if unsupported_files:
                warning_message = f"Skipped {len(unsupported_files)} unsupported files"
                logger.warning(warning_message)

            if not supported_files:
                logger.warning("⚠️ No supported files - creating fallback table")
                fallback_df = TableFormatter.create_fallback_dataframe("No supported files uploaded")
                metadata.status = 'failed'
                metadata.error_message = "No supported files found"
                fallback_df.attrs['pipeline_id'] = metadata.run_id
                fallback_df.attrs['metadata'] = metadata.to_dict()
                return fallback_df, "No supported files found for processing"

            # Process files and collect records
            all_records = []
            processing_start = time.perf_counter()

            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                for uploaded_file in supported_files:
                    try:
                        # Process single file
                        records = self._process_single_file_guaranteed(uploaded_file, temp_path)
                        all_records.extend(records)

                    except Exception as e:
                        logger.error(f"❌ Failed to process {uploaded_file.name}: {e}")
                        # Add fallback record for failed file
                        fallback_record = {
                            "number": len(all_records) + 1,
                            "date": DEFAULT_NO_DATE,
                            "event_particulars": f"Failed to process file {uploaded_file.name}: {str(e)}",
                            "citation": "No citation available (file processing failed)",
                            "document_reference": uploaded_file.name
                        }
                        all_records.append(fallback_record)

            # Capture total processing time
            metadata.total_seconds = time.perf_counter() - processing_start

            # GUARANTEE: Always have at least one record
            if not all_records:
                logger.warning("⚠️ No records generated - creating fallback")
                fallback_record = {
                    "number": 1,
                    "date": DEFAULT_NO_DATE,
                    "event_particulars": "No legal events could be extracted from any uploaded files",
                    "citation": "No citation available (extraction failed)",
                    "document_reference": "Multiple files processed"
                }
                all_records = [fallback_record]
                metadata.status = 'partial'

            # Convert to DataFrame using standardized formatter
            df = TableFormatter.normalize_records_to_dataframe(all_records)

            # Final validation
            if not TableFormatter.validate_dataframe_format(df):
                logger.error("❌ CRITICAL: Final DataFrame validation failed")
                df = TableFormatter.create_fallback_dataframe("Final validation failed")
                metadata.status = 'failed'
                metadata.error_message = "Final validation failed"
            else:
                # Populate quality metrics from successful results
                metadata.events_extracted = len(df)
                metadata.citations_found = self._count_real_citations(df)
                metadata.avg_detail_length = df[FIVE_COLUMN_HEADERS[2]].str.len().mean()
                metadata.status = 'success'

                # Extract timing metrics if available (from per-record timing)
                # Note: Timing values are the same for all events from a single document,
                # so we take the first value instead of summing (which would multiply by event count)
                if 'Docling_Seconds' in df.columns and len(df) > 0:
                    metadata.docling_seconds = df['Docling_Seconds'].iloc[0]
                if 'Extractor_Seconds' in df.columns and len(df) > 0:
                    metadata.extractor_seconds = df['Extractor_Seconds'].iloc[0]

            # Attach metadata to DataFrame (accessible for export and saving)
            df.attrs['pipeline_id'] = metadata.run_id
            df.attrs['metadata'] = metadata.to_dict()

            logger.info(f"✅ Pipeline completed successfully with {len(df)} legal events [Pipeline-ID: {metadata.run_id}]")
            return df, warning_message

        except Exception as e:
            logger.error(f"❌ CRITICAL pipeline failure: {e}")
            # ULTIMATE FALLBACK: Create emergency table with metadata
            emergency_df = TableFormatter.create_fallback_dataframe(f"Critical pipeline error: {str(e)}")
            metadata.status = 'failed'
            metadata.error_message = str(e)
            emergency_df.attrs['pipeline_id'] = metadata.run_id
            emergency_df.attrs['metadata'] = metadata.to_dict()
            return emergency_df, f"Pipeline failure: {str(e)}"

    def _process_single_file_guaranteed(self, uploaded_file, temp_path: Path) -> List[Dict]:
        """
        Process single file with guaranteed record generation
        Uses intelligent caching to avoid re-extracting same files

        Args:
            uploaded_file: Streamlit uploaded file
            temp_path: Temporary directory path

        Returns:
            List of records (guaranteed at least one)
        """
        # Check if performance timing is enabled
        timing_enabled = os.getenv("ENABLE_PERFORMANCE_TIMING", "true").lower() == "true"
        docling_seconds = None
        extractor_seconds = None
        total_seconds = None
        cache_hit = False

        try:
            # Generate cache key for this file
            cache_key = self._get_cache_key(uploaded_file, self.doc_extractor_type)

            # Try to retrieve from cache first
            doc_result = None
            if STREAMLIT_AVAILABLE and hasattr(st, 'session_state'):
                cache = st.session_state.get('doc_extraction_cache', {})
                if cache_key in cache:
                    doc_result = cache[cache_key]
                    docling_seconds = 0.0  # Instant from cache
                    cache_hit = True
                    logger.info(f"💾 Cache HIT: {uploaded_file.name} (skipping Docling extraction)")

            # Cache miss - extract document fresh
            if doc_result is None:
                # Save file
                file_path = self.file_handler.save_uploaded_file(uploaded_file, temp_path)
                file_extension = self.file_handler.get_file_extension(file_path)

                # Use document extractor adapter for text extraction (with timing)
                if timing_enabled:
                    start_docling = time.perf_counter()

                doc_result = self.document_extractor.extract(file_path)

                if timing_enabled:
                    docling_seconds = time.perf_counter() - start_docling

                # Store in cache for future use
                if STREAMLIT_AVAILABLE and hasattr(st, 'session_state'):
                    st.session_state['doc_extraction_cache'][cache_key] = doc_result
                    # Evict old entries if cache is full
                    self._evict_old_cache_entries()
                    logger.info(f"💾 Cached: {uploaded_file.name} ({docling_seconds:.2f}s extraction time)")

            # If document extraction failed completely
            if not doc_result.plain_text.strip():
                logger.warning(f"⚠️ Document extraction failed for {uploaded_file.name} - creating fallback record")
                return [{
                    "number": 1,
                    "date": DEFAULT_NO_DATE,
                    "event_particulars": f"Document processing failed for {uploaded_file.name}",
                    "citation": "No citation available (document extraction failed)",
                    "document_reference": uploaded_file.name
                }]

            # Use event extractor adapter for legal events extraction (with timing)
            # Create metadata for event extraction, including document name
            extraction_metadata = doc_result.metadata.copy()
            extraction_metadata["document_name"] = uploaded_file.name

            if timing_enabled:
                start_extractor = time.perf_counter()

            event_records = self.event_extractor.extract_events(doc_result.plain_text, extraction_metadata)

            if timing_enabled:
                extractor_seconds = time.perf_counter() - start_extractor
                total_seconds = docling_seconds + extractor_seconds

                # Log performance timing
                logger.info(
                    f"⏱️  {uploaded_file.name}: Docling={docling_seconds:.3f}s, "
                    f"Extractor={extractor_seconds:.3f}s, Total={total_seconds:.3f}s"
                )

            # Convert EventRecord instances to dict format expected by TableFormatter
            # CRITICAL: Preserve timing data in attributes
            legal_events = []
            for event_record in event_records:
                event_dict = {
                    "number": event_record.number,
                    "date": event_record.date,
                    "event_particulars": event_record.event_particulars,
                    "citation": event_record.citation,
                    "document_reference": event_record.document_reference
                }

                # Add timing columns if timing is enabled and available
                if timing_enabled and docling_seconds is not None:
                    event_dict["docling_seconds"] = docling_seconds
                    event_dict["extractor_seconds"] = extractor_seconds
                    event_dict["total_seconds"] = total_seconds

                legal_events.append(event_dict)

            logger.info(f"✅ Extracted {len(legal_events)} events from {uploaded_file.name} using adapters")
            return legal_events

        except Exception as e:
            logger.error(f"❌ Single file processing failed for {uploaded_file.name}: {e}")
            # Return fallback record
            fallback = {
                "number": 1,
                "date": DEFAULT_NO_DATE,
                "event_particulars": f"Processing error for {uploaded_file.name}: {str(e)}",
                "citation": "No citation available (processing error)",
                "document_reference": uploaded_file.name
            }

            # Add timing even for failures if available
            if timing_enabled and docling_seconds is not None:
                fallback["docling_seconds"] = docling_seconds
                fallback["extractor_seconds"] = extractor_seconds if extractor_seconds is not None else 0.0
                fallback["total_seconds"] = total_seconds if total_seconds is not None else docling_seconds

            return [fallback]

    def export_legal_events_table(self, df: pd.DataFrame, format_type: str = "xlsx") -> bytes:
        """
        Export legal events table using standardized formatter

        Args:
            df: Legal events DataFrame
            format_type: Export format ('xlsx', 'csv', 'json')

        Returns:
            Exported data as bytes
        """
        return TableFormatter.prepare_for_export(df, format_type)

    def validate_five_column_format(self, df: pd.DataFrame) -> bool:
        """Validate DataFrame format using standardized validator"""
        return TableFormatter.validate_dataframe_format(df)

    def get_table_summary(self, df: pd.DataFrame) -> Dict:
        """Get table summary using standardized formatter"""
        return TableFormatter.get_table_summary(df)

    def _count_real_citations(self, df: pd.DataFrame) -> int:
        """
        Count events with real citations (not default/fallback values)

        Args:
            df: Legal events DataFrame

        Returns:
            Count of events with meaningful citations
        """
        citation_col = FIVE_COLUMN_HEADERS[3]  # Citation column
        real_citations = df[
            (~df[citation_col].str.contains("No citation available", na=False)) &
            (~df[citation_col].str.contains("processing failed", na=False))
        ]
        return len(real_citations)
