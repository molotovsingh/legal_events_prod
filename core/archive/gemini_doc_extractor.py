"""
Gemini Document Extractor Adapter
Uses Gemini 2.5's native multimodal vision to process PDFs directly (alternative to Docling)
"""

import logging
import time
from pathlib import Path
from typing import Optional

from .interfaces import DocumentExtractor, ExtractedDocument
from .config import GeminiDocConfig

logger = logging.getLogger(__name__)


class GeminiDocumentExtractor:
    """
    Uses Gemini 2.5 File API for native PDF processing via multimodal vision

    Advantages over Docling:
    - Native document understanding (layout, tables, diagrams)
    - No local OCR preprocessing needed
    - Vision model sees formatting/structure

    Trade-offs:
    - 4.5x more expensive (image tokens + text tokens)
    - 50MB file size limit (Gemini File API)
    - Network latency for upload
    - Vendor lock-in to Google
    """

    def __init__(self, config: GeminiDocConfig):
        """
        Initialize with Gemini Document configuration

        Args:
            config: GeminiDocConfig instance with API key and model settings

        Raises:
            ExtractorConfigurationError: If required configuration is missing
        """
        from .extractor_factory import ExtractorConfigurationError

        self.config = config
        self._client = None
        self.available = False

        # Validate API key at initialization
        if not config.api_key or config.api_key.strip() == "":
            raise ExtractorConfigurationError(
                "Gemini API key is required for GeminiDocumentExtractor. "
                "Set GEMINI_API_KEY environment variable."
            )

        # Lazy import Gemini client
        try:
            import google.generativeai as genai
            self._genai = genai
            genai.configure(api_key=config.api_key)
            self.available = True
            logger.info(f"✅ GeminiDocumentExtractor initialized with model: {config.model_id}")
        except ImportError:
            logger.warning("⚠️ google-generativeai library not available - Gemini doc extractor will be disabled")
            self.available = False
        except Exception as e:
            logger.error(f"❌ Failed to initialize Gemini client: {e}")
            self.available = False

    def extract(self, file_path: Path) -> ExtractedDocument:
        """
        Extract text from PDF using Gemini's native multimodal vision

        Args:
            file_path: Path to the PDF file

        Returns:
            ExtractedDocument with markdown, plain_text and metadata

        Process:
            1. Check file size (<50MB limit)
            2. Upload PDF via File API (cached 48hrs)
            3. Send transcription prompt to Gemini
            4. Parse response into ExtractedDocument
        """
        if not self.available:
            logger.error("❌ Gemini document extractor not available")
            return self._create_fallback_document(
                file_path,
                "Gemini API not configured or library not installed"
            )

        # Validate file type
        if file_path.suffix.lower() != '.pdf':
            logger.warning(f"⚠️ Gemini currently only supports PDF files, got: {file_path.suffix}")
            return self._create_fallback_document(
                file_path,
                f"Unsupported file type: {file_path.suffix}"
            )

        # Check file size
        file_size_mb = file_path.stat().st_size / (1024 * 1024)
        if file_size_mb > self.config.max_file_size_mb:
            logger.error(
                f"❌ File too large for Gemini File API: {file_size_mb:.1f}MB "
                f"(max: {self.config.max_file_size_mb}MB)"
            )
            return self._create_fallback_document(
                file_path,
                f"File size {file_size_mb:.1f}MB exceeds {self.config.max_file_size_mb}MB limit"
            )

        try:
            start_time = time.time()

            # Step 1: Upload PDF via File API
            logger.info(f"📤 Uploading {file_path.name} to Gemini File API ({file_size_mb:.1f}MB)...")
            uploaded_file = self._genai.upload_file(file_path)
            upload_time = time.time() - start_time
            logger.info(f"✅ Upload complete in {upload_time:.1f}s (URI: {uploaded_file.uri})")

            # Step 2: Extract text using Gemini's multimodal vision
            extraction_start = time.time()
            content = self._extract_text_from_file(uploaded_file, file_path.name)
            extraction_time = time.time() - extraction_start

            total_time = time.time() - start_time
            logger.info(
                f"✅ Gemini extraction complete in {total_time:.1f}s "
                f"(upload: {upload_time:.1f}s, processing: {extraction_time:.1f}s)"
            )

            # Step 3: Create ExtractedDocument
            return ExtractedDocument(
                markdown=content,  # Gemini may preserve some markdown structure
                plain_text=content,  # Same content for plain text
                metadata={
                    "document_name": file_path.name,
                    "file_path": str(file_path),
                    "extractor": "gemini",
                    "model": self.config.model_id,
                    "file_size_mb": round(file_size_mb, 2),
                    "upload_time_seconds": round(upload_time, 2),
                    "extraction_time_seconds": round(extraction_time, 2),
                    "total_time_seconds": round(total_time, 2),
                    "gemini_file_uri": uploaded_file.uri,
                }
            )

        except Exception as e:
            logger.error(f"❌ Gemini document extraction failed for {file_path.name}: {e}")
            return self._create_fallback_document(file_path, f"Gemini extraction error: {str(e)}")

    def _extract_text_from_file(self, uploaded_file, filename: str) -> str:
        """
        Send uploaded file to Gemini for text extraction

        Args:
            uploaded_file: Gemini File API uploaded file object
            filename: Original filename (for logging)

        Returns:
            Extracted text content
        """
        # Create generative model
        model = self._genai.GenerativeModel(self.config.model_id)

        # Document transcription prompt optimized for legal documents
        # Emphasizes dates, citations, and structure critical for downstream event extraction
        prompt = """
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
        """.strip()

        # Generate content
        logger.info(f"🤖 Sending document to {self.config.model_id} for extraction...")
        response = model.generate_content(
            [uploaded_file, prompt],
            request_options={"timeout": self.config.timeout}
        )

        if not response or not response.text:
            raise ValueError("Gemini returned empty response")

        return response.text.strip()

    def _create_fallback_document(self, file_path: Path, error_message: str) -> ExtractedDocument:
        """
        Create a fallback ExtractedDocument when extraction fails

        Args:
            file_path: Path to the document
            error_message: Description of the failure

        Returns:
            ExtractedDocument with error information
        """
        fallback_text = f"[Gemini Document Extraction Failed: {error_message}]"

        return ExtractedDocument(
            markdown=fallback_text,
            plain_text=fallback_text,
            metadata={
                "document_name": file_path.name,
                "file_path": str(file_path),
                "extractor": "gemini",
                "extraction_failed": True,
                "error_message": error_message,
            }
        )

    def get_supported_types(self):
        """Return list of supported file extensions"""
        return ['.pdf']

    def is_available(self) -> bool:
        """Check if the extractor is available"""
        return self.available
