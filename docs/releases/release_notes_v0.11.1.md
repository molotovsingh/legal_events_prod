# Legal Events Production v0.11.1 - Type-Safe Job Enqueuing Hotfix

## 🎯 What's Fixed

This hotfix release improves code quality and prevents runtime errors by introducing **type-safe job enqueuing wrappers**.

## ✨ Improvements

### Type-Safe Job Enqueuing

**Before (v0.11.0):**
```python
job_id = enqueue_job("process_run", run_id=123, provider="openrouter", model="llama-3")
```
❌ String-based job names prone to typos
❌ No compile-time validation
❌ No IDE autocomplete support

**After (v0.11.1):**
```python
job_id = enqueue_process_run(run_id=123, provider="openrouter", model="llama-3")
```
✅ Function-based routing eliminates typos
✅ Type checking at development time
✅ Full IDE support (autocomplete, refactoring, go-to-definition)

### New Functions in `infra/queue.py`

- **`enqueue_process_run()`** - Type-safe wrapper for run processing jobs
- **`enqueue_process_document()`** - Type-safe wrapper for document processing jobs
- **`enqueue_generate_artifacts()`** - Type-safe wrapper for artifact generation jobs

### Frontend Improvements

- Added **`calculateFileSHA256()`** helper function for file integrity verification
- Fixed indentation issues in `frontend/simple.js`

## 🔧 Technical Details

### Impact

- **Eliminates runtime errors** from typos in job names
- **Better developer experience** with full IDE support
- **Easier refactoring** - renaming functions updates all call sites automatically
- **Compile-time safety** - invalid function signatures caught immediately

### Changed API Endpoints

`api/main.py` now uses:
```python
# Line 769
job_id = enqueue_process_run(
    run_id=db_run.id,
    provider=db_run.provider,
    model=db_run.model
)
```

Instead of:
```python
job_id = enqueue_job("process_run", ...)
```

## 📦 What's Included

- 3 files changed
- 41 lines added
- 17 lines removed
- No breaking changes
- 100% backward compatible

## 🚀 Upgrade Instructions

If you're on v0.11.0:

```bash
# Pull latest
git pull origin main
git checkout v0.11.1

# Restart API service (picks up new code)
docker compose restart legal_events_api

# Verify
curl http://localhost:8000/health
```

## 📝 Full Changelog

See [CHANGELOG.md](https://github.com/molotovsingh/legal_events_prod/blob/main/CHANGELOG.md#0111---2025-11-13) for complete details.

## ⬆️ Upgrading from v0.11.0

This is a **patch release** with no breaking changes. Simply pull and restart services.

**Recommended:** If you have custom job enqueuing code, migrate to the new type-safe wrappers for better safety.

🤖 Powered by [Claude Code](https://claude.com/claude-code)
