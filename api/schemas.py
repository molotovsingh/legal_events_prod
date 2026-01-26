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
    provider: Optional[str] = "openrouter"  # Standardized default (v0.11.0+)
    model: Optional[str] = "meta-llama/llama-3.3-70b-instruct"  # Standardized default (v0.11.0+)
    doc_extractor: Optional[str] = "docling"  # Document extractor: 'docling' or 'qwen_vl'
    files: Optional[List[Dict[str, Any]]] = None  # Optional file manifest from frontend upload
    # Document classification (Layer 1.5) - always enabled by default
    enable_classification: Optional[bool] = True
    classification_model: Optional[str] = "meta-llama/llama-3.3-70b-instruct"


class RunCreateResponse(BaseModel):
    run_id: int
    case_id: int
    status: str


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


class PaginationMetadata(BaseModel):
    """Pagination metadata for list endpoints"""
    total: int = Field(..., description="Total number of items matching the query")
    limit: int = Field(..., description="Number of items per page")
    offset: int = Field(..., description="Number of items skipped")
    has_next: bool = Field(..., description="Whether there are more items after this page")
    has_prev: bool = Field(..., description="Whether there are items before this page")


class RunListResponse(BaseModel):
    """Response schema for GET /v1/runs endpoint"""
    runs: List[RunResponse]
    pagination: PaginationMetadata


# ============================================================================
# Classification Schemas
# ============================================================================

class ClassifierModel(BaseModel):
    model_id: str
    display_name: str
    provider: str
    recommended: bool = False


class ClassifierListResponse(BaseModel):
    models: List[ClassifierModel]
    count: int
    timestamp: datetime


# ============================================================================
# Token Estimation Schemas
# ============================================================================

class FileRef(BaseModel):
    filename: str
    storage_key: str
    size_bytes: Optional[int] = None
    mime_type: Optional[str] = None


class TokenEstimateRequest(BaseModel):
    provider: str
    model: str
    doc_extractor: Optional[str] = "docling"
    files: List[FileRef]
    enable_classification: Optional[bool] = True
    classification_model: Optional[str] = "meta-llama/llama-3.3-70b-instruct"


class PerDocTokenEstimate(BaseModel):
    filename: str
    event_input_tokens: int
    classification_input_tokens: Optional[int] = None


class TokenTotals(BaseModel):
    event_input_tokens: int
    classification_input_tokens: int = 0
    total_input_tokens: int
    cost_input_usd: Optional[float] = None
    currency: str = "USD"
    approx: bool = False


class PricingInfo(BaseModel):
    cost_input_per_1m: Optional[float] = None
    cost_output_per_1m: Optional[float] = None


class TokenEstimateResponse(BaseModel):
    per_document: List[PerDocTokenEstimate]
    totals: TokenTotals
    # Mapping of role -> pricing (e.g., {"event": {...}, "classification": {...}})
    pricing: Optional[Dict[str, PricingInfo]] = None


# ============================================================================
# Temporary Upload Cleanup Schemas
# ============================================================================

class TempCleanupRequest(BaseModel):
    keys: List[str]


class TempCleanupResponse(BaseModel):
    deleted: int
    skipped: int


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
# Provider Schemas
# ============================================================================

class ProviderDetail(BaseModel):
    """Unified provider metadata (combines Handler 1 and Handler 2 fields)"""
    provider_id: str
    display_name: str  # Canonical field name
    name: str  # Backward compatibility alias (same as display_name)
    enabled: bool
    supports_runtime_model: bool
    recommended: bool
    notes: str
    documentation_url: Optional[str]
    is_working: bool  # Runtime validation (provider loaded in registry)
    models: List[str] = []  # Future: populate from model catalog


class ProvidersResponse(BaseModel):
    """Unified provider list response with metadata"""
    providers: List[ProviderDetail]
    count: int
    timestamp: str


# Backward compatibility alias
ProviderInfo = ProviderDetail
ProvidersListResponse = ProvidersResponse


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
# Authentication Schemas
# ============================================================================

class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Dict[str, Any]


# ============================================================================
# Health Check Schemas
# ============================================================================

class HealthStatus(BaseModel):
    status: str  # healthy, degraded, unhealthy
    timestamp: datetime
    components: Dict[str, str]


class WorkerHeartbeat(BaseModel):
    """Worker heartbeat information"""
    last_beat: str  # ISO 8601 timestamp
    seconds_ago: int
    is_alive: bool
    hostname: Optional[str] = None
    pid: Optional[int] = None


class WorkerInfo(BaseModel):
    """Individual worker information"""
    name: str
    queues: List[str]
    state: str
    successful_job_count: int = 0
    failed_job_count: int = 0
    heartbeat: Optional[WorkerHeartbeat] = None


class QueueStats(BaseModel):
    """Per-queue statistics"""
    queued: int = 0
    started: int = 0
    finished: int = 0
    failed: int = 0


class WorkerStatusResponse(BaseModel):
    """
    Worker status endpoint response with heartbeat-aware liveness detection.
    
    Fields:
        workers_registered: Total number of RQ workers registered in Redis
        workers_with_heartbeat: Number of workers with active (non-stale) heartbeats
        workers_stale: Number of workers with stale heartbeats (>60s old)
        healthy: True ONLY if workers_registered > 0 AND workers_with_heartbeat > 0 AND workers_stale == 0
        status: Overall status (healthy | degraded | unhealthy)
        workers: Detailed worker information with heartbeat data
        queue_depth: Total jobs queued across all queues
        jobs_processing: Total jobs currently being processed
        queues: Per-queue statistics (high, default, low)
        timestamp: ISO 8601 timestamp of status check
    
    Status determination logic (api/main.py:1232-1240):
        - status = "degraded" if workers_registered == 0
        - status = "degraded" if active_heartbeats == 0
        - status = "degraded" if stale_heartbeats > 0
        - status = "healthy" otherwise
    """
    workers_registered: int
    workers_with_heartbeat: int
    workers_stale: int
    workers: List[WorkerInfo]
    queue_depth: int
    jobs_processing: int
    queues: Dict[str, QueueStats]
    healthy: bool
    status: str  # "healthy" | "degraded" | "unhealthy"
    timestamp: str  # ISO 8601
