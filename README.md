# Legal Events Extraction - Production System

**Status:** 🚧 Work in Progress (Not Production-Ready)

This repository contains the production-track version of the legal events extraction system, forked from the POC testing environment (firstcut_testing_libs v0.10.1).

## 📊 Current Status

**Phase:** Iterative Fixes & Production Hardening

This system is being developed iteratively. Core functionality is validated but **not yet production-ready** and should not be deployed to production environments without thorough testing.

### What Works
- ✅ Directory structure created
- ✅ Core extraction pipeline copied from proven POC
- ⏳ Testing in progress

### What Needs Work
- ⚠️ System integration testing pending
- ⚠️ Bug fixes needed
- ⚠️ Production features (monitoring, auth, etc.) to be added
- ⚠️ Documentation to be completed

## 🏗️ Architecture

```
legal-events-production/
├── core/              # Battle-tested extraction logic (from POC)
│   ├── legal_pipeline_refactored.py
│   ├── docling_adapter.py
│   ├── *_adapter.py (OpenRouter, Anthropic, OpenAI, etc.)
│   └── config.py, constants.py, catalogs
├── api/               # FastAPI backend (needs testing)
│   ├── main.py       # REST API endpoints
│   ├── models.py     # SQLAlchemy models
│   └── schemas.py    # Pydantic validation
├── worker/            # Background processing (needs testing)
│   ├── main.py       # Worker entry point
│   └── tasks.py      # Document processing tasks
├── frontend/          # Simple UI
├── migrations/        # Database migrations (Alembic)
├── tests/             # Test suite (to be added)
└── docker-compose.yml # Service orchestration
```

## 🚀 Quick Start (For Testing)

**Prerequisites:**
- Docker and Docker Compose installed
- **At least ONE LLM API key** (choose one based on your preference):
  - `OPENROUTER_API_KEY` (recommended - unified access to multiple models)
  - `ANTHROPIC_API_KEY` (for Claude models only)
  - `OPENAI_API_KEY` (for GPT models only)
  - `GEMINI_API_KEY` (for Gemini models only)
  - `DEEPSEEK_API_KEY` (for DeepSeek models only)

**Setup:**

```bash
# 1. Copy environment file
cp .env.example .env

# 2. Edit .env and add at least ONE API key
#    Recommended: OPENROUTER_API_KEY=your_key_here
#    Alternative: Choose ANTHROPIC, OPENAI, GEMINI, or DEEPSEEK

# 3. Start services
./start.sh start

# 4. Check service status
./start.sh status

# 5. View logs
./start.sh logs
```

**Access Points:**
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- MinIO Console: http://localhost:9001 (minioadmin/minioadmin123)

## 📊 Monitoring Endpoints

The system provides two health monitoring endpoints:

### Basic Health Check
```bash
GET /health
```
Returns overall system health (database, storage, queue, workers). The "workers" component only checks if workers are registered, not if they have active heartbeats.

**Use for**: Load balancer health checks, basic uptime monitoring

### Detailed Worker Status (Recommended for Monitoring)
```bash
GET /v1/workers/status
```
Returns detailed worker health with **heartbeat-aware liveness detection**:
- Active heartbeat count
- Stale heartbeat detection (>60s)
- Per-worker heartbeat details (last_beat, is_alive, hostname, pid)
- Queue depths and processing stats

**Use for**: Production monitoring, alerting, troubleshooting

**Example:**
```bash
# Check worker health
curl http://localhost:8000/v1/workers/status | jq '.healthy, .status'

# Get detailed heartbeat info
curl http://localhost:8000/v1/workers/status | jq '.workers[].heartbeat'
```

**See**: [docs/OPERATIONS_RUNBOOK.md](docs/OPERATIONS_RUNBOOK.md) for troubleshooting guide

## 🔧 Services

This system uses Docker Compose to orchestrate:

1. **PostgreSQL** (port 5432) - Primary database
2. **Redis** (port 6379) - Job queue
3. **MinIO** (ports 9000, 9001) - S3-compatible storage
4. **FastAPI** (port 8000) - REST API
5. **Worker** - Background processing
6. **Frontend** (port 3000) - Simple UI

## 📝 Development Roadmap

This system follows an **iterative improvement approach** with no fixed deadlines:

### Phased Development

- **Phase 1: Repository Setup** ✅ **COMPLETE**
  - Clean workspace created, code migrated from POC v0.10.1
  - Docker configuration fixed for production structure

- **Phase 2: Testing & Bug Discovery** ✅ **COMPLETE** (v0.9.2)
  - Docker containers tested with sample PDFs
  - Comprehensive test suites created (test_providers.py, test_export_functionality.py)
  - 3/5 LLM providers validated (OpenRouter, Anthropic, OpenAI)
  - All export formats validated (CSV, XLSX, JSON - 100% success)
  - Critical bugs discovered and fixed (export functionality, worker monitoring)

- **Phase 3: Iterative Fixes** 🚧 **CURRENT PHASE**
  - Fixing discovered bugs one by one (v0.9.0-v0.9.2)
  - Export resilience improvements, worker health monitoring
  - No rush, gradual quality improvement

- **Phase 4: Production Hardening** 📋 **FUTURE**
  - Add monitoring, tests, CI/CD as needed
  - Authentication, rate limiting (if required)

- **Phase 5: Documentation** 📋 **ONGOING**
  - Document features as they stabilize
  - Add deployment guides when deployment works

- **Phase 6: Handoff** 📋 **FUTURE**
  - Transfer to experienced developers when production-ready
  - Timeline: TBD (1-6 months depending on progress)

**See `STATUS.md` for detailed progress tracking and current task checklist.**

## 🔗 Related Repositories

- **POC Repo:** `firstcut_testing_libs` - Testing environment (v0.10.1)
  - Active experimentation with models and prompts
  - Streamlit/Flask UI for quick testing
  - Discoveries flow from POC → Production

## ⚠️ Important Notes

1. **Not Production-Ready:** This system is under active development
2. **Testing Required:** All components need integration testing
3. **Bug Reports:** Document all issues in GitHub Issues
4. **Gradual Improvement:** Quality increases over time, no rush

## 📚 Documentation

Full documentation will be added as the system stabilizes:
- TESTING.md - How to test the system (coming soon)
- DEPLOYMENT.md - Deployment guide (coming soon)
- ARCHITECTURE.md - Technical details (coming soon)
- HANDOFF.md - For future team handoff (coming soon)

## 🆘 Troubleshooting

```bash
# Services won't start
./start.sh clean
./start.sh start

# View detailed logs
./start.sh logs

# Check specific service
docker logs legal_events_api
docker logs legal_events_worker
```

## 📄 License

Private and confidential. All rights reserved.

---

**Forked from:** firstcut_testing_libs v0.10.1 (2025-10-20)
**Purpose:** Production-track system with gradual improvements
**Status:** Pre-alpha, not production-ready
