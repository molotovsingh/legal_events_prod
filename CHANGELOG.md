# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

- **v0.9.x** - Worker heartbeat monitoring and testing infrastructure
- **v0.8.x** - Worker health monitoring with auto-restart
- **v0.7.x** - Multi-provider document extraction with UI selection
- **v0.6.x** - JWT authentication + provider discovery API
- **v0.5.x** - Document retry mechanism + local storage refactoring
- **v0.4.x** - Event-driven architecture (worker → API communication)
- **v0.3.x** - Technical debt sprint (provider import fixes)
- **v0.2.x** - Guardrails architecture (service boundaries)
- **v0.1.x** - Initial proof of concept
