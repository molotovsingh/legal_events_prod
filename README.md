# Legal Events Extraction - Production System

**Status:** 🚧 Work in Progress (Not Production-Ready)

This repository contains the production-track version of the legal events extraction system, forked from the POC testing environment (firstcut_testing_libs v0.10.1).

## 📊 Current Status

**Phase:** Initial Setup - Testing & Bug Discovery

This system is being developed iteratively. It is **not yet production-ready** and should not be deployed to production environments.

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
- At least one LLM API key (OPENROUTER_API_KEY recommended)

**Setup:**

```bash
# 1. Copy environment file
cp .env.example .env

# 2. Edit .env and add your API keys
#    At minimum: OPENROUTER_API_KEY=your_key_here

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

## 🔧 Services

This system uses Docker Compose to orchestrate:

1. **PostgreSQL** (port 5432) - Primary database
2. **Redis** (port 6379) - Job queue
3. **MinIO** (ports 9000, 9001) - S3-compatible storage
4. **FastAPI** (port 8000) - REST API
5. **Worker** - Background processing
6. **Frontend** (port 3000) - Simple UI

## 📝 Development Roadmap

This is a gradual improvement process with no fixed timeline:

- **Week 1:** Test system, discover bugs, document issues
- **Week 2-4:** Fix critical bugs
- **Week 5-8:** Add production features (monitoring, tests, CI/CD)
- **Week 9-12:** Polish and documentation
- **Future:** Hand off to experienced developers when ready

See `STATUS.md` (to be created) for current progress.

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
