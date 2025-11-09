# Legal Events Production System - Visual Code Map

**Version**: 2.0.0  
**Date**: November 9, 2025  
**Status**: Pre-Alpha (Phase 2 - Testing & Bug Discovery)  
**Repository**: https://github.com/molotovsingh/legal_events_prod.git

---

## 📋 Table of Contents

1. [System Architecture Overview](#system-architecture-overview)
2. [Interactive File Dependency Diagrams](#interactive-file-dependency-diagrams)
3. [API Endpoint Documentation](#api-endpoint-documentation)
4. [Database Schema Visualizations](#database-schema-visualizations)
5. [Docker Service Architecture](#docker-service-architecture)
6. [Data Flow Diagrams](#data-flow-diagrams)
7. [Component Relationships](#component-relationships)
8. [Configuration Dependencies](#configuration-dependencies)
9. [Development Workflow](#development-workflow)

---

## 🏗️ System Architecture Overview

### High-Level Architecture

```mermaid
graph TB
    subgraph "Client Layer"
        FE[Frontend: HTML/JS]
        API_CLIENT[API Client]
    end
    
    subgraph "Service Layer"
        API[FastAPI Service<br/>Port: 8000]
        WORKER[Worker Service<br/>Background Processing]
    end
    
    subgraph "Data Layer"
        PG[(PostgreSQL<br/>Port: 5432)]
        REDIS[(Redis<br/>Port: 6379)]
        MINIO[(MinIO S3<br/>Ports: 9000/9001)]
    end
    
    subgraph "External Services"
        LLM1[Anthropic Claude]
        LLM2[OpenAI GPT]
        LLM3[OpenRouter]
        LLM4[Google Gemini]
        LLM5[DeepSeek]
    end
    
    FE --> API
    API_CLIENT --> API
    API --> PG
    API --> REDIS
    API --> MINIO
    WORKER --> REDIS
    WORKER --> PG
    WORKER --> MINIO
    WORKER --> LLM1
    WORKER --> LLM2
    WORKER --> LLM3
    WORKER --> LLM4
    WORKER --> LLM5
```

### Project Structure

```
legal-events-production/
├── 📁 api/                     # FastAPI REST API (~2,944 LoC)
│   ├── main.py                # Application entry point
│   ├── schemas.py             # Pydantic validation schemas
│   ├── auth.py                # JWT authentication
│   └── event_processor.py     # Status update processor
│
├── 📁 core/                   # Battle-tested extraction pipeline (10,212 LoC)
│   ├── legal_pipeline_refactored.py  # Central orchestrator
│   ├── extractor_factory.py           # Provider registry
│   ├── document_processor.py          # Docling integration
│   ├── *_adapter.py                   # 8 LLM provider adapters
│   ├── config.py                      # Configuration management
│   ├── constants.py                   # Prompts & table headers
│   └── judges/                        # 3-Judge evaluation system
│
├── 📁 infra/                  # Infrastructure layer
│   ├── models.py              # SQLAlchemy database models
│   ├── database.py            # Database connection management
│   ├── storage.py             # MinIO S3 integration
│   ├── queue.py               # Redis/RQ integration
│   └── storage_keys.py        # Storage key generation
│
├── 📁 worker/                 # Background job processor
│   ├── main.py                # Worker entry point
│   ├── tasks.py               # Job definitions
│   └── tasks_refactored.py    # Updated job logic
│
├── 📁 migrations/             # Database migrations (Alembic)
├── 📁 tests/                  # Test suite
├── 📁 frontend/               # Static HTML UI
├── 📁 docs/                   # Documentation
├── 📁 bug_reports/           # Bug tracking system
├── 📁 recommendations/        # Improvement recommendations
├── 📁 research/              # Research documents
├── 📁 scripts/               # Utility scripts
├── 📁 shared/                # Shared utilities
├── 📁 test_documents/        # Testing samples
└── 📁 utils/                 # General utilities

Configuration Files:
├── docker-compose.yml         # Service orchestration
├── requirements.txt           # Python dependencies
├── alembic.ini               # Migration configuration
├── Dockerfile.api            # API container
├── Dockerfile.worker         # Worker container
└── start.sh                  # Management script
```

---

## 🔗 Interactive File Dependency Diagrams

### Core Pipeline Dependencies

```mermaid
graph TD
    subgraph "Entry Points"
        API_MAIN[api/main.py]
        WORKER_MAIN[worker/main.py]
    end
    
    subgraph "Core Pipeline"
        PIPELINE[core/legal_pipeline_refactored.py]
        FACTORY[core/extractor_factory.py]
        DOCLING[core/document_processor.py]
    end
    
    subgraph "Provider Adapters"
        ANTHROPIC[core/anthropic_adapter.py]
        OPENAI[core/openai_adapter.py]
        OPENROUTER[core/openrouter_adapter.py]
        GEMINI[core/gemini_adapter.py]
        DEEPSEEK[core/deepseek_adapter.py]
        OPENCODE[core/opencode_zen_adapter.py]
        QWEN[core/qwen_vl_doc_adapter.py]
        LANGEXTRACT[core/langextract_adapter.py]
    end
    
    subgraph "Configuration"
        CONFIG[core/config.py]
        CONSTANTS[core/constants.py]
        MODEL_CATALOG[core/model_catalog.py]
    end
    
    API_MAIN --> PIPELINE
    WORKER_MAIN --> PIPELINE
    
    PIPELINE --> FACTORY
    PIPELINE --> DOCLING
    
    FACTORY --> ANTHROPIC
    FACTORY --> OPENAI
    FACTORY --> OPENROUTER
    FACTORY --> GEMINI
    FACTORY --> DEEPSEEK
    FACTORY --> OPENCODE
    FACTORY --> QWEN
    FACTORY --> LANGEXTRACT
    
    PIPELINE --> CONFIG
    PIPELINE --> CONSTANTS
    PIPELINE --> MODEL_CATALOG
```

### API Layer Dependencies

```mermaid
graph TD
    subgraph "API Layer"
        MAIN[api/main.py]
        SCHEMAS[api/schemas.py]
        AUTH[api/auth.py]
        EVENT_PROC[api/event_processor.py]
    end
    
    subgraph "Infrastructure"
        MODELS[infra/models.py]
        DATABASE[infra/database.py]
        STORAGE[infra/storage.py]
        QUEUE[infra/queue.py]
        STORAGE_KEYS[infra/storage_keys.py]
    end
    
    MAIN --> SCHEMAS
    MAIN --> AUTH
    MAIN --> EVENT_PROC
    
    MAIN --> MODELS
    MAIN --> DATABASE
    MAIN --> STORAGE
    MAIN --> QUEUE
    MAIN --> STORAGE_KEYS
    
    EVENT_PROC --> DATABASE
```

### Worker Dependencies

```mermaid
graph TD
    subgraph "Worker Layer"
        WORKER_MAIN[worker/main.py]
        TASKS[worker/tasks.py]
        TASKS_REF[worker/tasks_refactored.py]
    end
    
    subgraph "Core Components"
        PIPELINE[core/legal_pipeline_refactored.py]
        CONFIG[core/config.py]
        CONSTANTS[core/constants.py]
    end
    
    subgraph "Infrastructure"
        DATABASE[infra/database.py]
        STORAGE[infra/storage.py]
        QUEUE[infra/queue.py]
    end
    
    WORKER_MAIN --> TASKS
    WORKER_MAIN --> TASKS_REF
    
    TASKS --> PIPELINE
    TASKS_REF --> PIPELINE
    
    TASKS --> CONFIG
    TASKS --> CONSTANTS
    TASKS --> DATABASE
    TASKS --> STORAGE
    TASKS --> QUEUE
```

---

## 🌐 API Endpoint Documentation

### API Overview

**Base URL**: `http://localhost:8000`  
**API Version**: v1  
**Authentication**: JWT Bearer Token (enabled for write operations)  
**Documentation**: http://localhost:8000/docs

### Authentication Endpoints

#### POST /v1/auth/login
Authenticate user and return JWT token.

**Request:**
```json
{
  "email": "admin@legalevents.local",
  "password": "admin123"
}
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "email": "admin@legalevents.local",
    "name": "Admin User",
    "role": "admin"
  }
}
```

### Client Management

#### POST /v1/clients
Create a new client organization.

**Headers:**
- `Authorization: Bearer <token>`

**Request:**
```json
{
  "name": "Firm ABC Law",
  "reference_code": "FIRM-ABC",
  "notes": "Main corporate client"
}
```

**Response:**
```json
{
  "id": 1,
  "name": "Firm ABC Law",
  "reference_code": "FIRM-ABC",
  "notes": "Main corporate client",
  "status": "active",
  "created_at": "2025-11-09T07:30:00Z",
  "updated_at": "2025-11-09T07:30:00Z"
}
```

#### GET /v1/clients
List all clients with pagination.

**Query Parameters:**
- `skip` (int): Number of records to skip (default: 0)
- `limit` (int): Maximum records to return (default: 100, max: 1000)

**Response:**
```json
{
  "id": 1,
  "name": "Firm ABC Law",
  "reference_code": "FIRM-ABC",
  "notes": "Main corporate client",
  "status": "active",
  "created_at": "2025-11-09T07:30:00Z",
  "updated_at": "2025-11-09T07:30:00Z"
}
```

### Case Management

#### POST /v1/cases
Create a new case.

**Request:**
```json
{
  "client_id": 1,
  "name": "Contract Dispute 2025",
  "description": "Breach of contract case",
  "retention_days": 365
}
```

#### GET /v1/clients/{client_id}/cases
List cases for a client.

### Run Management (Document Processing)

#### POST /v1/runs
Create a new processing run.

**Request:**
```json
{
  "case_id": 1,
  "provider": "openrouter",
  "model": "meta-llama/llama-3.3-70b-instruct",
  "doc_extractor": "docling"
}
```

**Response:**
```json
{
  "run_id": 1,
  "case_id": 1,
  "status": "queued"
}
```

#### PUT /v1/runs/{run_id}/upload
Upload files to MinIO storage.

**Request:** Multipart form with file upload

**Response:**
```json
{
  "status": "uploaded",
  "filename": "contract.pdf",
  "storage_key": "clients/1/cases/1/runs/1/contract.pdf",
  "size_bytes": 1024000
}
```

#### PUT /v1/runs/{run_id}/start
Start processing a run.

**Headers:**
- `Authorization: Bearer <token>`
- `Idempotency-Key: <unique-key>` (optional)

**Request:**
```json
{
  "files": [
    {
      "filename": "contract.pdf",
      "size_bytes": 1024000,
      "sha256": "abc123...",
      "storage_key": "clients/1/cases/1/runs/1/contract.pdf",
      "mime_type": "application/pdf"
    }
  ],
  "idempotency_key": "unique-processing-key-123"
}
```

**Response:**
```json
{
  "status": "accepted",
  "run_id": 1,
  "job_id": "rq:job:123",
  "message": "Run processing started"
}
```

#### GET /v1/runs/{run_id}
Get run details and progress.

**Response:**
```json
{
  "run_id": 1,
  "case_id": 1,
  "status": "processing",
  "provider": "openrouter",
  "model": "meta-llama/llama-3.3-70b-instruct",
  "created_at": "2025-11-09T07:30:00Z",
  "started_at": "2025-11-09T07:31:00Z",
  "finished_at": null,
  "counts": {
    "total": 3,
    "processed": 1,
    "failed": 0,
    "pending": 2
  },
  "timings": {
    "docling_seconds": 12.5,
    "extractor_seconds": 45.2,
    "total_seconds": 57.7
  },
  "cost_usd": 0.15,
  "error": null
}
```

#### GET /v1/runs/{run_id}/events
Get extracted events (paginated).

**Query Parameters:**
- `cursor` (int): Event ID for pagination
- `limit` (int): Maximum events to return (default: 100, max: 1000)

**Response:**
```json
{
  "events": [
    {
      "id": 1,
      "number": 1,
      "date": "2024-01-15",
      "event_particulars": "Contract signed by both parties",
      "citation": "Section 2.1 of the agreement",
      "document_reference": "contract.pdf",
      "document_id": 1
    },
    {
      "id": 2,
      "number": 2,
      "date": "2024-02-20",
      "event_particulars": "Payment due date",
      "citation": "Section 3.2 of the agreement",
      "document_reference": "contract.pdf",
      "document_id": 1
    }
  ],
  "next_cursor": 2,
  "has_more": false
}
```

#### GET /v1/runs/{run_id}/stream
Server-Sent Events for real-time progress.

**Response:** Event stream with updates:
- `progress`: Regular status updates
- `complete`: Final status
- `error`: Error notifications
- `timeout`: Stream timeout (1 hour max)

#### GET /v1/runs/{run_id}/export
Generate and download export files.

**Query Parameters:**
- `fmt` (string): Format (csv, xlsx, json)

**Response:** File download with appropriate content-type

#### PUT /v1/runs/{run_id}/retry
Retry a failed or stuck run.

**Headers:**
- `Authorization: Bearer <token>`
- `Idempotency-Key: <unique-key>` (optional)

**Response:**
```json
{
  "status": "accepted",
  "run_id": 1,
  "job_id": "rq:job:456",
  "documents_reset": 2,
  "failed_documents": 1,
  "stuck_documents": 1
}
```

### Model Catalog

#### GET /v1/models
List available models with pricing and capabilities.

**Query Parameters:**
- `provider` (string): Filter by provider
- `recommended` (boolean): Filter to recommended models only

**Response:**
```json
{
  "models": [
    {
      "provider": "openrouter",
      "model_id": "meta-llama/llama-3.3-70b-instruct",
      "display_name": "Llama 3.3 70B Instruct",
      "cost_input_per_million": 0.39,
      "cost_output_per_million": 0.39,
      "context_window": 131072,
      "supports_json_mode": true,
      "badges": ["recommended", "fast"],
      "status": "stable",
      "is_recommended": true
    }
  ]
}
```

#### GET /v1/providers
List available event extraction providers.

**Query Parameters:**
- `enabled` (boolean): Filter to enabled providers
- `recommended_only` (boolean): Only recommended providers

**Response:**
```json
{
  "providers": [
    {
      "provider_id": "langextract",
      "display_name": "Gemini (LangExtract)",
      "enabled": true,
      "supports_runtime_model": true,
      "recommended": true,
      "notes": "Google's structured extraction service",
      "documentation_url": "https://ai.google.dev/"
    }
  ],
  "count": 8,
  "timestamp": "2025-11-09T07:30:00Z"
}
```

### Health & Status

#### GET /health
Comprehensive health check.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-11-09T07:30:00Z",
  "components": {
    "database": "healthy",
    "storage": "healthy",
    "queue": "healthy"
  }
}
```

---

## 🗄️ Database Schema Visualizations

### Entity Relationship Diagram

```mermaid
erDiagram
    CLIENT {
        int id PK
        string name
        string reference_code UK
        text notes
        enum status
        datetime created_at
        datetime updated_at
    }
    
    CASE {
        int id PK
        int client_id FK
        string name
        text description
        int retention_days
        enum status
        datetime created_at
        datetime updated_at
    }
    
    USER {
        int id PK
        string email UK
        string name
        enum role
        string password_hash
        boolean is_active
        datetime created_at
        datetime updated_at
    }
    
    CASE_ASSIGNMENT {
        int id PK
        int case_id FK
        int user_id FK
        string role_in_case
        datetime created_at
    }
    
    RUN {
        int id PK
        int case_id FK
        enum status
        string provider
        string model
        string doc_extractor
        string prompt_version
        datetime created_at
        datetime started_at
        datetime finished_at
        float docling_seconds
        float extractor_seconds
        float total_seconds
        float cost_usd
        text error
        json run_metadata
    }
    
    DOCUMENT {
        int id PK
        int run_id FK
        int case_id FK
        string filename
        int size_bytes
        string sha256 UK
        string storage_key
        string mime_type
        boolean ocr_detected
        int pages
        enum status
        text error
        datetime created_at
        datetime processed_at
        float processing_time_seconds
        text extracted_text
    }
    
    EVENT {
        int id PK
        int run_id FK
        int document_id FK
        int number
        string date
        text event_particulars
        text citation
        string document_reference
        float confidence_score
        datetime created_at
    }
    
    ARTIFACT {
        int id PK
        int run_id FK
        string kind
        string storage_key
        int size_bytes
        datetime created_at
        datetime expires_at
    }
    
    MODEL_CATALOG {
        int id PK
        string provider
        string model_id UK
        string display_name
        float cost_input_per_million
        float cost_output_per_million
        int context_window
        boolean supports_json_mode
        boolean supports_vision
        json badges
        string status
        boolean is_recommended
        datetime created_at
        datetime updated_at
    }
    
    CLIENT ||--o{ CASE : "owns"
    CASE ||--o{ RUN : "contains"
    CASE ||--o{ CASE_ASSIGNMENT : "has"
    USER ||--o{ CASE_ASSIGNMENT : "assigned_to"
    RUN ||--o{ DOCUMENT : "processes"
    RUN ||--o{ EVENT : "produces"
    RUN ||--o{ ARTIFACT : "generates"
    DOCUMENT ||--o{ EVENT : "sources"
```

### Database Tables Overview

| Table | Purpose | Key Fields | Relationships |
|-------|---------|------------|---------------|
| **clients** | Client organizations | id, name, reference_code | 1:N with cases |
| **cases** | Legal cases/matters | id, client_id, name | N:1 with clients, 1:N with runs |
| **users** | System users | id, email, role | N:M with cases via assignments |
| **case_assignments** | User-case access | case_id, user_id, role | N:1 with cases, N:1 with users |
| **runs** | Processing sessions | id, case_id, status | N:1 with cases, 1:N with documents/events |
| **documents** | Files to process | id, run_id, filename | N:1 with runs, 1:N with events |
| **events** | Extracted legal events | id, run_id, document_id | N:1 with runs, N:1 with documents |
| **artifacts** | Export files | id, run_id, kind | N:1 with runs |
| **model_catalog** | Available models | provider, model_id | Independent table |

### Indexes for Performance

```sql
-- Case lookups by client and status
CREATE INDEX idx_case_client_status ON cases(client_id, status);

-- Run queries by case and status
CREATE INDEX idx_run_case_status ON runs(case_id, status);
CREATE INDEX idx_run_created ON runs(created_at);

-- Document deduplication and status tracking
CREATE INDEX idx_doc_sha256 ON documents(sha256);
CREATE INDEX idx_doc_run_status ON documents(run_id, status);

-- Event queries
CREATE INDEX idx_event_run ON events(run_id);
CREATE INDEX idx_event_document ON events(document_id);
CREATE INDEX idx_event_date ON events(date);

-- Model catalog lookups
CREATE INDEX idx_model_provider_id ON model_catalog(provider, model_id);

-- Case assignment uniqueness
CREATE UNIQUE INDEX idx_case_user_unique ON case_assignments(case_id, user_id);
```

### Enumerations

```python
# User roles
class UserRole(enum.Enum):
    ADMIN = "admin"
    CASE_MANAGER = "case_manager" 
    REVIEWER = "reviewer"

# Run processing states
class RunStatus(enum.Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    PARTIAL_SUCCESS = "partial"
    SUCCESS = "success"
    FAILED = "failed"

# Document processing states
class DocumentStatus(enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"

# Client account status
class ClientStatus(enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"

# Case lifecycle
class CaseStatus(enum.Enum):
    OPEN = "open"
    CLOSED = "closed"
    ARCHIVED = "archived"
```

---

## 🐳 Docker Service Architecture

### Service Overview

```yaml
# docker-compose.yml Structure
services:
  postgres:     # PostgreSQL 16 - Primary database
  redis:        # Redis 7 - Job queue and cache
  minio:        # MinIO - S3-compatible storage
  api:          # FastAPI - REST API service
  worker:       # RQ Worker - Background processing
  frontend:     # Static HTML - User interface
```

### Service Dependencies

```mermaid
graph TB
    subgraph "Infrastructure Services"
        PG[(postgres)]
        REDIS[(redis)]
        MINIO[(minio)]
    end
    
    subgraph "Application Services"
        API[api:8000]
        WORKER[worker]
        FE[frontend:3000]
    end
    
    API --> PG
    API --> REDIS
    API --> MINIO
    WORKER --> PG
    WORKER --> REDIS
    WORKER --> MINIO
    FE --> API
```

### Individual Service Configurations

#### PostgreSQL Service
```yaml
postgres:
  image: postgres:16-alpine
  container_name: legal_events_db
  ports:
    - "5432:5432"
  environment:
    POSTGRES_DB: ${POSTGRES_DB:-legal_events}
    POSTGRES_USER: ${POSTGRES_USER:-legal_user}
    POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-generate-strong-password}
  volumes:
    - postgres_data:/var/lib/postgresql/data
  deploy:
    resources:
      limits:
        cpus: '2'
        memory: 2G
      reservations:
        cpus: '0.5'
        memory: 512M
```

#### Redis Service
```yaml
redis:
  image: redis:7-alpine
  container_name: legal_events_redis
  ports:
    - "6379:6379"
  volumes:
    - redis_data:/data
  deploy:
    resources:
      limits:
        cpus: '1'
        memory: 512M
      reservations:
        cpus: '0.25'
        memory: 128M
```

#### MinIO Service
```yaml
minio:
  image: minio/minio:latest
  container_name: legal_events_minio
  ports:
    - "9000:9000"     # API port
    - "9001:9001"     # Console port
  environment:
    MINIO_ROOT_USER: ${MINIO_ROOT_USER:-minioadmin}
    MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD:-generate-strong-password}
  command: server /data --console-address ":9001"
  deploy:
    resources:
      limits:
        cpus: '2'
        memory: 1G
      reservations:
        cpus: '0.5'
        memory: 256M
```

#### API Service
```yaml
api:
  build:
    context: .
    dockerfile: Dockerfile.api
  container_name: legal_events_api
  ports:
    - "8000:8000"
  environment:
    APP_ENV: ${APP_ENV:-development}
    DATABASE_URL: postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
    REDIS_URL: ${REDIS_URL:-redis://redis:6379}
    MINIO_ENDPOINT: ${MINIO_ENDPOINT:-minio:9000}
    # LLM API Keys
    OPENROUTER_API_KEY: ${OPENROUTER_API_KEY:-}
    ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY:-}
    OPENAI_API_KEY: ${OPENAI_API_KEY:-}
    GEMINI_API_KEY: ${GEMINI_API_KEY:-}
  depends_on:
    postgres:
      condition: service_healthy
    redis:
      condition: service_healthy
    minio:
      condition: service_healthy
  deploy:
    resources:
      limits:
        cpus: '2'
        memory: 2G
      reservations:
        cpus: '0.5'
        memory: 512M
```

#### Worker Service
```yaml
worker:
  build:
    context: .
    dockerfile: Dockerfile.worker
  container_name: legal_events_worker
  environment:
    APP_ENV: ${APP_ENV:-development}
    DATABASE_URL: postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
    REDIS_URL: ${REDIS_URL:-redis://redis:6379}
    MINIO_ENDPOINT: ${MINIO_ENDPOINT:-minio:9000}
    # LLM API Keys
    OPENROUTER_API_KEY: ${OPENROUTER_API_KEY:-}
    ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY:-}
    OPENAI_API_KEY: ${OPENAI_API_KEY:-}
    GEMINI_API_KEY: ${GEMINI_API_KEY:-}
  depends_on:
    - redis
    - postgres
    - minio
  command: python -m worker.main
  deploy:
    resources:
      limits:
        cpus: '4'
        memory: 4G
      reservations:
        cpus: '1'
        memory: 1G
```

#### Frontend Service
```yaml
frontend:
  build:
    context: .
    dockerfile: Dockerfile.frontend
  container_name: legal_events_ui
  ports:
    - "3000:80"
  environment:
    API_URL: http://api:8000
  depends_on:
    - api
  deploy:
    resources:
      limits:
        cpus: '0.5'
        memory: 256M
      reservations:
        cpus: '0.1'
        memory: 64M
```

### Service Communication

```mermaid
sequenceDiagram
    participant Client
    participant Frontend
    participant API
    participant Worker
    participant PostgreSQL
    participant Redis
    participant MinIO
    participant LLM

    Client->>Frontend: Upload documents
    Frontend->>API: Create run & upload files
    API->>MinIO: Store files
    API->>PostgreSQL: Create run record
    API->>Redis: Enqueue processing job
    Worker->>Redis: Dequeue job
    Worker->>MinIO: Download files
    Worker->>PostgreSQL: Update document status
    Worker->>LLM: Extract events
    Worker->>PostgreSQL: Store events
    Worker->>PostgreSQL: Update run status
    API->>Client: Return run status
```

---

## 🔄 Data Flow Diagrams

### End-to-End Processing Flow

```mermaid
flowchart TD
    subgraph "User Interface"
        U1[Upload Documents]
        U2[Create Case]
        U3[Start Processing]
        U4[Monitor Progress]
        U5[View Results]
        U6[Export Data]
    end
    
    subgraph "API Layer"
        A1[POST /v1/runs]
        A2[PUT /v1/runs/{id}/upload]
        A3[PUT /v1/runs/{id}/start]
        A4[GET /v1/runs/{id}]
        A5[GET /v1/runs/{id}/events]
    end
    
    subgraph "Storage Layer"
        S1[(MinIO S3)]
        S2[(PostgreSQL)]
        S3[(Redis Queue)]
    end
    
    subgraph "Worker Processing"
        W1[Dequeue Job]
        W2[Download Files]
        W3[Docling Extraction]
        W4[LLM Processing]
        W5[Store Results]
    end
    
    subgraph "External Services"
        E1[Docling OCR]
        E2[Anthropic Claude]
        E3[OpenAI GPT]
        E4[OpenRouter]
        E5[Google Gemini]
        E6[DeepSeek]
    end
    
    U1 --> A1
    U1 --> A2
    U2 --> A1
    A1 --> S2
    A2 --> S1
    A3 --> S3
    S3 --> W1
    W1 --> W2
    W2 --> S1
    W3 --> E1
    W4 --> E2
    W4 --> E3
    W4 --> E4
    W4 --> E5
    W4 --> E6
    W5 --> S2
    A4 --> S2
    A5 --> S2
```

### Document Processing Pipeline

```mermaid
flowchart LR
    subgraph "File Input"
        F1[PDF Upload]
        F2[Email .eml]
        F3[Image Files]
    end
    
    subgraph "Preprocessing"
        P1[File Validation]
        P2[Hash Calculation]
        P3[Storage Upload]
        P4[DB Record Creation]
    end
    
    subgraph "Docling Extraction"
        D1[Text Extraction]
        D2[OCR Processing]
        D3[Table Detection]
        D4[Structure Analysis]
    end
    
    subgraph "LLM Processing"
        L1[Provider Selection]
        L2[Prompt Engineering]
        L3[Event Extraction]
        L4[Result Parsing]
    end
    
    subgraph "Post-processing"
        PP1[Validation]
        PP2[Storage]
        PP3[Metadata Update]
    end
    
    F1 --> P1
    F2 --> P1
    F3 --> P1
    P1 --> P2
    P2 --> P3
    P3 --> P4
    P4 --> D1
    D1 --> D2
    D2 --> D3
    D3 --> D4
    D4 --> L1
    L1 --> L2
    L2 --> L3
    L3 --> L4
    L4 --> PP1
    PP1 --> PP2
    PP2 --> PP3
```

### Event Extraction Flow

```mermaid
flowchart TD
    subgraph "Input Document"
        D1[Raw PDF/Email]
    end
    
    subgraph "Docling Processing"
        D2[Text Extraction]
        D3[OCR (if needed)]
        D4[Table Structure]
        D5[Layout Analysis]
    end
    
    subgraph "LLM Extraction"
        L1[Provider Adapter]
        L2[Prompt V1/V2]
        L3[API Call]
        L4[JSON Response]
    end
    
    subgraph "Processing Logic"
        P1[Event Parsing]
        P2[Field Validation]
        P3[Citation Extraction]
        P4[Confidence Scoring]
    end
    
    subgraph "Output"
        O1[5-Column Structure]
        O2[Database Storage]
        O3[Export Generation]
    end
    
    D1 --> D2
    D2 --> D3
    D3 --> D4
    D4 --> D5
    D5 --> L1
    L1 --> L2
    L2 --> L3
    L3 --> L4
    L4 --> P1
    P1 --> P2
    P2 --> P3
    P3 --> P4
    P4 --> O1
    O1 --> O2
    O1 --> O3
```

### Multi-Tenant Data Flow

```mermaid
graph TB
    subgraph "Client 1"
        C1[Client: Law Firm ABC]
        CA1[Case 1: Contract Dispute]
        CA2[Case 2: Employment Issue]
        R1A[Run A: Document Batch 1]
        R1B[Run B: Document Batch 2]
    end
    
    subgraph "Client 2"
        C2[Client: Legal Corp XYZ]
        CB1[Case 3: IP Litigation]
        R2A[Run C: Document Batch 3]
    end
    
    subgraph "Shared Infrastructure"
        DB[(PostgreSQL<br/>Multi-tenant)]
        S3[(MinIO S3<br/>Bucket isolation)]
        Q[(Redis Queue<br/>Shared processing)]
    end
    
    C1 --> CA1
    C1 --> CA2
    C2 --> CB1
    CA1 --> R1A
    CA1 --> R1B
    CB1 --> R2A
    
    R1A --> DB
    R1B --> DB
    R2A --> DB
    R1A --> S3
    R1B --> S3
    R2A --> S3
    
    Q --> R1A
    Q --> R1B
    Q --> R2A
```

### Error Handling & Retry Flow

```mermaid
flowchart TD
    J1[Job Enqueued]
    J2[Worker Picks Job]
    J3[Process Document]
    J4[Success?]
    J5[Store Results]
    J6[Mark Complete]
    J7[Log Error]
    J8[Update DB Status]
    J9[Retry Logic]
    J10[Max Retries?]
    J11[Mark Failed]
    J12[Cleanup Resources]
    
    J1 --> J2
    J2 --> J3
    J3 --> J4
    J4 -->|Yes| J5
    J5 --> J6
    J6 --> J12
    J4 -->|No| J7
    J7 --> J8
    J8 --> J9
    J9 --> J10
    J10 -->|No| J3
    J10 -->|Yes| J11
    J11 --> J12
```

---

## 🔗 Component Relationships

### Core Component Dependencies

```mermaid
graph TB
    subgraph "API Layer"
        A[api/main.py]
        S[api/schemas.py]
        AUTH[api/auth.py]
        EP[api/event_processor.py]
    end
    
    subgraph "Core Pipeline"
        LP[core/legal_pipeline_refactored.py]
        EF[core/extractor_factory.py]
        DP[core/document_processor.py]
        C[core/config.py]
        CONST[core/constants.py]
    end
    
    subgraph "Provider Layer"
        ANTH[core/anthropic_adapter.py]
        OPENAI[core/openai_adapter.py]
        OPENR[core/openrouter_adapter.py]
        GEM[core/gemini_adapter.py]
        DEEP[core/deepseek_adapter.py]
    end
    
    subgraph "Infrastructure"
        M[infra/models.py]
        DB[infra/database.py]
        ST[infra/storage.py]
        Q[infra/queue.py]
    end
    
    subgraph "Worker"
        WM[worker/main.py]
        WT[worker/tasks.py]
    end
    
    A --> S
    A --> AUTH
    A --> EP
    A --> LP
    A --> ST
    A --> Q
    A --> DB
    
    LP --> EF
    LP --> DP
    LP --> C
    LP --> CONST
    
    EF --> ANTH
    EF --> OPENAI
    EF --> OPENR
    EF --> GEM
    EF --> DEEP
    
    WM --> WT
    WT --> LP
    WT --> DB
    WT --> ST
    WT --> Q
```

### Data Flow Dependencies

```mermaid
graph LR
    subgraph "Request Flow"
        R1[HTTP Request]
        R2[Validation]
        R3[Authentication]
        R4[Business Logic]
        R5[Database Query]
        R6[Response]
    end
    
    subgraph "Processing Flow"
        P1[Job Queue]
        P2[Worker Fetch]
        P3[Document Download]
        P4[Core Pipeline]
        P5[LLM API Calls]
        P6[Result Storage]
    end
    
    R1 --> R2
    R2 --> R3
    R3 --> R4
    R4 --> R5
    R5 --> R6
    
    R4 --> P1
    P1 --> P2
    P2 --> P3
    P3 --> P4
    P4 --> P5
    P5 --> P6
```

---

## ⚙️ Configuration Dependencies

### Environment Configuration

```mermaid
graph TB
    subgraph "Environment Variables"
        ENV1[POSTGRES_DB]
        ENV2[POSTGRES_USER]
        ENV3[POSTGRES_PASSWORD]
        ENV4[REDIS_URL]
        ENV5[MINIO_ENDPOINT]
        ENV6[JWT_SECRET_KEY]
        ENV7[OPENROUTER_API_KEY]
        ENV8[ANTHROPIC_API_KEY]
    end
    
    subgraph "Configuration Loading"
        CFG1[Load .env]
        CFG2[Validate Required]
        CFG3[Set Defaults]
    end
    
    subgraph "Service Configuration"
        SVC1[API Service]
        SVC2[Worker Service]
        SVC3[Database]
        SVC4[Storage]
    end
    
    ENV1 --> CFG1
    ENV2 --> CFG1
    ENV3 --> CFG1
    ENV4 --> CFG1
    ENV5 --> CFG1
    ENV6 --> CFG1
    ENV7 --> CFG1
    ENV8 --> CFG1
    
    CFG1 --> CFG2
    CFG2 --> CFG3
    
    CFG3 --> SVC1
    CFG3 --> SVC2
    CFG3 --> SVC3
    CFG3 --> SVC4
```

### Model Configuration

```mermaid
graph TB
    subgraph "Model Catalog"
        MC1[Model Metadata]
        MC2[Pricing Info]
        MC3[Capabilities]
        MC4[Status]
    end
    
    subgraph "Provider Config"
        PC1[API Endpoints]
        PC2[Rate Limits]
        PC3[Auth Methods]
        PC4[Retry Logic]
    end
    
    subgraph "Runtime Selection"
        RS1[User Selection]
        RS2[Cost Optimization]
        RS3[Quality Requirements]
        RS4[Fallback Chain]
    end
    
    MC1 --> PC1
    MC2 --> PC2
    MC3 --> PC3
    MC4 --> PC4
    
    RS1 --> RS2
    RS2 --> RS3
    RS3 --> RS4
```

---

## 🔄 Development Workflow

### Local Development Setup

```mermaid
graph TB
    subgraph "Setup"
        S1[Clone Repository]
        S2[Copy .env.example]
        S3[Add API Keys]
        S4[Install Dependencies]
    end
    
    subgraph "Development"
        D1[Start Services]
        D2[Run Tests]
        D3[Code Changes]
        D4[Debug Issues]
    end
    
    subgraph "Deployment"
        DEP1[Build Images]
        DEP2[Push to Registry]
        DEP3[Deploy to Staging]
        DEP4[Deploy to Production]
    end
    
    S1 --> S2
    S2 --> S3
    S3 --> S4
    S4 --> D1
    D1 --> D2
    D2 --> D3
    D3 --> D4
    D2 --> DEP1
    DEP1 --> DEP2
    DEP2 --> DEP3
    DEP3 --> DEP4
```

### Testing Workflow

```mermaid
graph TB
    subgraph "Unit Tests"
        U1[Core Pipeline]
        U2[Provider Adapters]
        U3[API Endpoints]
        U4[Database Models]
    end
    
    subgraph "Integration Tests"
        I1[API + Database]
        I2[Worker + Queue]
        I3[Storage Operations]
        I4[End-to-End Flow]
    end
    
    subgraph "System Tests"
        S1[Docker Compose]
        S2[Health Checks]
        S3[Performance Tests]
        S4[Load Testing]
    end
    
    U1 --> I1
    U2 --> I1
    U3 --> I2
    U4 --> I2
    I1 --> I3
    I2 --> I3
    I3 --> I4
    I4 --> S1
    S1 --> S2
    S2 --> S3
    S3 --> S4
```

### Debug Workflow

```mermaid
graph TB
    subgraph "Issue Detection"
        D1[Error Logs]
        D2[Health Check Failures]
        D3[Performance Issues]
        D4[User Reports]
    end
    
    subgraph "Investigation"
        I1[Log Analysis]
        I2[Database Queries]
        I3[Service Status]
        I4[Network Debug]
    end
    
    subgraph "Resolution"
        R1[Code Fix]
        R2[Configuration Update]
        R3[Infrastructure Change]
        R4[Documentation Update]
    end
    
    D1 --> I1
    D2 --> I2
    D3 --> I3
    D4 --> I4
    I1 --> R1
    I2 --> R2
    I3 --> R3
    I4 --> R4
```

---

## 📊 System Metrics & Monitoring

### Key Performance Indicators

| Metric | Target | Current Status |
|--------|--------|----------------|
| API Response Time | < 2 seconds | Monitoring |
| Document Processing | 5-20 seconds | Based on provider |
| Queue Processing | 99% success | In testing |
| Storage Utilization | < 80% | Monitoring |
| Database Performance | < 100ms queries | Monitoring |

### Health Check Endpoints

- `GET /health` - Overall system health
- `GET /health/database` - Database connectivity
- `GET /health/storage` - MinIO storage health
- `GET /health/queue` - Redis queue health

---

## 🔧 Troubleshooting Guide

### Common Issues

#### Docker Services Not Starting
```bash
# Check logs
./start.sh logs

# Restart services
./start.sh stop
./start.sh start

# Clean restart
./start.sh clean
./start.sh start
```

#### Database Connection Issues
```bash
# Check PostgreSQL health
docker logs legal_events_db

# Verify environment variables
cat .env | grep DATABASE

# Test connection
docker exec -it legal_events_db psql -U legal_user -d legal_events
```

#### Worker Not Processing Jobs
```bash
# Check Redis connection
docker logs legal_events_redis

# Check worker logs
docker logs legal_events_worker

# Verify job queue
docker exec -it legal_events_redis redis-cli
> LLEN rq:default
```

#### API Key Issues
```bash
# Verify API keys are set
cat .env | grep API_KEY

# Test provider connectivity
curl -H "Authorization: Bearer $OPENROUTER_API_KEY" \
     https://openrouter.ai/api/v1/models
```

---

## 📈 Scaling Considerations

### Horizontal Scaling

- **API Services**: Multiple instances behind load balancer
- **Worker Services**: Auto-scaling based on queue depth
- **Database**: Read replicas for query performance
- **Storage**: MinIO cluster for high availability

### Performance Optimization

- **Caching**: Redis for frequently accessed data
- **Connection Pooling**: Database connection optimization
- **Batch Processing**: Process multiple documents together
- **Async Processing**: Non-blocking operations

---

## 🔐 Security Considerations

### Authentication & Authorization

- JWT-based authentication
- Role-based access control (RBAC)
- API key management
- CORS configuration

### Data Security

- Encryption at rest (MinIO)
- Encryption in transit (TLS)
- Data retention policies
- Audit logging

---

## 📞 Support & Contact

For technical support or questions about this code map:

- **Documentation**: See `/docs` directory
- **Bug Reports**: Use `/bug_reports` system
- **Recommendations**: See `/recommendations` directory
- **Research**: Check `/research` directory

---

**Document Version**: 1.0  
**Last Updated**: November 9, 2025  
**Next Review**: Phase 2 Completion (TBD)

---

*This code map provides a comprehensive overview of the Legal Events Production System architecture, dependencies, and workflows. For the most current information, always refer to the source code and inline documentation.*
