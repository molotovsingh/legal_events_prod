"""
FastAPI Application for Legal Events Extraction v2
Main application entry point with all API routes
"""

from fastapi import FastAPI, Depends, HTTPException, File, UploadFile, BackgroundTasks, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional, Dict, Any
import logging
import os
from datetime import datetime
import json
import uuid
import hashlib
from contextlib import asynccontextmanager

# Local imports (we'll create these next)
from infra.database import get_db, init_db
from infra.models import *
from .schemas import *
from infra.storage import MinioStorage
from infra.storage_keys import generate_document_key, generate_artifact_key
from infra.queue import enqueue_job, enqueue_process_run
from legal_events_core import count_text, TokenizerUnavailable, FIVE_COLUMN_HEADERS
from legal_events_core.prompts.event_extractor_catalog import get_event_extractor_catalog
# ✅ Authentication enabled - requires valid JWT Bearer token
from .auth import get_current_user, require_auth

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# Authorization Helpers
# ============================================================================

async def authorize_run_access(run_id: int, db: Session, user: User) -> Run:
    """
    Verify user can access a run, return run or raise 403/404.

    Authorization rules:
    - Admin users can access any run
    - Non-admin users must be assigned to the run's case via CaseAssignment

    Args:
        run_id: The run ID to authorize access for
        db: Database session
        user: Current authenticated user

    Returns:
        Run object if authorized

    Raises:
        HTTPException 404: If run not found
        HTTPException 403: If user not authorized to access the run
    """
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    if user.role != UserRole.ADMIN:
        assignment = db.query(CaseAssignment).filter(
            CaseAssignment.case_id == run.case_id,
            CaseAssignment.user_id == user.id
        ).first()
        if not assignment:
            raise HTTPException(status_code=403, detail="Access denied to this run")

    return run


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events
    """
    # Startup
    logger.info("🚀 Starting Legal Events API v2...")

    # Start the event processor to handle worker status updates (service boundary enforcement)
    from api.event_processor import start_event_processor, stop_event_processor
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    start_event_processor(redis_url)
    logger.info("✅ Event processor started - service boundaries enforced")

    # Validate required environment variables
    logger.info("🔐 Validating security configuration...")
    required_vars = ["JWT_SECRET_KEY", "DATABASE_URL"]
    missing_vars = []

    for var_name in required_vars:
        if not os.getenv(var_name):
            missing_vars.append(var_name)

    if missing_vars:
        error_msg = f"CRITICAL: Missing required environment variables: {', '.join(missing_vars)}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)

    logger.info("✅ Environment variables validated")

    # Validate provider configuration (v0.11.0+)
    logger.info("🏭 Validating provider configuration...")
    try:
        from legal_events_core.providers import validate_providers_on_startup
        is_valid, errors = validate_providers_on_startup()
        if not is_valid:
            error_msg = f"CRITICAL: Provider validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
            logger.error(error_msg)
            logger.warning("⚠️ API will start but some providers may not work. Check environment variables.")
            # Don't raise - allow API to start but log warnings
        else:
            logger.info("✅ All enabled providers validated successfully")
    except Exception as e:
        logger.error(f"⚠️ Provider validation error: {e}")
        logger.warning("⚠️ API will start but provider functionality may be limited")

    # Initialize database
    init_db()
    logger.info("✅ Database initialized")

    # Sync model catalog from Python registry to database
    logger.info("📋 Syncing model catalog to database...")
    try:
        from sqlalchemy.orm import sessionmaker
        from infra.database import engine
        from infra.models import ModelCatalog as ModelCatalogTable
        from legal_events_core.prompts.model_catalog import _MODEL_REGISTRY

        Session = sessionmaker(bind=engine)
        session = Session()

        # Fetch all existing models in one query (optimization: 1 query instead of N)
        existing_models = session.query(
            ModelCatalogTable.provider,
            ModelCatalogTable.model_id
        ).all()
        existing_keys = {(m.provider, m.model_id) for m in existing_models}

        logger.info(f"Syncing {len(_MODEL_REGISTRY)} models from Python registry...")

        added = 0
        updated = 0
        for model_entry in _MODEL_REGISTRY:
            key = (model_entry.provider, model_entry.model_id)

            row_data = {
                "provider": model_entry.provider,
                "model_id": model_entry.model_id,
                "display_name": model_entry.display_name,
                "cost_input_per_million": model_entry.cost_input_per_1m,
                "cost_output_per_million": model_entry.cost_output_per_1m,
                "context_window": model_entry.context_window,
                "supports_json_mode": model_entry.supports_json_mode,
                "supports_vision": model_entry.supports_vision,
                "badges": model_entry.badges,
                "status": model_entry.status.value,
                "is_recommended": model_entry.recommended,
            }

            if key in existing_keys:
                # Update existing model
                existing = session.query(ModelCatalogTable).filter_by(
                    provider=model_entry.provider,
                    model_id=model_entry.model_id
                ).first()
                for k, v in row_data.items():
                    setattr(existing, k, v)
                updated += 1
            else:
                # Insert new model
                new_model = ModelCatalogTable(**row_data)
                session.add(new_model)
                added += 1

        session.commit()
        logger.info(f"✅ Model catalog synced: {added} added, {updated} updated, {len(_MODEL_REGISTRY)} total")
        session.close()

    except Exception as e:
        logger.warning(f"⚠️ Model catalog sync failed (non-fatal): {e}")
        logger.info("Run 'python scripts/sync_model_catalog.py' to manually sync models")

    # Initialize storage
    storage = MinioStorage()
    storage.ensure_bucket()
    logger.info("✅ MinIO storage initialized")

    # Note: Provider validation now uses unified registry (core/providers.py)
    # Legacy catalog (core/event_extractor_catalog.py) retained for backward compatibility in factory only

    logger.info("🔒 Security: Authentication ENABLED (JWT required for write operations)")

    yield

    # Shutdown
    logger.info("👋 Shutting down Legal Events API...")
    stop_event_processor()
    logger.info("✅ Event processor stopped")


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
    # Frontend URLs (include localhost and 127.0.0.1 variants to avoid incognito CORS mismatches)
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:5001",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "http://127.0.0.1:5001",
        "http://127.0.0.1:8000",
        "http://0.0.0.0:8000",
        "null",  # Allow file:// origin for local testing
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for frontend (serves index.html, simple.html, app.js, simple.js)
# Note: This must be done AFTER defining API routes to avoid conflicts
# The actual mount happens at the end of this file after all routes are defined


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
        db.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_status = "unhealthy"
    
    # Check storage
    storage = MinioStorage()
    storage_status = "healthy" if storage.health_check() else "unhealthy"
    
    # Check Redis (queue)
    r = None
    try:
        import redis
        r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
        r.ping()
        queue_status = "healthy"
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        queue_status = "unhealthy"
    finally:
        if r is not None:
            r.close()
    
    # Check workers (NEW)
    try:
        from infra.queue import get_worker_stats
        worker_stats = get_worker_stats()
        workers_count = worker_stats.get("total_workers", 0)
        if workers_count == 0:
            worker_status = "degraded"
            logger.warning("⚠️ No workers registered - job processing unavailable")
        else:
            worker_status = "healthy"
    except Exception as e:
        logger.error(f"Worker health check failed: {e}")
        worker_status = "unhealthy"
    
    overall_status = "healthy" if all(
        s == "healthy" for s in [db_status, storage_status, queue_status, worker_status]
    ) else "degraded"
    
    return {
        "status": overall_status,
        "timestamp": datetime.utcnow().isoformat(),
        "components": {
            "database": db_status,
            "storage": storage_status,
            "queue": queue_status,
            "workers": worker_status
        }
    }


@app.get("/v1/providers", response_model=ProvidersResponse)
async def list_providers(
    enabled: bool = True,
    recommended_only: Optional[bool] = None
):
    """
    List available event extraction providers (Unified API)

    Provides dynamic provider discovery with complete metadata including
    runtime status, capabilities, and documentation links.

    Query params:
    - enabled: Filter to enabled providers only (default: true)
    - recommended_only: Only return recommended providers if true

    Returns:
    {
        "providers": [
            {
                "provider_id": "langextract",
                "display_name": "Gemini",
                "name": "Gemini",
                "enabled": true,
                "supports_runtime_model": true,
                "recommended": true,
                "notes": "Google Gemini 2.0 Flash...",
                "documentation_url": "https://ai.google.dev/gemini-api/docs",
                "is_working": true,
                "models": []
            },
            ...
        ],
        "count": 5,
        "timestamp": "2025-11-10T12:00:00.000000"
    }
    """
    try:
        # Use new unified provider registry (v0.11.0+)
        from legal_events_core import PROVIDERS, list_providers as get_providers_list

        # Get providers based on enabled filter
        provider_list = get_providers_list(enabled_only=enabled)

        # Apply recommended filter if specified
        if recommended_only:
            # For now, mark openrouter as recommended (standardized default)
            provider_list = [p for p in provider_list if p.id == "openrouter"]

        providers = [
            {
                "provider_id": p.id,
                "display_name": p.name,
                "name": p.name,  # Backward compatibility alias
                "enabled": p.enabled,
                "supports_runtime_model": p.supports_model_override,
                "recommended": p.id == "openrouter",  # openrouter is standardized default
                "notes": p.notes,
                "documentation_url": p.docs_url,
                "is_working": p.enabled,  # Enabled = working in new architecture
                "models": []  # Future: populate from model catalog
            }
            for p in provider_list
        ]

        return {
            "providers": providers,
            "count": len(providers),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        correlation_id = str(uuid.uuid4())[:8]
        logger.error(f"Error listing providers (correlation_id: {correlation_id}): {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error. Please contact support with reference: {correlation_id}"
        )


@app.get("/v1/modes", response_model=ProcessingModesResponse)
async def list_processing_modes():
    """
    List available processing modes for end users.

    Returns simplified mode options that abstract away provider/model details.
    Each mode maps to a specific provider/model combination configured on the backend.

    This is the user-facing API - it hides technical details like provider names
    and model IDs, presenting simple choices like "Best Quality", "Balanced", "Fast".

    Returns:
        modes: List of available modes with name, description, icon
        default: ID of the recommended default mode
        timestamp: ISO 8601 timestamp
    """
    from core.modes import list_modes, DEFAULT_MODE_ID

    modes = list_modes()

    return {
        "modes": [
            {
                "id": mode.id,
                "name": mode.name,
                "description": mode.description,
                "icon": mode.icon,
                "estimated_speed": mode.estimated_speed
            }
            for mode in modes
        ],
        "default": DEFAULT_MODE_ID,
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/v1/modes/{mode_id}", response_model=ProcessingModeDetail)
async def get_processing_mode(mode_id: str):
    """
    Get full mode details including provider/model (for admin/developer use).

    This endpoint returns the complete configuration for a mode including
    the underlying provider, model, and document extractor settings.

    Args:
        mode_id: Mode identifier ("best", "balanced", "fast")

    Returns:
        Full mode configuration including provider/model details
    """
    from core.modes import get_mode

    mode = get_mode(mode_id)
    if not mode:
        raise HTTPException(status_code=404, detail=f"Mode '{mode_id}' not found")

    return {
        "id": mode.id,
        "name": mode.name,
        "description": mode.description,
        "provider": mode.provider,
        "model": mode.model,
        "doc_extractor": mode.doc_extractor,
        "icon": mode.icon,
        "estimated_speed": mode.estimated_speed
    }


@app.get("/v1/classifiers", response_model=ClassifierListResponse)
async def list_classifiers():
    """
    List available document classification models (OpenRouter-based).
    Returns only enabled models from the classification catalog filtered to provider 'openrouter'.
    """
    try:
        from legal_events_core.prompts.classification_catalog import list_classification_models

        models = list_classification_models(enabled=True, provider="openrouter")
        payload = [
            {
                "model_id": m.model_id,
                "display_name": m.display_name,
                "provider": m.provider,
                "recommended": m.recommended,
            }
            for m in models
        ]
        return {
            "models": payload,
            "count": len(payload),
            "timestamp": datetime.utcnow()
        }
    except Exception as e:
        correlation_id = str(uuid.uuid4())[:8]
        logger.error(f"Error listing classifiers (correlation_id: {correlation_id}): {e}")
        raise HTTPException(status_code=500, detail="Failed to list classifiers")


@app.post("/v1/estimate-tokens", response_model=TokenEstimateResponse)
async def estimate_tokens(payload: TokenEstimateRequest):
    """
    Accurate pre-run input token estimation using provider/model tokenizers.

    - Runs Docling-only extraction on uploaded files (MinIO temp storage)
    - Counts exact input tokens for the selected provider/model
    - Optionally counts classification input tokens on an excerpt
    - Converts tokens→$ using static pricing from model_catalog
    """
    from legal_events_core import create_default_extractors
    from legal_events_core.prompts.model_catalog import get_model_catalog
    import tempfile, os
    from pathlib import Path as _P

    provider = payload.provider
    model = payload.model
    doc_extractor_id = payload.doc_extractor or "docling"
    enable_cls = bool(payload.enable_classification)
    cls_model = payload.classification_model or "meta-llama/llama-3.3-70b-instruct"

    if not payload.files:
        raise HTTPException(status_code=400, detail="No files provided")

    # Initialize Docling extractor only (event extractor unused here)
    doc_extractor, _ = create_default_extractors(provider, runtime_model=model, doc_extractor_override=doc_extractor_id)

    storage = MinioStorage()
    per_doc: list[PerDocTokenEstimate] = []
    total_event_tokens = 0
    total_cls_tokens = 0

    for f in payload.files:
        tmp_path = None
        try:
            data = storage.download_bytes(f.storage_key)
            if data is None:
                raise RuntimeError(f"Failed to download {f.storage_key}")
            suffix = os.path.splitext(f.filename)[1] or ""
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(data)
                tmp_path = tmp.name

            extracted = doc_extractor.extract(_P(tmp_path))
            text = extracted.plain_text or extracted.markdown or ""

            try:
                ev_tokens = count_text(text, provider, model)
            except TokenizerUnavailable as te:
                raise HTTPException(status_code=400, detail=str(te))

            cls_tokens = None
            if enable_cls:
                excerpt = (text or "")[:2000]
                try:
                    cls_tokens = count_text(excerpt, "openrouter", cls_model)
                except TokenizerUnavailable as te:
                    raise HTTPException(status_code=400, detail=f"Classification tokenizer unavailable: {te}")

            per_doc.append(PerDocTokenEstimate(
                filename=f.filename,
                event_input_tokens=ev_tokens,
                classification_input_tokens=cls_tokens
            ))
            total_event_tokens += ev_tokens
            if cls_tokens:
                total_cls_tokens += cls_tokens
        finally:
            try:
                if tmp_path and os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            except Exception:
                pass

    # Compute input-only cost from model catalog pricing
    catalog = get_model_catalog()
    pricing_event = catalog.get_pricing(model)
    ev_in = float(pricing_event["cost_input_per_1m"]) if pricing_event else 0.0
    cost_input_usd = (total_event_tokens / 1_000_000.0) * ev_in
    pricing_cls = None
    if enable_cls and total_cls_tokens > 0:
        pricing_cls = catalog.get_pricing(cls_model)
        cls_in = float(pricing_cls["cost_input_per_1m"]) if pricing_cls else 0.0
        cost_input_usd += (total_cls_tokens / 1_000_000.0) * cls_in

    totals = TokenTotals(
        event_input_tokens=total_event_tokens,
        classification_input_tokens=total_cls_tokens,
        total_input_tokens=total_event_tokens + total_cls_tokens,
        cost_input_usd=cost_input_usd,
        approx=False
    )
    # For transparency, return event pricing; classifier pricing if used
    combined_pricing = {}
    if pricing_event:
        combined_pricing["event"] = pricing_event
    if pricing_cls:
        combined_pricing["classification"] = pricing_cls
    pricing_out = combined_pricing if combined_pricing else None

    return TokenEstimateResponse(
        per_document=per_doc,
        totals=totals,
        pricing=pricing_out
    )


@app.post("/v1/uploads/cleanup", response_model=TempCleanupResponse)
async def cleanup_temp_uploads(req: TempCleanupRequest, current_user: User = Depends(require_auth)):
    """
    Delete temporary uploaded objects created for estimation.

    Security: Only deletes keys under the 'temp/' prefix to prevent arbitrary object deletion.
    """
    storage = MinioStorage()
    deleted = 0
    skipped = 0
    for key in req.keys or []:
        try:
            # Only allow deletion of temp objects
            if not key.startswith("temp/"):
                skipped += 1
                continue
            ok = storage.delete_object(key)
            if ok:
                deleted += 1
            else:
                skipped += 1
        except Exception:
            skipped += 1
    return TempCleanupResponse(deleted=deleted, skipped=skipped)


# ============================================================================
# Authentication Endpoints
# ============================================================================

@app.post("/v1/auth/login", response_model=LoginResponse)
async def login_endpoint(
    credentials: LoginRequest,
    db: Session = Depends(get_db)
):
    """
    Authenticate user and return JWT token

    Use this endpoint to obtain a JWT token for authenticated API access.

    **Development Credentials:**
    - email: dev@localhost
    - password: devpass123
    """
    from .auth import login
    return await login(credentials.email, credentials.password, db)


@app.post("/v1/auth/dev/reset-password")
async def dev_reset_password(
    email: str,
    new_password: str,
    db: Session = Depends(get_db)
):
    """
    Development-only password reset endpoint (disabled in production/staging)
    
    **Security:** This endpoint is only available in development mode.
    
    Usage:
    ```bash
    curl -X POST "http://localhost:8000/v1/auth/dev/reset-password?email=dev@localhost&new_password=newpass123"
    ```
    """
    # Security check - only allow in development
    env_mode = os.getenv("ENVIRONMENT", "development").lower()
    if env_mode in ["production", "staging"]:
        raise HTTPException(
            status_code=403,
            detail="Password reset endpoint is disabled in production/staging environments"
        )
    
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(
            status_code=404,
            detail=f"User not found: {email}"
        )
    
    from api.auth import get_password_hash
    user.password_hash = get_password_hash(new_password)
    db.commit()
    
    logger.info(f"Password reset for {email} via dev endpoint")
    
    return {
        "message": f"Password reset successful for {email}",
        "new_password": new_password
    }


# ============================================================================
# Client Management Endpoints
# ============================================================================

@app.post("/v1/clients", response_model=ClientResponse)
async def create_client(
    client: ClientCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)  # Enforce authentication
):
    """Create a new client organization

    Note: A default 'General' case is auto-created and the creator is assigned to it.
    This ensures the creator can immediately access the new client.
    """
    db_client = Client(
        name=client.name,
        reference_code=client.reference_code,
        notes=client.notes
    )
    db.add(db_client)
    db.commit()
    db.refresh(db_client)

    # Auto-create a default "General" case for the new client
    default_case = Case(
        client_id=db_client.id,
        name="General",
        description="Default case for general documents"
    )
    db.add(default_case)
    db.commit()
    db.refresh(default_case)

    # Auto-assign the creator to the default case with 'lead' role
    assignment = CaseAssignment(
        case_id=default_case.id,
        user_id=current_user.id,
        role_in_case="lead"
    )
    db.add(assignment)
    db.commit()

    # current_user is now guaranteed by require_auth dependency
    logger.info(f"Created client: {db_client.name} (ID: {db_client.id}) by user {current_user.email} (with default case)")
    return db_client


@app.get("/v1/clients", response_model=List[ClientResponse])
async def list_clients(
    skip: int = Query(default=0, ge=0, description="Number of records to skip"),
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum number of records to return"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)
):
    """List clients the user has access to (via case assignments)

    Security: Only returns clients that have cases assigned to the current user.
    Admin users see all clients.

    Pagination limits:
    - skip: Must be >= 0
    - limit: Must be between 1 and 1000
    """
    from sqlalchemy import distinct

    # Admin users can see all clients
    if current_user.role == UserRole.ADMIN:
        clients = db.query(Client).offset(skip).limit(limit).all()
        return clients

    # Non-admin users: filter to clients with cases they're assigned to
    # Get distinct client_ids from cases the user is assigned to
    accessible_client_ids = db.query(distinct(Case.client_id)).join(
        CaseAssignment, CaseAssignment.case_id == Case.id
    ).filter(
        CaseAssignment.user_id == current_user.id
    ).subquery()

    clients = db.query(Client).filter(
        Client.id.in_(accessible_client_ids)
    ).offset(skip).limit(limit).all()

    return clients


@app.get("/v1/clients/{client_id}", response_model=ClientResponse)
async def get_client(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)
):
    """Get client details

    Security: Only returns the client if the user has access to at least one
    case belonging to this client, or if the user is an admin.
    """
    from sqlalchemy import distinct

    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Admin users can access any client
    if current_user.role != UserRole.ADMIN:
        # Check if user is assigned to any case belonging to this client
        has_access = db.query(CaseAssignment.id).join(
            Case, CaseAssignment.case_id == Case.id
        ).filter(
            Case.client_id == client_id,
            CaseAssignment.user_id == current_user.id
        ).first()

        if not has_access:
            raise HTTPException(status_code=403, detail="Access denied to this client")

    return client


# ============================================================================
# Case Management Endpoints
# ============================================================================

@app.post("/v1/cases", response_model=CaseResponse)
async def create_case(
    case: CaseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)  # Enforce authentication
):
    """Create a new case

    Note: The creator is automatically assigned to the case with 'lead' role.
    """
    # Validate client exists
    client = db.query(Client).filter(Client.id == case.client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    db_case = Case(
        client_id=case.client_id,
        name=case.name,
        description=case.description,
        retention_days=case.retention_days or 90
    )
    db.add(db_case)
    db.commit()
    db.refresh(db_case)

    # Auto-assign the creator to the case with 'lead' role
    assignment = CaseAssignment(
        case_id=db_case.id,
        user_id=current_user.id,
        role_in_case="lead"
    )
    db.add(assignment)
    db.commit()

    # current_user is now guaranteed by require_auth dependency
    logger.info(f"Created case: {db_case.name} (ID: {db_case.id}) by user {current_user.email} (auto-assigned as lead)")
    return db_case


@app.get("/v1/clients/{client_id}/cases", response_model=List[CaseResponse])
async def list_client_cases(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)
):
    """List cases for a client that the user has access to

    Security: Only returns cases the current user is assigned to.
    Admin users see all cases for the client.
    """
    # Admin users can see all cases
    if current_user.role == UserRole.ADMIN:
        cases = db.query(Case).filter(Case.client_id == client_id).all()
        return cases

    # Non-admin users: filter to cases they're assigned to
    cases = db.query(Case).join(
        CaseAssignment, CaseAssignment.case_id == Case.id
    ).filter(
        Case.client_id == client_id,
        CaseAssignment.user_id == current_user.id
    ).all()

    return cases


@app.get("/v1/cases/{case_id}", response_model=CaseResponse)
async def get_case(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)
):
    """Get case details

    Security: Only returns the case if the user is assigned to it or is an admin.
    """
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # Admin users can access any case
    if current_user.role != UserRole.ADMIN:
        # Check if user is assigned to this case
        assignment = db.query(CaseAssignment).filter(
            CaseAssignment.case_id == case_id,
            CaseAssignment.user_id == current_user.id
        ).first()
        if not assignment:
            raise HTTPException(status_code=403, detail="Access denied to this case")

    return case


@app.post("/v1/cases/{case_id}/assign")
async def assign_user_to_case(
    case_id: int,
    assignment: CaseAssignmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)  # Enforce authentication
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

    # current_user is now guaranteed by require_auth dependency
    logger.info(f"User {assignment.user_id} assigned to case {case_id} by {current_user.email}")
    return {"message": "User assigned successfully"}


# ============================================================================
# File Upload Endpoints
# ============================================================================

@app.post("/v1/upload")
async def upload_files(
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user)
):
    """
    Upload files temporarily before creating a run.

    This is a compatibility endpoint for the frontend upload flow.
    Files are uploaded to temporary MinIO storage and can be associated
    with a run later.

    Args:
        files: List of files to upload
        current_user: Authenticated user

    Returns:
        Dictionary with:
        - files: List of uploaded file metadata (filename, storage_path, size, sha256)
        - count: Number of files uploaded

    Requires:
        - Authentication (JWT token)
        - At least one file
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    storage = MinioStorage()
    uploaded_files = []

    for file in files:
        try:
            # Generate temporary storage key (without run_id yet)
            temp_key = f"temp/{uuid.uuid4()}/{file.filename}"

            # Read file content
            file_content = await file.read()

            # Upload to MinIO
            storage.upload_bytes(temp_key, file_content)

            # Calculate SHA256 hash for integrity verification
            sha256_hash = hashlib.sha256(file_content).hexdigest()

            uploaded_files.append({
                "filename": file.filename,
                "storage_path": temp_key,  # Frontend expects this field
                "storage_key": temp_key,
                "size_bytes": len(file_content),
                "sha256": sha256_hash,
                "mime_type": file.content_type or "application/pdf"
            })

            logger.info(f"Uploaded file {file.filename} to temporary storage: {temp_key} (SHA256: {sha256_hash[:16]}...)")

        except Exception as e:
            logger.error(f"Failed to upload file {file.filename}: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to upload file {file.filename}: {str(e)}"
            )

    return {
        "files": uploaded_files,
        "count": len(uploaded_files)
    }


@app.post("/v1/cases/{case_id}/documents")
async def upload_case_documents(
    case_id: int,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Upload documents for a specific case.

    This endpoint validates that the case exists before accepting file uploads,
    providing better error handling and UX compared to generic upload endpoint.
    Files are uploaded to temporary MinIO storage and can be associated with
    a run later.

    Args:
        case_id: ID of the case to upload documents for
        files: List of files to upload
        db: Database session
        current_user: Authenticated user

    Returns:
        Dictionary with:
        - files: List of uploaded file metadata (filename, storage_path, size, sha256)
        - count: Number of files uploaded
        - case_id: ID of the associated case

    Raises:
        404: Case not found
        400: No files provided
        500: Upload failure

    Requires:
        - Authentication (JWT token)
        - Valid case_id
        - At least one file
    """
    # Validate case exists
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail=f"Case with ID {case_id} not found")

    # Validate files provided
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    # Reuse upload logic from /v1/upload endpoint
    storage = MinioStorage()
    uploaded_files = []

    for file in files:
        try:
            # Generate temporary storage key (without run_id yet)
            temp_key = f"temp/{uuid.uuid4()}/{file.filename}"

            # Read file content
            file_content = await file.read()

            # Upload to MinIO
            storage.upload_bytes(temp_key, file_content)

            # Calculate SHA256 hash for integrity verification
            sha256_hash = hashlib.sha256(file_content).hexdigest()

            uploaded_files.append({
                "filename": file.filename,
                "storage_path": temp_key,  # Frontend expects this field
                "storage_key": temp_key,
                "size_bytes": len(file_content),
                "sha256": sha256_hash,
                "mime_type": file.content_type or "application/pdf"
            })

            logger.info(f"Uploaded file {file.filename} for case {case_id} to temporary storage: {temp_key} (SHA256: {sha256_hash[:16]}...)")

        except Exception as e:
            logger.error(f"Failed to upload file {file.filename} for case {case_id}: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to upload file {file.filename}: {str(e)}"
            )

    return {
        "files": uploaded_files,
        "count": len(uploaded_files),
        "case_id": case_id
    }


# ============================================================================
# Run Management Endpoints
# ============================================================================

@app.post("/v1/runs", response_model=RunCreateResponse)
async def create_run(
run: RunCreate,
db: Session = Depends(get_db),
current_user: User = Depends(get_current_user)  # Optional auth for testing
):
    """
    Create a new run for document processing.

    Files are uploaded via the /v1/runs/{run_id}/upload proxy endpoint,
    which avoids presigned URL signature mismatch issues in Docker environments.

    Flow:
    1. Create run → Get run_id
    2. Upload files via /v1/runs/{run_id}/upload
    3. Start processing via /v1/runs/{run_id}/start with file manifest
    """
    # Get case to retrieve client_id for multi-tenancy
    case = db.query(Case).filter(Case.id == run.case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # Resolve mode to provider/model/doc_extractor if mode is provided
    if run.mode:
        from core.modes import get_mode, get_default_mode
        mode = get_mode(run.mode)
        if not mode:
            raise HTTPException(status_code=400, detail=f"Invalid mode: {run.mode}. Valid modes: best, balanced, fast")
        provider = mode.provider
        model = mode.model
        doc_extractor = mode.doc_extractor
        logger.info(f"Resolved mode '{run.mode}' to provider={provider}, model={model}, doc_extractor={doc_extractor}")
    else:
        # Use explicit values or defaults
        provider = run.provider or "openrouter"
        model = run.model or "meta-llama/llama-3.3-70b-instruct"
        doc_extractor = run.doc_extractor or "docling"

    # Create run in database
    db_run = Run(
        case_id=run.case_id,
        provider=provider,
        model=model,
        doc_extractor=doc_extractor,
        status=RunStatus.QUEUED
    )
    db.add(db_run)
    db.commit()
    db.refresh(db_run)

    user_email = current_user.email if current_user else "anonymous"
    logger.info(f"Created run {db_run.id} for client {case.client_id} by {user_email}")

    # Persist optional classification settings in run_metadata (no schema changes required)
    try:
        meta = db_run.run_metadata or {}
        if run.enable_classification is not None:
            meta["enable_classification"] = bool(run.enable_classification)
        if run.classification_model:
            meta["classification_model"] = run.classification_model
        db_run.run_metadata = meta
        db.commit()
    except Exception as e:
        logger.warning(f"Failed to persist classification run metadata: {e}")

    # If files are provided, create documents and enqueue processing job
    if run.files:
        for file_info in run.files:
            # Create document record
            doc = Document(
                run_id=db_run.id,
                case_id=run.case_id,
                filename=file_info.get("filename"),
                storage_key=file_info.get("storage_path") or file_info.get("storage_key"),
                size_bytes=file_info.get("size_bytes", 0),
                mime_type=file_info.get("mime_type", "application/pdf"),
                status=DocumentStatus.PENDING
            )
            db.add(doc)

        db.commit()

        # Enqueue processing job
        # Note: doc_extractor is stored in Run record (line 728), worker reads it from DB
        job_id = enqueue_process_run(
            run_id=db_run.id,
            provider=db_run.provider,
            model=db_run.model or "meta-llama/llama-3.3-70b-instruct"
        )

        logger.info(f"Enqueued processing job {job_id} for run {db_run.id} with {len(run.files)} files")

    return {
        "run_id": db_run.id,
        "case_id": run.case_id,
        "status": db_run.status.value
    }


@app.get("/v1/runs", response_model=RunListResponse)
async def list_runs(
    client_id: Optional[int] = Query(None, description="Filter by client ID"),
    case_id: Optional[int] = Query(None, description="Filter by case ID"),
    status: Optional[str] = Query(None, description="Filter by status (queued, processing, success, failed, partial)"),
    limit: int = Query(20, ge=1, le=100, description="Number of results per page (max 100)"),
    offset: int = Query(0, ge=0, description="Number of results to skip for pagination"),
    order_by: str = Query("created_at", description="Field to sort by (created_at, finished_at, status)"),
    order: str = Query("desc", description="Sort direction (asc or desc)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)
):
    """
    List runs with filtering and pagination.

    Security: Only returns runs for cases the current user is assigned to.
    Admin users see all runs.

    This endpoint provides efficient access to runs without the N+1 query problem
    of fetching clients → cases → runs separately.

    Filtering:
    - client_id: Show only runs for a specific client
    - case_id: Show only runs for a specific case
    - status: Show only runs with a specific status

    Pagination:
    - limit: Results per page (1-100, default 20)
    - offset: Number of results to skip (for pagination)

    Sorting:
    - order_by: Field to sort by (created_at, finished_at, status)
    - order: Direction (asc/desc, default desc)

    Returns runs with pagination metadata (total, has_next, has_prev).
    """
    # Build query with filters
    query = db.query(Run)

    # Security: Filter by user's accessible cases (unless admin)
    if current_user.role != UserRole.ADMIN:
        # Get case IDs the user is assigned to
        accessible_case_ids = db.query(CaseAssignment.case_id).filter(
            CaseAssignment.user_id == current_user.id
        ).subquery()
        query = query.filter(Run.case_id.in_(accessible_case_ids))

    # Apply additional filters
    if case_id is not None:
        query = query.filter(Run.case_id == case_id)
    elif client_id is not None:
        # Filter by client_id requires join with Case
        query = query.join(Case, Run.case_id == Case.id).filter(Case.client_id == client_id)

    if status is not None:
        # Validate status enum
        valid_statuses = ["queued", "processing", "success", "failed", "partial"]
        if status not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
            )
        query = query.filter(Run.status == status)

    # Get total count before pagination
    total = query.count()

    # Apply sorting
    valid_order_by = ["created_at", "finished_at", "status"]
    if order_by not in valid_order_by:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid order_by field. Must be one of: {', '.join(valid_order_by)}"
        )

    if order.lower() not in ["asc", "desc"]:
        raise HTTPException(status_code=400, detail="Order must be 'asc' or 'desc'")

    # Apply ordering
    order_column = getattr(Run, order_by)
    if order.lower() == "desc":
        query = query.order_by(order_column.desc())
    else:
        query = query.order_by(order_column.asc())

    # Apply pagination
    runs = query.offset(offset).limit(limit).all()

    # Build RunResponse objects
    run_responses = []
    for run in runs:
        # Get document counts
        total_docs = db.query(Document).filter(Document.run_id == run.id).count()
        processed_docs = db.query(Document).filter(
            Document.run_id == run.id,
            Document.status.in_([DocumentStatus.SUCCESS])
        ).count()
        failed_docs = db.query(Document).filter(
            Document.run_id == run.id,
            Document.status == DocumentStatus.FAILED
        ).count()
        # Clamp to non-negative to handle race conditions between count queries
        pending_docs = max(0, total_docs - processed_docs - failed_docs)

        run_responses.append(RunResponse(
            run_id=run.id,
            case_id=run.case_id,
            status=run.status.value,
            provider=run.provider,
            model=run.model,
            created_at=run.created_at,
            started_at=run.started_at,
            finished_at=run.finished_at,
            counts={
                "total": total_docs,
                "processed": processed_docs,
                "failed": failed_docs,
                "pending": pending_docs
            },
            timings={
                "docling_seconds": run.docling_seconds,
                "extractor_seconds": run.extractor_seconds,
                "total_seconds": run.total_seconds
            },
            cost_usd=run.cost_usd,
            error=run.error
        ))

    # Calculate pagination metadata
    has_next = (offset + limit) < total
    has_prev = offset > 0

    return RunListResponse(
        runs=run_responses,
        pagination=PaginationMetadata(
            total=total,
            limit=limit,
            offset=offset,
            has_next=has_next,
            has_prev=has_prev
        )
    )


@app.put("/v1/runs/{run_id}/upload")
async def upload_file_proxy(
run_id: int,
file: UploadFile = File(...),
db: Session = Depends(get_db),
current_user: User = Depends(get_current_user)  # Optional auth for testing
):
    """
    Proxy file upload to MinIO (avoids presigned URL signature issues in Docker)

    This endpoint receives file uploads from the browser and forwards them to MinIO
    using the internal Docker network, avoiding hostname/signature mismatch issues.
    """
    # Get run to extract client_id and case_id
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    # Get case to retrieve client_id for multi-tenancy
    case = db.query(Case).filter(Case.id == run.case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # Generate storage key
    storage_key = generate_document_key(
        client_id=case.client_id,
        case_id=run.case_id,
        run_id=run_id,
        filename=file.filename
    )

    # Upload to MinIO
    storage = MinioStorage()
    file_content = await file.read()
    storage.upload_bytes(storage_key, file_content)

    logger.info(f"Uploaded file {file.filename} to {storage_key} for run {run_id}")

    return {
        "status": "uploaded",
        "filename": file.filename,
        "storage_key": storage_key,
        "size_bytes": len(file_content)
    }


@app.put("/v1/runs/{run_id}/start")
async def start_run(
    run_id: int,
    manifest: RunManifest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)  # Enforce authentication
):
    """
    Start processing a run with uploaded documents

    Idempotency:
    If idempotency_key is provided and a run with this key was already started,
    return the previous result instead of creating duplicates.
    """
    # Handle idempotency via Redis with an atomic lock to avoid races
    idempotency_key = manifest.idempotency_key
    if idempotency_key:
        try:
            import redis
            r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
            cache_key = f"idempotency:start_run:{idempotency_key}"
            lock_key = f"idempotency:start_run:lock:{idempotency_key}"

            # If we already have a cached result, return it immediately
            cached_result = r.get(cache_key)
            if cached_result:
                logger.info(f"Idempotency hit for key {idempotency_key}")
                try:
                    r.close()
                except Exception:
                    pass
                return json.loads(cached_result)

            # Try to acquire processing lock (SETNX with short TTL)
            acquired = r.set(lock_key, "1", nx=True, ex=300)
            if not acquired:
                # Another request is processing the same idempotency key
                cached_result = r.get(cache_key)
                try:
                    r.close()
                except Exception:
                    pass
                if cached_result:
                    return json.loads(cached_result)
                # No cached result yet: ask client to retry later
                raise HTTPException(status_code=409, detail="Duplicate request in progress for this idempotency key. Please retry.")
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"Idempotency check/lock failed: {e}, proceeding without cache")

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
    job_id = enqueue_process_run(
        run_id=run_id,
        provider=run.provider,
        model=run.model
    )

    response = {
        "status": "accepted",
        "run_id": run_id,
        "job_id": job_id,
        "message": "Run processing started"
    }

    # Cache the result for idempotency (24-hour TTL) and release lock
    if idempotency_key:
        try:
            import redis
            r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
            cache_key = f"idempotency:start_run:{idempotency_key}"
            lock_key = f"idempotency:start_run:lock:{idempotency_key}"
            r.setex(cache_key, 86400, json.dumps(response))
            try:
                r.delete(lock_key)
            finally:
                r.close()
        except Exception as e:
            logger.warning(f"Failed to finalize idempotency cache: {e}")

    # current_user is now guaranteed by require_auth dependency
    logger.info(f"Started run {run_id} with job {job_id} by {current_user.email}")

    return response


@app.get("/v1/runs/{run_id}", response_model=RunResponse)
async def get_run(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)
):
    """Get run details with progress information

    Security: Only returns run if user is assigned to the run's case or is admin.
    """
    run = await authorize_run_access(run_id, db, current_user)
    
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
            "pending": max(0, total_docs - processed_docs - failed_docs)
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
    cursor: Optional[int] = Query(default=None, ge=0, description="Cursor for pagination (event ID)"),
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum number of events to return"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)
):
    """Get events extracted in a run (paginated)

    Security: Only returns events if user is assigned to the run's case or is admin.

    Pagination limits:
    - cursor: Must be >= 0 if provided
    - limit: Must be between 1 and 1000
    """
    # Authorize access to the run
    await authorize_run_access(run_id, db, current_user)

    query = db.query(Event).filter(Event.run_id == run_id)

    if cursor is not None:
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


@app.get("/v1/runs/{run_id}/classification")
async def get_run_classification(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)
):
    """
    Return per-document classification results if available.
    Reads artifact 'classification_json' from storage if present.

    Security: Only returns classification if user is assigned to the run's case or is admin.
    """
    run = await authorize_run_access(run_id, db, current_user)

    artifact = db.query(Artifact).filter(
        Artifact.run_id == run_id,
        Artifact.kind == "classification_json"
    ).first()

    if not artifact:
        return {"available": False, "results": {}}

    storage = MinioStorage()
    try:
        content_bytes = storage.download_bytes(artifact.storage_key)
        if content_bytes is None:
            raise RuntimeError("No content")
        data = json.loads(content_bytes.decode('utf-8'))
        return {"available": True, "results": data}
    except Exception as e:
        logger.error(f"Failed to read classification artifact for run {run_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to load classification results")


@app.get("/v1/runs/{run_id}/token-usage")
async def get_run_token_usage(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)
):
    """
    Return per-document token usage and totals if available.
    Reads artifact 'token_usage_json' from storage if present.

    Security: Only returns token usage if user is assigned to the run's case or is admin.
    """
    run = await authorize_run_access(run_id, db, current_user)

    artifact = db.query(Artifact).filter(
        Artifact.run_id == run_id,
        Artifact.kind == "token_usage_json"
    ).first()

    if not artifact:
        return {"available": False, "results": {}}

    storage = MinioStorage()
    try:
        content_bytes = storage.download_bytes(artifact.storage_key)
        if content_bytes is None:
            raise RuntimeError("No content")
        data = json.loads(content_bytes.decode('utf-8'))
        return {"available": True, "results": data}
    except Exception as e:
        logger.error(f"Failed to read token usage artifact for run {run_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to load token usage")


@app.get("/v1/runs/{run_id}/artifacts")
async def get_run_artifacts(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)
):
    """Get available export artifacts for a run

    Security: Only returns artifacts if user is assigned to the run's case or is admin.
    """
    # Authorize access to the run
    await authorize_run_access(run_id, db, current_user)

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


@app.put("/v1/runs/{run_id}/retry")
async def retry_run(
    run_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")
):
    """
    Retry a failed or stuck run.
    
    This endpoint:
    1. Resets FAILED documents to PENDING
    2. Resets stuck PROCESSING documents (configurable threshold) to PENDING
    3. Resets run status to QUEUED
    4. Enqueues new processing job
    
    Supports idempotency via Idempotency-Key header to prevent duplicate retries.
    
    Returns:
        JSON with retry status and number of documents reset
    """
    from datetime import timedelta
    from legal_events_core import RetryConfig
    import redis
    
    # Load retry configuration
    retry_config = RetryConfig()
    stuck_threshold_hours = retry_config.stuck_document_hours
    stuck_threshold_seconds = stuck_threshold_hours * 3600
    
    # Check idempotency cache
    if idempotency_key:
        r = None
        try:
            r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
            cache_key = f"idempotency:retry_run:{idempotency_key}"
            cached_response = r.get(cache_key)
            if cached_response:
                logger.info(f"Returning cached retry response for idempotency key: {idempotency_key}")
                return json.loads(cached_response)
        except Exception as e:
            logger.warning(f"Failed to check idempotency cache: {e}")
        finally:
            if r is not None:
                r.close()
    
    # Get run
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    
    # Validate run has documents
    total_docs = db.query(Document).filter(Document.run_id == run_id).count()
    if total_docs == 0:
        raise HTTPException(status_code=400, detail="Cannot retry run with no documents")
    
    # Only allow retry for failed/partial/stuck runs
    if run.status not in [RunStatus.FAILED, RunStatus.PARTIAL_SUCCESS]:
        # Check if run is stuck (PROCESSING > configured threshold)
        if run.status == RunStatus.PROCESSING:
            if not run.started_at or (datetime.utcnow() - run.started_at).total_seconds() < stuck_threshold_seconds:
                raise HTTPException(status_code=400, detail="Run is still processing")
        else:
            raise HTTPException(status_code=400, detail=f"Cannot retry run in {run.status.value} state")
    
    # Start database transaction for atomic updates
    try:
        # Reset FAILED documents to PENDING
        failed_docs = db.query(Document).filter(
            Document.run_id == run_id,
            Document.status == DocumentStatus.FAILED
        ).all()
        
        for doc in failed_docs:
            doc.status = DocumentStatus.PENDING
            doc.error = None
            doc.processed_at = None
        
        # Reset stuck PROCESSING documents (>configured threshold)
        stuck_docs = db.query(Document).filter(
            Document.run_id == run_id,
            Document.status == DocumentStatus.PROCESSING,
            Document.created_at < datetime.utcnow() - timedelta(hours=stuck_threshold_hours)
        ).all()
        
        for doc in stuck_docs:
            doc.status = DocumentStatus.PENDING
            doc.processed_at = None
        
        # Reset run status
        run.status = RunStatus.QUEUED
        run.error = None
        run.finished_at = None
        
        # Flush changes before enqueueing (ensures DB consistency)
        db.flush()
        
        # Enqueue new processing job
        job_id = enqueue_job(
            "process_run",
            run_id=run_id,
            provider=run.provider,
            model=run.model
        )
        
        # Commit transaction after successful job enqueue
        db.commit()
        
        logger.info(f"Retrying run {run_id}, reset {len(failed_docs)} failed + {len(stuck_docs)} stuck docs by {current_user.email}")
        
        response = {
            "status": "accepted",
            "run_id": run_id,
            "job_id": job_id,
            "documents_reset": len(failed_docs) + len(stuck_docs),
            "failed_documents": len(failed_docs),
            "stuck_documents": len(stuck_docs)
        }
        
        # Cache the result for idempotency (24-hour TTL)
        if idempotency_key:
            try:
                r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
                cache_key = f"idempotency:retry_run:{idempotency_key}"
                r.setex(cache_key, 86400, json.dumps(response))
                r.close()
            except Exception as e:
                logger.warning(f"Failed to cache idempotency result: {e}")
        
        return response
        
    except Exception as e:
        db.rollback()
        import uuid
        correlation_id = str(uuid.uuid4())[:8]
        logger.error(f"Failed to retry run {run_id} (correlation_id: {correlation_id}): {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retry run. Please contact support with reference: {correlation_id}"
        )


@app.get("/v1/runs/{run_id}/export")
async def export_run(
    run_id: int,
    fmt: str = "csv",
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)
):
    """Generate and return export file

    Security: Only allows export if user is assigned to the run's case or is admin.
    """
    # Authorize access to the run first
    await authorize_run_access(run_id, db, current_user)

    if fmt not in ["csv", "xlsx", "json"]:
        raise HTTPException(status_code=400, detail="Format must be csv, xlsx, or json")
    
    # Check if artifact already exists
    artifact = db.query(Artifact).filter(
        Artifact.run_id == run_id,
        Artifact.kind == fmt
    ).first()
    
    existing_artifact = artifact if artifact else None
    if artifact:
        # Stream existing artifact directly when available; if missing in storage, regenerate
        storage = MinioStorage()
        file_bytes = storage.download_bytes(artifact.storage_key)

        if file_bytes:
            # Set content type based on format
            content_types = {
                "csv": "text/csv",
                "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "json": "application/json"
            }

            filename = f"run_{run_id}_events.{fmt}"

            return StreamingResponse(
                iter([file_bytes]),
                media_type=content_types.get(fmt, "application/octet-stream"),
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )
        else:
            logger.warning(
                f"Artifact record exists but object missing in storage: {artifact.storage_key} — regenerating"
            )
    
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
        content_type = "application/json"
    
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
        content_type = "text/csv"
    
    else:  # xlsx
        # Generate Excel export
        import pandas as pd
        import io
        
        data = [event.to_dict() for event in events]
        df = pd.DataFrame(data)
        
        output = io.BytesIO()
        # Use openpyxl engine (available per requirements.txt) for writing xlsx
        df.to_excel(output, index=False, sheet_name="Legal Events", engine='openpyxl')
        content_bytes = output.getvalue()
        content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    
    # Determine case via the run to avoid relying on event relationships
    run_obj = db.query(Run).filter(Run.id == run_id).first()
    if not run_obj:
        raise HTTPException(status_code=404, detail="Run not found")
    case = db.query(Case).filter(Case.id == run_obj.case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found for run")

    # Use standardized storage key generation
    storage_key = generate_artifact_key(
        client_id=case.client_id,
        case_id=case.id,
        run_id=run_id,
        format=fmt
    )

    # Upload to storage first; if DB commit fails later, delete the object
    uploaded_ok = storage.upload_bytes(storage_key, content_bytes, content_type=content_type)
    if not uploaded_ok:
        raise HTTPException(status_code=500, detail="Failed to upload artifact to storage")

    # Create or update artifact record with cleanup on failure
    try:
        if existing_artifact is not None:
            # Update existing metadata
            existing_artifact.size_bytes = len(content_bytes)
            existing_artifact.storage_key = storage_key
            db.add(existing_artifact)
        else:
            artifact = Artifact(
                run_id=run_id,
                kind=fmt,
                storage_key=storage_key,
                size_bytes=len(content_bytes)
            )
            db.add(artifact)
        db.commit()
    except Exception as e:
        db.rollback()
        try:
            storage.delete_object(storage_key)
        except Exception:
            logger.error("Failed to rollback uploaded artifact from storage after DB error")
        logger.error(f"Failed to save artifact metadata: {e}")
        raise HTTPException(status_code=500, detail="Failed to save artifact metadata")

    # Stream file directly (avoids MinIO hostname issues)
    content_types = {
        "csv": "text/csv",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "json": "application/json"
    }

    filename = f"run_{run_id}_events.{fmt}"

    return StreamingResponse(
        iter([content_bytes]),
        media_type=content_types.get(fmt, "application/octet-stream"),
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.delete("/v1/runs/{run_id}/artifacts")
async def delete_artifact(
    run_id: int,
    fmt: str = "json",
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)  # Enforce authentication for destructive operations
):
    """
    Delete export artifact from MinIO storage (for testing regeneration)

    This endpoint deletes only the storage object, keeping the database record.
    This allows testing the regeneration path where the export endpoint detects
    a missing artifact and regenerates it from the events table.

    Use case: Integration testing of artifact regeneration logic

    **Requires authentication** - Only authenticated users can delete artifacts.
    """
    if fmt not in ["csv", "xlsx", "json"]:
        raise HTTPException(status_code=400, detail="Format must be csv, xlsx, or json")

    # Find artifact record
    artifact = db.query(Artifact).filter(
        Artifact.run_id == run_id,
        Artifact.kind == fmt
    ).first()

    if not artifact:
        raise HTTPException(status_code=404, detail=f"No {fmt} artifact found for run {run_id}")

    # Delete from MinIO storage only (keep DB record for regeneration testing)
    storage = MinioStorage()
    deleted = storage.delete_object(artifact.storage_key)

    if deleted:
        logger.info(f"Deleted artifact from storage: {artifact.storage_key} by user {current_user.email}")
        return {
            "status": "deleted",
            "storage_key": artifact.storage_key,
            "format": fmt,
            "message": "Artifact deleted from storage (database record preserved for regeneration testing)"
        }
    else:
        logger.warning(f"Artifact not found in storage: {artifact.storage_key}")
        raise HTTPException(status_code=404, detail="Artifact not found in storage")


# ============================================================================
# SSE Endpoint for Progress Streaming
# ============================================================================

@app.get("/v1/runs/{run_id}/stream")
async def stream_run_progress(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_auth)
):
    """
    Server-Sent Events endpoint for real-time progress updates

    Security: Only streams progress if user is assigned to the run's case or is admin.

    Note: Proper DB session management for long-lived SSE connections.
    Each loop iteration gets a fresh db session to avoid connection lifecycle issues.

    Safety Features:
    - Maximum iterations: 1800 (1 hour at 2s intervals)
    - Timeout protection prevents infinite loops
    - Graceful termination on completion or error
    """
    # Authorize access before starting stream (uses request-scoped db session)
    await authorize_run_access(run_id, db, current_user)

    from sse_starlette.sse import EventSourceResponse
    import asyncio
    import json
    from infra.database import SessionLocal

    # Safety limits to prevent infinite loops
    MAX_ITERATIONS = 1800  # 1 hour at 2-second intervals
    POLL_INTERVAL = 2  # seconds between updates

    async def event_generator():
        """Generate SSE events for run progress"""
        iteration = 0
        
        while iteration < MAX_ITERATIONS:
            iteration += 1
            
            # Create fresh DB session for each iteration (SSE streams are long-lived)
            db = SessionLocal()
            try:
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
                await asyncio.sleep(POLL_INTERVAL)

            finally:
                # Always close the session to avoid connection leaks
                db.close()
        
        # Safety timeout reached
        if iteration >= MAX_ITERATIONS:
            yield {
                "event": "timeout",
                "data": json.dumps({
                    "error": "Stream timeout reached after 1 hour",
                    "run_id": run_id
                })
            }

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


@app.get("/v1/workers/status", response_model=WorkerStatusResponse)
async def get_worker_status():
    """
    Get current worker status and queue metrics with heartbeat-aware liveness detection.
    
    Returns WorkerStatusResponse with:
    - Number of registered workers
    - Active heartbeat count (workers_with_heartbeat)
    - Stale heartbeat count (workers_stale - >60s old)
    - Worker details with heartbeat information
    - Queue depths and processing stats
    - Overall health status (boolean and string)
    
    Health semantics:
        healthy = workers_registered > 0 AND workers_with_heartbeat > 0 AND workers_stale == 0
    
    Status determination:
        - "degraded" if workers_registered == 0
        - "degraded" if active_heartbeats == 0
        - "degraded" if stale_heartbeats > 0
        - "healthy" otherwise
    
    Returns:
        JSON with worker and queue statistics (see api/schemas.py:WorkerStatusResponse)
    """
    try:
        from infra.queue import get_worker_stats, get_queue_stats, get_worker_heartbeats, cleanup_stale_workers
        
        # Get worker statistics from RQ
        worker_stats = get_worker_stats()
        
        # Get queue statistics
        queue_stats = {
            "high": get_queue_stats("high"),
            "default": get_queue_stats("default"),
            "low": get_queue_stats("low")
        }
        
        # Calculate total queue depth
        total_queued = sum(q.get("queued", 0) for q in queue_stats.values())
        total_processing = sum(q.get("started", 0) for q in queue_stats.values())
        
        # Get worker heartbeats with detailed data
        heartbeats = get_worker_heartbeats()
        active_heartbeats = len([h for h in heartbeats.values() if not h.get('is_stale', False)])
        stale_heartbeats = len([h for h in heartbeats.values() if h.get('is_stale', False)])
        
        # Enrich worker data with heartbeat information
        enriched_workers = []
        for worker in worker_stats.get("workers", []):
            worker_data = worker.copy()
            worker_id = worker['name']
            
            if worker_id in heartbeats:
                hb = heartbeats[worker_id]
                worker_data['heartbeat'] = {
                    'last_beat': hb['timestamp'],
                    'seconds_ago': hb['seconds_since_heartbeat'],
                    'is_alive': not hb['is_stale'],
                    'hostname': hb.get('hostname'),
                    'pid': hb.get('pid')
                }
            else:
                worker_data['heartbeat'] = None
            
            enriched_workers.append(worker_data)
        
        # Determine health status
        workers_count = worker_stats.get("total_workers", 0)
        healthy = workers_count > 0 and active_heartbeats > 0 and stale_heartbeats == 0
        
        # Determine overall status
        if workers_count == 0:
            status = "degraded"
        elif active_heartbeats == 0:
            status = "degraded"
        elif stale_heartbeats > 0:
            status = "degraded"
        else:
            status = "healthy"
        
        return {
            "workers_registered": workers_count,
            "workers_with_heartbeat": active_heartbeats,
            "workers_stale": stale_heartbeats,
            "workers": enriched_workers,
            "queue_depth": total_queued,
            "jobs_processing": total_processing,
            "queues": queue_stats,
            "healthy": healthy,
            "status": status,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Error getting worker status: {e}")
        # Return a schema-conformant fallback to satisfy response_model validation
        return {
            "workers_registered": 0,
            "workers_with_heartbeat": 0,
            "workers_stale": 0,
            "workers": [],
            "queue_depth": 0,
            "jobs_processing": 0,
            "queues": {},
            "healthy": False,
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat()
        }


@app.post("/v1/workers/cleanup")
async def cleanup_stale_workers_endpoint(current_user: dict = Depends(get_current_user)):
    """
    Clean up stale worker registrations.
    
    Requires authentication. Removes workers that:
    - Have no heartbeat OR
    - Have a heartbeat older than 60 seconds
    
    Returns:
        Number of stale workers cleaned up
    """
    try:
        from infra.queue import cleanup_stale_workers
        
        cleaned_count = cleanup_stale_workers()
        
        return {
            "status": "success",
            "workers_cleaned": cleaned_count,
            "message": f"Cleaned up {cleaned_count} stale worker(s)",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        correlation_id = str(uuid.uuid4())[:8]
        logger.error(f"Error cleaning up stale workers (correlation_id: {correlation_id}): {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Worker cleanup failed. Please contact support with reference: {correlation_id}"
        )


# ============================================================================
# Static File Serving (Frontend)
# ============================================================================
# Mount frontend static files AFTER all API routes to avoid conflicts
# This serves index.html, simple.html, app.js, simple.js from the frontend directory

import os.path
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
    logger.info(f"✅ Frontend static files mounted from: {frontend_dir}")
else:
    logger.warning(f"⚠️ Frontend directory not found: {frontend_dir}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
