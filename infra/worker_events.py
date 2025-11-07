"""
Worker Event System - Service Boundary Compliant Communication

This module provides a clean event-based communication system between Worker and API.
Worker emits events to Redis, API consumes and updates its owned entities.

Architecture:
- Worker: Write-only to events/artifacts, emit status updates via Redis
- API: Owns runs/documents state, consumes worker events to update status
- Communication: Redis pub/sub or job metadata, no direct DB writes from worker
"""

import json
import logging
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
import redis

logger = logging.getLogger(__name__)


class WorkerEventType(Enum):
    """Types of events emitted by worker"""
    # Run lifecycle events
    RUN_STARTED = "run.started"
    RUN_COMPLETED = "run.completed"
    RUN_FAILED = "run.failed"
    RUN_PROGRESS = "run.progress"
    
    # Document lifecycle events
    DOCUMENT_STARTED = "document.started"
    DOCUMENT_COMPLETED = "document.completed"
    DOCUMENT_FAILED = "document.failed"
    DOCUMENT_PROGRESS = "document.progress"
    
    # Event creation events (worker's primary output)
    EVENT_CREATED = "event.created"
    ARTIFACT_CREATED = "artifact.created"


@dataclass
class WorkerEvent:
    """Event emitted by worker for API consumption"""
    event_type: WorkerEventType
    timestamp: datetime
    run_id: int
    document_id: Optional[int] = None
    payload: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    
    def to_json(self) -> str:
        """Serialize event to JSON for Redis"""
        data = asdict(self)
        data['event_type'] = self.event_type.value
        data['timestamp'] = self.timestamp.isoformat()
        return json.dumps(data)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'WorkerEvent':
        """Deserialize event from JSON"""
        data = json.loads(json_str)
        data['event_type'] = WorkerEventType(data['event_type'])
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)


class WorkerEventEmitter:
    """
    Event emitter for Worker service.
    Publishes events to Redis for API consumption.
    """
    
    def __init__(self, redis_conn: redis.Redis):
        self.redis = redis_conn
        self.channel = "worker:events"
        
    def emit_run_started(self, run_id: int):
        """Emit run started event"""
        event = WorkerEvent(
            event_type=WorkerEventType.RUN_STARTED,
            timestamp=datetime.utcnow(),
            run_id=run_id
        )
        self._publish(event)
        logger.info(f"Emitted RUN_STARTED for run {run_id}")
        
    def emit_run_completed(self, run_id: int, stats: Dict[str, Any]):
        """Emit run completed event with statistics"""
        event = WorkerEvent(
            event_type=WorkerEventType.RUN_COMPLETED,
            timestamp=datetime.utcnow(),
            run_id=run_id,
            payload=stats
        )
        self._publish(event)
        logger.info(f"Emitted RUN_COMPLETED for run {run_id}")
        
    def emit_run_failed(self, run_id: int, error: str):
        """Emit run failed event"""
        event = WorkerEvent(
            event_type=WorkerEventType.RUN_FAILED,
            timestamp=datetime.utcnow(),
            run_id=run_id,
            error=error
        )
        self._publish(event)
        logger.info(f"Emitted RUN_FAILED for run {run_id}: {error}")
        
    def emit_document_started(self, run_id: int, document_id: int):
        """Emit document processing started"""
        event = WorkerEvent(
            event_type=WorkerEventType.DOCUMENT_STARTED,
            timestamp=datetime.utcnow(),
            run_id=run_id,
            document_id=document_id
        )
        self._publish(event)
        logger.info(f"Emitted DOCUMENT_STARTED for document {document_id}")
        
    def emit_document_completed(self, run_id: int, document_id: int, stats: Dict[str, Any]):
        """Emit document processing completed"""
        event = WorkerEvent(
            event_type=WorkerEventType.DOCUMENT_COMPLETED,
            timestamp=datetime.utcnow(),
            run_id=run_id,
            document_id=document_id,
            payload=stats
        )
        self._publish(event)
        logger.info(f"Emitted DOCUMENT_COMPLETED for document {document_id}")
        
    def emit_document_failed(self, run_id: int, document_id: int, error: str):
        """Emit document processing failed"""
        event = WorkerEvent(
            event_type=WorkerEventType.DOCUMENT_FAILED,
            timestamp=datetime.utcnow(),
            run_id=run_id,
            document_id=document_id,
            error=error
        )
        self._publish(event)
        logger.info(f"Emitted DOCUMENT_FAILED for document {document_id}: {error}")
        
    def emit_progress(self, run_id: int, message: str, document_id: Optional[int] = None):
        """Emit progress update"""
        event = WorkerEvent(
            event_type=WorkerEventType.RUN_PROGRESS if document_id is None else WorkerEventType.DOCUMENT_PROGRESS,
            timestamp=datetime.utcnow(),
            run_id=run_id,
            document_id=document_id,
            payload={"message": message}
        )
        self._publish(event)
        
    def emit_event_created(self, run_id: int, event_id: int, document_id: int):
        """Emit notification that a legal event was created"""
        event = WorkerEvent(
            event_type=WorkerEventType.EVENT_CREATED,
            timestamp=datetime.utcnow(),
            run_id=run_id,
            document_id=document_id,
            payload={"event_id": event_id}
        )
        self._publish(event)
        
    def emit_artifact_created(self, run_id: int, artifact_id: int, document_id: Optional[int] = None):
        """Emit notification that an artifact was created"""
        event = WorkerEvent(
            event_type=WorkerEventType.ARTIFACT_CREATED,
            timestamp=datetime.utcnow(),
            run_id=run_id,
            document_id=document_id,
            payload={"artifact_id": artifact_id}
        )
        self._publish(event)
        
    def _publish(self, event: WorkerEvent):
        """Publish event to Redis"""
        try:
            self.redis.publish(self.channel, event.to_json())
            # Also store in a list for persistence (last 1000 events)
            self.redis.lpush(f"worker:events:history:{event.run_id}", event.to_json())
            self.redis.ltrim(f"worker:events:history:{event.run_id}", 0, 999)
            # Set expiry on history (7 days)
            self.redis.expire(f"worker:events:history:{event.run_id}", 604800)
        except Exception as e:
            logger.error(f"Failed to publish event: {e}")


class WorkerEventConsumer:
    """
    Event consumer for API service.
    Subscribes to worker events and processes them.
    """
    
    def __init__(self, redis_conn: redis.Redis):
        self.redis = redis_conn
        self.channel = "worker:events"
        self.pubsub = None
        
    def start(self, callback):
        """
        Start consuming events.
        
        Args:
            callback: Function to call with each event (event: WorkerEvent)
        """
        self.pubsub = self.redis.pubsub()
        self.pubsub.subscribe(self.channel)
        
        for message in self.pubsub.listen():
            if message['type'] == 'message':
                try:
                    event = WorkerEvent.from_json(message['data'])
                    callback(event)
                except Exception as e:
                    logger.error(f"Failed to process event: {e}")
                    
    def stop(self):
        """Stop consuming events"""
        if self.pubsub:
            self.pubsub.unsubscribe()
            self.pubsub.close()
            
    def get_run_history(self, run_id: int) -> list[WorkerEvent]:
        """Get historical events for a run"""
        events = []
        raw_events = self.redis.lrange(f"worker:events:history:{run_id}", 0, -1)
        for raw in raw_events:
            try:
                events.append(WorkerEvent.from_json(raw))
            except Exception as e:
                logger.error(f"Failed to parse historical event: {e}")
        return events