"""
Comprehensive Test Suite for Code Audit Fixes
Tests all 5 critical security and stability fixes:
1. Idempotency race condition (api/main.py)
2. Export relationship guard (api/main.py)
3. Temp file cleanup (worker/tasks_refactored.py)
4. Batch transaction (worker/tasks_refactored.py)
5. Redis connection guard (worker/tasks_refactored.py)
"""

import os
import time
import tempfile
import threading
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
try:
    import redis
except ImportError:
    redis = None  # Redis not installed in test environment
import json

# Test environment setup
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379/15"
os.environ["JWT_SECRET_KEY"] = "test_secret_for_audit_tests"
os.environ["MINIO_ENDPOINT"] = "localhost:9000"
os.environ["MINIO_ACCESS_KEY"] = "test_access"
os.environ["MINIO_SECRET_KEY"] = "test_secret"
os.environ["APP_ENV"] = "development"

from infra.models import (
    Base, Client, Case, Run, Document, Event, Artifact,
    RunStatus, DocumentStatus, ClientStatus, CaseStatus
)
from infra.database import get_db
from worker.tasks_refactored import process_run
from api.main import app
from api.auth import create_access_token


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def db_session():
    """Create a clean test database for each test"""
    # Use check_same_thread=False for SQLite to work with FastAPI TestClient
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def test_client(db_session):
    """FastAPI test client with database override"""
    def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers(db_session):
    """Authentication headers for protected endpoints"""
    from infra.models import User, UserRole
    from api.auth import get_password_hash
    
    # Create test user in database
    test_user = User(
        email="test@audit.local",
        name="Test User",
        role=UserRole.ADMIN,
        password_hash=get_password_hash("test123"),
        is_active=True
    )
    db_session.add(test_user)
    db_session.commit()
    
    token = create_access_token({"sub": "test@audit.local", "role": "admin"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def test_data(db_session):
    """Standard test data hierarchy"""
    client = Client(name="Audit Test Client", reference_code="ATC001", status=ClientStatus.ACTIVE)
    db_session.add(client)
    db_session.flush()
    
    case = Case(client_id=client.id, name="Audit Test Case", status=CaseStatus.OPEN)
    db_session.add(case)
    db_session.flush()
    
    run = Run(
        case_id=case.id,
        provider="langextract",
        model="gemini-1.5-flash",
        status=RunStatus.QUEUED
    )
    db_session.add(run)
    db_session.flush()
    
    doc = Document(
        run_id=run.id,
        case_id=case.id,
        filename="test.pdf",
        storage_key="test/test.pdf",
        status=DocumentStatus.PENDING
    )
    db_session.add(doc)
    db_session.commit()
    
    return {"client": client, "case": case, "run": run, "doc": doc}


@pytest.fixture
def mock_redis():
    """Mock Redis connection for testing"""
    mock_r = MagicMock()
    mock_r.get.return_value = None
    mock_r.set.return_value = True
    mock_r.setex.return_value = True
    mock_r.delete.return_value = True
    mock_r.close.return_value = None
    return mock_r


# ============================================================================
# FIX #1: Idempotency Race Condition Tests
# ============================================================================

class TestIdempotencyRaceCondition:
    """Test atomic lock prevents duplicate run execution"""
    
    def test_idempotency_lock_prevents_concurrent_execution(self, test_client, db_session, test_data, auth_headers, mock_redis):
        """Test that concurrent requests with same idempotency_key don't execute twice"""
        idempotency_key = "test-race-key-001"
        
        # First request acquires lock
        mock_redis.set.return_value = True  # Lock acquired
        mock_redis.get.return_value = None  # No cached result yet
        
        with patch('redis.from_url', return_value=mock_redis):
            with patch('api.main.enqueue_job', return_value="job_001"):
                response1 = test_client.put(
                    f"/v1/runs/{test_data['run'].id}/start",
                    json={"files": [], "idempotency_key": idempotency_key},
                    headers=auth_headers
                )
        
        assert response1.status_code == 200
        job_id_1 = response1.json()["job_id"]
        
        # Verify lock was acquired with SETNX (nx=True)
        lock_calls = [call for call in mock_redis.set.call_args_list 
                      if 'lock' in str(call)]
        assert len(lock_calls) > 0
        # Check nx=True parameter was used
        for call_obj in lock_calls:
            if 'nx' in call_obj.kwargs:
                assert call_obj.kwargs['nx'] is True
    
    def test_idempotency_returns_conflict_for_concurrent_request(self, test_client, test_data, auth_headers, mock_redis):
        """Test that second request gets 409 Conflict when lock is held"""
        idempotency_key = "test-race-key-002"
        
        # Second request fails to acquire lock
        mock_redis.set.return_value = False  # Lock NOT acquired (already held)
        mock_redis.get.return_value = None   # No cached result yet
        
        with patch('redis.from_url', return_value=mock_redis):
            response = test_client.put(
                f"/v1/runs/{test_data['run'].id}/start",
                json={"files": [], "idempotency_key": idempotency_key},
                headers=auth_headers
            )
        
        # Should return 409 Conflict
        assert response.status_code == 409
        assert "duplicate request" in response.json()["detail"].lower()
    
    def test_idempotency_returns_cached_result_after_completion(self, test_client, test_data, auth_headers, mock_redis):
        """Test that completed requests return cached result"""
        idempotency_key = "test-race-key-003"
        cached_response = json.dumps({
            "status": "accepted",
            "run_id": test_data['run'].id,
            "job_id": "cached_job_123",
            "message": "Run processing started"
        })
        
        # Cached result exists
        mock_redis.get.return_value = cached_response.encode('utf-8')
        
        with patch('redis.from_url', return_value=mock_redis):
            response = test_client.put(
                f"/v1/runs/{test_data['run'].id}/start",
                json={"files": [], "idempotency_key": idempotency_key},
                headers=auth_headers
            )
        
        assert response.status_code == 200
        assert response.json()["job_id"] == "cached_job_123"
        
        # Verify set() was NOT called (no new lock needed)
        assert not any('lock' in str(call) and call.kwargs.get('nx') 
                      for call in mock_redis.set.call_args_list)
    
    def test_idempotency_lock_released_after_success(self, test_client, db_session, test_data, auth_headers, mock_redis):
        """Test that lock is released after successful job enqueue"""
        idempotency_key = "test-race-key-004"
        mock_redis.set.return_value = True  # Lock acquired
        
        with patch('redis.from_url', return_value=mock_redis):
            with patch('api.main.enqueue_job', return_value="job_004"):
                response = test_client.put(
                    f"/v1/runs/{test_data['run'].id}/start",
                    json={"files": [], "idempotency_key": idempotency_key},
                    headers=auth_headers
                )
        
        assert response.status_code == 200
        
        # Verify lock was deleted
        delete_calls = [call for call in mock_redis.delete.call_args_list 
                       if 'lock' in str(call)]
        assert len(delete_calls) > 0
    
    def test_idempotency_graceful_degradation_on_redis_failure(self, test_client, db_session, test_data, auth_headers):
        """Test that Redis failures don't block request processing"""
        idempotency_key = "test-race-key-005"
        
        # Mock Redis to raise exception
        mock_redis_fail = MagicMock()
        mock_redis_fail.get.side_effect = Exception("Redis unavailable")
        
        with patch('redis.from_url', return_value=mock_redis_fail):
            with patch('api.main.enqueue_job', return_value="job_005"):
                response = test_client.put(
                    f"/v1/runs/{test_data['run'].id}/start",
                    json={"files": [], "idempotency_key": idempotency_key},
                    headers=auth_headers
                )
        
        # Should still succeed (graceful degradation)
        assert response.status_code == 200


# ============================================================================
# FIX #2: Export Relationship Guard Tests
# ============================================================================

class TestExportRelationshipGuard:
    """Test robust handling of missing relationships in export"""
    
    def test_export_handles_missing_run_gracefully(self, test_client, db_session, test_data, auth_headers):
        """Test export fails gracefully when run is missing"""
        # Create events but delete the run
        event = Event(
            run_id=999999,  # Non-existent run
            document_id=test_data['doc'].id,
            number=1,
            date="2025-01-01",
            event_particulars="Test event",
            citation="Test citation",
            document_reference="test.pdf"
        )
        db_session.add(event)
        db_session.commit()
        
        # Mock storage
        with patch('api.main.MinioStorage'):
            response = test_client.get(f"/v1/runs/999999/export?fmt=csv")
        
        # Should return 404 with clear error
        assert response.status_code == 404
        assert "run not found" in response.json()["detail"].lower()
    
    def test_export_handles_missing_case_gracefully(self, test_client, db_session, test_data, auth_headers):
        """Test export fails gracefully when case is missing"""
        # Create run with invalid case_id
        orphan_run = Run(
            case_id=999999,  # Non-existent case
            provider="test",
            model="test",
            status=RunStatus.SUCCESS
        )
        db_session.add(orphan_run)
        db_session.flush()
        
        event = Event(
            run_id=orphan_run.id,
            document_id=test_data['doc'].id,
            number=1,
            date="2025-01-01",
            event_particulars="Test",
            citation="Test",
            document_reference="test.pdf"
        )
        db_session.add(event)
        db_session.commit()
        
        with patch('api.main.MinioStorage'):
            response = test_client.get(f"/v1/runs/{orphan_run.id}/export?fmt=csv")
        
        assert response.status_code == 404
        assert "case not found" in response.json()["detail"].lower()
    
    def test_export_no_events_returns_404(self, test_client, db_session, test_data):
        """Test export returns 404 when no events exist"""
        with patch('api.main.MinioStorage'):
            response = test_client.get(f"/v1/runs/{test_data['run'].id}/export?fmt=csv")
        
        assert response.status_code == 404
        assert "no events" in response.json()["detail"].lower()


# ============================================================================
# FIX #3: Temp File Cleanup Tests
# ============================================================================

class TestTempFileCleanup:
    """Test guaranteed cleanup of temporary files"""
    
    def test_temp_file_cleaned_on_success(self, db_session, test_data):
        """Test that temp file is deleted after successful processing"""
        temp_files_created = []
        
        def track_tempfile(*args, **kwargs):
            tmp = tempfile.NamedTemporaryFile(*args, **kwargs)
            temp_files_created.append(tmp.name)
            return tmp
        
        with patch('tempfile.NamedTemporaryFile', side_effect=track_tempfile):
            with patch('worker.tasks_refactored.MinioStorage') as mock_storage:
                with patch('worker.tasks_refactored.LegalEventsPipeline') as mock_pipeline:
                    with patch('worker.tasks_refactored.SessionLocal', return_value=db_session):
                        with patch('redis.from_url') as mock_redis_factory:
                            # Mock Redis
                            mock_redis = MagicMock()
                            mock_redis_factory.return_value = mock_redis
                            
                            # Setup mocks
                            mock_storage_instance = Mock()
                            mock_storage_instance.download_file = Mock()
                            mock_storage.return_value = mock_storage_instance
                            
                            mock_pipeline_instance = Mock()
                            mock_pipeline_instance.process_documents_for_legal_events.return_value = (
                                Mock(empty=True), None
                            )
                            mock_pipeline.return_value = mock_pipeline_instance
                            
                            # Process run
                            result = process_run(test_data['run'].id)
        
        # Verify all temp files were cleaned up
        for tmp_path in temp_files_created:
            assert not os.path.exists(tmp_path), f"Temp file not cleaned: {tmp_path}"
    
    def test_temp_file_cleaned_on_exception(self, db_session, test_data):
        """Test that temp file is deleted even when processing fails"""
        temp_files_created = []
        
        def track_tempfile(*args, **kwargs):
            tmp = tempfile.NamedTemporaryFile(*args, **kwargs)
            temp_files_created.append(tmp.name)
            return tmp
        
        with patch('tempfile.NamedTemporaryFile', side_effect=track_tempfile):
            with patch('worker.tasks_refactored.MinioStorage') as mock_storage:
                with patch('worker.tasks_refactored.LegalEventsPipeline') as mock_pipeline:
                    with patch('worker.tasks_refactored.SessionLocal', return_value=db_session):
                        with patch('redis.from_url') as mock_redis_factory:
                            # Mock Redis
                            mock_redis = MagicMock()
                            mock_redis_factory.return_value = mock_redis
                            
                            # Setup mocks
                            mock_storage_instance = Mock()
                            mock_storage_instance.download_file = Mock()
                            mock_storage.return_value = mock_storage_instance
                            
                            # Make pipeline raise exception
                            mock_pipeline_instance = Mock()
                            mock_pipeline_instance.process_documents_for_legal_events.side_effect = \
                                Exception("Processing failed!")
                            mock_pipeline.return_value = mock_pipeline_instance
                            
                            # Process run (will fail)
                            result = process_run(test_data['run'].id)
        
        # Verify temp files were still cleaned up despite exception
        for tmp_path in temp_files_created:
            assert not os.path.exists(tmp_path), f"Temp file leaked: {tmp_path}"
    
    def test_temp_file_cleanup_handles_already_deleted(self, db_session, test_data):
        """Test cleanup doesn't crash if file already deleted"""
        with patch('worker.tasks_refactored.MinioStorage') as mock_storage:
            with patch('worker.tasks_refactored.LegalEventsPipeline') as mock_pipeline:
                with patch('worker.tasks_refactored.SessionLocal', return_value=db_session):
                    with patch('redis.from_url') as mock_redis_factory:
                        with patch('os.unlink', side_effect=FileNotFoundError("Already deleted")):
                            # Mock Redis
                            mock_redis = MagicMock()
                            mock_redis_factory.return_value = mock_redis
                            
                            # Setup mocks
                            mock_storage_instance = Mock()
                            mock_storage_instance.download_file = Mock()
                            mock_storage.return_value = mock_storage_instance
                            
                            mock_pipeline_instance = Mock()
                            mock_pipeline_instance.process_documents_for_legal_events.return_value = (
                                Mock(empty=True), None
                            )
                            mock_pipeline.return_value = mock_pipeline_instance
                            
                            # Should not crash
                            result = process_run(test_data['run'].id)
                            assert result["success"] is True


# ============================================================================
# FIX #4: Batch Transaction Tests
# ============================================================================

class TestBatchTransaction:
    """Test atomic event commits"""
    
    def test_all_events_committed_atomically(self, db_session, test_data):
        """Test that all events are committed in single transaction"""
        # Create mock events data
        mock_events = [
            {"number": i, "date": "2025-01-01", "event_particulars": f"Event {i}",
             "citation": "", "document_reference": "test.pdf"}
            for i in range(1, 51)  # 50 events
        ]
        
        with patch('worker.tasks_refactored.MinioStorage') as mock_storage:
            with patch('worker.tasks_refactored.LegalEventsPipeline') as mock_pipeline:
                with patch('worker.tasks_refactored.SessionLocal', return_value=db_session):
                    with patch('redis.from_url') as mock_redis_factory:
                        # Mock Redis
                        mock_redis = MagicMock()
                        mock_redis_factory.return_value = mock_redis
                        
                        # Setup mocks
                        mock_storage_instance = Mock()
                        mock_storage_instance.download_file = Mock()
                        mock_storage.return_value = mock_storage_instance
                        
                        # Create DataFrame with events
                        import pandas as pd
                        from core.constants import FIVE_COLUMN_HEADERS
                        df = pd.DataFrame([
                            {FIVE_COLUMN_HEADERS[0]: e['number'],
                             FIVE_COLUMN_HEADERS[1]: e['date'],
                             FIVE_COLUMN_HEADERS[2]: e['event_particulars'],
                             FIVE_COLUMN_HEADERS[3]: e['citation'],
                             FIVE_COLUMN_HEADERS[4]: e['document_reference']}
                            for e in mock_events
                        ])
                        
                        mock_pipeline_instance = Mock()
                        mock_pipeline_instance.process_documents_for_legal_events.return_value = (df, None)
                        mock_pipeline.return_value = mock_pipeline_instance
                        
                        # Process run
                        result = process_run(test_data['run'].id)
        
        # Verify all 50 events were created atomically
        events = db_session.query(Event).filter(Event.run_id == test_data['run'].id).all()
        assert len(events) == 50, f"Expected 50 events, got {len(events)}"
    
    def test_commit_count_optimized(self, db_session, test_data):
        """Test that events are committed in a single batch, not per-event"""
        with patch('worker.tasks_refactored.MinioStorage') as mock_storage:
            with patch('worker.tasks_refactored.LegalEventsPipeline') as mock_pipeline:
                with patch('worker.tasks_refactored.SessionLocal', return_value=db_session):
                    with patch('redis.from_url') as mock_redis_factory:
                        # Mock Redis
                        mock_redis = MagicMock()
                        mock_redis_factory.return_value = mock_redis
                        
                        # Setup mocks
                        mock_storage_instance = Mock()
                        mock_storage_instance.download_file = Mock()
                        mock_storage.return_value = mock_storage_instance
                        
                        # Create DataFrame with 10 events
                        import pandas as pd
                        from core.constants import FIVE_COLUMN_HEADERS
                        df = pd.DataFrame([
                            {FIVE_COLUMN_HEADERS[0]: i,
                             FIVE_COLUMN_HEADERS[1]: "2025-01-01",
                             FIVE_COLUMN_HEADERS[2]: f"Event {i}",
                             FIVE_COLUMN_HEADERS[3]: "",
                             FIVE_COLUMN_HEADERS[4]: "test.pdf"}
                            for i in range(1, 11)
                        ])
                        
                        mock_pipeline_instance = Mock()
                        mock_pipeline_instance.process_documents_for_legal_events.return_value = (df, None)
                        mock_pipeline.return_value = mock_pipeline_instance
                        
                        # Track commits
                        original_commit = db_session.commit
                        commit_count = [0]
                        
                        def counting_commit():
                            commit_count[0] += 1
                            return original_commit()
                        
                        db_session.commit = counting_commit
                        
                        # Process run
                        result = process_run(test_data['run'].id)
        
        # Should only commit once per document (batch), not 10 times (per event)
        # Note: There may be additional commits for document status updates
        assert commit_count[0] <= 2, f"Too many commits: {commit_count[0]} (expected ≤2 for batch processing)"


# ============================================================================
# FIX #5: Redis Connection Guard Tests
# ============================================================================

class TestRedisConnectionGuard:
    """Test graceful handling of Redis failures"""
    
    def test_worker_continues_without_redis(self, db_session, test_data):
        """Test that worker processes documents even if Redis fails"""
        with patch('redis.from_url', side_effect=Exception("Redis down")):
            with patch('worker.tasks_refactored.MinioStorage') as mock_storage:
                with patch('worker.tasks_refactored.LegalEventsPipeline') as mock_pipeline:
                    with patch('worker.tasks_refactored.SessionLocal', return_value=db_session):
                        # Setup mocks
                        mock_storage_instance = Mock()
                        mock_storage_instance.download_file = Mock()
                        mock_storage.return_value = mock_storage_instance
                        
                        mock_pipeline_instance = Mock()
                        mock_pipeline_instance.process_documents_for_legal_events.return_value = (
                            Mock(empty=True), None
                        )
                        mock_pipeline.return_value = mock_pipeline_instance
                        
                        # Should not crash despite Redis failure
                        result = process_run(test_data['run'].id)
                        assert result["success"] is True
    
    def test_redis_close_doesnt_crash_on_none(self, db_session, test_data):
        """Test that cleanup doesn't crash if redis_conn is None"""
        # This test verifies the finally block handles None gracefully
        with patch('redis.from_url', return_value=None):
            with patch('worker.tasks_refactored.MinioStorage') as mock_storage:
                with patch('worker.tasks_refactored.LegalEventsPipeline') as mock_pipeline:
                    with patch('worker.tasks_refactored.SessionLocal', return_value=db_session):
                        mock_storage_instance = Mock()
                        mock_storage_instance.download_file = Mock()
                        mock_storage.return_value = mock_storage_instance
                        
                        mock_pipeline_instance = Mock()
                        mock_pipeline_instance.process_documents_for_legal_events.return_value = (
                            Mock(empty=True), None
                        )
                        mock_pipeline.return_value = mock_pipeline_instance
                        
                        # Should not raise NameError or AttributeError
                        result = process_run(test_data['run'].id)
    
    def test_emitter_calls_guarded(self, db_session, test_data):
        """Test that all emitter calls check if emitter is None"""
        # Redis fails, so emitter will be None
        with patch('redis.from_url', side_effect=Exception("Redis down")):
            with patch('worker.tasks_refactored.MinioStorage') as mock_storage:
                with patch('worker.tasks_refactored.LegalEventsPipeline') as mock_pipeline:
                    with patch('worker.tasks_refactored.SessionLocal', return_value=db_session):
                        mock_storage_instance = Mock()
                        mock_storage_instance.download_file = Mock()
                        mock_storage.return_value = mock_storage_instance
                        
                        mock_pipeline_instance = Mock()
                        mock_pipeline_instance.process_documents_for_legal_events.return_value = (
                            Mock(empty=True), None
                        )
                        mock_pipeline.return_value = mock_pipeline_instance
                        
                        # Should not crash with AttributeError on emitter.emit_*
                        result = process_run(test_data['run'].id)
                        assert result["success"] is True


# ============================================================================
# Integration Tests
# ============================================================================

class TestAuditFixesIntegration:
    """End-to-end tests combining multiple fixes"""
    
    def test_complete_run_with_all_fixes(self, test_client, db_session, test_data, auth_headers):
        """Test a complete run that exercises all 5 fixes"""
        idempotency_key = "integration-test-001"
        
        # 1. Start run with idempotency (Fix #1)
        with patch('redis.from_url') as mock_redis_factory:
            mock_r = MagicMock()
            mock_r.get.return_value = None
            mock_r.set.return_value = True
            mock_redis_factory.return_value = mock_r
            
            with patch('api.main.enqueue_job', return_value="job_int_001"):
                response = test_client.put(
                    f"/v1/runs/{test_data['run'].id}/start",
                    json={"files": [], "idempotency_key": idempotency_key},
                    headers=auth_headers
                )
        
        assert response.status_code == 200
        
        # 2. Process documents (Fix #3, #4, #5)
        with patch('worker.tasks_refactored.MinioStorage') as mock_storage:
            with patch('worker.tasks_refactored.LegalEventsPipeline') as mock_pipeline:
                with patch('worker.tasks_refactored.SessionLocal', return_value=db_session):
                    with patch('redis.from_url') as mock_redis_factory:
                        mock_redis = MagicMock()
                        mock_redis_factory.return_value = mock_redis
                        
                        mock_storage_instance = Mock()
                        mock_storage_instance.download_file = Mock()
                        mock_storage.return_value = mock_storage_instance
                        
                        import pandas as pd
                        from core.constants import FIVE_COLUMN_HEADERS
                        df = pd.DataFrame([{
                            FIVE_COLUMN_HEADERS[0]: 1,
                            FIVE_COLUMN_HEADERS[1]: "2025-01-01",
                            FIVE_COLUMN_HEADERS[2]: "Integration test event",
                            FIVE_COLUMN_HEADERS[3]: "Test citation",
                            FIVE_COLUMN_HEADERS[4]: "test.pdf"
                        }])
                        
                        mock_pipeline_instance = Mock()
                        mock_pipeline_instance.process_documents_for_legal_events.return_value = (df, None)
                        mock_pipeline.return_value = mock_pipeline_instance
                        
                        result = process_run(test_data['run'].id)
        
        assert result["success"] is True
        
        # 3. Export results (Fix #2)
        with patch('api.main.MinioStorage') as mock_storage:
            mock_storage_instance = Mock()
            mock_storage_instance.upload_bytes.return_value = True
            mock_storage.return_value = mock_storage_instance
            
            response = test_client.get(f"/v1/runs/{test_data['run'].id}/export?fmt=csv")
        
        # Should succeed without crashing on relationships
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
