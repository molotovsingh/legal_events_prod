"""
Shared Data Schemas for API and Worker
This module defines data structures used across services without creating service dependencies.
Used for inter-service communication and database access patterns.
"""

from enum import Enum
from typing import Optional, Dict, Any, List
from datetime import datetime


class RunStatus(str, Enum):
    """Run processing status"""
    QUEUED = "queued"
    PROCESSING = "processing"
    PARTIAL_SUCCESS = "partial"
    SUCCESS = "success"
    FAILED = "failed"


class DocumentStatus(str, Enum):
    """Document processing status"""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"


class ClientStatus(str, Enum):
    """Client account status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class CaseStatus(str, Enum):
    """Case status"""
    OPEN = "open"
    CLOSED = "closed"
    ARCHIVED = "archived"


# Data Transfer Objects for Worker operations
class RunData:
    """Represents run data for worker access"""
    def __init__(
        self,
        id: int,
        case_id: int,
        status: str,
        provider: str,
        model: Optional[str] = None,
        prompt_version: str = "v1",
        created_at: Optional[datetime] = None,
    ):
        self.id = id
        self.case_id = case_id
        self.status = status
        self.provider = provider
        self.model = model
        self.prompt_version = prompt_version
        self.created_at = created_at or datetime.utcnow()
        self.started_at: Optional[datetime] = None
        self.finished_at: Optional[datetime] = None
        self.docling_seconds: Optional[float] = None
        self.extractor_seconds: Optional[float] = None
        self.total_seconds: Optional[float] = None
        self.cost_usd: Optional[float] = None
        self.error: Optional[str] = None
        self.run_metadata: Optional[Dict[str, Any]] = None


class DocumentData:
    """Represents document data for worker access"""
    def __init__(
        self,
        id: int,
        run_id: int,
        case_id: int,
        filename: str,
        storage_key: str,
        status: str = DocumentStatus.PENDING.value,
        size_bytes: Optional[int] = None,
        sha256: Optional[str] = None,
    ):
        self.id = id
        self.run_id = run_id
        self.case_id = case_id
        self.filename = filename
        self.storage_key = storage_key
        self.status = status
        self.size_bytes = size_bytes
        self.sha256 = sha256
        self.extracted_text: Optional[str] = None
        self.processed_at: Optional[datetime] = None
        self.processing_time_seconds: Optional[float] = None
        self.pages: Optional[int] = None
        self.ocr_detected: bool = False
        self.error: Optional[str] = None


class EventData:
    """Represents event data extracted from documents"""
    def __init__(
        self,
        run_id: int,
        document_id: int,
        number: int,
        date: str,
        event_particulars: str,
        citation: str,
        document_reference: str,
    ):
        self.run_id = run_id
        self.document_id = document_id
        self.number = number
        self.date = date
        self.event_particulars = event_particulars
        self.citation = citation
        self.document_reference = document_reference


class ProcessRunRequest:
    """Request to process a run"""
    def __init__(
        self,
        run_id: int,
        provider: str = "openrouter",
        model: Optional[str] = None,
    ):
        self.run_id = run_id
        self.provider = provider
        self.model = model


class ProcessingResult:
    """Result of processing operation"""
    def __init__(
        self,
        run_id: int,
        status: str,
        processed: int,
        failed: int,
        total_events: int,
        duration_seconds: float,
        error: Optional[str] = None,
    ):
        self.run_id = run_id
        self.status = status
        self.processed = processed
        self.failed = failed
        self.total_events = total_events
        self.duration_seconds = duration_seconds
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "run_id": self.run_id,
            "status": self.status,
            "processed": self.processed,
            "failed": self.failed,
            "total_events": self.total_events,
            "duration_seconds": self.duration_seconds,
            "error": self.error,
        }
