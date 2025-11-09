# Run Processing Flow

This diagram shows the end-to-end flow after files are uploaded and you click the Process button.

```mermaid
sequenceDiagram
    participant UI as Frontend (Browser)
    participant API as FastAPI API
    participant Redis as Redis (Queue + Events)
    participant Worker as Worker (RQ)
    participant S3 as MinIO (S3)
    participant DB as Postgres (DB)

    Note over UI: 1) Create run 2) Upload files

    UI->>API: PUT /v1/runs/{run_id}/upload (file)
    API->>S3: Upload bytes (generate_document_key)
    S3-->>API: 200 OK
    API-->>UI: { storage_key }

    Note over UI: Click Process

    UI->>API: PUT /v1/runs/{run_id}/start (manifest)
    API->>Redis: SETNX lock (idempotency)
    API->>DB: INSERT documents, UPDATE run.status=PROCESSING, COMMIT
    API->>Redis: Enqueue job process_run(run_id)
    API-->>UI: { status: accepted, job_id }

    Note over Redis,Worker: Background processing begins

    Redis-->>Worker: RQ job: process_run
    Worker->>Redis: emit run.started
    Redis-->>API: worker event (run.started)
    API->>DB: UPDATE run.status=PROCESSING

    loop For each document
        Worker->>Redis: emit document.started
        Redis-->>API: worker event (document.started)
        API->>DB: UPDATE document.status=PROCESSING

        Worker->>S3: Download object to temp file
        Worker->>Worker: LegalEventsPipeline.extract
        Worker->>DB: INSERT events (transaction per document)
        Worker->>Redis: emit event.created (per event)
        Worker->>Redis: emit document.completed
        Redis-->>API: worker event (document.completed)
        API->>DB: UPDATE document.status=SUCCESS, counters
    end

    Worker->>Redis: emit run.completed (stats)
    Redis-->>API: worker event (run.completed)
    API->>DB: UPDATE run.status=SUCCESS, timings, cost

    Note over UI,API: Progress updates
    UI-->>API: GET /v1/runs/{id}/stream (SSE)
    API-->>UI: progress, complete, or timeout events

    opt Export
        UI->>API: GET /v1/runs/{id}/export?fmt=csv|xlsx|json
        API->>DB: SELECT events
        API->>S3: Upload artifact (storage key)
        API->>DB: INSERT artifact (rollback & delete on failure)
        API-->>UI: Stream file (download)
    end
```

Key behaviors
- Idempotency lock prevents concurrent duplicate starts for the same key and caches the accepted response for 24h.
- Worker never mutates run/document state directly; it emits events that the API consumes to update state.
- Event inserts are transactional per document to avoid partial persistence.
- SSE stream provides periodic progress updates and a final completion event.
- Export uploads the artifact to S3 and rolls back the object if the DB insert fails.

