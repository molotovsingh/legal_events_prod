"""
Shared module for cross-service data structures
Contains enums and DTOs used by both API and Worker services
"""

from .schemas import (
    RunStatus,
    DocumentStatus,
    ClientStatus,
    CaseStatus,
    RunData,
    DocumentData,
    EventData,
    ProcessRunRequest,
    ProcessingResult,
)

__all__ = [
    "RunStatus",
    "DocumentStatus",
    "ClientStatus",
    "CaseStatus",
    "RunData",
    "DocumentData",
    "EventData",
    "ProcessRunRequest",
    "ProcessingResult",
]
