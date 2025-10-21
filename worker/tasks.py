"""
Background Worker Tasks
Processes documents using the existing legal pipeline
"""

import os
import logging
import tempfile
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
import pandas as pd
import json
from sqlalchemy.orm import Session

# Import existing pipeline
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from core.legal_pipeline_refactored import LegalEventsPipeline
from core.constants import FIVE_COLUMN_HEADERS

# Import v2 components
from ..api.database import SessionLocal
from ..api.models import (
    Run, RunStatus, Document, DocumentStatus, Event, Artifact,
    Case, Client
)
from ..api.storage import MinioStorage
from ..api.queue import JobProgress

logger = logging.getLogger(__name__)


def process_run(run_id: int, provider: str = "openrouter", model: str = None) -> Dict[str, Any]:
    """
    Process all documents in a run
    
    Args:
        run_id: Run ID to process
        provider: LLM provider to use
        model: Specific model to use
        
    Returns:
        Result dictionary with stats
    """
    db = SessionLocal()
    storage = MinioStorage()
    
    try:
        # Get run and documents
        run = db.query(Run).filter(Run.id == run_id).first()
        if not run:
            raise ValueError(f"Run {run_id} not found")
        
        logger.info(f"🚀 Starting processing for run {run_id}")
        
        # Update run status
        run.status = RunStatus.PROCESSING
        run.started_at = datetime.utcnow()
        db.commit()
        
        # Get documents to process
        documents = db.query(Document).filter(
            Document.run_id == run_id,
            Document.status == DocumentStatus.PENDING
        ).all()
        
        logger.info(f"📄 Processing {len(documents)} documents")
        
        # Initialize pipeline with specified provider
        pipeline = LegalEventsPipeline(
            event_extractor=provider,
            runtime_model=model
        )
        
        # Track results
        total_docs = len(documents)
        processed = 0
        failed = 0
        total_events = 0
        total_docling_time = 0
        total_extractor_time = 0
        
        # Process each document
        for doc in documents:
            try:
                logger.info(f"Processing document: {doc.filename}")
                
                # Update document status
                doc.status = DocumentStatus.PROCESSING
                db.commit()
                
                # Download document from storage
                with tempfile.NamedTemporaryFile(suffix=os.path.splitext(doc.filename)[1]) as tmp_file:
                    # Download from MinIO
                    storage.download_file(doc.storage_key, tmp_file.name)
                    
                    # Create a file-like object compatible with the pipeline
                    class FileWrapper:
                        def __init__(self, path, name):
                            self.name = name
                            self._path = path
                        
                        def getbuffer(self):
                            with open(self._path, 'rb') as f:
                                return f.read()
                    
                    file_obj = FileWrapper(tmp_file.name, doc.filename)
                    
                    # Process with pipeline
                    start_time = time.time()
                    
                    # Process single document
                    df, metadata = pipeline.process_documents(
                        [file_obj],
                        case_name=f"Run_{run_id}"
                    )
                    
                    processing_time = time.time() - start_time
                    
                    # Extract timing from metadata
                    if metadata and "performance" in metadata:
                        perf = metadata["performance"]
                        docling_time = perf.get("docling_time", 0)
                        extractor_time = perf.get("extractor_time", 0)
                        total_docling_time += docling_time
                        total_extractor_time += extractor_time
                    else:
                        docling_time = 0
                        extractor_time = processing_time
                        total_extractor_time += extractor_time
                    
                    # Update document with extracted text (cache)
                    if metadata and "extracted_text" in metadata:
                        doc.extracted_text = metadata["extracted_text"][:10000]  # Limit size
                    
                    # Save events to database
                    event_number = 1
                    for _, row in df.iterrows():
                        event = Event(
                            run_id=run_id,
                            document_id=doc.id,
                            number=event_number,
                            date=str(row.get("Date", "")),
                            event_particulars=str(row.get("Event Particulars", "")),
                            citation=str(row.get("Citation", "")),
                            document_reference=doc.filename  # Use actual filename
                        )
                        db.add(event)
                        event_number += 1
                        total_events += 1
                    
                    # Update document status
                    doc.status = DocumentStatus.SUCCESS
                    doc.processed_at = datetime.utcnow()
                    doc.processing_time_seconds = processing_time
                    doc.pages = metadata.get("pages", 0) if metadata else 0
                    doc.ocr_detected = metadata.get("ocr_detected", False) if metadata else False
                    
                    processed += 1
                    logger.info(f"✅ Processed {doc.filename}: {len(df)} events extracted")
                    
            except Exception as e:
                logger.error(f"❌ Failed to process {doc.filename}: {str(e)}")
                doc.status = DocumentStatus.FAILED
                doc.error = str(e)
                failed += 1
            
            finally:
                db.commit()
        
        # Calculate final status
        if processed == total_docs:
            final_status = RunStatus.SUCCESS
        elif processed > 0:
            final_status = RunStatus.PARTIAL_SUCCESS
        else:
            final_status = RunStatus.FAILED
        
        # Calculate cost estimate (rough)
        # Assuming ~1000 tokens per page, ~2 pages per doc average
        estimated_tokens = processed * 2000
        cost_per_million = 0.52  # Default for Llama 3.3 70B
        estimated_cost = (estimated_tokens / 1_000_000) * cost_per_million * 2  # Input + output
        
        # Update run with final stats
        run.status = final_status
        run.finished_at = datetime.utcnow()
        run.docling_seconds = total_docling_time
        run.extractor_seconds = total_extractor_time
        run.total_seconds = (run.finished_at - run.started_at).total_seconds()
        run.cost_usd = estimated_cost
        
        # Add metadata
        run.metadata = {
            "total_documents": total_docs,
            "processed": processed,
            "failed": failed,
            "total_events": total_events,
            "provider": provider,
            "model": model
        }
        
        db.commit()
        
        # Generate artifacts (exports)
        generate_artifacts(run_id)
        
        logger.info(f"✅ Run {run_id} complete: {processed}/{total_docs} docs, {total_events} events")
        
        return {
            "run_id": run_id,
            "status": final_status.value,
            "processed": processed,
            "failed": failed,
            "total_events": total_events,
            "duration_seconds": run.total_seconds
        }
        
    except Exception as e:
        logger.error(f"❌ Run {run_id} failed: {str(e)}")
        
        # Update run status to failed
        run = db.query(Run).filter(Run.id == run_id).first()
        if run:
            run.status = RunStatus.FAILED
            run.error = str(e)
            run.finished_at = datetime.utcnow()
            db.commit()
        
        raise
    
    finally:
        db.close()


def process_document(
    document_id: int,
    provider: str = "openrouter",
    model: str = None
) -> Dict[str, Any]:
    """
    Process a single document (for retries or individual processing)
    
    Args:
        document_id: Document ID
        provider: LLM provider
        model: Specific model
        
    Returns:
        Result dictionary
    """
    db = SessionLocal()
    storage = MinioStorage()
    
    try:
        # Get document
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            raise ValueError(f"Document {document_id} not found")
        
        logger.info(f"📄 Processing single document: {doc.filename}")
        
        # Initialize pipeline
        pipeline = LegalEventsPipeline(
            event_extractor=provider,
            runtime_model=model
        )
        
        # Download and process
        with tempfile.NamedTemporaryFile(suffix=os.path.splitext(doc.filename)[1]) as tmp_file:
            storage.download_file(doc.storage_key, tmp_file.name)
            
            # Create file wrapper
            class FileWrapper:
                def __init__(self, path, name):
                    self.name = name
                    self._path = path
                
                def getbuffer(self):
                    with open(self._path, 'rb') as f:
                        return f.read()
            
            file_obj = FileWrapper(tmp_file.name, doc.filename)
            
            # Process
            df, metadata = pipeline.process_documents(
                [file_obj],
                case_name=f"Doc_{document_id}"
            )
            
            # Delete existing events for this document
            db.query(Event).filter(Event.document_id == document_id).delete()
            
            # Save new events
            event_number = 1
            for _, row in df.iterrows():
                event = Event(
                    run_id=doc.run_id,
                    document_id=document_id,
                    number=event_number,
                    date=str(row.get("Date", "")),
                    event_particulars=str(row.get("Event Particulars", "")),
                    citation=str(row.get("Citation", "")),
                    document_reference=doc.filename
                )
                db.add(event)
                event_number += 1
            
            # Update document
            doc.status = DocumentStatus.SUCCESS
            doc.processed_at = datetime.utcnow()
            doc.error = None
            
            db.commit()
            
            logger.info(f"✅ Processed {doc.filename}: {len(df)} events")
            
            return {
                "document_id": document_id,
                "filename": doc.filename,
                "events_extracted": len(df),
                "status": "success"
            }
            
    except Exception as e:
        logger.error(f"❌ Failed to process document {document_id}: {str(e)}")
        
        # Update document status
        doc = db.query(Document).filter(Document.id == document_id).first()
        if doc:
            doc.status = DocumentStatus.FAILED
            doc.error = str(e)
            db.commit()
        
        raise
    
    finally:
        db.close()


def generate_artifacts(run_id: int) -> Dict[str, str]:
    """
    Generate export artifacts (CSV, XLSX, JSON) for a run
    
    Args:
        run_id: Run ID
        
    Returns:
        Dictionary of artifact types and their storage keys
    """
    db = SessionLocal()
    storage = MinioStorage()
    
    try:
        # Get run and events
        run = db.query(Run).filter(Run.id == run_id).first()
        if not run:
            raise ValueError(f"Run {run_id} not found")
        
        events = db.query(Event).filter(Event.run_id == run_id).order_by(Event.number).all()
        
        if not events:
            logger.warning(f"No events found for run {run_id}")
            return {}
        
        # Get case and client for path
        case = db.query(Case).filter(Case.id == run.case_id).first()
        client = db.query(Client).filter(Client.id == case.client_id).first()
        
        # Prepare data
        data = []
        for event in events:
            data.append({
                "No": event.number,
                "Date": event.date,
                "Event Particulars": event.event_particulars,
                "Citation": event.citation,
                "Document Reference": event.document_reference
            })
        
        df = pd.DataFrame(data)
        artifacts = {}
        
        # Generate CSV
        csv_path = f"clients/{client.id}/cases/{case.id}/runs/{run_id}/artifacts/{run_id}.csv"
        csv_content = df.to_csv(index=False)
        storage.upload_bytes(csv_path, csv_content.encode('utf-8'), "text/csv")
        
        artifact = Artifact(
            run_id=run_id,
            kind="csv",
            storage_key=csv_path,
            size_bytes=len(csv_content.encode('utf-8'))
        )
        db.add(artifact)
        artifacts["csv"] = csv_path
        
        # Generate XLSX
        import io
        xlsx_path = f"clients/{client.id}/cases/{case.id}/runs/{run_id}/artifacts/{run_id}.xlsx"
        xlsx_buffer = io.BytesIO()
        
        with pd.ExcelWriter(xlsx_buffer, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Legal Events', index=False)
            
            # Auto-adjust column widths
            worksheet = writer.sheets['Legal Events']
            for column in df:
                column_width = max(df[column].astype(str).map(len).max(), len(column))
                col_idx = df.columns.get_loc(column)
                worksheet.column_dimensions[chr(65 + col_idx)].width = min(column_width + 2, 50)
        
        xlsx_content = xlsx_buffer.getvalue()
        storage.upload_bytes(xlsx_path, xlsx_content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        
        artifact = Artifact(
            run_id=run_id,
            kind="xlsx",
            storage_key=xlsx_path,
            size_bytes=len(xlsx_content)
        )
        db.add(artifact)
        artifacts["xlsx"] = xlsx_path
        
        # Generate JSON
        json_path = f"clients/{client.id}/cases/{case.id}/runs/{run_id}/artifacts/{run_id}.json"
        json_content = json.dumps(data, indent=2)
        storage.upload_bytes(json_path, json_content.encode('utf-8'), "application/json")
        
        artifact = Artifact(
            run_id=run_id,
            kind="json",
            storage_key=json_path,
            size_bytes=len(json_content.encode('utf-8'))
        )
        db.add(artifact)
        artifacts["json"] = json_path
        
        db.commit()
        
        logger.info(f"📁 Generated artifacts for run {run_id}: {list(artifacts.keys())}")
        return artifacts
        
    except Exception as e:
        logger.error(f"Failed to generate artifacts: {str(e)}")
        raise
    
    finally:
        db.close()


def cleanup_old_runs(days: int = 90) -> int:
    """
    Clean up old runs and their data
    
    Args:
        days: Delete runs older than this many days
        
    Returns:
        Number of runs deleted
    """
    db = SessionLocal()
    storage = MinioStorage()
    
    try:
        from datetime import timedelta
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Find old runs
        old_runs = db.query(Run).filter(Run.created_at < cutoff_date).all()
        
        count = 0
        for run in old_runs:
            # Get case for storage paths
            case = db.query(Case).filter(Case.id == run.case_id).first()
            if not case:
                continue
            
            # Delete storage objects
            prefix = f"clients/{case.client_id}/cases/{case.id}/runs/{run.id}/"
            objects = storage.list_objects(prefix)
            
            for obj in objects:
                storage.delete_object(obj)
            
            # Delete database records (cascades to documents, events, artifacts)
            db.delete(run)
            count += 1
        
        db.commit()
        
        logger.info(f"🧹 Cleaned up {count} old runs")
        return count
        
    except Exception as e:
        logger.error(f"Failed to cleanup old runs: {str(e)}")
        db.rollback()
        return 0
    
    finally:
        db.close()
