"""
Docling Document Extractor Adapter
Wraps DocumentProcessor with configured options to implement DocumentExtractor interface
"""

import logging
from pathlib import Path
from typing import List

import fitz  # PyMuPDF

from .interfaces import DocumentExtractor, ExtractedDocument
from .document_processor import DocumentProcessor
from .config import DoclingConfig
from .email_parser import parse_email_file, get_email_metadata

logger = logging.getLogger(__name__)


def is_scanned_pdf(file_path: Path, sample_pages: int = 3, text_threshold: int = 50) -> bool:
    """
    Detect if a PDF is scanned (image-based) by checking for embedded text.

    Args:
        file_path: Path to the PDF file
        sample_pages: Number of pages to check (default: 3)
        text_threshold: Minimum text length to consider as digital (default: 50 chars)

    Returns:
        True if PDF appears to be scanned (no text layer), False if digital

    Note:
        This is a heuristic check - scans with poor OCR or minimal text may
        be misclassified. Checks first N pages for performance.
    """
    try:
        doc = fitz.open(file_path)
        pages_checked = min(sample_pages, len(doc))

        for page_num in range(pages_checked):
            page = doc[page_num]
            text = page.get_text().strip()

            # If we find substantial text, it's a digital PDF
            if len(text) > text_threshold:
                doc.close()
                return False

        # No substantial text found in sampled pages - likely scanned
        doc.close()
        return True

    except Exception as e:
        logger.warning(f"PDF detection failed for {file_path.name}: {e}, assuming digital")
        return False  # Default to digital (fast path) on error


class DoclingDocumentExtractor:
    """Adapter that wraps DocumentProcessor to implement DocumentExtractor interface"""

    def __init__(self, config: DoclingConfig):
        """
        Initialize with Docling configuration

        Args:
            config: DoclingConfig instance with all Docling settings
        """
        self.config = config
        self.processor = DocumentProcessor(config)
        self.ocr_processor = None  # Lazy-init cache for OCR-enabled processor
        logger.info("✅ DoclingDocumentExtractor initialized")

    def extract(self, file_path: Path) -> ExtractedDocument:
        """
        Extract text using configured DocumentProcessor with optional OCR auto-detection

        Args:
            file_path: Path to the document file

        Returns:
            ExtractedDocument with markdown, plain_text and metadata
        """
        try:
            # Get file extension from path
            file_type = file_path.suffix.lstrip('.')

            # Determine if OCR should be used for this specific document
            needs_ocr = self.config.do_ocr  # Default: use config setting
            ocr_auto_detected = False

            # Auto-detect OCR requirement for PDFs
            if (file_type.lower() == 'pdf' and
                self.config.auto_ocr_detection and
                not self.config.do_ocr):  # Only auto-detect if OCR is currently disabled

                if is_scanned_pdf(file_path):
                    needs_ocr = True
                    ocr_auto_detected = True
                    logger.info(f"🔍 OCR auto-detected for scanned PDF: {file_path.name}")

            # Create processor with appropriate OCR setting
            if needs_ocr and not self.config.do_ocr:
                # Need OCR but current processor doesn't have it - use cached OCR processor
                if self.ocr_processor is None:
                    # Lazy initialization: create OCR-enabled processor once
                    from copy import deepcopy
                    ocr_config = deepcopy(self.config)
                    ocr_config.do_ocr = True
                    self.ocr_processor = DocumentProcessor(ocr_config)
                    logger.info("🔧 Created cached OCR processor for scanned PDFs")
                processor = self.ocr_processor
            else:
                # Use default processor
                processor = self.processor

            # Use DocumentProcessor to get Docling result
            text, extraction_method = processor.extract_text(file_path, file_type)

            # Check for extraction failure (but allow empty text for images with no text content)
            if extraction_method == "failed":
                # True failure - extraction process itself failed
                return ExtractedDocument(
                    markdown="",
                    plain_text="",
                    metadata={
                        "file_path": str(file_path),
                        "file_type": file_type,
                        "extraction_method": "failed",
                        "needs_ocr": needs_ocr,
                        "ocr_auto_detected": ocr_auto_detected,
                        "config": {
                            "do_ocr": self.config.do_ocr,
                            "table_mode": self.config.table_mode,
                            "backend": self.config.backend
                        }
                    }
                )

            # Empty text is OK for images (e.g., images with no text content)
            # Don't treat it as a failure - just return empty result with successful extraction method

            # For Docling extractions, get both markdown and plain text
            if extraction_method in ["docling", "docling_image_ocr"]:
                # Re-run Docling to get both formats (use appropriate processor)
                result = processor.converter.convert(file_path)
                markdown = result.document.export_to_markdown()
                plain_text = result.document.export_to_text()
            else:
                # For non-Docling extractions (email, etc.), text is plain text
                markdown = text  # Use same content for both
                plain_text = text

            # Build base metadata
            metadata = {
                "file_path": str(file_path),
                "file_type": file_type,
                "extraction_method": extraction_method,
                "needs_ocr": needs_ocr,
                "ocr_auto_detected": ocr_auto_detected,
                "config": {
                    "do_ocr": self.config.do_ocr,
                    "table_mode": self.config.table_mode,
                    "backend": self.config.backend
                }
            }

            # Add email-specific metadata for .eml files
            if extraction_method == "email_parser":
                try:
                    parsed_email = parse_email_file(file_path)
                    email_metadata = get_email_metadata(parsed_email)
                    metadata.update(email_metadata)
                except Exception as e:
                    logger.warning(f"⚠️ Failed to extract email metadata for {file_path.name}: {e}")

            return ExtractedDocument(
                markdown=markdown,
                plain_text=plain_text,
                metadata=metadata
            )

        except Exception as e:
            logger.error(f"❌ DoclingDocumentExtractor failed for {file_path.name}: {e}")
            # Return empty strings on exception
            return ExtractedDocument(
                markdown="",
                plain_text="",
                metadata={
                    "file_path": str(file_path),
                    "file_type": file_path.suffix.lstrip('.'),
                    "extraction_method": "failed",
                    "needs_ocr": locals().get('needs_ocr', self.config.do_ocr),
                    "ocr_auto_detected": locals().get('ocr_auto_detected', False),
                    "error": str(e)
                }
            )

    def get_supported_types(self) -> List[str]:
        """
        Get supported file types from DocumentProcessor

        Returns:
            List of supported file extensions
        """
        return self.processor.get_supported_types()