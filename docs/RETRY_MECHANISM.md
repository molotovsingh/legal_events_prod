# Document Retry Mechanism Documentation

## Overview

The Legal Events Production system implements a robust retry mechanism for failed and stuck document processing. This ensures resilience against transient failures and allows recovery from system crashes.

## Architecture

### Service Boundaries

The retry mechanism respects the v0.4.0 event-driven architecture:

- **API Service**: Owns document status transitions and provides manual retry endpoint
- **Worker Service**: Reads document statuses but never mutates them directly
- **Communication**: Status updates flow via Redis pub/sub events

### Retry Strategies

#### 1. Automatic Retry (Worker-Initiated)

The worker automatically retries documents in the following states:

- **FAILED**: Documents that previously failed processing
- **STUCK PROCESSING**: Documents in PROCESSING state for >threshold (configurable via `STUCK_DOCUMENT_HOURS`, default 1 hour)

**Configuration**: Set environment variable `STUCK_DOCUMENT_HOURS` to customize threshold (e.g., `STUCK_DOCUMENT_HOURS=2` for 2 hours)

**Implementation**: `worker/tasks_refactored.py` lines 84-110

```python
# Load retry configuration for stuck document threshold
from core.config import RetryConfig
retry_config = RetryConfig()
stuck_threshold_hours = retry_config.stuck_document_hours

# Query PENDING and FAILED documents (allows automatic retry)
documents = db.query(Document).filter(
    Document.run_id == run_id,
    Document.status.in_([DocumentStatus.PENDING, DocumentStatus.FAILED])
).all()

# Check for stuck PROCESSING documents (configurable threshold)
if not documents:
    stuck_documents = db.query(Document).filter(
        Document.run_id == run_id,
        Document.status == DocumentStatus.PROCESSING,
        Document.created_at < datetime.utcnow() - timedelta(hours=stuck_threshold_hours)
    ).all()
```

#### 2. Manual Retry (API-Initiated)

Users can manually trigger retries via the API endpoint:

**Endpoint**: `PUT /v1/runs/{run_id}/retry`

**Authorization**: Requires valid JWT token

**Headers**:
- `Authorization: Bearer <token>` (required)
- `Idempotency-Key: <unique-key>` (optional, recommended for network reliability)

**Process**:
1. Checks idempotency cache (if key provided) to prevent duplicate retries
2. Validates run has documents and is in retryable state (FAILED, PARTIAL_SUCCESS, or stuck PROCESSING)
3. Resets FAILED documents to PENDING (clears error, processed_at)
4. Resets stuck PROCESSING documents to PENDING (uses configurable threshold)
5. Resets run status to QUEUED (clears error, finished_at)
6. Flushes database changes before job enqueue
7. Enqueues new processing job
8. Commits transaction atomically
9. Caches response (if idempotency key provided) with 24-hour TTL

**Idempotency Protection**: Duplicate requests with same `Idempotency-Key` return cached response without re-enqueueing job

**Transaction Safety**: Database changes are rolled back if job enqueue fails

**Implementation**: `api/main.py` lines 548-675

## Status Transitions

### Document Status Flow

```
PENDING → PROCESSING → SUCCESS
   ↑          ↓
   └─────── FAILED
```

### Retry Status Transitions

1. **Failed Document Retry**:
   - FAILED → PENDING (via API reset)
   - PENDING → PROCESSING (worker picks up)
   - PROCESSING → SUCCESS/FAILED (based on outcome)

2. **Stuck Document Recovery**:
   - PROCESSING (>1hr) → PENDING (via API reset)
   - PENDING → PROCESSING (worker picks up)
   - PROCESSING → SUCCESS/FAILED (based on outcome)

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `STUCK_DOCUMENT_HOURS` | `1` | Threshold (in hours) for detecting stuck PROCESSING documents |
| `REDIS_URL` | `redis://localhost:6379` | Redis connection URL for idempotency cache |

### Timeouts

- **Stuck Document Threshold**: Configurable via `STUCK_DOCUMENT_HOURS` (default: 1 hour)
- **Worker Job Timeout**: 2 hours (Redis queue configuration)
- **Idempotency Cache TTL**: 24 hours

### Retry Limits

Currently unlimited retries are allowed. Future enhancements could add:
- Max retry count per document (see `RetryConfig.max_retry_count` comment in `core/config.py`)
- Exponential backoff between retries (see `RetryConfig.retry_backoff_seconds` comment)
- Dead letter queue for permanently failed documents

## API Reference

### Retry Run Endpoint

**Request**:
```http
PUT /v1/runs/{run_id}/retry
Authorization: Bearer <token>
Idempotency-Key: unique-request-id-123
```

**Response (200 OK)**:
```json
{
    "status": "accepted",
    "run_id": 123,
    "job_id": "abc-def-ghi",
    "documents_reset": 5,
    "failed_documents": 3,
    "stuck_documents": 2
}
```

**Error Responses**:
- `400 Bad Request`: Run is still actively processing, or run has no documents
- `401 Unauthorized`: Missing or invalid authentication token
- `404 Not Found`: Run ID does not exist
- `500 Internal Server Error`: Failed to enqueue job (transaction rolled back)

**Idempotency**: Include `Idempotency-Key` header to safely retry requests without duplicate job processing. Cached for 24 hours.

## Event Flow

### Retry Event Sequence

1. **API Retry Triggered**:
   ```
   User → API.retry_run() → Reset statuses → Enqueue job
   ```

2. **Worker Processes Retry**:
   ```
   Worker.process_run() → Query PENDING+FAILED → Emit events
   ```

3. **API Updates Status**:
   ```
   EventProcessor → Consume events → Update document/run status
   ```

## Monitoring

### Key Metrics

Monitor these metrics to track retry health:

1. **Document Retry Rate**:
   ```sql
   SELECT COUNT(*) FROM documents 
   WHERE status = 'FAILED' 
   AND updated_at > NOW() - INTERVAL '1 hour';
   ```

2. **Stuck Documents**:
   ```sql
   SELECT COUNT(*) FROM documents 
   WHERE status = 'PROCESSING' 
   AND created_at < NOW() - INTERVAL '1 hour';
   ```

3. **Retry Success Rate**:
   Track documents that succeed after retry vs permanent failures

### Redis Event History

View retry events:
```bash
# Monitor live retry events
redis-cli SUBSCRIBE "worker:events"

# Check historical events for a run
redis-cli LRANGE "worker:events:history:123" 0 -1
```

## Testing

### Unit Tests

Test file: `tests/test_retry_functionality.py`

Key test scenarios:
1. Automatic retry of FAILED documents
2. Stuck document recovery
3. API retry endpoint validation
4. Authentication requirements
5. Prevention of active run retry

### Manual Testing

1. **Simulate Failed Document**:
   ```bash
   # Mark a document as failed in database
   UPDATE documents SET status = 'FAILED' WHERE id = 123;
   ```

2. **Trigger Manual Retry**:
   ```bash
   curl -X PUT http://localhost:8000/v1/runs/123/retry \
     -H "Authorization: Bearer <token>"
   ```

3. **Monitor Processing**:
   ```bash
   # Watch worker logs
   docker compose logs -f worker
   
   # Monitor Redis events
   redis-cli SUBSCRIBE "worker:events"
   ```

## Troubleshooting

### Common Issues

1. **Documents Not Being Retried**:
   - Check document status in database
   - Verify worker is querying correct statuses
   - Check Redis queue for stuck jobs

2. **Infinite Retry Loop**:
   - Verify error is being properly logged
   - Check if same error occurs repeatedly
   - Consider implementing retry limits

3. **Stuck Documents Not Detected**:
   - Verify timestamp comparison logic
   - Check database timezone settings
   - Ensure created_at is being set correctly

### Debug Commands

```bash
# Check document statuses for a run
SELECT status, COUNT(*) FROM documents 
WHERE run_id = 123 
GROUP BY status;

# Find stuck processing documents
SELECT id, filename, created_at FROM documents 
WHERE status = 'PROCESSING' 
AND created_at < NOW() - INTERVAL '1 hour';

# View failed job details in Redis
redis-cli
> LRANGE "rq:queue:failed" 0 -1
```

## Future Enhancements

1. **Configurable Retry Policies**:
   - Per-client retry limits
   - Exponential backoff
   - Custom timeout thresholds

2. **Retry Metadata**:
   - Track retry count per document
   - Store retry history
   - Record failure reasons

3. **Smart Retry Logic**:
   - Skip retries for specific error types
   - Prioritize newer documents
   - Batch retry operations

4. **Monitoring Dashboard**:
   - Real-time retry metrics
   - Success/failure trends
   - Alert on high failure rates

## Security Considerations

1. **Authentication**: Retry endpoint requires valid JWT token
2. **Authorization**: Consider adding role-based access (only admins can retry)
3. **Rate Limiting**: Prevent retry spam/abuse
4. **Audit Trail**: Log all retry attempts with user identity

## Performance Impact

- **Database Queries**: Retry adds additional WHERE clauses but uses indexed columns
- **Redis Events**: Minimal overhead from event emission
- **Worker Load**: Retrying documents adds to processing queue
- **API Latency**: Retry endpoint is async, returns immediately after enqueue

## Version History

- **v0.6.0** (Current): Enhanced retry mechanism
  - Added configurable stuck document threshold via `STUCK_DOCUMENT_HOURS`
  - Implemented idempotency protection for retry endpoint
  - Added transaction safety with rollback on enqueue failures
  - Added validation to prevent retrying runs with no documents
  - Improved logging with authenticated user tracking
  - Added comprehensive test coverage (8 new tests)
- **v0.5.0**: Initial retry mechanism implementation
- **v0.4.0**: Event-driven architecture (prerequisite)
- **v0.3.0**: Service boundary enforcement
- **v0.2.0**: Guardrails architecture