"""
Pydantic schemas for API request/response validation
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


# ============================================================================
# Enums (matching database)
# ============================================================================

class UserRoleEnum(str, Enum):
    admin = "admin"
    case_manager = "case_manager"
    reviewer = "reviewer"


class RunStatusEnum(str, Enum):
    queued = "queued"
    processing = "processing"
    partial = "partial"
    success = "success"
    failed = "failed"


class DocumentStatusEnum(str, Enum):
    pending = "pending"
    processing = "processing"
    success = "success"
    failed = "failed"


# ============================================================================
# Client Schemas
# ============================================================================

class ClientCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    reference_code: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = None


class ClientResponse(BaseModel):
    id: int
    name: str
    reference_code: Optional[str]
    notes: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Case Schemas
# ============================================================================

class CaseCreate(BaseModel):
    client_id: int
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    retention_days: Optional[int] = Field(90, ge=1, le=3650)  # 1 day to 10 years


class CaseResponse(BaseModel):
    id: int
    client_id: int
    name: str
    description: Optional[str]
    retention_days: int
    status: str
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class CaseAssignmentCreate(BaseModel):
    user_id: int
    role_in_case: Optional[str] = Field("reviewer", max_length=50)


# ============================================================================
# User Schemas
# ============================================================================

class UserCreate(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    name: str = Field(..., min_length=1, max_length=255)
    role: UserRoleEnum = UserRoleEnum.reviewer
    password: Optional[str] = Field(None, min_length=8)  # For future auth


class UserResponse(BaseModel):
    id: int
    email: str
    name: str
    role: str
    is_active: bool
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Run Schemas
# ============================================================================

class RunCreate(BaseModel):
    case_id: int
    provider: Optional[str] = "openrouter"
    model: Optional[str] = "meta-llama/llama-3.3-70b-instruct"
    file_count: Optional[int] = Field(1, ge=1, le=100)  # For generating upload URLs


class RunCreateResponse(BaseModel):
    run_id: int
    case_id: int
    status: str
    upload_urls: List[str]


class FileManifestItem(BaseModel):
    filename: str
    size_bytes: int
    sha256: str
    storage_key: str
    mime_type: Optional[str] = "application/pdf"


class RunManifest(BaseModel):
    files: List[FileManifestItem]
    idempotency_key: Optional[str] = None


class RunResponse(BaseModel):
    run_id: int
    case_id: int
    status: str
    provider: Optional[str]
    model: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    counts: Dict[str, int]  # total, processed, failed, pending
    timings: Dict[str, Optional[float]]  # docling_seconds, extractor_seconds, total_seconds
    cost_usd: Optional[float]
    error: Optional[str]


# ============================================================================
# Document Schemas
# ============================================================================

class DocumentResponse(BaseModel):
    id: int
    run_id: int
    case_id: int
    filename: str
    size_bytes: Optional[int]
    status: str
    error: Optional[str]
    pages: Optional[int]
    ocr_detected: bool
    processing_time_seconds: Optional[float]
    
    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Event Schemas
# ============================================================================

class EventCreate(BaseModel):
    number: int
    date: str
    event_particulars: str
    citation: Optional[str]
    document_reference: str


class EventResponse(BaseModel):
    id: int
    number: int
    date: str
    event_particulars: str
    citation: Optional[str]
    document_reference: str
    document_id: int
    confidence_score: Optional[float]
    
    model_config = ConfigDict(from_attributes=True)


class EventListResponse(BaseModel):
    events: List[Dict[str, Any]]
    next_cursor: Optional[int]
    has_more: bool


# ============================================================================
# Artifact Schemas
# ============================================================================

class ArtifactResponse(BaseModel):
    id: int
    kind: str
    size_bytes: int
    created_at: datetime
    download_url: str


# ============================================================================
# Model Catalog Schemas
# ============================================================================

class ModelInfo(BaseModel):
    provider: str
    model_id: str
    display_name: str
    cost_input_per_million: Optional[float]
    cost_output_per_million: Optional[float]
    context_window: Optional[int]
    supports_json_mode: bool
    badges: Optional[List[str]]
    status: str
    is_recommended: bool


# ============================================================================
# Progress/Streaming Schemas
# ============================================================================

class ProgressUpdate(BaseModel):
    run_id: int
    status: str
    documents: List[Dict[str, Any]]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class DocumentProgress(BaseModel):
    id: int
    filename: str
    status: str
    progress_percent: Optional[float] = None
    error: Optional[str] = None


# ============================================================================
# Export Schemas
# ============================================================================

class ExportRequest(BaseModel):
    format: str = Field("csv", pattern="^(csv|xlsx|json)$")
    include_metadata: bool = False


class ExportResponse(BaseModel):
    download_url: str
    expires_at: Optional[datetime]
    size_bytes: Optional[int]


# ============================================================================
# Health Check Schemas
# ============================================================================

class HealthStatus(BaseModel):
    status: str  # healthy, degraded, unhealthy
    timestamp: datetime
    components: Dict[str, str]
