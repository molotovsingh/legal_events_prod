"""
Core Document Processing Module - Docling Integration
Simplified for compatibility - uses default DocumentConverter
"""

import logging
from pathlib import Path
from typing import Tuple, Optional

from docling.document_converter import DocumentConverter

try:
    import extract_msg
    EXTRACT_MSG_AVAILABLE = True
except ImportError:
    EXTRACT_MSG_AVAILABLE = False
    extract_msg = None

from .config import DoclingConfig, load_config
from .email_parser import parse_email_file, format_email_as_text

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """Handles document text extraction using Docling"""

    def __init__(self, config: Optional[DoclingConfig] = None):
        """
        Initialize DocumentProcessor with Docling

        Args:
            config: DoclingConfig instance, defaults to loaded from environment
        """
        if config is None:
            config, _ = load_config()

        self.config = config

        # Initialize DocumentConverter with default configuration
        # Complex pipeline options are deferred to v0.3.0 release
        logger.info("✅ Initializing DocumentConverter with default configuration")
        self.converter = DocumentConverter()

        logger.info(f"✅ DocumentProcessor initialized")

    def extract_text(self, file_path: Path, file_type: str) -> Tuple[str, str]:
        """
        Extract text from document using DOCLING ONLY - Pure test pipeline

        Args:
            file_path: Path to the document
            file_type: File extension without dot

        Returns:
            Tuple of (extracted_text, extraction_method)
        """
        try:
            text = ""
            extraction_method = "failed"

            # Images: JPEG, PNG (route through Docling with OCR)
            if file_type.lower() in ['jpg', 'jpeg', 'png']:
                result = self.converter.convert(file_path)
                text = result.document.export_to_markdown()
                extraction_method = "docling_image_ocr"

                # Check if OCR extracted meaningful text
                if len(text.strip()) < 20:
                    logger.warning(f"⚠️ Minimal text extracted from {file_path.name} "
                                  f"({len(text)} chars) - low quality image or no text present")

                logger.info(f"✅ IMAGE OCR SUCCESS: {file_path.name}")

            elif file_type in ['pdf', 'docx', 'txt', 'pptx', 'html']:
                # PURE DOCLING PROCESSING - NO FALLBACKS
                result = self.converter.convert(file_path)
                text = result.document.export_to_markdown()
                extraction_method = "docling"
                logger.info(f"✅ DOCLING SUCCESS: {file_path.name}")

            elif file_type in ['eml', 'msg']:
                # Email files use specialized parsers
                if file_type == 'msg':
                    # Outlook .msg files
                    if EXTRACT_MSG_AVAILABLE:
                        try:
                            msg = extract_msg.openMsg(file_path)
                            text = f"Subject: {msg.subject}\nFrom: {msg.sender}\nDate: {msg.date}\n\n{msg.body}"
                            extraction_method = "extract_msg"
                        except Exception as e:
                            logger.warning(f"⚠️ extract_msg failed for {file_path.name}: {e}, falling back to raw text")
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                text = f.read()
                            extraction_method = "raw_text_fallback"
                    else:
                        logger.warning(f"⚠️ extract_msg not available for {file_path.name}, falling back to raw text")
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            text = f.read()
                        extraction_method = "raw_text_fallback"
                else:
                    # .eml files - use new email parser
                    try:
                        parsed_email = parse_email_file(file_path)
                        text = format_email_as_text(parsed_email)
                        extraction_method = "email_parser"
                        logger.info(f"✅ EMAIL PARSER SUCCESS: {file_path.name}")
                    except Exception as e:
                        logger.warning(f"⚠️ Email parsing failed for {file_path.name}: {e}, falling back to raw text")
                        # Graceful fallback to raw text if parser fails
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            text = f.read()
                        extraction_method = "raw_text_fallback"

            return text.strip(), extraction_method

        except Exception as e:
            logger.error(f"❌ DOCLING FAILED: {file_path.name} - {str(e)}")
            return "", "failed"

    def get_supported_types(self) -> list[str]:
        """Get list of supported file types"""
        return ['pdf', 'docx', 'txt', 'pptx', 'html', 'eml', 'msg', 'jpg', 'jpeg', 'png']
