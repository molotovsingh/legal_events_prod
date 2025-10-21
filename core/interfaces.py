"""
Extractor Interfaces - Clean abstractions for modular document and event processing
Enables swapping implementations (Docling, LangExtract, etc.) without changing pipeline code
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Any, Optional, Protocol
from dataclasses import dataclass


@dataclass
class ExtractedDocument:
    """Standardized document extraction result"""
    markdown: str
    plain_text: str
    metadata: Dict[str, Any]


@dataclass
class TimingMetrics:
    """Performance timing metrics for document processing"""
    docling_seconds: float
    extractor_seconds: float
    total_seconds: float
    document_name: str


@dataclass
class EventRecord:
    """Standardized event record for legal events pipeline"""
    number: int
    date: str
    event_particulars: str
    citation: str
    document_reference: str
    attributes: Dict[str, Any]


class DocumentExtractor(Protocol):
    """Interface for document text extraction components"""

    @abstractmethod
    def extract(self, file_path: Path) -> ExtractedDocument:
        """
        Extract text from a document

        Args:
            file_path: Path to the document file

        Returns:
            ExtractedDocument with markdown, plain_text and metadata
        """
        pass

    @abstractmethod
    def get_supported_types(self) -> List[str]:
        """
        Get list of supported file types

        Returns:
            List of supported file extensions without dots
        """
        pass


class EventExtractor(Protocol):
    """Interface for event extraction components"""

    @abstractmethod
    def extract_events(self, text: str, metadata: Dict[str, Any]) -> List[EventRecord]:
        """
        Extract events from document text

        Args:
            text: Document text content
            metadata: Document metadata including source filename

        Returns:
            List of EventRecord instances
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if the extractor is properly configured and available

        Returns:
            True if extractor can be used, False otherwise
        """
        pass


class ExtractorFactory(ABC):
    """Factory interface for creating extractors"""

    @abstractmethod
    def create_document_extractor(self, config: Any) -> DocumentExtractor:
        """Create a document extractor instance"""
        pass

    @abstractmethod
    def create_event_extractor(self, config: Any) -> EventExtractor:
        """Create an event extractor instance"""
        pass