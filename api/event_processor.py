"""
API Event Processor - Consumes Worker Events and Updates State

This module handles worker events and updates API-owned entities.
Maintains service boundaries by having API own all state transitions.

Features:
- Exponential backoff retry mechanism
- Dead Letter Queue (DLQ) for permanently failed events
- Configurable retry attempts (default: 3)
"""

import logging
import threading
import time
import json
from datetime import datetime
from typing import Optional
import redis
from sqlalchemy.orm import Session

from infra.database import SessionLocal
from infra.models import Run, RunStatus, Document, DocumentStatus
from infra.worker_events import WorkerEventConsumer, WorkerEvent, WorkerEventType

logger = logging.getLogger(__name__)

# Retry configuration
MAX_RETRY_ATTEMPTS = 3  # Maximum number of retry attempts
RETRY_BASE_DELAY = 1.0  # Base delay in seconds (exponential backoff: 1s, 2s, 4s)
DLQ_KEY = "worker:events:dlq"  # Redis key for Dead Letter Queue


class APIEventProcessor:
    """
    Processes worker events and updates API-owned entities.
    Runs in a background thread to consume events from Redis.
    
    Resource Management:
    - Closes Redis connection on shutdown
    - Gracefully stops consumer and background thread
    - Can be used as context manager for automatic cleanup
    """
    
    def __init__(self, redis_url: str):
        self.redis_conn = redis.from_url(redis_url)
        self.consumer = WorkerEventConsumer(self.redis_conn)
        self.thread = None
        self.running = False
    
    def __enter__(self):
        """Context manager entry"""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures cleanup"""
        self.stop()
        return False
        
    def start(self):
        """Start processing events in background thread"""
        if self.running:
            logger.warning("Event processor already running")
            return
            
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        logger.info("API Event Processor started")
        
    def stop(self):
        """Stop processing events and cleanup resources"""
        self.running = False
        self.consumer.stop()
        if self.thread:
            self.thread.join(timeout=5)
        
        # Close Redis connection to prevent resource leak
        try:
            self.redis_conn.close()
            logger.info("API Event Processor Redis connection closed")
        except Exception as e:
            logger.warning(f"Error closing Redis connection: {e}")
        
        logger.info("API Event Processor stopped")
        
    def _run(self):
        """Main event processing loop"""
        try:
            self.consumer.start(self._process_event)
        except Exception as e:
            logger.error(f"Event processor failed: {e}")
            self.running = False
            
    def _process_event(self, event: WorkerEvent):
        """
        Process a single worker event with retry mechanism.
        Updates API-owned entities based on event type.

        Retry Strategy:
        - Attempt 1: Immediate
        - Attempt 2: After 1s delay
        - Attempt 3: After 2s delay (cumulative: 3s)
        - Attempt 4: After 4s delay (cumulative: 7s)
        - If all fail: Move to DLQ
        """
        retry_count = 0
        last_error = None

        while retry_count < MAX_RETRY_ATTEMPTS:
            db: Optional[Session] = None
            try:
                db = SessionLocal()

                if event.event_type == WorkerEventType.RUN_STARTED:
                    self._handle_run_started(db, event)

                elif event.event_type == WorkerEventType.RUN_COMPLETED:
                    self._handle_run_completed(db, event)

                elif event.event_type == WorkerEventType.RUN_FAILED:
                    self._handle_run_failed(db, event)

                elif event.event_type == WorkerEventType.DOCUMENT_STARTED:
                    self._handle_document_started(db, event)

                elif event.event_type == WorkerEventType.DOCUMENT_COMPLETED:
                    self._handle_document_completed(db, event)

                elif event.event_type == WorkerEventType.DOCUMENT_FAILED:
                    self._handle_document_failed(db, event)

                elif event.event_type in [WorkerEventType.EVENT_CREATED, WorkerEventType.ARTIFACT_CREATED]:
                    # These are informational only - worker has already created the entities
                    logger.debug(f"Worker created entity: {event.event_type.value}")

                else:
                    logger.debug(f"Unhandled event type: {event.event_type.value}")

                # Success - break retry loop
                if retry_count > 0:
                    logger.info(f"Event {event.event_type.value} succeeded after {retry_count} retries")
                return

            except Exception as e:
                retry_count += 1
                last_error = e
                logger.warning(
                    f"Failed to process event {event.event_type.value} "
                    f"(attempt {retry_count}/{MAX_RETRY_ATTEMPTS}): {e}"
                )

                if retry_count < MAX_RETRY_ATTEMPTS:
                    # Exponential backoff: 1s, 2s, 4s
                    delay = RETRY_BASE_DELAY * (2 ** (retry_count - 1))
                    logger.debug(f"Retrying after {delay}s delay...")
                    time.sleep(delay)

            finally:
                if db:
                    db.close()

        # All retries exhausted - move to DLQ
        self._move_to_dlq(event, last_error)
                
    def _handle_run_started(self, db: Session, event: WorkerEvent):
        """Handle run started event"""
        run = db.query(Run).filter(Run.id == event.run_id).first()
        if run:
            run.status = RunStatus.PROCESSING
            run.started_at = event.timestamp
            db.commit()
            logger.info(f"Updated run {event.run_id} to PROCESSING")
            
    def _handle_run_completed(self, db: Session, event: WorkerEvent):
        """Handle run completed event"""
        run = db.query(Run).filter(Run.id == event.run_id).first()
        if run:
            # Determine final status based on document outcomes
            stats = event.payload or {}
            if stats.get('documents_failed', 0) == 0:
                run.status = RunStatus.SUCCESS
            elif stats.get('documents_success', 0) > 0:
                run.status = RunStatus.PARTIAL_SUCCESS
            else:
                run.status = RunStatus.FAILED
                
            run.finished_at = event.timestamp
            
            # Update timing and cost metadata
            if run.started_at:
                run.total_seconds = (run.finished_at - run.started_at).total_seconds()
            
            run.docling_seconds = stats.get('docling_seconds')
            run.extractor_seconds = stats.get('extractor_seconds')
            run.cost_usd = stats.get('cost_usd')
            
            # Store run metadata
            run.run_metadata = {
                "documents_processed": stats.get('documents_processed', 0),
                "documents_success": stats.get('documents_success', 0),
                "documents_failed": stats.get('documents_failed', 0),
                "events_extracted": stats.get('events_extracted', 0),
                "artifacts_created": stats.get('artifacts_created', 0),
            }
            
            db.commit()
            logger.info(f"Updated run {event.run_id} to {run.status.value}")
            
    def _handle_run_failed(self, db: Session, event: WorkerEvent):
        """Handle run failed event"""
        run = db.query(Run).filter(Run.id == event.run_id).first()
        if run:
            run.status = RunStatus.FAILED
            run.finished_at = event.timestamp
            run.error = event.error
            
            if run.started_at:
                run.total_seconds = (run.finished_at - run.started_at).total_seconds()
                
            db.commit()
            logger.info(f"Updated run {event.run_id} to FAILED: {event.error}")
            
    def _handle_document_started(self, db: Session, event: WorkerEvent):
        """Handle document processing started - supports retry scenarios"""
        doc = db.query(Document).filter(Document.id == event.document_id).first()
        if doc:
            # Allow restart from PENDING, FAILED, or stuck PROCESSING states
            if doc.status in [DocumentStatus.PENDING, DocumentStatus.FAILED, DocumentStatus.PROCESSING]:
                doc.status = DocumentStatus.PROCESSING
                doc.error = None  # Clear previous error on retry
                db.commit()
                logger.debug(f"Updated document {event.document_id} to PROCESSING (was {doc.status.value})")
            else:
                # Document is already SUCCESS - shouldn't be reprocessed
                logger.warning(f"Document {event.document_id} in unexpected state {doc.status.value} for processing")
            
    def _handle_document_completed(self, db: Session, event: WorkerEvent):
        """Handle document processing completed"""
        doc = db.query(Document).filter(Document.id == event.document_id).first()
        if doc:
            doc.status = DocumentStatus.SUCCESS
            doc.processed_at = event.timestamp
            
            stats = event.payload or {}
            doc.pages = stats.get('pages')
            doc.ocr_detected = stats.get('ocr_detected', False)
            doc.processing_time_seconds = stats.get('processing_time_seconds')
            
            db.commit()
            logger.debug(f"Updated document {event.document_id} to SUCCESS")
            
    def _handle_document_failed(self, db: Session, event: WorkerEvent):
        """Handle document processing failed"""
        doc = db.query(Document).filter(Document.id == event.document_id).first()
        if doc:
            doc.status = DocumentStatus.FAILED
            doc.error = event.error
            doc.processed_at = event.timestamp

            db.commit()
            logger.debug(f"Updated document {event.document_id} to FAILED: {event.error}")

    def _move_to_dlq(self, event: WorkerEvent, error: Exception):
        """
        Move failed event to Dead Letter Queue (DLQ) after exhausting retries

        Args:
            event: The failed event
            error: The last exception encountered

        DLQ Format:
            Redis List: worker:events:dlq
            Each entry is a JSON object with:
            - event: Serialized event data
            - error: Error message
            - failed_at: Timestamp
            - retry_attempts: Number of retry attempts made
        """
        try:
            dlq_entry = {
                "event": {
                    "event_type": event.event_type.value,
                    "run_id": event.run_id,
                    "document_id": event.document_id,
                    "timestamp": event.timestamp.isoformat() if event.timestamp else None,
                    "payload": event.payload,
                    "error": event.error
                },
                "processing_error": str(error),
                "failed_at": datetime.utcnow().isoformat(),
                "retry_attempts": MAX_RETRY_ATTEMPTS
            }

            # Push to DLQ (Redis list)
            self.redis_conn.lpush(DLQ_KEY, json.dumps(dlq_entry))

            # Trim DLQ to last 1000 entries to prevent unbounded growth
            self.redis_conn.ltrim(DLQ_KEY, 0, 999)

            logger.error(
                f"Event {event.event_type.value} moved to DLQ after {MAX_RETRY_ATTEMPTS} failed attempts. "
                f"Error: {error}. Check DLQ for manual recovery."
            )

        except Exception as dlq_error:
            # Last resort: Log to stderr if DLQ push fails
            logger.critical(
                f"CRITICAL: Failed to move event to DLQ! Event: {event.event_type.value}, "
                f"Original Error: {error}, DLQ Error: {dlq_error}"
            )


# Global processor instance
_processor: Optional[APIEventProcessor] = None


def start_event_processor(redis_url: str):
    """Start the global event processor"""
    global _processor
    if not _processor:
        _processor = APIEventProcessor(redis_url)
        _processor.start()
        
        
def stop_event_processor():
    """Stop the global event processor"""
    global _processor
    if _processor:
        _processor.stop()
        _processor = None