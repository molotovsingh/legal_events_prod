# Service Boundary Architecture

**Version:** 1.0.0  
**Date:** 2025-11-07  
**Status:** Implemented

## Overview

This document describes the service boundary architecture implemented to ensure clean separation between the API and Worker services. This architecture prevents tight coupling, enables independent scaling, and maintains clear ownership of data entities.

## Architecture Principles

### 1. Service Separation

```
┌─────────────────────────────────────────────────────────┐
│                     API Service                          │
│  - Owns: clients, cases, runs, documents                 │
│  - Read/Write: All owned entities                        │
│  - Exposes: REST endpoints, authentication               │
│  - Consumes: Worker events via Redis                     │
└─────────────────────────────────────────────────────────┘
                            │
                            │ Redis Events
                            ▼
┌─────────────────────────────────────────────────────────┐
│                   Worker Service                         │
│  - Owns: events, artifacts (write-only)                  │
│  - Read-only: clients, cases, runs, documents            │
│  - Processes: Document extraction tasks                  │
│  - Emits: Status updates via Redis                       │
└─────────────────────────────────────────────────────────┘
```

### 2. Data Ownership

| Entity | API Service | Worker Service |
|--------|-------------|----------------|
| Clients | ✅ Read/Write | ❌ No access |
| Cases | ✅ Read/Write | ❌ No access |
| Runs | ✅ Read/Write | 🔍 Read-only |
| Documents | ✅ Read/Write | 🔍 Read-only |
| Events | 🔍 Read-only | ✅ Write-only |
| Artifacts | 🔍 Read-only | ✅ Write-only |

### 3. Communication Patterns

#### API → Worker: Job Enqueuing
```python
# API enqueues jobs using string references (no imports)
from infra.queue import enqueue_job

job_id = enqueue_job(
    func_name="process_run",
    queue_name="default",
    run_id=run_id,
    provider=provider
)
```

#### Worker → API: Event Emission
```python
# Worker emits events to Redis
emitter.emit_run_started(run_id)
emitter.emit_document_completed(run_id, doc_id, stats)
emitter.emit_run_failed(run_id, error_msg)

# API consumes events and updates owned entities
event_processor.handle_run_started(event)  # Updates run.status
event_processor.handle_document_completed(event)  # Updates doc.status
```

## Implementation Details

### File Structure

```
legal-events-production/
├── infra/                      # Shared infrastructure
│   ├── models.py              # ORM models (shared read definitions)
│   ├── database.py            # Database connections
│   ├── storage.py             # MinIO storage client
│   ├── queue.py               # RQ job management
│   └── worker_events.py       # Event emission/consumption system
│
├── api/
│   ├── main.py                # FastAPI app
│   ├── event_processor.py     # Consumes worker events
│   └── schemas.py             # API-specific schemas
│
└── worker/
    ├── main.py                # Worker entry point
    ├── tasks_refactored.py    # Service-boundary compliant tasks
    └── database.py            # Worker's DB connection
```

### Key Components

#### 1. Worker Event System (`infra/worker_events.py`)

Provides event-based communication between services:

```python
class WorkerEventType(Enum):
    RUN_STARTED = "run.started"
    RUN_COMPLETED = "run.completed"
    DOCUMENT_STARTED = "document.started"
    DOCUMENT_COMPLETED = "document.completed"
    EVENT_CREATED = "event.created"
    ARTIFACT_CREATED = "artifact.created"
```

#### 2. Event Processor (`api/event_processor.py`)

Consumes worker events and updates API-owned entities:

```python
class APIEventProcessor:
    def _handle_run_started(self, db, event):
        run = db.query(Run).filter(Run.id == event.run_id).first()
        run.status = RunStatus.PROCESSING
        run.started_at = event.timestamp
        db.commit()
```

#### 3. Refactored Worker Tasks (`worker/tasks_refactored.py`)

Worker tasks that respect service boundaries:

```python
def process_run(run_id: int):
    # READ run info (read-only)
    run = db.query(Run).filter(Run.id == run_id).first()
    
    # EMIT status update (no direct mutation)
    emitter.emit_run_started(run_id)
    
    # WRITE worker-owned entities only
    event = Event(...)
    db.add(event)
    db.commit()
    
    # EMIT completion
    emitter.emit_run_completed(run_id, stats)
```

## Migration Guide

### Before (Boundary Violation)
```python
# worker/tasks.py - WRONG
def process_run(run_id):
    run.status = RunStatus.PROCESSING  # ❌ Mutating API-owned entity
    run.started_at = datetime.utcnow()  # ❌ Direct write
    db.commit()
```

### After (Service Boundary Compliant)
```python
# worker/tasks_refactored.py - CORRECT
def process_run(run_id):
    emitter.emit_run_started(run_id)  # ✅ Event emission
    # API's event processor will update run.status
```

## Benefits

1. **Independent Deployment**: Services can be deployed separately
2. **Scalability**: Worker instances can scale without affecting API
3. **Testing**: Services can be tested in isolation
4. **Resilience**: Worker failures don't corrupt API state
5. **Clarity**: Clear ownership reduces bugs and confusion

## Monitoring

### Event Flow Monitoring
```bash
# Monitor Redis event stream
redis-cli SUBSCRIBE "worker:events"

# Check event history for a run
redis-cli LRANGE "worker:events:history:123" 0 -1
```

### Health Checks
- API: Owns database state consistency
- Worker: Reports processing metrics only
- Events: Track emission/consumption lag

## Common Patterns

### 1. Status Updates
```python
# Worker: Emit event
emitter.emit_document_started(run_id, doc_id)

# API: Handle event
def _handle_document_started(self, db, event):
    doc.status = DocumentStatus.PROCESSING
```

### 2. Progress Tracking
```python
# Worker: Emit progress
emitter.emit_progress(run_id, "Processing page 5/10", doc_id)

# API: Update progress (optional)
run.progress_message = event.payload["message"]
```

### 3. Error Handling
```python
# Worker: Emit failure
emitter.emit_run_failed(run_id, str(exception))

# API: Handle failure
run.status = RunStatus.FAILED
run.error = event.error
```

## Enforcement

### CI/CD Checks

1. **Import Linting**: Prevent cross-service imports
   ```yaml
   - name: Check Service Boundaries
     run: |
       ! grep -r "from api import" worker/
       ! grep -r "from worker import" api/
   ```

2. **Database Access Auditing**: Log and alert on boundary violations

3. **Code Reviews**: Enforce boundary rules in PR reviews

## FAQ

**Q: Why can't the worker update run status directly?**  
A: The API owns the business logic for state transitions. The worker reports what happened; the API decides what that means for the business state.

**Q: What if Redis is down?**  
A: Jobs will queue but status updates will lag. The system remains eventually consistent. Consider adding a fallback polling mechanism for critical updates.

**Q: Can we share code between services?**  
A: Yes, through the `infra/` and `core/` modules. These contain shared utilities and data definitions, not business logic.

**Q: How do we handle long-running operations?**  
A: Worker emits periodic progress events. API can expose these via SSE or polling endpoints.

## Future Improvements

1. **Event Sourcing**: Store all events for full audit trail
2. **CQRS**: Separate read/write models for better performance
3. **Saga Pattern**: Coordinate complex multi-service transactions
4. **GraphQL Subscriptions**: Real-time updates for clients
5. **Event Schema Registry**: Versioned event schemas

## References

- [Domain-Driven Design](https://martinfowler.com/tags/domain%20driven%20design.html)
- [Microservices Patterns](https://microservices.io/patterns/index.html)
- [Event-Driven Architecture](https://martinfowler.com/articles/201701-event-driven.html)