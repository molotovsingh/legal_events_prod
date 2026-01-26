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
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import pandas as pd
import json
import redis
from sqlalchemy.orm import Session

# Import from legal_events_core package (private extraction engine)
from legal_events_core import (
    LegalEventsPipeline,
    count_text,
    TokenizerUnavailable,
    FIVE_COLUMN_HEADERS,
)

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
    redis_conn = None
    try:
        redis_conn = redis.from_url(redis_url)
    except Exception as e:
        logger.error(f"Failed to create Redis connection: {e}")
        # Continue without emitter; API will not receive progress events
    emitter = WorkerEventEmitter(redis_conn) if redis_conn else None
    
    try:
        # READ run info (read-only)
        run = db.query(Run).filter(Run.id == run_id).first()
        if not run:
            raise ValueError(f"Run {run_id} not found")
        
        logger.info(f"🚀 Starting processing for run {run_id}")
        
        # EMIT run started event (API will update status)
        if emitter:
            emitter.emit_run_started(run_id)
        start_time = datetime.utcnow()
        
        # READ documents to process (read-only) - includes failed docs for retry
        # Query PENDING and FAILED documents (allows automatic retry)
        # Load retry configuration for stuck document threshold
        from legal_events_core import RetryConfig
        retry_config = RetryConfig()
        stuck_threshold_hours = retry_config.stuck_document_hours
        
        # Query documents to process: PENDING and FAILED (aligned with API retry logic)
        documents = db.query(Document).filter(
            Document.run_id == run_id,
            Document.status.in_([DocumentStatus.PENDING, DocumentStatus.FAILED])
        ).all()
        
        # If no pending/failed, check for stuck PROCESSING documents (configurable threshold)
        if not documents:
            logger.info(f"No pending/failed documents for run {run_id}, checking for stuck documents (>{stuck_threshold_hours}h)...")
            stuck_documents = db.query(Document).filter(
                Document.run_id == run_id,
                Document.status == DocumentStatus.PROCESSING,
                Document.created_at < datetime.utcnow() - timedelta(hours=stuck_threshold_hours)
            ).all()
            
            if stuck_documents:
                logger.warning(f"Found {len(stuck_documents)} stuck PROCESSING documents (>{stuck_threshold_hours}h) for run {run_id}")
                documents = stuck_documents
        
        if not documents:
            logger.warning(f"No documents to process for run {run_id} (no pending, failed, or stuck docs)")
            if emitter:
                emitter.emit_run_failed(run_id, "No documents to process")
            return {"error": "No documents to process"}
        
        # Initialize pipeline with doc_extractor from run configuration
        doc_extractor = getattr(run, 'doc_extractor', None) or 'docling'  # Default to docling
        logger.info(f"🔧 Initializing pipeline: doc_extractor={doc_extractor}, event_extractor={provider}, model={model}")
        
        pipeline = LegalEventsPipeline(
            event_extractor=provider,
            runtime_model=model,
            doc_extractor=doc_extractor
        )

        # Optional document classification (Layer 1.5)
        classification_enabled = False
        classification_model = None
        classifier = None
        try:
            meta = getattr(run, 'run_metadata', None) or {}
            classification_enabled = bool(meta.get('enable_classification', False))
            classification_model = meta.get('classification_model')
            if classification_enabled:
                # Default to recommended Llama 70B if not specified
                classification_model = classification_model or 'meta-llama/llama-3.3-70b-instruct'
                from legal_events_core.prompts.classification_factory import create_classifier
                from legal_events_core.prompts.prompt_registry import get_default_variant
                classifier = create_classifier(
                    model_id=classification_model,
                    prompt_variant=get_default_variant()
                )
                logger.info(f"🧭 Classification enabled with model: {classification_model}")
        except Exception as e:
            logger.warning(f"Classification disabled due to error initializing classifier: {e}")
            classification_enabled = False
        
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
        classification_results = {}
        token_usage = {}
        total_event_prompt = 0
        total_event_completion = 0
        total_cls_prompt = 0
        total_cls_completion = 0
        for doc in documents:
            tmp_path = None
            try:
                logger.info(f"📄 Processing document {doc.id}: {doc.filename}")
                
                # EMIT document started event
                if emitter:
                    emitter.emit_document_started(run_id, doc.id)
                doc_start = time.time()
                
                # Download document from storage
                _, ext = os.path.splitext(doc.filename)
                with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                    tmp_path = tmp.name
                    storage.download_file(doc.storage_key, tmp_path)
                
                # Process with pipeline
                if emitter:
                    emitter.emit_progress(run_id, f"Extracting text from {doc.filename}", doc.id)
                
                # Create a file-like object for the pipeline
                class FileWrapper:
                    def __init__(self, path, name):
                        with open(path, 'rb') as f:
                            self.content = f.read()
                        self.name = name
                    def read(self):
                        return self.content
                    def getbuffer(self):
                        """Return buffer for compatibility with pipeline cache key generation"""
                        return self.content
                
                file_obj = FileWrapper(tmp_path, doc.filename)
                df, warning = pipeline.process_documents_for_legal_events([file_obj])

                # Extract plain text once for token counting fallbacks and classification
                from pathlib import Path as _P
                extracted_doc = pipeline.document_extractor.extract(_P(tmp_path))
                extracted_text = extracted_doc.plain_text or extracted_doc.markdown or ''

                # If classification is enabled, run it on the extracted text
                if classification_enabled and classifier is not None:
                    try:
                        text_for_cls = extracted_text
                        cls_result = classifier.classify(text_for_cls, document_title=doc.filename)
                        # Persist in memory; uploaded as artifact at end of run
                        classification_results[doc.filename] = {
                            'primary': cls_result.get('primary'),
                            'confidence': cls_result.get('confidence'),
                            'model': cls_result.get('model'),
                            'prompt_version': cls_result.get('prompt_version'),
                            'prompt_tokens': cls_result.get('prompt_tokens'),
                            'completion_tokens': cls_result.get('completion_tokens')
                        }
                        # Accumulate classifier token usage if present
                        if cls_result.get('prompt_tokens') is not None:
                            total_cls_prompt += int(cls_result.get('prompt_tokens') or 0)
                        if cls_result.get('completion_tokens') is not None:
                            total_cls_completion += int(cls_result.get('completion_tokens') or 0)
                    except Exception as ce:
                        logger.warning(f"Classification skipped for {doc.filename}: {ce}")

                # Convert DataFrame to event records
                # CRITICAL: Rename display headers back to internal field names
                if not df.empty:
                    from legal_events_core import FIVE_COLUMN_HEADERS, INTERNAL_FIELDS

                    # Create column mapping from display to internal names
                    column_mapping = {
                        FIVE_COLUMN_HEADERS[0]: INTERNAL_FIELDS[0],  # "No" -> "number"
                        FIVE_COLUMN_HEADERS[1]: INTERNAL_FIELDS[1],  # "Date" -> "date"
                        FIVE_COLUMN_HEADERS[2]: INTERNAL_FIELDS[2],  # "Event Particulars" -> "event_particulars"
                        FIVE_COLUMN_HEADERS[3]: INTERNAL_FIELDS[3],  # "Citation" -> "citation"
                        FIVE_COLUMN_HEADERS[4]: INTERNAL_FIELDS[4],  # "Document Reference" -> "document_reference"
                    }

                    # Rename only the columns that exist in the DataFrame
                    df_renamed = df.rename(columns={k: v for k, v in column_mapping.items() if k in df.columns})

                    results = {"events": df_renamed.to_dict('records')}
                else:
                    results = {"events": []}
                
                # WRITE events (worker's primary output)
                # Batch all events into single transaction
                events_created = 0
                # Always try to capture event token usage, even if no events were extracted
                try:
                    ev_usage = None
                    if results and results.get("events") and len(results["events"]) > 0:
                        first = results["events"][0]
                        ev_usage = first.get("usage")
                    if ev_usage:
                        ev_prompt = int(ev_usage.get("prompt_tokens") or 0)
                        ev_completion = int(ev_usage.get("completion_tokens") or 0)
                        total_event_prompt += ev_prompt
                        total_event_completion += ev_completion
                        token_usage[str(doc.id)] = token_usage.get(str(doc.id), {})
                        token_usage[str(doc.id)]["event"] = {
                            "prompt_tokens": ev_prompt,
                            "completion_tokens": ev_completion
                        }
                    else:
                        # Fallback: count prompt tokens from extracted text when no events/usage present
                        try:
                            ev_prompt = count_text(extracted_text, provider, model)
                            total_event_prompt += ev_prompt
                            token_usage[str(doc.id)] = token_usage.get(str(doc.id), {})
                            token_usage[str(doc.id)]["event"] = {
                                "prompt_tokens": ev_prompt,
                                "completion_tokens": 0
                            }
                        except Exception:
                            pass
                except Exception:
                    pass

                if results and results.get("events"):
                    events_to_add = []
                    try:
                        # Collect all event objects first (no database operations yet)
                        for event_data in results["events"]:
                            event = Event(
                                run_id=run_id,
                                document_id=doc.id,
                                number=event_data.get("number", len(events_to_add) + 1),
                                date=event_data.get("date", "Date not available"),
                                event_particulars=event_data.get("event_particulars", ""),
                                citation=event_data.get("citation", ""),
                                document_reference=event_data.get("document_reference", doc.filename),
                                confidence_score=event_data.get("confidence_score")
                            )
                            events_to_add.append(event)
                        # (Token usage already captured above; nothing to do here.)
                        
                        # Single atomic operation: add all events and commit
                        if events_to_add:
                            db.add_all(events_to_add)
                            db.commit()
                            events_created = len(events_to_add)
                            
                            # Emit Redis events AFTER successful commit
                            if emitter:
                                for event in events_to_add:
                                    emitter.emit_event_created(run_id, event.id, doc.id)
                    except Exception as e:
                        db.rollback()
                        logger.error(f"Failed to persist events for document {doc.id}: {e}")
                        raise
                
                # WRITE artifacts (worker's secondary output)
                # Note: The pipeline doesn't produce artifacts in this mode
                # Artifacts are only created when explicitly exporting
                
                # Update stats
                doc_time = time.time() - doc_start
                stats["documents_success"] += 1
                stats["events_extracted"] += events_created
                
                # EMIT document completed event
                if emitter:
                    emitter.emit_document_completed(run_id, doc.id, {
                        "pages": 0,  # Not tracked by pipeline
                        "ocr_detected": False,  # Not tracked by pipeline
                        "processing_time_seconds": doc_time,
                        "events_created": events_created
                    })
                
            except Exception as e:
                logger.error(f"Failed to process document {doc.id}: {e}")
                stats["documents_failed"] += 1
                
                # EMIT document failed event
                if emitter:
                    emitter.emit_document_failed(run_id, doc.id, str(e))
            
            finally:
                stats["documents_processed"] += 1
                # Ensure temporary file cleanup
                try:
                    if tmp_path and os.path.exists(tmp_path):
                        os.unlink(tmp_path)
                except Exception as _e:
                    logger.warning(f"Failed to cleanup temp file {tmp_path}: {_e}")
        
        # Calculate final stats
        # Compute cost from model catalog pricing
        try:
            from legal_events_core.prompts.model_catalog import get_model_catalog
            catalog = get_model_catalog()
            pricing_ev = catalog.get_pricing(model)
            ev_in = float(pricing_ev["cost_input_per_1m"]) if pricing_ev else 0.0
            ev_out = float(pricing_ev["cost_output_per_1m"]) if pricing_ev else 0.0
        except Exception:
            ev_in = 0.0
            ev_out = 0.0
        cls_in = 0.0
        cls_out = 0.0
        if classification_enabled and classification_model:
            try:
                from legal_events_core.prompts.model_catalog import get_model_catalog
                catalog = get_model_catalog()
                pricing_cls = catalog.get_pricing(classification_model)
                cls_in = float(pricing_cls["cost_input_per_1m"]) if pricing_cls else 0.0
                cls_out = float(pricing_cls["cost_output_per_1m"]) if pricing_cls else 0.0
            except Exception:
                pass

        cost_usd = (
            (total_event_prompt/1_000_000.0) * ev_in + (total_event_completion/1_000_000.0) * ev_out +
            (total_cls_prompt/1_000_000.0) * cls_in + (total_cls_completion/1_000_000.0) * cls_out
        )

        # Persist token usage artifact
        try:
            usage_payload = {
                "per_document": token_usage,
                "totals": {
                    "event_prompt_tokens": total_event_prompt,
                    "event_completion_tokens": total_event_completion,
                    "classification_prompt_tokens": total_cls_prompt,
                    "classification_completion_tokens": total_cls_completion,
                    "cost_usd": cost_usd
                },
                "models": {
                    "event": model,
                    "classification": classification_model if classification_enabled else None
                }
            }
            key = f"runs/{run_id}/artifacts/token_usage.json"
            storage.upload_bytes(key, json.dumps(usage_payload).encode('utf-8'))
            artifact = Artifact(
                run_id=run_id,
                kind='token_usage_json',
                storage_key=key,
                size_bytes=len(json.dumps(usage_payload))
            )
            db.add(artifact)
            db.commit()
            stats["artifacts_created"] += 1
        except Exception as e:
            db.rollback()
            logger.warning(f"Failed to persist token usage artifact: {e}")

        # Persist classification results artifact (if any)
        try:
            if classification_results:
                # Build storage key and save JSON
                case = db.query(Case).filter(Case.id == run.case_id).first()
                client_id = case.client_id if case else 0
                cls_key = f"clients/{client_id}/cases/{run.case_id}/runs/{run_id}/artifacts/classification.json"
                storage.upload_bytes(cls_key, json.dumps(classification_results).encode('utf-8'))
                cls_artifact = Artifact(
                    run_id=run_id,
                    kind='classification_json',
                    storage_key=cls_key,
                    size_bytes=len(json.dumps(classification_results))
                )
                db.add(cls_artifact)
                db.commit()
                stats["artifacts_created"] += 1
        except Exception as e:
            db.rollback()
            logger.warning(f"Failed to persist classification artifact: {e}")

        # Update run metadata and cost
        try:
            meta = run.run_metadata or {}
            meta["token_usage"] = {
                "event_prompt": total_event_prompt,
                "event_completion": total_event_completion,
                "classification_prompt": total_cls_prompt,
                "classification_completion": total_cls_completion,
                "cost_usd": cost_usd
            }
            run.run_metadata = meta
            run.cost_usd = cost_usd
            db.commit()
        except Exception as e:
            db.rollback()
            logger.warning(f"Failed to persist run token metadata: {e}")
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
        if emitter:
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
        if emitter:
            emitter.emit_run_failed(run_id, str(e))
        
        return {
            "success": False,
            "error": str(e),
            "run_id": run_id
        }
        
    finally:
        db.close()
        try:
            if redis_conn:
                redis_conn.close()
        except Exception:
            pass


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
    redis_conn = None
    try:
        redis_conn = redis.from_url(redis_url)
    except Exception as e:
        logger.error(f"Failed to create Redis connection: {e}")
    emitter = WorkerEventEmitter(redis_conn) if redis_conn else None
    
    try:
        # READ document info (read-only)
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            raise ValueError(f"Document {document_id} not found")
            
        logger.info(f"📄 Processing document {document_id}: {doc.filename}")
        
        # EMIT document started event
        if emitter:
            emitter.emit_document_started(doc.run_id, document_id)
        start_time = time.time()
        
        # Download and process
        tmp_path = None
        _, ext = os.path.splitext(doc.filename)
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp_path = tmp.name
            storage.download_file(doc.storage_key, tmp_path)
        
        # Initialize pipeline
        pipeline = LegalEventsPipeline(
            event_extractor=provider,
            runtime_model=model,
            doc_extractor=None  # Use default
        )
        
        # Process document
        # Create a file-like object for the pipeline
        class FileWrapper:
            def __init__(self, path, name):
                with open(path, 'rb') as f:
                    self.content = f.read()
                self.name = name
            def read(self):
                return self.content
        
        file_obj = FileWrapper(tmp_path, doc.filename)
        df, warning = pipeline.process_documents_for_legal_events([file_obj])

        # Convert DataFrame to event records
        # CRITICAL: Rename display headers back to internal field names
        if not df.empty:
            from legal_events_core import FIVE_COLUMN_HEADERS, INTERNAL_FIELDS

            # Create column mapping from display to internal names
            column_mapping = {
                FIVE_COLUMN_HEADERS[0]: INTERNAL_FIELDS[0],  # "No" -> "number"
                FIVE_COLUMN_HEADERS[1]: INTERNAL_FIELDS[1],  # "Date" -> "date"
                FIVE_COLUMN_HEADERS[2]: INTERNAL_FIELDS[2],  # "Event Particulars" -> "event_particulars"
                FIVE_COLUMN_HEADERS[3]: INTERNAL_FIELDS[3],  # "Citation" -> "citation"
                FIVE_COLUMN_HEADERS[4]: INTERNAL_FIELDS[4],  # "Document Reference" -> "document_reference"
            }

            # Rename only the columns that exist in the DataFrame
            df_renamed = df.rename(columns={k: v for k, v in column_mapping.items() if k in df.columns})

            results = {"events": df_renamed.to_dict('records')}
        else:
            results = {"events": []}
        
        # WRITE events
        # Batch all events into single transaction
        events_created = 0
        if results and results.get("events"):
            events_to_add = []
            try:
                # Collect all event objects first (no database operations yet)
                for event_data in results["events"]:
                    event = Event(
                        run_id=doc.run_id,
                        document_id=document_id,
                        number=event_data.get("number", len(events_to_add) + 1),
                        date=event_data.get("date", "Date not available"),
                        event_particulars=event_data.get("event_particulars", ""),
                        citation=event_data.get("citation", ""),
                        document_reference=event_data.get("document_reference", doc.filename),
                        confidence_score=event_data.get("confidence_score")
                    )
                    events_to_add.append(event)
                
                # Single atomic operation: add all events and commit
                if events_to_add:
                    db.add_all(events_to_add)
                    db.commit()
                    events_created = len(events_to_add)
                    
                    # Emit Redis events AFTER successful commit
                    if emitter:
                        for event in events_to_add:
                            emitter.emit_event_created(doc.run_id, event.id, document_id)
            except Exception as e:
                db.rollback()
                logger.error(f"Failed to persist events for document {document_id}: {e}")
                raise
        
        # Calculate processing time
        processing_time = time.time() - start_time
        
        # EMIT document completed event
        if emitter:
            emitter.emit_document_completed(doc.run_id, document_id, {
            "processing_time_seconds": processing_time,
            "events_created": events_created,
            "pages": results.get("pages", 0),
            "ocr_detected": results.get("ocr_detected", False)
        })
        
        # Clean up handled in finally
        
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
        if 'doc' in locals() and emitter:
            emitter.emit_document_failed(doc.run_id, document_id, str(e))
        
        return {
            "success": False,
            "document_id": document_id,
            "error": str(e)
        }
        
    finally:
        # Ensure temp file cleanup
        try:
            if 'tmp_path' in locals() and tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
        except Exception as _e:
            logger.warning(f"Failed to cleanup temp file {tmp_path}: {_e}")
        db.close()
        try:
            if redis_conn:
                redis_conn.close()
        except Exception:
            pass


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
                "No": event.number,
                "Date": event.date,
                "Event Particulars": event.event_particulars,
                "Citation": event.citation,
                "Document Reference": event.document_reference,
                "Confidence Score": event.confidence_score,
                "Extracted At": event.created_at.isoformat() if event.created_at else None
            })
        
        # Create DataFrame
        df = pd.DataFrame(export_data)
        
        # Generate export file
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        
        tmp_path = None
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
        uploaded = storage.upload_file(tmp_path, artifact_key)
        if not uploaded:
            return {"error": "Failed to upload export artifact"}
        
        # WRITE artifact record (worker output)
        try:
            artifact = Artifact(
                run_id=run_id,
                kind=f"export_{format}",  # Correct field name
                storage_key=artifact_key,
                size_bytes=os.path.getsize(tmp_path) if os.path.exists(tmp_path) else 0,
                expires_at=datetime.utcnow() + timedelta(days=7)  # Optional: add expiration
            )
            db.add(artifact)
            db.commit()
        except Exception as e:
            db.rollback()
            # Roll back the uploaded object to avoid orphaned files
            try:
                storage.delete_object(artifact_key)
            except Exception as _e:
                logger.error(f"Failed to delete orphaned artifact {artifact_key}: {_e}")
            raise
        
        # Clean up temp file (best-effort)
        try:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
        except Exception as _e:
            logger.warning(f"Failed to cleanup temp file {tmp_path}: {_e}")
        
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
