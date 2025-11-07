"""
Background Worker Tasks - Service Boundary Compliant Version

This module processes documents using the legal pipeline.
It maintains strict service boundaries:
- READ-ONLY: clients, cases, runs, documents (for context only)
- WRITE-ONLY: events, artifacts (worker's primary output)  
- STATUS UPDATES: Via Redis events to API

No direct mutations of API-owned entities (runs/documents).
"""

import os
import logging
import tempfile
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
import pandas as pd
import json
import redis
from sqlalchemy.orm import Session

# Import existing pipeline
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from core.legal_pipeline_refactored import LegalEventsPipeline
from core.constants import FIVE_COLUMN_HEADERS

# Import worker-owned dependencies
from worker.database import SessionLocal

# Import ORM models (read-only access for worker)
from infra.models import (
    Run, RunStatus, Document, DocumentStatus, Event, Artifact,
    Case, Client
)

# Import storage layer
from infra.storage import MinioStorage

# Import event emitter for status updates
from infra.worker_events import WorkerEventEmitter

logger = logging.getLogger(__name__)


def process_run(run_id: int, provider: str = "openrouter", model: str = None) -> Dict[str, Any]:
    """
    Process all documents in a run - Service Boundary Compliant Version
    
    This function:
    - READS run/document info for processing context
    - WRITES events and artifacts (worker's output)
    - EMITS status updates via Redis for API to consume
    - NEVER mutates run/document status directly
    
    Args:
        run_id: Run ID to process
        provider: LLM provider to use
        model: Specific model to use
        
    Returns:
        Result dictionary with stats
    """
    db = SessionLocal()
    storage = MinioStorage()
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    redis_conn = redis.from_url(redis_url)
    emitter = WorkerEventEmitter(redis_conn)
    
    try:
        # READ run info (read-only)
        run = db.query(Run).filter(Run.id == run_id).first()
        if not run:
            raise ValueError(f"Run {run_id} not found")
        
        logger.info(f"🚀 Starting processing for run {run_id}")
        
        # EMIT run started event (API will update status)
        emitter.emit_run_started(run_id)
        start_time = datetime.utcnow()
        
        # READ documents to process (read-only)
        documents = db.query(Document).filter(
            Document.run_id == run_id
        ).all()
        
        if not documents:
            logger.warning(f"No documents found for run {run_id}")
            emitter.emit_run_failed(run_id, "No documents to process")
            return {"error": "No documents to process"}
        
        # Initialize pipeline
        pipeline = LegalEventsPipeline(
            provider=provider,
            model_override=model,
            store_artifacts=True
        )
        
        # Track processing stats
        stats = {
            "documents_processed": 0,
            "documents_success": 0,
            "documents_failed": 0,
            "events_extracted": 0,
            "artifacts_created": 0,
            "docling_seconds": 0,
            "extractor_seconds": 0,
            "cost_usd": 0.0
        }
        
        # Process each document
        for doc in documents:
            try:
                logger.info(f"📄 Processing document {doc.id}: {doc.filename}")
                
                # EMIT document started event
                emitter.emit_document_started(run_id, doc.id)
                doc_start = time.time()
                
                # Download document from storage
                _, ext = os.path.splitext(doc.filename)
                with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                    tmp_path = tmp.name
                    storage.download_file(doc.storage_key, tmp_path)
                
                # Process with pipeline
                emitter.emit_progress(run_id, f"Extracting text from {doc.filename}", doc.id)
                
                results = pipeline.process_documents(
                    file_paths=[tmp_path],
                    output_dir=tempfile.mkdtemp(),
                    case_name=f"run_{run_id}"
                )
                
                # WRITE events (worker's primary output)
                events_created = 0
                if results and results.get("events"):
                    for event_data in results["events"]:
                        event = Event(
                            run_id=run_id,
                            document_id=doc.id,
                            event_type=event_data.get("event_type", "Unknown"),
                            event_date=event_data.get("date"),
                            description=event_data.get("description"),
                            parties=json.dumps(event_data.get("parties", [])),
                            metadata=event_data
                        )
                        db.add(event)
                        db.commit()
                        events_created += 1
                        emitter.emit_event_created(run_id, event.id, doc.id)
                
                # WRITE artifacts (worker's secondary output)
                if results and results.get("artifacts"):
                    for artifact_path in results["artifacts"]:
                        # Upload to storage
                        artifact_key = f"runs/{run_id}/artifacts/{os.path.basename(artifact_path)}"
                        storage.upload_file(artifact_path, artifact_key)
                        
                        # Create artifact record
                        artifact = Artifact(
                            run_id=run_id,
                            document_id=doc.id,
                            artifact_type="extraction_output",
                            storage_key=artifact_key,
                            metadata={"source_document": doc.filename}
                        )
                        db.add(artifact)
                        db.commit()
                        stats["artifacts_created"] += 1
                        emitter.emit_artifact_created(run_id, artifact.id, doc.id)
                
                # Update stats
                doc_time = time.time() - doc_start
                stats["documents_success"] += 1
                stats["events_extracted"] += events_created
                
                # EMIT document completed event
                emitter.emit_document_completed(run_id, doc.id, {
                    "pages": results.get("pages", 0),
                    "ocr_detected": results.get("ocr_detected", False),
                    "processing_time_seconds": doc_time,
                    "events_created": events_created
                })
                
                # Clean up temp file
                os.unlink(tmp_path)
                
            except Exception as e:
                logger.error(f"Failed to process document {doc.id}: {e}")
                stats["documents_failed"] += 1
                
                # EMIT document failed event
                emitter.emit_document_failed(run_id, doc.id, str(e))
            
            finally:
                stats["documents_processed"] += 1
        
        # Calculate final stats
        end_time = datetime.utcnow()
        total_time = (end_time - start_time).total_seconds()
        
        # Get pipeline metrics if available
        if hasattr(pipeline, 'get_metrics'):
            metrics = pipeline.get_metrics()
            stats["docling_seconds"] = metrics.get("docling_time", 0)
            stats["extractor_seconds"] = metrics.get("extractor_time", 0)
            stats["cost_usd"] = metrics.get("total_cost", 0)
        
        stats["total_seconds"] = total_time
        
        # EMIT run completed event
        emitter.emit_run_completed(run_id, stats)
        
        logger.info(f"✅ Run {run_id} completed: {stats['documents_success']}/{stats['documents_processed']} successful")
        
        return {
            "success": True,
            "run_id": run_id,
            "stats": stats
        }
        
    except Exception as e:
        logger.error(f"❌ Run {run_id} failed: {e}")
        
        # EMIT run failed event
        emitter.emit_run_failed(run_id, str(e))
        
        return {
            "success": False,
            "error": str(e),
            "run_id": run_id
        }
        
    finally:
        db.close()
        redis_conn.close()


def process_document(document_id: int, provider: str = "openrouter", model: str = None) -> Dict[str, Any]:
    """
    Process a single document - Service Boundary Compliant Version
    
    This function:
    - READS document info for processing context
    - WRITES events and artifacts
    - EMITS status updates via Redis
    - NEVER mutates document status directly
    
    Args:
        document_id: Document ID to process
        provider: LLM provider to use
        model: Specific model to use
        
    Returns:
        Result dictionary
    """
    db = SessionLocal()
    storage = MinioStorage()
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    redis_conn = redis.from_url(redis_url)
    emitter = WorkerEventEmitter(redis_conn)
    
    try:
        # READ document info (read-only)
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            raise ValueError(f"Document {document_id} not found")
            
        logger.info(f"📄 Processing document {document_id}: {doc.filename}")
        
        # EMIT document started event
        emitter.emit_document_started(doc.run_id, document_id)
        start_time = time.time()
        
        # Download and process
        _, ext = os.path.splitext(doc.filename)
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp_path = tmp.name
            storage.download_file(doc.storage_key, tmp_path)
        
        # Initialize pipeline
        pipeline = LegalEventsPipeline(
            provider=provider,
            model_override=model,
            store_artifacts=True
        )
        
        # Process document
        results = pipeline.process_documents(
            file_paths=[tmp_path],
            output_dir=tempfile.mkdtemp(),
            case_name=f"doc_{document_id}"
        )
        
        # WRITE events
        events_created = 0
        if results and results.get("events"):
            for event_data in results["events"]:
                event = Event(
                    run_id=doc.run_id,
                    document_id=document_id,
                    event_type=event_data.get("event_type", "Unknown"),
                    event_date=event_data.get("date"),
                    description=event_data.get("description"),
                    parties=json.dumps(event_data.get("parties", [])),
                    metadata=event_data
                )
                db.add(event)
                db.commit()
                events_created += 1
                emitter.emit_event_created(doc.run_id, event.id, document_id)
        
        # Calculate processing time
        processing_time = time.time() - start_time
        
        # EMIT document completed event
        emitter.emit_document_completed(doc.run_id, document_id, {
            "processing_time_seconds": processing_time,
            "events_created": events_created,
            "pages": results.get("pages", 0),
            "ocr_detected": results.get("ocr_detected", False)
        })
        
        # Clean up
        os.unlink(tmp_path)
        
        logger.info(f"✅ Document {document_id} processed: {events_created} events extracted")
        
        return {
            "success": True,
            "document_id": document_id,
            "events_created": events_created,
            "processing_time": processing_time
        }
        
    except Exception as e:
        logger.error(f"❌ Document {document_id} processing failed: {e}")
        
        # EMIT document failed event
        if 'doc' in locals():
            emitter.emit_document_failed(doc.run_id, document_id, str(e))
        
        return {
            "success": False,
            "document_id": document_id,
            "error": str(e)
        }
        
    finally:
        db.close()
        redis_conn.close()


def export_run_events(run_id: int, format: str = "csv") -> Dict[str, Any]:
    """
    Export events for a run - READ-ONLY operation
    
    This function only reads data and creates export artifacts.
    It does not mutate any API-owned entities.
    
    Args:
        run_id: Run ID to export
        format: Export format (csv, xlsx, json)
        
    Returns:
        Export result with artifact info
    """
    db = SessionLocal()
    storage = MinioStorage()
    
    try:
        # READ events (read-only)
        events = db.query(Event).filter(Event.run_id == run_id).all()
        
        if not events:
            return {"error": "No events found for run"}
        
        # READ case info for export metadata
        run = db.query(Run).filter(Run.id == run_id).first()
        case = db.query(Case).filter(Case.id == run.case_id).first() if run else None
        client = db.query(Client).filter(Client.id == case.client_id).first() if case else None
        
        # Prepare export data
        export_data = []
        for event in events:
            doc = db.query(Document).filter(Document.id == event.document_id).first()
            export_data.append({
                "Event ID": event.id,
                "Document": doc.filename if doc else "Unknown",
                "Event Type": event.event_type,
                "Date": event.event_date,
                "Description": event.description,
                "Parties": event.parties,
                "Extracted At": event.created_at
            })
        
        # Create DataFrame
        df = pd.DataFrame(export_data)
        
        # Generate export file
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        
        if format == "csv":
            filename = f"events_run_{run_id}_{timestamp}.csv"
            with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as tmp:
                df.to_csv(tmp.name, index=False)
                tmp_path = tmp.name
                
        elif format == "xlsx":
            filename = f"events_run_{run_id}_{timestamp}.xlsx"
            with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
                with pd.ExcelWriter(tmp.name, engine='openpyxl') as writer:
                    df.to_excel(writer, sheet_name='Events', index=False)
                    
                    # Add metadata sheet
                    metadata_df = pd.DataFrame([{
                        "Run ID": run_id,
                        "Client": client.name if client else "Unknown",
                        "Case": case.name if case else "Unknown",
                        "Export Date": datetime.utcnow(),
                        "Total Events": len(events)
                    }])
                    metadata_df.to_excel(writer, sheet_name='Metadata', index=False)
                tmp_path = tmp.name
                
        elif format == "json":
            filename = f"events_run_{run_id}_{timestamp}.json"
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp:
                json.dump({
                    "metadata": {
                        "run_id": run_id,
                        "client": client.name if client else "Unknown",
                        "case": case.name if case else "Unknown",
                        "export_date": datetime.utcnow().isoformat(),
                        "total_events": len(events)
                    },
                    "events": export_data
                }, tmp, indent=2, default=str)
                tmp_path = tmp.name
        else:
            return {"error": f"Unsupported format: {format}"}
        
        # Upload to storage
        artifact_key = f"runs/{run_id}/exports/{filename}"
        storage.upload_file(tmp_path, artifact_key)
        
        # WRITE artifact record (worker output)
        artifact = Artifact(
            run_id=run_id,
            artifact_type=f"export_{format}",
            storage_key=artifact_key,
            metadata={
                "format": format,
                "events_count": len(events),
                "exported_at": datetime.utcnow().isoformat()
            }
        )
        db.add(artifact)
        db.commit()
        
        # Clean up
        os.unlink(tmp_path)
        
        return {
            "success": True,
            "artifact_id": artifact.id,
            "storage_key": artifact_key,
            "events_count": len(events),
            "format": format
        }
        
    except Exception as e:
        logger.error(f"Export failed for run {run_id}: {e}")
        return {"error": str(e)}
        
    finally:
        db.close()