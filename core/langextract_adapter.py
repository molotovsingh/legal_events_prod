"""
LangExtract Event Extractor Adapter
Wraps LangExtractClient to implement EventExtractor interface
"""

import logging
from typing import List, Dict, Any

from .interfaces import EventExtractor, EventRecord
from .langextract_client import LangExtractClient
from .config import LangExtractConfig
from .constants import DEFAULT_NO_DATE, DEFAULT_NO_CITATION

logger = logging.getLogger(__name__)


class LangExtractEventExtractor:
    """Adapter that wraps LangExtractClient to implement EventExtractor interface"""

    def __init__(self, config: LangExtractConfig):
        """
        Initialize with LangExtract configuration

        Args:
            config: LangExtractConfig instance with all LangExtract settings
        """
        self.config = config
        try:
            self.client = LangExtractClient()
            self.available = True
            logger.info("✅ LangExtractEventExtractor initialized")
        except Exception as e:
            logger.error(f"❌ LangExtractEventExtractor initialization failed: {e}")
            self.client = None
            self.available = False

    def extract_events(self, text: str, metadata: Dict[str, Any]) -> List[EventRecord]:
        """
        Extract legal events using LangExtractClient

        Args:
            text: Document text content
            metadata: Document metadata including source filename

        Returns:
            List of EventRecord instances (guaranteed at least one)
        """
        # Extract document name from metadata
        document_name = metadata.get("file_path", "Unknown document")
        if isinstance(document_name, str) and "/" in document_name:
            document_name = document_name.split("/")[-1]  # Get filename only

        if not self.available:
            logger.warning("⚠️ LangExtractEventExtractor not available - creating fallback record")
            return [self._create_fallback_record(document_name, "LangExtract client not available")]

        if not text or not text.strip():
            logger.warning(f"⚠️ No text provided for {document_name} - creating fallback record")
            return [self._create_fallback_record(document_name, "No text content to process")]

        try:
            # Use LangExtractClient to extract legal events
            result = self.client.extract_legal_events(text, document_name)

            if not result.get("success", False):
                error_msg = result.get("error", "Unknown LangExtract error")
                logger.error(f"❌ LangExtract failed for {document_name}: {error_msg}")
                return [self._create_fallback_record(document_name, f"LangExtract failed: {error_msg}")]

            extractions = result.get("extractions", [])
            if not extractions:
                logger.warning(f"⚠️ No events extracted from {document_name}")
                return [self._create_fallback_record(document_name, "No legal events found")]

            # Convert LangExtract results to EventRecord format
            event_records = []
            for i, extraction in enumerate(extractions, 1):
                extraction_attributes = extraction.get("attributes") or {}

                # Merge LangExtract attributes with additional metadata
                merged_attributes = extraction_attributes.copy()
                merged_attributes.update({
                    "extraction_text": extraction.get("extraction_text", ""),
                    "extraction_class": extraction.get("extraction_class", ""),
                    "model_id": self.client.model_id,
                    "temperature": self.config.temperature
                })

                event_record = EventRecord(
                    number=i,
                    date=extraction_attributes.get("date", DEFAULT_NO_DATE),
                    event_particulars=extraction_attributes.get("event_particulars", "Event details not available"),
                    citation=extraction_attributes.get("citation", DEFAULT_NO_CITATION),
                    document_reference=document_name,
                    attributes=merged_attributes
                )
                event_records.append(event_record)

            logger.info(f"✅ Extracted {len(event_records)} legal events from {document_name}")
            return event_records

        except Exception as e:
            logger.error(f"❌ LangExtractEventExtractor failed for {document_name}: {e}")
            return [self._create_fallback_record(document_name, f"Processing error: {str(e)}")]

    def _create_fallback_record(self, document_name: str, reason: str) -> EventRecord:
        """
        Create a fallback EventRecord when extraction fails

        Args:
            document_name: Source document name
            reason: Reason for fallback

        Returns:
            EventRecord with fallback content
        """
        return EventRecord(
            number=1,
            date=DEFAULT_NO_DATE,
            event_particulars=f"Failed to extract legal events from {document_name}: {reason}",
            citation="No citation available (extraction failed)",
            document_reference=document_name,
            attributes={"fallback": True, "reason": reason}
        )

    def is_available(self) -> bool:
        """
        Check if LangExtract is properly configured and available

        Returns:
            True if extractor can be used, False otherwise
        """
        return self.available and self.client is not None and self.client.is_available()