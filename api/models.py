"""
Database Models for Legal Events Extraction v2
Based on PRD specifications with PostgreSQL and future multi-tenant support
"""

from sqlalchemy import (
    Column, String, Integer, Text, DateTime, Float, 
    ForeignKey, Enum, Boolean, Index, JSON, LargeBinary
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import enum
import hashlib

Base = declarative_base()


class UserRole(enum.Enum):
    """User role enumeration"""
    ADMIN = "admin"
    CASE_MANAGER = "case_manager" 
    REVIEWER = "reviewer"


class RunStatus(enum.Enum):
    """Run processing status"""
    QUEUED = "queued"
    PROCESSING = "processing"
    PARTIAL_SUCCESS = "partial"
    SUCCESS = "success"
    FAILED = "failed"


class DocumentStatus(enum.Enum):
    """Document processing status"""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"


class ClientStatus(enum.Enum):
    """Client account status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class CaseStatus(enum.Enum):
    """Case status"""
    OPEN = "open"
    CLOSED = "closed"
    ARCHIVED = "archived"


class Client(Base):
    """Client (organization) that owns cases"""
    __tablename__ = "clients"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    reference_code = Column(String(100), unique=True)
    notes = Column(Text)
    status = Column(Enum(ClientStatus), default=ClientStatus.ACTIVE)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    cases = relationship("Case", back_populates="client", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Client {self.name}>"


class Case(Base):
    """Legal case containing multiple document runs"""
    __tablename__ = "cases"
    
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    retention_days = Column(Integer, default=90)
    status = Column(Enum(CaseStatus), default=CaseStatus.OPEN)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    client = relationship("Client", back_populates="cases")
    runs = relationship("Run", back_populates="case", cascade="all, delete-orphan")
    assignments = relationship("CaseAssignment", back_populates="case", cascade="all, delete-orphan")
    
    # Indexes for common queries
    __table_args__ = (
        Index('idx_case_client_status', 'client_id', 'status'),
    )
    
    def __repr__(self):
        return f"<Case {self.name}>"


class User(Base):
    """System users (lawyers, paralegals, admins)"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.REVIEWER)
    password_hash = Column(String(255))  # For future auth implementation
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    assignments = relationship("CaseAssignment", back_populates="user")
    
    def __repr__(self):
        return f"<User {self.email}>"


class CaseAssignment(Base):
    """Many-to-many relationship between cases and users"""
    __tablename__ = "case_assignments"
    
    id = Column(Integer, primary_key=True)
    case_id = Column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role_in_case = Column(String(50))  # e.g., "lead", "reviewer", "assistant"
    created_at = Column(DateTime, server_default=func.now())
    
    # Relationships
    case = relationship("Case", back_populates="assignments")
    user = relationship("User", back_populates="assignments")
    
    # Unique constraint
    __table_args__ = (
        Index('idx_case_user_unique', 'case_id', 'user_id', unique=True),
    )


class Run(Base):
    """A processing run for a batch of documents"""
    __tablename__ = "runs"
    
    id = Column(Integer, primary_key=True)
    case_id = Column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    status = Column(Enum(RunStatus), default=RunStatus.QUEUED)
    
    # Model configuration
    provider = Column(String(50))  # openrouter, anthropic, openai, etc.
    model = Column(String(100))    # specific model name
    prompt_version = Column(String(20), default="v1")  # v1, v2, etc.
    
    # Timing and cost tracking
    created_at = Column(DateTime, server_default=func.now())
    started_at = Column(DateTime)
    finished_at = Column(DateTime)
    docling_seconds = Column(Float)
    extractor_seconds = Column(Float) 
    total_seconds = Column(Float)
    cost_usd = Column(Float)
    
    # Error tracking
    error = Column(Text)
    
    # Metadata
    metadata = Column(JSON)  # For additional tracking data
    
    # Relationships
    case = relationship("Case", back_populates="runs")
    documents = relationship("Document", back_populates="run", cascade="all, delete-orphan")
    events = relationship("Event", back_populates="run", cascade="all, delete-orphan")
    artifacts = relationship("Artifact", back_populates="run", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('idx_run_case_status', 'case_id', 'status'),
        Index('idx_run_created', 'created_at'),
    )
    
    def __repr__(self):
        return f"<Run {self.id} - {self.status.value}>"


class Document(Base):
    """Individual document within a run"""
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("runs.id", ondelete="CASCADE"), nullable=False)
    case_id = Column(Integer, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    
    # File information
    filename = Column(String(255), nullable=False)
    size_bytes = Column(Integer)
    sha256 = Column(String(64))  # For deduplication
    storage_key = Column(String(500))  # MinIO/S3 path
    mime_type = Column(String(100))
    
    # Processing information
    ocr_detected = Column(Boolean, default=False)
    pages = Column(Integer)
    status = Column(Enum(DocumentStatus), default=DocumentStatus.PENDING)
    error = Column(Text)
    
    # Timing
    created_at = Column(DateTime, server_default=func.now())
    processed_at = Column(DateTime)
    processing_time_seconds = Column(Float)
    
    # Extracted text cache (optional)
    extracted_text = Column(Text)  # Cache of docling output
    
    # Relationships
    run = relationship("Run", back_populates="documents")
    events = relationship("Event", back_populates="document", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('idx_doc_sha256', 'sha256'),
        Index('idx_doc_run_status', 'run_id', 'status'),
    )
    
    def calculate_sha256(self, file_content: bytes) -> str:
        """Calculate SHA256 hash of file content"""
        return hashlib.sha256(file_content).hexdigest()
    
    def __repr__(self):
        return f"<Document {self.filename}>"


class Event(Base):
    """Extracted legal event"""
    __tablename__ = "events"
    
    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("runs.id", ondelete="CASCADE"), nullable=False)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    
    # Five-column structure
    number = Column(Integer)  # Event number (No column)
    date = Column(String(100))  # Date string (can be "Date not available")
    event_particulars = Column(Text, nullable=False)  # Main event description
    citation = Column(Text)  # Legal citations
    document_reference = Column(String(255))  # Source document name
    
    # Additional metadata
    confidence_score = Column(Float)  # Optional ML confidence
    created_at = Column(DateTime, server_default=func.now())
    
    # Relationships
    run = relationship("Run", back_populates="events")
    document = relationship("Document", back_populates="events")
    
    # Indexes
    __table_args__ = (
        Index('idx_event_run', 'run_id'),
        Index('idx_event_document', 'document_id'),
        Index('idx_event_date', 'date'),
    )
    
    def to_dict(self):
        """Convert to dictionary for export"""
        return {
            "No": self.number,
            "Date": self.date,
            "Event Particulars": self.event_particulars,
            "Citation": self.citation,
            "Document Reference": self.document_reference
        }
    
    def __repr__(self):
        return f"<Event {self.number} from {self.document_reference}>"


class Artifact(Base):
    """Generated export files (CSV, XLSX, JSON)"""
    __tablename__ = "artifacts"
    
    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("runs.id", ondelete="CASCADE"), nullable=False)
    kind = Column(String(20))  # csv, xlsx, json
    storage_key = Column(String(500))  # MinIO/S3 path
    size_bytes = Column(Integer)
    created_at = Column(DateTime, server_default=func.now())
    expires_at = Column(DateTime)  # For presigned URL expiration tracking
    
    # Relationships
    run = relationship("Run", back_populates="artifacts")
    
    def __repr__(self):
        return f"<Artifact {self.kind} for Run {self.run_id}>"


class ModelCatalog(Base):
    """Available models and their capabilities"""
    __tablename__ = "model_catalog"
    
    id = Column(Integer, primary_key=True)
    provider = Column(String(50), nullable=False)  # openrouter, anthropic, etc.
    model_id = Column(String(100), nullable=False)  # model identifier
    display_name = Column(String(255))
    
    # Costs (per 1M tokens)
    cost_input_per_million = Column(Float)
    cost_output_per_million = Column(Float)
    
    # Capabilities
    context_window = Column(Integer)
    supports_json_mode = Column(Boolean, default=False)
    supports_vision = Column(Boolean, default=False)
    
    # Metadata
    badges = Column(JSON)  # ["recommended", "fast", "quality", etc.]
    status = Column(String(20), default="stable")  # stable, experimental, deprecated
    is_recommended = Column(Boolean, default=False)
    
    # Tracking
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Unique constraint
    __table_args__ = (
        Index('idx_model_provider_id', 'provider', 'model_id', unique=True),
    )
    
    def __repr__(self):
        return f"<Model {self.provider}:{self.model_id}>"
