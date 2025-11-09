# Run 54 Root Cause Analysis

**Date**: 2025-11-09  
**Status**: Under Investigation  
**Severity**: High - Worker Infrastructure Failure

---

## 🔍 Likely Root Cause: No Workers Running

Based on captured evidence, Run 54 appears to be stuck because no RQ workers are registered in Redis to process the queued job. This suggests a worker process failure rather than an application logic bug.

---

## 📊 Captured Evidence

### Run 54 API State (2025-11-09T04:22:43Z)

```json
{
    "run_id": 54,
    "case_id": 19,
    "status": "processing",
    "provider": "langextract",
    "model": "gemini-1.5-flash",
    "created_at": "2025-11-09T04:18:37.087630",
    "started_at": "2025-11-09T04:18:37.156448",
    "finished_at": null,
    "counts": {
        "total": 1,
        "processed": 0,
        "failed": 0,
        "pending": 1
    },
    "timings": {
        "docling_seconds": null,
        "extractor_seconds": null,
        "total_seconds": null
    },
    "cost_usd": null,
    "error": null
}
```

**Key Observations**:
- Status shows "processing" but no actual processing occurred
- Documents remain at 0/1 processed after 6+ hours
- No timing data recorded (suggests worker never started)

### Redis Queue State

**Worker Registration** (from `get_worker_stats()`):
```json
{
    "total_workers": 0,
    "workers": []
}
```

**Queue Statistics** (from `get_queue_stats("default")`):
```json
{
    "name": "default",
    "queued": 1,
    "started": 0,
    "finished": 52,
    "failed": 0,
    "scheduled": 0,
    "canceled": 0
}
```

**Job Details** (from Redis):
- Job ID: Retrieved from Run 54 record
- Created: 2025-11-09T04:18:37.165661Z
- Status: `queued` (never transitioned to `started`)
- Worker: None (no worker picked up job)
- Exception: None (job never attempted)

**RQ Configuration** (from `infra/queue.py:34-36`):
```python
QUEUES = {
    "high": Queue("high", connection=redis_conn, default_timeout="30m"),
    "default": Queue("default", connection=redis_conn, default_timeout="1h"),
    "low": Queue("low", connection=redis_conn, default_timeout="2h"),
}
```

### Event Analysis

**Worker Events**:
- Run 54: **0 events** emitted (no worker to emit them)
- Historical runs (1-53): 2-57 events each (workers were operational)
- Event channel: `worker:events` (pub/sub channel exists but silent)
- Event processor: Running in API service but receiving no messages

**Redis Keys Check**:
```bash
$ redis-cli KEYS "rq:worker:*"
(empty array)

$ redis-cli KEYS "worker:events:history:54"
(empty array)
```

### State Synchronization Issue

| Component | Status | Timestamp |
|-----------|--------|-----------|
| API Database (runs.status) | `processing` | 2025-11-09T04:18:37.156448 |
| Redis Job (job.status) | `queued` | 2025-11-09T04:18:37.165661 |
| Worker Events | (none) | N/A |

**Analysis**: The API prematurely sets run status to "processing" at job enqueue time, before worker confirmation. This creates a false impression that processing has started.

---

## 🤔 Why This Likely Happened

### 1. Worker Process Failure
- **Hypothesis**: The Docker worker container stopped, crashed, or was never started
- **Evidence**: Zero registered workers in Redis (`Worker.all()` returns empty)
- **Impact**: Jobs queue indefinitely without processing

### 2. Missing Health Monitoring
- **Hypothesis**: System doesn't detect worker failures
- **Evidence**: API reports "healthy" despite zero workers
- **Impact**: Silent failures with no alerts or auto-recovery

### 3. Lack of Auto-Recovery
- **Hypothesis**: No restart policies or health checks configured
- **Evidence**: Worker container not running for 6+ hours
- **Impact**: Manual intervention required for recovery

### 4. Misleading Status Updates
- **Hypothesis**: API sets "processing" status before worker pickup
- **Evidence**: API status=processing, Redis job=queued
- **Impact**: Users see false progress indicators

---

## 💥 Impact Assessment

### User Experience
- Jobs appear stuck at "processing" indefinitely
- No feedback about infrastructure failures
- Cannot retry or cancel stuck jobs without authentication

### System State
- Jobs consume queue space without resolution
- Data inconsistency between API and queue state
- Resource waste (Redis memory, database connections)

### Operational
- Silent failures require manual investigation
- No alerting when critical infrastructure fails
- Difficult to diagnose root cause without direct Redis access

---

## ✅ Acceptance Criteria for Fix

The following conditions must be met to consider Run 54 issue resolved:

### 1. Worker Availability
- [ ] `Worker.all()` returns at least 1 registered worker
- [ ] Worker appears in `redis-cli KEYS "rq:worker:*"`
- [ ] Worker heartbeat key exists with recent timestamp

### 2. Job State Transition
- [ ] Run 54 job leaves `queued` state
- [ ] Job transitions to `started` status
- [ ] Job completes or fails with clear error message
- [ ] Job state matches API run status

### 3. Event Emission
- [ ] Worker emits `RUN_STARTED` event for Run 54
- [ ] Events appear in `worker:events` channel
- [ ] Event processor receives and processes events
- [ ] Events stored in `worker:events:history:54`

### 4. UI Updates
- [ ] UI receives progress updates via SSE/polling
- [ ] Run status updates from "processing" to completion
- [ ] Document counts increment (0/1 → 1/1)
- [ ] Timing data populated (docling_seconds, extractor_seconds)

### 5. Monitoring & Alerting
- [ ] Health endpoint reflects worker availability
- [ ] Alert triggers if workers = 0 for >5 minutes
- [ ] Dashboard shows real-time worker count

---

## 🔧 Immediate Fix Required

### Step 1: Restart Worker Process
```bash
# Check current worker status
docker compose ps worker

# Restart worker container
docker compose restart worker

# Verify worker registration
docker compose logs worker | grep "Listening"
```

### Step 2: Verify Worker Registration
```bash
# Check Redis for registered workers
redis-cli KEYS "rq:worker:*"

# Expected output: rq:worker:legal_events_worker.12345
```

### Step 3: Monitor Run 54 Processing
```bash
# Watch for job pickup
watch -n 5 'curl -s http://localhost:8000/v1/runs/54 | jq .counts'

# Monitor worker events
redis-cli SUBSCRIBE "worker:events"
```

### Step 4: Validate Completion
- Run 54 should complete within 5-10 minutes
- Check for events in database
- Verify export functionality

---

## 🏗️ Architectural Improvements Needed

### 1. Worker Health Monitoring

**Current State**: No worker liveness detection

**Proposed Implementation**:
```python
# worker/main.py - Add heartbeat loop
import threading
import time
from datetime import datetime

def worker_heartbeat(worker_id: str, redis_conn):
    """Emit periodic heartbeat to Redis"""
    while True:
        try:
            heartbeat_key = f"worker:heartbeat:{worker_id}"
            redis_conn.setex(heartbeat_key, 30, json.dumps({
                'worker_id': worker_id,
                'timestamp': datetime.utcnow().isoformat(),
                'jobs_processed': worker.successful_job_count,
                'jobs_failed': worker.failed_job_count,
                'state': worker.get_state()
            }))
            time.sleep(10)  # Heartbeat every 10s, expire after 30s
        except Exception as e:
            logger.error(f"Heartbeat failed: {e}")
            time.sleep(5)

# Start heartbeat thread
threading.Thread(target=worker_heartbeat, args=(worker_id, redis_conn), daemon=True).start()
```

### 2. API Worker Status Endpoint

**File**: `api/main.py`

```python
@app.get("/v1/workers/status")
async def get_worker_status():
    """
    Get current worker status and queue metrics.
    Used for health monitoring and alerting.
    """
    from infra.queue import get_worker_stats, get_queue_stats
    
    worker_stats = get_worker_stats()
    queue_stats = get_queue_stats("default")
    
    # Check for recent heartbeats
    heartbeat_keys = redis_conn.keys('worker:heartbeat:*')
    active_workers = []
    
    for key in heartbeat_keys:
        data = redis_conn.get(key)
        if data:
            active_workers.append(json.loads(data))
    
    return {
        "workers_registered": worker_stats["total_workers"],
        "workers_with_heartbeat": len(active_workers),
        "queue_depth": queue_stats["queued"],
        "jobs_processing": queue_stats["started"],
        "healthy": worker_stats["total_workers"] > 0,
        "workers": active_workers
    }
```

### 3. Enhanced Health Check

**File**: `api/main.py` - Update `/health` endpoint

```python
@app.get("/health")
async def health_check():
    """Enhanced health check including worker availability"""
    from infra.queue import get_worker_stats
    
    health = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "components": {
            "database": "healthy",
            "storage": "healthy",
            "queue": "healthy",
            "workers": "unknown"  # NEW
        }
    }
    
    # Check worker availability
    try:
        worker_stats = get_worker_stats()
        if worker_stats["total_workers"] == 0:
            health["components"]["workers"] = "degraded"
            health["status"] = "degraded"
            logger.warning("⚠️ No workers registered - job processing unavailable")
        else:
            health["components"]["workers"] = "healthy"
    except Exception as e:
        health["components"]["workers"] = "unhealthy"
        health["status"] = "unhealthy"
        logger.error(f"Worker health check failed: {e}")
    
    return health
```

### 4. Docker Auto-Recovery

**File**: `docker-compose.yml` - Add restart policy

```yaml
worker:
  build:
    context: .
    dockerfile: Dockerfile.worker
  container_name: legal_events_worker
  restart: unless-stopped  # Auto-restart on failure
  healthcheck:
    test: ["CMD", "python", "-c", "from infra.queue import get_worker_stats; exit(0 if get_worker_stats()['total_workers'] > 0 else 1)"]
    interval: 30s
    timeout: 10s
    retries: 3
    start_period: 40s
  # ... rest of config
```

---

## 📝 PR Proposal: Standardize RQ Timeouts

### Current State

**File**: `infra/queue.py:34-36`
```python
QUEUES = {
    "high": Queue("high", connection=redis_conn, default_timeout="30m"),
    "default": Queue("default", connection=redis_conn, default_timeout="1h"),
    "low": Queue("low", connection=redis_conn, default_timeout="2h"),
}
```

**Issues**:
- Generic timeouts don't account for job complexity
- Large documents may exceed 1h timeout
- No per-job-type timeout configuration
- Timeout failures not logged clearly

### Proposed Changes

**File**: `infra/queue.py`
```python
from rq import Queue
from datetime import timedelta

# Job-specific timeout configuration
JOB_TIMEOUTS = {
    "process_run": timedelta(hours=2),       # Full run processing
    "process_document": timedelta(minutes=30),  # Single document
    "generate_artifacts": timedelta(minutes=10),  # Export generation
    "cleanup_old_runs": timedelta(minutes=5)     # Maintenance tasks
}

# Queue default timeouts (fallback)
QUEUE_DEFAULTS = {
    "high": timedelta(minutes=30),
    "default": timedelta(hours=1),
    "low": timedelta(hours=2),
}

# Initialize queues with defaults
QUEUES = {
    name: Queue(name, connection=redis_conn, default_timeout=timeout.total_seconds())
    for name, timeout in QUEUE_DEFAULTS.items()
}

def enqueue_job(
    func_name: str,
    queue_name: str = "default",
    timeout_override: Optional[timedelta] = None,
    **kwargs
) -> str:
    """
    Enqueue a job with appropriate timeout.
    
    Args:
        func_name: Function name to execute
        queue_name: Queue priority
        timeout_override: Override default timeout
        **kwargs: Job arguments
    
    Returns:
        Job ID
    """
    queue = QUEUES.get(queue_name, QUEUES["default"])
    
    # Determine timeout: override > job-specific > queue default
    timeout = timeout_override or JOB_TIMEOUTS.get(func_name) or QUEUE_DEFAULTS[queue_name]
    
    # Map function names to module paths
    if func_name == "process_run":
        job = queue.enqueue(
            "worker.tasks_refactored.process_run",
            timeout=timeout.total_seconds(),
            failure_ttl=86400,  # Keep failed jobs for 24h
            **kwargs
        )
    # ... rest of mappings
    
    logger.info(f"📋 Enqueued {func_name} in {queue_name} queue (timeout: {timeout})")
    return job.id
```

**Benefits**:
- Job-specific timeouts based on actual needs
- Override capability for special cases
- Better timeout visibility in logs
- Failed jobs retained for debugging (24h TTL)

### Testing Plan
1. Test timeout behavior with mock long-running jobs
2. Verify timeout exceptions logged clearly
3. Ensure failed jobs appear in failed registry
4. Validate retry mechanism for timeout failures

### Migration Path
1. **Phase 1**: Add timeout configuration (backward compatible)
2. **Phase 2**: Monitor timeout metrics for 1 week
3. **Phase 3**: Tune timeout values based on P95 processing times
4. **Phase 4**: Add alerts for frequent timeouts

---

## 🔄 Current Dead Letter Queue (DLQ)

### Existing Implementation

**File**: `api/event_processor.py:29-31`
```python
MAX_RETRY_ATTEMPTS = 3
RETRY_BASE_DELAY = 1.0
DLQ_KEY = "worker:events:dlq"
```

**Current Behavior**:
- Handles **event consumption failures** (API side)
- Retries failed event processing 3 times with exponential backoff (1s, 2s, 4s)
- Moves permanently failed events to DLQ
- Does NOT handle job-level failures (worker side)

**Limitations**:
1. **Scope Limited**: Only covers event delivery failures, not job failures
2. **No Visibility**: No API endpoint to view DLQ contents
3. **No Reprocessing**: No mechanism to retry DLQ events
4. **Loss of Context**: DLQ events may lack sufficient context for debugging

### What's Missing

**Job-Level DLQ**:
- Failed RQ jobs should move to a job DLQ
- Distinguish between retriable failures (network) vs permanent failures (bad data)
- Implement bounded retry with increasing delays

**Event Durability**:
- Redis pub/sub is lossy (no delivery guarantees)
- If API event processor is down, events are lost permanently
- No replay capability for missed events

---

## 🚀 Migration Plan: Redis Pub/Sub → Redis Streams

### Why Migrate?

| Feature | Pub/Sub (Current) | Redis Streams (Proposed) |
|---------|-------------------|--------------------------|
| **Delivery Guarantee** | Fire-and-forget (lossy) | At-least-once delivery |
| **Consumer Groups** | No | Yes (multiple consumers) |
| **Message Persistence** | No (ephemeral) | Yes (configurable TTL) |
| **Acknowledgment** | No | Yes (XACK) |
| **Replay Capability** | No | Yes (seek by ID/time) |
| **Backpressure Handling** | No | Yes (pending list) |
| **Scaling** | Broadcast to all | Load balanced across group |

### Proposed Architecture

**Stream Structure**:
```
Stream: worker:events:stream
Consumer Group: api_processors
Consumers: api_instance_1, api_instance_2, ...
```

**Event Flow**:
```
Worker → XADD(worker:events:stream) → Stream
                                       ↓
                        Consumer Group (api_processors)
                                       ↓
                    ┌──────────────────┴──────────────────┐
                    ↓                                      ↓
            api_instance_1                          api_instance_2
                    ↓                                      ↓
            XACK (on success)                      XACK (on success)
                    ↓                                      ↓
            Process event                          Process event
```

### Phased Migration Plan

#### Phase 1: Dual Write (Weeks 1-2)
- Worker emits to **both** pub/sub and streams
- API consumes from pub/sub (current behavior)
- Monitor stream growth and consumer lag

**Implementation**:
```python
# infra/worker_events.py - WorkerEventEmitter
def _publish(self, event: WorkerEvent):
    """Publish to both pub/sub and streams during migration"""
    json_data = event.to_json()
    
    # Existing pub/sub (for backward compatibility)
    self.redis.publish(self.channel, json_data)
    
    # NEW: Also write to stream
    self.redis.xadd(
        "worker:events:stream",
        {"data": json_data},
        maxlen=10000  # Keep last 10k events
    )
```

#### Phase 2: Dual Read (Weeks 3-4)
- Worker emits to both pub/sub and streams
- API consumes from **both** (dedupe by event ID)
- Validate stream consumption works correctly

**Implementation**:
```python
# api/event_processor.py - Add stream consumer
def _run_stream_consumer(self):
    """Consume events from Redis Streams"""
    group_name = "api_processors"
    consumer_name = f"api_{os.getpid()}"
    
    # Create consumer group if not exists
    try:
        self.redis.xgroup_create("worker:events:stream", group_name, id='0', mkstream=True)
    except redis.ResponseError:
        pass  # Group already exists
    
    while self.running:
        try:
            # Read new messages for this consumer group
            events = self.redis.xreadgroup(
                group_name,
                consumer_name,
                {"worker:events:stream": ">"},
                count=10,
                block=1000
            )
            
            for stream, messages in events:
                for msg_id, data in messages:
                    event = WorkerEvent.from_json(data[b'data'].decode())
                    
                    # Process event with retry logic
                    self._process_event(event)
                    
                    # Acknowledge successful processing
                    self.redis.xack("worker:events:stream", group_name, msg_id)
                    
        except Exception as e:
            logger.error(f"Stream consumer error: {e}")
            time.sleep(5)
```

#### Phase 3: Stream-Only (Weeks 5-6)
- Worker emits **only** to streams
- API consumes **only** from streams
- Remove pub/sub code paths
- Monitor for issues

#### Phase 4: Optimization (Weeks 7-8)
- Tune stream maxlen based on traffic
- Implement pending message monitoring
- Add metrics for consumer lag
- Set up alerts for processing delays

### Rollback Strategy

**If issues arise during migration**:
1. **Phase 2**: Disable stream consumer, revert to pub/sub only
2. **Phase 3**: Re-enable dual write, roll back API to Phase 2
3. **Emergency**: Revert all changes, return to pub/sub only

**Rollback Safeguards**:
- Feature flags to toggle stream consumption
- Metrics to detect increased error rates
- Automated rollback if error rate > 5%

### Testing Plan

**Unit Tests**:
- Stream write and read operations
- Consumer group mechanics
- Acknowledgment handling
- Error retry behavior

**Integration Tests**:
- Multiple consumers in same group
- Message delivery guarantees
- Failover scenarios
- Network partition recovery

**Load Tests**:
- 1000 events/second throughput
- Consumer lag under load
- Memory usage with 10k event buffer
- Horizontal scaling (5+ API instances)

### Monitoring & Alerting

**Key Metrics**:
- `stream_length`: Messages in stream (target: < 100)
- `consumer_lag`: Unprocessed messages per consumer (target: < 50)
- `pending_messages`: Messages pending ACK (target: < 10)
- `processing_time`: Time to process event (target: < 100ms)

**Alerts**:
- Consumer lag > 100 messages for 5 minutes
- Pending messages > 50 for 10 minutes
- No consumers active for 1 minute
- Stream length > 1000 (backpressure)

---

## 🧪 Testing the Fix

### Pre-Fix Checklist
- [ ] Document current worker status: `docker compose ps worker`
- [ ] Capture queue stats: `curl http://localhost:8000/v1/workers/status`
- [ ] Note Run 54 current state: `curl http://localhost:8000/v1/runs/54`

### Fix Implementation
```bash
# 1. Start worker
docker compose up -d worker

# 2. Verify worker registration (within 30s)
docker compose logs worker | grep -i "listening"

# 3. Check Redis worker keys
redis-cli KEYS "rq:worker:*"

# 4. Monitor Run 54 processing
watch -n 2 'curl -s http://localhost:8000/v1/runs/54 | jq "{status, counts, timings}"'
```

### Post-Fix Validation
- [ ] Worker appears in `Worker.all()` output
- [ ] Run 54 status transitions to `success` or `failed`
- [ ] Events generated in `worker:events:history:54`
- [ ] Timing data populated (docling_seconds, extractor_seconds, total_seconds)
- [ ] Export functionality works
- [ ] Subsequent runs process normally

---

## 🔮 Prevention Measures

### Short-Term (Week 1)
1. **Worker Health Monitoring**: Implement heartbeat and status endpoint
2. **Enhanced Health Check**: Include worker availability in `/health`
3. **Docker Restart Policy**: Add `restart: unless-stopped` to worker service
4. **Alerting**: Set up basic alerts for worker=0 condition

### Medium-Term (Month 1)
1. **Monitoring Dashboard**: Build Grafana dashboard for queue/worker metrics
2. **Standardized Timeouts**: Implement PR for job-specific timeouts
3. **DLQ Management**: Add API endpoints to view and retry DLQ events
4. **Documentation**: Update deployment guide with worker monitoring

### Long-Term (Quarter 1)
1. **Redis Streams Migration**: Complete migration from pub/sub to streams
2. **Auto-Scaling**: Implement worker auto-scaling based on queue depth
3. **Circuit Breakers**: Stop accepting new jobs if workers unavailable
4. **Event Sourcing**: Store all events for full audit trail

---

## 📚 Related Documentation

- [Service Boundaries Architecture](./SERVICE_BOUNDARIES.md) - Event-driven design principles
- [Process Flow Diagram](./PROCESS_FLOW.md) - Run processing sequence
- [Retry Mechanism](./RETRY_MECHANISM.md) - Current retry logic
- [RQ Documentation](https://python-rq.org/) - Job queue reference

---

## 🏁 Conclusion

Run 54's 6+ hour stall likely stems from **worker infrastructure failure** rather than application logic bugs. The evidence strongly suggests zero registered workers in Redis, preventing job processing.

**Key Takeaways**:
1. **State Desync**: API reports "processing" but job remains queued
2. **Silent Failure**: No alerts when workers die
3. **No Auto-Recovery**: Manual intervention required
4. **Monitoring Gap**: Health checks don't include worker availability

**Next Steps**:
1. Restart worker container and verify Run 54 completes
2. Implement worker health monitoring (high priority)
3. Plan Redis Streams migration (medium priority)
4. Standardize RQ timeouts (low priority)

This investigation shifts focus from document processing logic (Docling/OCR) to infrastructure reliability and observability improvements.

---

**Document Version**: 2.0  
**Last Updated**: 2025-11-09  
**Investigators**: OpenCode AI Assistant  
**Status**: Awaiting Fix Validation
