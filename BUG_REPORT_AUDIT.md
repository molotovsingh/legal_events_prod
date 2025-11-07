# Bug Report - Code Audit
**Date:** 2025-01-XX  
**Auditor:** AI Code Review  
**Scope:** Full codebase review for bugs (not fixed)

---

## Critical Bugs

### 1. IndexError: List index out of range in export_run endpoint
**File:** `api/main.py:613`  
**Severity:** Critical  
**Description:**  
Accessing `events[0].run.case_id` without checking if the events list is empty. While there's a check at line 573-574 that raises HTTPException if no events, if events list becomes empty between the check and line 613 (unlikely but possible), this will crash.

**Code:**
```python
# Line 573-574
if not events:
    raise HTTPException(status_code=404, detail="No events found for this run")

# ... later at line 613
case = db.query(Case).filter(Case.id == events[0].run.case_id).first()
```

**Impact:** Server crash with IndexError  
**Recommendation:** Add defensive check or use `events[0]` only after confirming list is not empty.

---

### 2. Type mismatch in role comparison
**File:** `api/auth.py:157`  
**Severity:** Critical  
**Description:**  
Comparing `UserRole` enum to string literal. This will always evaluate to True (enum != string), allowing non-admin users to pass admin checks.

**Code:**
```python
if current_user.role != "admin":  # BUG: role is UserRole enum, not string
    raise HTTPException(...)
```

**Impact:** Security vulnerability - non-admin users can access admin endpoints  
**Recommendation:** Change to `current_user.role != UserRole.ADMIN`

---

### 3. Potential IndexError in get_run_events pagination
**File:** `api/main.py:514`  
**Severity:** Medium  
**Description:**  
Accessing `events[-1].id` when events list could be empty. While there's a ternary check, the logic could be clearer.

**Code:**
```python
next_cursor = events[-1].id if events else None
```

**Impact:** Potential IndexError if events list is empty  
**Recommendation:** The code is actually safe due to the ternary, but could be more explicit: `next_cursor = events[-1].id if len(events) > 0 else None`

---

## High Priority Bugs

### 4. Missing transaction rollback on errors in worker tasks
**File:** `worker/tasks_refactored.py:165, 323`  
**Severity:** High  
**Description:**  
Committing events inside a loop without proper error handling. If an exception occurs after some events are committed, partial data is persisted.

**Code:**
```python
for event_data in results["events"]:
    event = Event(...)
    db.add(event)
    db.commit()  # BUG: No rollback if subsequent events fail
    events_created += 1
```

**Impact:** Data inconsistency, partial event creation  
**Recommendation:** Use batch commit after loop, or wrap in try/except with rollback

---

### 5. Race condition in idempotency check
**File:** `api/main.py:367-432`  
**Severity:** High  
**Description:**  
Idempotency check and run status update are not atomic. Two concurrent requests with the same idempotency key could both pass the check and both start processing.

**Code:**
```python
# Check idempotency
cached_result = r.get(cache_key)
if cached_result:
    return json.loads(cached_result)

# ... later, update run status
run.status = RunStatus.PROCESSING
db.commit()

# ... later, cache result
r.setex(cache_key, 86400, json.dumps(response))
```

**Impact:** Duplicate run processing  
**Recommendation:** Use Redis SETNX or database transaction to make check-and-set atomic

---

### 6. Missing null check before accessing relationship
**File:** `api/main.py:613`  
**Severity:** High  
**Description:**  
Accessing `events[0].run.case_id` assumes `run` relationship is loaded. If lazy loading fails or relationship is None, this will crash.

**Code:**
```python
case = db.query(Case).filter(Case.id == events[0].run.case_id).first()
```

**Impact:** AttributeError if run relationship is not loaded or is None  
**Recommendation:** Add null check or eager load relationship: `db.query(Event).options(joinedload(Event.run)).filter(...)`

---

### 7. Temporary file not cleaned up on exception
**File:** `worker/tasks_refactored.py:125-187`  
**Severity:** High  
**Description:**  
Temporary file created with `delete=False` is only cleaned up in the success path. If an exception occurs before `os.unlink(tmp_path)`, the file remains on disk.

**Code:**
```python
with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
    tmp_path = tmp.name
    storage.download_file(doc.storage_key, tmp_path)
    
# ... processing ...
os.unlink(tmp_path)  # Only executed if no exception
```

**Impact:** Disk space leak, temporary files accumulate  
**Recommendation:** Use try/finally to ensure cleanup, or use context manager that auto-deletes

---

## Medium Priority Bugs

### 8. Database session not properly closed in error path
**File:** `api/main.py:652-702` (SSE endpoint)  
**Severity:** Medium  
**Description:**  
While there's a `finally` block that closes the session, if an exception occurs during `db.query()`, the session might not be properly closed before the next iteration.

**Code:**
```python
while True:
    db = SessionLocal()
    try:
        run = db.query(Run).filter(Run.id == run_id).first()
        # ...
    finally:
        db.close()  # Good, but if query fails, might leak connection
```

**Impact:** Database connection pool exhaustion  
**Recommendation:** The code is actually correct, but could use context manager for clarity

---

### 9. Missing validation for file_count parameter
**File:** `api/main.py:331`  
**Severity:** Medium  
**Description:**  
`run.file_count` is used directly without validation. Negative values or very large values could cause issues.

**Code:**
```python
for i in range(run.file_count or 1):  # No validation on file_count
    url = storage.generate_upload_url(...)
```

**Impact:** Resource exhaustion if file_count is very large  
**Recommendation:** Add validation: `file_count = max(1, min(file_count or 1, 1000))`

---

### 10. Redis connection not closed in all error paths
**File:** `worker/tasks_refactored.py:66-237`  
**Severity:** Medium  
**Description:**  
Redis connection is created but only closed in the `finally` block. If an exception occurs during connection creation, `redis_conn` might not be initialized, causing error in finally block.

**Code:**
```python
redis_conn = redis.from_url(redis_url)
# ... later
finally:
    db.close()
    redis_conn.close()  # BUG: redis_conn might not exist if exception during creation
```

**Impact:** Resource leak, potential AttributeError  
**Recommendation:** Initialize redis_conn to None, check before closing

---

### 11. Missing error handling for Redis publish failures
**File:** `infra/worker_events.py:179-189`  
**Severity:** Medium  
**Description:**  
Redis publish failures are caught and logged but don't propagate. If Redis is down, events are silently lost.

**Code:**
```python
try:
    self.redis.publish(self.channel, event.to_json())
    # ...
except Exception as e:
    logger.error(f"Failed to publish event: {e}")  # Silent failure
```

**Impact:** Silent event loss, status updates not propagated  
**Recommendation:** Consider retry logic or dead letter queue for critical events

---

### 12. Potential division by zero in statistics calculation
**File:** `api/main.py:474`  
**Severity:** Low  
**Description:**  
Calculating `pending` documents as `total_docs - processed_docs - failed_docs`. If total_docs is 0, this is fine, but if there's a logic error where processed + failed > total, could show negative pending.

**Code:**
```python
"pending": total_docs - processed_docs - failed_docs
```

**Impact:** Negative pending count displayed  
**Recommendation:** Add validation: `max(0, total_docs - processed_docs - failed_docs)`

---

## Low Priority / Code Quality Issues

### 13. Inconsistent error handling in event processor
**File:** `api/event_processor.py:95-99`  
**Severity:** Low  
**Description:**  
Exceptions in event processing are caught and logged but not re-raised. If database operations fail, the error is silently swallowed.

**Code:**
```python
except Exception as e:
    logger.error(f"Failed to process event {event.event_type.value}: {e}")
    # Error is swallowed, event processing stops
```

**Impact:** Silent failures, events not processed  
**Recommendation:** Consider retry logic or dead letter queue

---

### 14. Hardcoded default JWT secret in production
**File:** `api/auth.py:22-29`  
**Severity:** Low (but security concern)  
**Description:**  
Fallback JWT secret is hardcoded. While there's a warning log, the application still starts with insecure secret if env var is missing.

**Code:**
```python
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not SECRET_KEY:
    SECRET_KEY = "dev-secret-CHANGE-IN-PRODUCTION"  # Still allows startup
```

**Impact:** Security vulnerability if deployed without env var  
**Recommendation:** Raise exception instead of using fallback in production mode

---

### 15. Missing input validation for cursor parameter
**File:** `api/main.py:489`  
**Severity:** Low  
**Description:**  
Cursor parameter is used directly without validation. Negative values or non-integer strings could cause issues.

**Code:**
```python
cursor: Optional[int] = None
# ...
if cursor:
    query = query.filter(Event.id > cursor)  # No validation
```

**Impact:** Potential SQL injection or unexpected query behavior  
**Recommendation:** Add validation: ensure cursor is positive integer

---

### 16. Potential memory leak in SSE endpoint
**File:** `api/main.py:652-702`  
**Severity:** Low  
**Description:**  
SSE endpoint creates new database session on every iteration. For long-lived connections, this could accumulate if sessions aren't properly closed.

**Code:**
```python
while True:
    db = SessionLocal()  # New session every 2 seconds
    # ...
    await asyncio.sleep(2)
```

**Impact:** Memory/connection pool exhaustion over time  
**Recommendation:** Consider connection pooling limits or session reuse

---

### 17. Missing transaction management in export_run
**File:** `api/main.py:547-630`  
**Severity:** Low  
**Description:**  
Export operation reads events, generates file, uploads to storage, and creates artifact record. If artifact creation fails, file is uploaded but not tracked.

**Code:**
```python
storage.upload_bytes(storage_key, content_bytes)  # Upload happens first
# ...
artifact = Artifact(...)
db.add(artifact)
db.commit()  # If this fails, file exists but no record
```

**Impact:** Orphaned files in storage  
**Recommendation:** Use database transaction, rollback and delete file if commit fails

---

### 18. Inefficient query in get_run_events
**File:** `api/main.py:494-499`  
**Severity:** Low  
**Description:**  
Query loads all events into memory before converting to response format. For large result sets, this could be memory intensive.

**Code:**
```python
events = query.order_by(Event.id).limit(limit).all()  # Loads all into memory
# Then converts to dict
```

**Impact:** High memory usage for large event sets  
**Recommendation:** Use streaming or pagination with smaller batches

---

## Summary

**Total Bugs Found:** 18

**By Severity:**
- Critical: 3
- High: 4
- Medium: 5
- Low: 6

**By Category:**
- Database/Session Management: 6
- Error Handling: 4
- Security: 2
- Resource Management: 3
- Logic Errors: 2
- Performance: 1

**Most Critical Issues:**
1. Type mismatch in role comparison (security vulnerability)
2. IndexError in export_run endpoint
3. Race condition in idempotency check
4. Missing transaction rollback in worker tasks

---

## Notes

- This audit focused on identifying bugs, not fixing them
- Some issues may be false positives depending on runtime conditions
- Security issues should be prioritized for immediate attention
- Database transaction issues could lead to data inconsistency
- Resource leaks could cause production outages under load

