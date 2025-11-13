# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.11.0] - 2025-11-13

### Added
- POST /v1/cases/{case_id}/documents endpoint for case-scoped document uploads
  - Validates case exists before accepting uploads
  - Returns file metadata in expected format
  - Reuses secure MinIO upload logic
- Dynamic API URL resolution in frontend
  - Eliminates localhost/127.0.0.1 CORS mismatches
  - Fixes connectivity issues in incognito/private browsing mode
  - Automatic same-origin detection for local development
- Debug badge showing resolved API URL with copy functionality
  - Improves troubleshooting visibility
  - One-click URL copying for support scenarios
- Enhanced CORS configuration for local development
  - Added 127.0.0.1 variants (ports 3000, 3001, 5001, 8000)
  - Added null origin for file:// protocol testing
  - Improved development experience across browsers

### Fixed
- **CRITICAL (P0):** Network error on Process button - field mismatch and worker params
  - Frontend expected 'id' but API returns 'run_id' (caused "Run undefined started" status)
  - Polling failed with 404 errors on GET /v1/runs/undefined
  - Worker job crashed with TypeError on unexpected kwargs (doc_extractor, status params)
  - Impact: Complete workflow failure when clicking "Process Documents"
- **CRITICAL (P0):** Client ID/Case ID document upload workflow bug
  - Frontend called non-existent endpoint POST /v1/cases/{case_id}/documents
  - All document uploads via simple.html failed with 404 errors
  - Impact: End-to-end workflow broken at document upload stage
- **CRITICAL (P0):** Redis connection leaks causing production outages
  - Health check endpoint leaked connections when Redis unavailable
  - Retry endpoint leaked connections on idempotency cache hits
  - Impact: Connection pool exhaustion under load
- **CRITICAL (P0):** Null pointer error in export generation
  - Missing null checks on case/client queries caused AttributeError
  - Impact: Worker crashes when foreign key references deleted
- **MAJOR (P1):** MinioStorage resource leak in long-running workers
  - Added MinioStorage.close() method to clear HTTP connection pool
  - Impact: Prevents connection pool exhaustion in production
- **MAJOR (P1):** Event consumer infinite loop blocking graceful shutdown
  - Added running flag to control event listening loop
  - Impact: Workers can now shut down within timeout window
- **MAJOR (P1):** Silent error swallowing in event consumer
  - Failed events now pushed to Redis DLQ (worker:events:dlq)
  - Impact: Prevents data loss, enables manual recovery
- **MAJOR (P1):** OpenRouter active_model → model field bug
  - Fixed AttributeError in fallback event parser
  - Impact: OpenRouter provider now fully functional
- Frontend error display showing "[object Object]"
  - Improved error message extraction from API responses
  - Added status-code-specific user guidance (401, 404, 500)
  - Better network error detection with actionable messages
- Frontend/backend API contract mismatches
  - Fixed field names: event_extractor_key → provider
  - Fixed field names: model_name → model
  - Fixed field names: doc_extractor_key → doc_extractor
  - Fixed response structure: uploadResponse.data → uploadResponse.data.files

### Changed
- Provider Architecture (v0.11.0) - COMPLETE
  - All 6 providers now in unified registry (openrouter, openai, anthropic, deepseek, google, langextract)
  - Enhanced startup validation instantiates adapters (catches real errors)
  - Removed legacy catalog validation (single source of truth)
  - Aligned metadata defaults to openrouter system-wide
  - Renamed DEFAULT_MODEL → GEMINI_DEFAULT_MODEL (eliminates ambiguity)
- Job queue integration improved
  - Changed from job object to job_id return value
  - Cleaner enqueue_job call signature
- Content Security Policy enforcement
  - Removed unsafe-inline from script-src
  - Moved inline event handlers to external scripts
  - Improved CSP compliance across both interfaces

### Security
- **MEDIUM:** CSP hardening with removal of unsafe-inline
  - All inline event handlers moved to app.js/simple.js
  - Reduced XSS attack surface

### Documentation
- Updated OPEN_BUGS_DIGEST.md - All P0 bugs resolved
- Added AUTH_IMPROVEMENTS_SUMMARY.md - Auth enhancement summary
- Added LOGIN_FIXED_README.md - Login troubleshooting guide
- Added QUICK_START_AUTH.md - Fast-track guide for new users
- Added docs/FRONTEND_ARCHITECTURE.md - Dual interface design rationale
- Added bug reports for P0 issues (BUG_REPORT_20251112T025945Z.md)
- Enhanced scripts: reset_dev_password.py, seed_test_users.py, sync_model_catalog.py

## [0.10.0] - 2025-11-11

### Added
- GET /v1/runs endpoint with comprehensive filtering and pagination
  - Filter by client_id, case_id, status
  - Pagination support (limit, offset, order_by, order)
  - Efficient single-query implementation eliminates N+1 queries
- DELETE /v1/runs/{run_id}/artifacts endpoint for artifact management
  - Authentication required for destructive operations
  - Enables operational cleanup and testing workflows
- GitHub Actions CI/CD pipeline
  - Multi-version Python testing (3.9, 3.10, 3.11, 3.12)
  - Automated quality gates (Ruff linting + formatting)
  - Test badge integration in README
- Comprehensive export API integration tests (test_export_integration.py)
  - Tests CSV, XLSX, JSON export generation
  - Validates artifact regeneration logic
  - 580 lines of new test infrastructure
- Frontend authentication UI
  - Login modal with email/password fields
  - JWT token persistence in localStorage
  - Automatic token injection via Axios interceptors
  - 401 response handling with re-authentication flow
- Frontend UI feature restoration
  - Export buttons for CSV, XLSX, JSON formats
  - Document extractor selector (Docling/Qwen3-VL dropdown)
  - Run details panel with metadata, timing, and cost estimates
  - SHA256 file hashing for integrity verification

### Security
- **CRITICAL:** Removed hardcoded admin credentials (admin123)
  - Environment-based admin provisioning via ADMIN_EMAIL/ADMIN_PASSWORD_HASH
  - Production deployments fail hard without proper credentials
  - Development mode creates non-admin dev@localhost user
- **HIGH:** Fixed admin provisioning bypass on existing deployments
  - Admin user creation now runs on every startup
  - Ensures admin access in all environments
- **HIGH:** Patched XSS vulnerabilities in frontend
  - Replaced innerHTML with secure DOM manipulation
  - Integrated DOMPurify for HTML sanitization
  - Removed onclick handlers, using addEventListener
- **HIGH:** Hardened JWT secret key handling
  - Removed development fallback for JWT_SECRET_KEY
  - Added minimum entropy validation (32 bytes / 64 hex chars)
  - All environments now require secure JWT secret
- **MEDIUM:** Fixed information disclosure in API error responses
  - Generic error messages with correlation IDs
  - Full error details retained in server logs
- Fixed Content Security Policy violations
  - Moved 743 lines of inline JavaScript to external app.js
  - CSP now properly allows API connections (connect-src)
  - No more browser blocking of application logic
- Fixed authentication bypass on DELETE /v1/runs/{run_id}/artifacts
  - All destructive operations now require authentication
  - Prevents unauthorized artifact deletion

### Fixed
- Negative pending document count in GET /v1/runs list
  - Applied max(0, ...) clamping for race condition handling
  - Consistent with single run endpoint implementation
- Test isolation issues preventing CI execution
  - Converted to FastAPI TestClient (no external services)
  - Proper pytest fixtures with module scope
  - Zero Redis/MinIO/PostgreSQL dependencies for provider tests
- Frontend authentication field name mismatch
  - Changed login request from username to email field
  - Fixed bcrypt hash validation errors
- Invalid bcrypt password hash for dev user
  - Replaced corrupted hash with valid bcrypt hash
  - Development login now works with dev@localhost/devpass123

### Changed
- Frontend architecture refactored for security
  - All JavaScript moved from inline to external app.js (743 lines)
  - frontend/index.html reduced from 1,600+ to ~700 lines
  - Clean HTML structure with proper CSP compliance
- Test infrastructure improved
  - 14 fully isolated provider endpoint tests
  - Module-scoped mocks prevent leakage
  - Air-gapped CI execution capability

### Documentation
- Updated README.md with Phase 3 completion status (83%)
- Enhanced LEGAL_EVENTS_CODE_MAP.md with new endpoints
- Added GRANITE_INTEGRATION_RESEARCH.md (351 lines)
- Marked DeepSeek integration as deferred (4 providers sufficient)

## [0.9.2] - 2025-11-10

### Fixed
- Critical export functionality bug causing blank browser tabs
  - Frontend: Changed from JSON response parsing to blob download handling
  - Backend: Added proper StreamingResponse handling with axios responseType: 'blob'
  - Impact: CSV, XLSX, and JSON exports now download correctly instead of opening blank tabs
- Export resilience improvements for edge cases
  - Regenerate artifacts when storage objects are missing (prevents 404 errors)
  - Update existing artifact metadata instead of creating duplicates
  - Add content-type specification for MinIO uploads (application/json, text/csv, xlsx)
  - Specify openpyxl engine explicitly for XLSX generation (prevents ambiguous engine selection)
- Worker status endpoint error handling
  - Return schema-compliant response on exceptions (prevents 500 errors)
  - Changed workers_with_heartbeat from None to 0 in fallback response
  - Ensures Pydantic validation always succeeds

### Technical Details
- Frontend changes (index.html): Export download handling with blob URLs
- Backend changes (api/main.py): Export endpoint hardening and artifact regeneration
- All changes backward compatible with existing API contracts

## [0.9.1] - 2025-11-09

### Added
- Comprehensive LLM provider API key validation test suite (test_providers.py)
  - Tests all 5 configured providers (OpenRouter, Anthropic, OpenAI, LangExtract, DeepSeek)
  - Validates extraction quality with real PDF documents
  - Reports: 4/5 API keys working correctly, detailed cost analysis per provider
- Comprehensive export functionality test suite (test_export_functionality.py)
  - Tests CSV, XLSX, and JSON export generation
  - Validates output structure and content integrity
  - Reports: All 3 export formats working (100% success rate)
- Operations Runbook (docs/OPERATIONS_RUNBOOK.md)
  - Troubleshooting procedures for 3 common scenarios
  - Monitoring and alerting setup guide (3 alert rules, 2 scripts)
  - Redis inspection commands and escalation paths
- Pydantic schemas for worker status monitoring (api/schemas.py)
  - WorkerStatusResponse, WorkerHeartbeat, WorkerInfo, QueueStats models
  - Comprehensive docstrings documenting health semantics

### Changed
- Enhanced LangExtract error handling with retry logic
  - Exponential backoff with 3 retry attempts
  - Improved API key error messages with setup instructions
  - Better text length validation and diagnostics

### Fixed
- TypeError in provider tests when text extraction returns None
  - Split null check from length validation to prevent len(None) calls
  - Document extraction failures now report explicit status instead of raising exceptions
- Documentation accuracy improvements
  - Removed brittle line-number references from code map and runbook
  - Corrected Redis key patterns (worker:heartbeat:* format)
  - Fixed heartbeat timing documentation (10s emit interval, 30s TTL, 60s stale threshold)
- LangExtract provider failure documentation
  - Root cause: Python version incompatibility (requires Python >=3.10)
  - Replaced "dependency issue" with accurate Python version constraint
  - Added actionable solutions for Docker and local development

### Documentation
- Expanded worker status API documentation with example responses
- Added monitoring endpoints comparison (basic /health vs /v1/workers/status)
- Updated README.md with heartbeat-aware monitoring guidance
- Enhanced STATUS.md with health semantics alignment changes
- Created PROVIDER_TEST_RESULTS.md (235 lines) with validation results
- Created EXPORT_TEST_RESULTS.md (245 lines) with export format analysis

## [0.9.0] - 2025-11-09

### Added
- Worker heartbeat system with stale detection
  - Workers emit heartbeats to Redis every 10 seconds
  - Heartbeats include worker metadata (hostname, PID, job stats)
  - 30-second TTL with auto-expiration on crash
  - Stale heartbeat detection (>60 seconds threshold)
- Enhanced /v1/workers/status endpoint with heartbeat data
  - Per-worker liveness status (last_beat, seconds_ago, is_alive)
  - New metrics: workers_with_heartbeat, workers_stale
  - Health degradation detection for monitoring/alerting
- Infrastructure for automatic stale worker cleanup

### Changed
- Health detection now requires active heartbeats (not just registration)
  - "degraded" status if zero workers registered
  - "degraded" status if any stale heartbeats detected
  - "healthy" only when workers active AND heartbeats recent

## [0.8.2] - 2025-11-08

### Documentation
- Incident response documentation for event provider import failures
  - Root cause analysis of factory_callable import path issues
  - Impact assessment (only langextract provider working)
  - Workaround documentation with UI default selection update
- Deployment workflow documentation
  - Two-stage Docker architecture (immutable production + dev hot-reload)
  - Production vs development deployment commands
  - Environment variable validation patterns

## [0.8.1] - 2025-11-08

### Documentation
- Incident documentation for worker restart timing race condition
  - Detailed root cause analysis and timeline
  - Impact assessment on worker health monitoring
  - Remediation plan with heartbeat TTL adjustments

## [0.8.0] - 2025-11-08

### Added
- Worker health monitoring system
  - Real-time worker registration via Redis sets
  - /v1/workers/status endpoint with detailed worker information
  - Auto-restart mechanism for crashed workers
  - Health status reporting ("healthy", "degraded", "unhealthy")
- Worker lifecycle management
  - Graceful shutdown handling
  - Worker metadata tracking (hostname, PID, start time)
  - Job statistics (queued, started, finished, failed)

### Changed
- Health endpoint now checks worker availability
  - Returns "degraded" if no workers available
  - Enhanced health response with worker_count metric

## [0.7.1] - 2025-11-07

### Documentation
- Incident documentation for CORS preflight failures
  - Root cause analysis of middleware ordering
  - Impact assessment and remediation plan
  - Production deployment verification steps

## [0.7.0] - 2025-11-07

### Added
- Document extractor selection in UI
  - Dropdown menu to select between docling (default) and qwen_vl
  - Provider configuration persistence across uploads
  - Dynamic extractor factory integration
- Enhanced document processing pipeline
  - Support for multiple document extraction providers
  - Graceful fallback when qwen_vl unavailable
  - Provider-specific error handling and logging

### Changed
- Document upload form now includes extractor selection
- Backend accepts document_extractor parameter in POST /v1/runs/
- Improved error messages for unsupported extractors

## [0.6.2] - 2025-11-06

### Fixed
- Critical race condition in run status updates
  - Worker tasks now use event-driven communication
  - API event processor updates run status via Redis pub/sub
  - Eliminated direct database writes from worker service
- Service boundary violations
  - Removed worker database mutation code
  - Enforced read-only worker access to runs/documents
  - Implemented proper event emission for status changes

### Changed
- Run status updates now flow through event system
  - Worker emits RUN_STARTED, RUN_COMPLETED, RUN_FAILED events
  - API consumes events and updates database
  - Maintains strict service boundaries

## [0.6.1] - 2025-11-06

### Added
- Deployment infrastructure with Docker Compose override pattern
  - docker-compose.yml: Production (immutable images, COPY only)
  - docker-compose.override.yml: Development (bind mounts for hot-reload)
- Environment-specific deployment commands
  - Production: docker compose -f docker-compose.yml up -d
  - Development: docker compose up (auto-loads override)

### Documentation
- DEPLOYMENT.md with infrastructure architecture
- Enhanced README.md with deployment instructions
- Service boundary enforcement documentation

## [0.6.0] - 2025-11-06

### Added
- JWT-based authentication system
  - POST /v1/auth/login endpoint (username/password)
  - POST /v1/auth/register endpoint (admin-only)
  - Access token generation with configurable expiry
  - Bearer token authentication for all API endpoints
- Provider discovery API
  - GET /v1/providers endpoint
  - Lists available document and event extractors
  - Dynamic provider availability detection
  - Frontend provider dropdown population

### Changed
- All API endpoints now require authentication (except /health, /docs)
- Frontend updated to handle authentication flow
  - Login/register forms
  - Token storage in localStorage
  - Automatic token inclusion in API requests
- Provider selection now uses dynamic API data

### Security
- Password hashing with bcrypt
- JWT secret key configuration via environment variables
- Protected admin-only registration endpoint

## [0.5.2] - 2025-11-05

### Changed
- Storage architecture refactored from S3 to local filesystem
  - Documents stored in ./storage/documents/
  - Artifacts stored in ./storage/artifacts/
  - Removed all AWS S3 dependencies and credentials
- Simplified deployment with no cloud dependencies
- Improved local development experience

### Removed
- AWS S3 storage backend
- S3-related environment variables
- boto3 and AWS SDK dependencies

## [0.5.1] - 2025-11-05

### Security
- Enforced authentication on all document upload endpoints
  - POST /v1/clients/{client_id}/cases/{case_id}/runs/ now requires auth
  - Prevents unauthorized document processing
- Added authentication enforcement tests
- Updated frontend to always include auth tokens

### Fixed
- Security vulnerability allowing unauthenticated document uploads

## [0.5.0] - 2025-11-05

### Added
- Document retry mechanism for failed processing
  - POST /v1/runs/{run_id}/documents/{document_id}/retry endpoint
  - Allows reprocessing of failed documents without full run retry
  - Maintains original document metadata and timestamps
- Enhanced error recovery
  - Per-document retry tracking
  - Status history preservation
  - Granular failure handling

### Changed
- Document processing now supports individual retry
- Run retry endpoint can optionally retry all documents
- Improved error messages for document processing failures

---

## Version History Summary

- **v0.10.x** - Security hardening + API enhancements + UI restoration
- **v0.9.x** - Worker heartbeat monitoring and testing infrastructure
- **v0.8.x** - Worker health monitoring with auto-restart
- **v0.7.x** - Multi-provider document extraction with UI selection
- **v0.6.x** - JWT authentication + provider discovery API
- **v0.5.x** - Document retry mechanism + local storage refactoring
- **v0.4.x** - Event-driven architecture (worker → API communication)
- **v0.3.x** - Technical debt sprint (provider import fixes)
- **v0.2.x** - Guardrails architecture (service boundaries)
- **v0.1.x** - Initial proof of concept
