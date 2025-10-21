"""
FastAPI Application for Legal Events Extraction v2
Main application entry point with all API routes
"""

from fastapi import FastAPI, Depends, HTTPException, File, UploadFile, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import logging
import os
from datetime import datetime
import json
from contextlib import asynccontextmanager

# Local imports (we'll create these next)
from .database import get_db, init_db
from .models import *
from .schemas import *
from .storage import MinioStorage
from .queue import enqueue_job
from .auth import get_current_user, create_access_token

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events
    """
    # Startup
    logger.info("🚀 Starting Legal Events API v2...")
    
    # Initialize database
    init_db()
    logger.info("✅ Database initialized")
    
    # Initialize storage
    storage = MinioStorage()
    storage.ensure_bucket()
    logger.info("✅ MinIO storage initialized")
    
    yield
    
    # Shutdown
    logger.info("👋 Shutting down Legal Events API...")


# Create FastAPI app
app = FastAPI(
    title="Legal Events Extraction API",
    description="Production-ready API for legal document processing and event extraction",
    version="2.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5001"],  # Frontend URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Health & Status Endpoints
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "name": "Legal Events Extraction API",
        "version": "2.0.0",
        "status": "operational",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """
    Health check endpoint
    Returns system status and component health
    """
    try:
        # Check database
        db.execute("SELECT 1")
        db_status = "healthy"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_status = "unhealthy"
    
    # Check storage
    storage = MinioStorage()
    storage_status = "healthy" if storage.health_check() else "unhealthy"
    
    # Check Redis (queue)
    try:
        import redis
        r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
        r.ping()
        queue_status = "healthy"
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        queue_status = "unhealthy"
    
    overall_status = "healthy" if all(
        s == "healthy" for s in [db_status, storage_status, queue_status]
    ) else "degraded"
    
    return {
        "status": overall_status,
        "timestamp": datetime.utcnow().isoformat(),
        "components": {
            "database": db_status,
            "storage": storage_status,
            "queue": queue_status
        }
    }


# ============================================================================
# Client Management Endpoints
# ============================================================================

@app.post("/v1/clients", response_model=ClientResponse)
async def create_client(
    client: ClientCreate,
    db: Session = Depends(get_db),
    # current_user: User = Depends(get_current_user)  # TODO: Enable auth
):
    """Create a new client organization"""
    db_client = Client(
        name=client.name,
        reference_code=client.reference_code,
        notes=client.notes
    )
    db.add(db_client)
    db.commit()
    db.refresh(db_client)
    
    logger.info(f"Created client: {db_client.name} (ID: {db_client.id})")
    return db_client


@app.get("/v1/clients", response_model=List[ClientResponse])
async def list_clients(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List all clients"""
    clients = db.query(Client).offset(skip).limit(limit).all()
    return clients


@app.get("/v1/clients/{client_id}", response_model=ClientResponse)
async def get_client(
    client_id: int,
    db: Session = Depends(get_db)
):
    """Get client details"""
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


# ============================================================================
# Case Management Endpoints
# ============================================================================

@app.post("/v1/cases", response_model=CaseResponse)
async def create_case(
    case: CaseCreate,
    db: Session = Depends(get_db)
):
    """Create a new case"""
    db_case = Case(
        client_id=case.client_id,
        name=case.name,
        description=case.description,
        retention_days=case.retention_days or 90
    )
    db.add(db_case)
    db.commit()
    db.refresh(db_case)
    
    logger.info(f"Created case: {db_case.name} (ID: {db_case.id})")
    return db_case


@app.get("/v1/clients/{client_id}/cases", response_model=List[CaseResponse])
async def list_client_cases(
    client_id: int,
    db: Session = Depends(get_db)
):
    """List all cases for a client"""
    cases = db.query(Case).filter(Case.client_id == client_id).all()
    return cases


@app.post("/v1/cases/{case_id}/assign")
async def assign_user_to_case(
    case_id: int,
    assignment: CaseAssignmentCreate,
    db: Session = Depends(get_db)
):
    """Assign a user to a case"""
    # Check if assignment already exists
    existing = db.query(CaseAssignment).filter(
        CaseAssignment.case_id == case_id,
        CaseAssignment.user_id == assignment.user_id
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="User already assigned to case")
    
    db_assignment = CaseAssignment(
        case_id=case_id,
        user_id=assignment.user_id,
        role_in_case=assignment.role_in_case
    )
    db.add(db_assignment)
    db.commit()
    
    return {"message": "User assigned successfully"}


# ============================================================================
# Run Management Endpoints
# ============================================================================

@app.post("/v1/runs", response_model=RunCreateResponse)
async def create_run(
    run: RunCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new run and get presigned upload URLs
    """
    # Create run in database
    db_run = Run(
        case_id=run.case_id,
        provider=run.provider or "openrouter",
        model=run.model or "meta-llama/llama-3.3-70b-instruct",
        status=RunStatus.QUEUED
    )
    db.add(db_run)
    db.commit()
    db.refresh(db_run)
    
    # Generate presigned upload URLs
    storage = MinioStorage()
    upload_urls = []
    
    # For now, return a batch of URLs (client will specify how many needed)
    # In production, this would be based on the actual files to upload
    for i in range(run.file_count or 1):
        url = storage.generate_upload_url(
            case_id=run.case_id,
            run_id=db_run.id,
            filename=f"document_{i}.pdf"  # Placeholder
        )
        upload_urls.append(url)
    
    logger.info(f"Created run {db_run.id} with {len(upload_urls)} upload URLs")
    
    return {
        "run_id": db_run.id,
        "case_id": run.case_id,
        "status": db_run.status.value,
        "upload_urls": upload_urls
    }


@app.put("/v1/runs/{run_id}/start")
async def start_run(
    run_id: int,
    manifest: RunManifest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Start processing a run with uploaded documents
    """
    # Get run
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    if run.status != RunStatus.QUEUED:
        raise HTTPException(status_code=400, detail=f"Run is {run.status.value}, not queued")
    
    # Create document records
    for file_info in manifest.files:
        doc = Document(
            run_id=run_id,
            case_id=run.case_id,
            filename=file_info.filename,
            size_bytes=file_info.size_bytes,
            sha256=file_info.sha256,
            storage_key=file_info.storage_key,
            mime_type=file_info.mime_type
        )
        db.add(doc)
    
    # Update run status
    run.status = RunStatus.PROCESSING
    run.started_at = datetime.utcnow()
    
    db.commit()
    
    # Enqueue processing job
    job_id = enqueue_job(
        "process_run",
        run_id=run_id,
        provider=run.provider,
        model=run.model
    )
    
    logger.info(f"Started run {run_id} with job {job_id}")
    
    return {
        "status": "accepted",
        "run_id": run_id,
        "job_id": job_id,
        "message": "Run processing started"
    }


@app.get("/v1/runs/{run_id}", response_model=RunResponse)
async def get_run(
    run_id: int,
    db: Session = Depends(get_db)
):
    """Get run details with progress information"""
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    # Get document counts
    total_docs = db.query(Document).filter(Document.run_id == run_id).count()
    processed_docs = db.query(Document).filter(
        Document.run_id == run_id,
        Document.status == DocumentStatus.SUCCESS
    ).count()
    failed_docs = db.query(Document).filter(
        Document.run_id == run_id,
        Document.status == DocumentStatus.FAILED
    ).count()
    
    return {
        "run_id": run.id,
        "case_id": run.case_id,
        "status": run.status.value,
        "provider": run.provider,
        "model": run.model,
        "created_at": run.created_at,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "counts": {
            "total": total_docs,
            "processed": processed_docs,
            "failed": failed_docs,
            "pending": total_docs - processed_docs - failed_docs
        },
        "timings": {
            "docling_seconds": run.docling_seconds,
            "extractor_seconds": run.extractor_seconds,
            "total_seconds": run.total_seconds
        },
        "cost_usd": run.cost_usd,
        "error": run.error
    }


@app.get("/v1/runs/{run_id}/events")
async def get_run_events(
    run_id: int,
    cursor: Optional[int] = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get events extracted in a run (paginated)"""
    query = db.query(Event).filter(Event.run_id == run_id)
    
    if cursor:
        query = query.filter(Event.id > cursor)
    
    events = query.order_by(Event.id).limit(limit).all()
    
    # Convert to response format
    event_list = []
    for event in events:
        event_list.append({
            "id": event.id,
            "number": event.number,
            "date": event.date,
            "event_particulars": event.event_particulars,
            "citation": event.citation,
            "document_reference": event.document_reference,
            "document_id": event.document_id
        })
    
    next_cursor = events[-1].id if events else None
    
    return {
        "events": event_list,
        "next_cursor": next_cursor,
        "has_more": len(events) == limit
    }


@app.get("/v1/runs/{run_id}/artifacts")
async def get_run_artifacts(
    run_id: int,
    db: Session = Depends(get_db)
):
    """Get available export artifacts for a run"""
    artifacts = db.query(Artifact).filter(Artifact.run_id == run_id).all()
    
    storage = MinioStorage()
    artifact_list = []
    
    for artifact in artifacts:
        download_url = storage.generate_download_url(artifact.storage_key)
        artifact_list.append({
            "id": artifact.id,
            "kind": artifact.kind,
            "size_bytes": artifact.size_bytes,
            "created_at": artifact.created_at,
            "download_url": download_url
        })
    
    return {"artifacts": artifact_list}


@app.get("/v1/runs/{run_id}/export")
async def export_run(
    run_id: int,
    fmt: str = "csv",
    db: Session = Depends(get_db)
):
    """Generate and return export file"""
    if fmt not in ["csv", "xlsx", "json"]:
        raise HTTPException(status_code=400, detail="Format must be csv, xlsx, or json")
    
    # Check if artifact already exists
    artifact = db.query(Artifact).filter(
        Artifact.run_id == run_id,
        Artifact.kind == fmt
    ).first()
    
    if artifact:
        # Return existing artifact
        storage = MinioStorage()
        download_url = storage.generate_download_url(artifact.storage_key)
        return {"download_url": download_url}
    
    # Generate new artifact (this would be done in background normally)
    # For now, we'll do it synchronously as a placeholder
    events = db.query(Event).filter(Event.run_id == run_id).all()
    
    if not events:
        raise HTTPException(status_code=404, detail="No events found for this run")
    
    # Create export based on format
    storage = MinioStorage()
    
    if fmt == "json":
        # Generate JSON export
        data = [event.to_dict() for event in events]
        content = json.dumps(data, indent=2)
        content_bytes = content.encode('utf-8')
    
    elif fmt == "csv":
        # Generate CSV export
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=FIVE_COLUMN_HEADERS)
        writer.writeheader()
        
        for event in events:
            writer.writerow(event.to_dict())
        
        content = output.getvalue()
        content_bytes = content.encode('utf-8')
    
    else:  # xlsx
        # Generate Excel export
        import pandas as pd
        import io
        
        data = [event.to_dict() for event in events]
        df = pd.DataFrame(data)
        
        output = io.BytesIO()
        df.to_excel(output, index=False, sheet_name="Legal Events")
        content_bytes = output.getvalue()
    
    # Upload to storage
    case = db.query(Case).filter(Case.id == events[0].run.case_id).first()
    storage_key = f"clients/{case.client_id}/cases/{case.id}/runs/{run_id}/artifacts/{run_id}.{fmt}"
    
    storage.upload_bytes(storage_key, content_bytes)
    
    # Create artifact record
    artifact = Artifact(
        run_id=run_id,
        kind=fmt,
        storage_key=storage_key,
        size_bytes=len(content_bytes)
    )
    db.add(artifact)
    db.commit()
    
    # Return download URL
    download_url = storage.generate_download_url(storage_key)
    return {"download_url": download_url}


# ============================================================================
# SSE Endpoint for Progress Streaming
# ============================================================================

@app.get("/v1/runs/{run_id}/stream")
async def stream_run_progress(
    run_id: int,
    db: Session = Depends(get_db)
):
    """
    Server-Sent Events endpoint for real-time progress updates
    """
    from sse_starlette.sse import EventSourceResponse
    import asyncio
    import json
    
    async def event_generator():
        """Generate SSE events for run progress"""
        while True:
            # Get current run status
            run = db.query(Run).filter(Run.id == run_id).first()
            if not run:
                yield {"event": "error", "data": json.dumps({"error": "Run not found"})}
                break
            
            # Get document progress
            docs = db.query(Document).filter(Document.run_id == run_id).all()
            
            progress_data = {
                "run_id": run_id,
                "status": run.status.value,
                "documents": []
            }
            
            for doc in docs:
                progress_data["documents"].append({
                    "id": doc.id,
                    "filename": doc.filename,
                    "status": doc.status.value
                })
            
            yield {
                "event": "progress",
                "data": json.dumps(progress_data)
            }
            
            # If run is complete, send final event and close
            if run.status in [RunStatus.SUCCESS, RunStatus.FAILED, RunStatus.PARTIAL_SUCCESS]:
                yield {
                    "event": "complete",
                    "data": json.dumps({
                        "run_id": run_id,
                        "status": run.status.value,
                        "finished_at": run.finished_at.isoformat() if run.finished_at else None
                    })
                }
                break
            
            # Wait before next update
            await asyncio.sleep(2)
    
    return EventSourceResponse(event_generator())


# ============================================================================
# Model Catalog Endpoints
# ============================================================================

@app.get("/v1/models")
async def list_models(
    provider: Optional[str] = None,
    recommended: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """List available models from catalog"""
    query = db.query(ModelCatalog)
    
    if provider:
        query = query.filter(ModelCatalog.provider == provider)
    
    if recommended is not None:
        query = query.filter(ModelCatalog.is_recommended == recommended)
    
    models = query.all()
    
    return {
        "models": [
            {
                "provider": m.provider,
                "model_id": m.model_id,
                "display_name": m.display_name,
                "cost_input_per_million": m.cost_input_per_million,
                "cost_output_per_million": m.cost_output_per_million,
                "context_window": m.context_window,
                "supports_json_mode": m.supports_json_mode,
                "badges": m.badges,
                "status": m.status,
                "is_recommended": m.is_recommended
            }
            for m in models
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
