"""
Integration Tests for Document Retry Functionality

Tests the retry mechanism for failed and stuck documents:
- Worker automatic retry of FAILED documents
- API retry endpoint for manual retry
- Stuck document recovery
- Service boundary compliance
"""

import os
import time
import tempfile
from datetime import datetime, timedelta
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import Mock, patch, MagicMock
import redis

# Configure test environment
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379/15"  # Use test DB
os.environ["JWT_SECRET_KEY"] = "test_secret_key_for_testing"
os.environ["MINIO_ENDPOINT"] = "localhost:9000"
os.environ["MINIO_ACCESS_KEY"] = "test_access"
os.environ["MINIO_SECRET_KEY"] = "test_secret"

from infra.models import (
    Base, Client, Case, Run, Document, Event,
    RunStatus, DocumentStatus, ClientStatus, CaseStatus
)
from infra.database import get_db
from worker.tasks_refactored import process_run
from api.main import app, retry_run
from api.auth import create_access_token
from fastapi.testclient import TestClient


@pytest.fixture
def db_session():
    """Create a test database session"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def test_client(db_session):
    """Create test client with database override"""
    def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers():
    """Create authentication headers for API requests"""
    token = create_access_token({"sub": "test@example.com"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def test_data(db_session):
    """Create test data hierarchy"""
    # Create client
    client = Client(
        name="Test Client",
        reference_code="TC001",
        status=ClientStatus.ACTIVE
    )
    db_session.add(client)
    db_session.flush()
    
    # Create case
    case = Case(
        client_id=client.id,
        name="Test Case",
        description="Test case for retry testing",
        status=CaseStatus.OPEN
    )
    db_session.add(case)
    db_session.flush()
    
    # Create run
    run = Run(
        case_id=case.id,
        provider="openrouter",
        model="test-model",
        status=RunStatus.FAILED
    )
    db_session.add(run)
    db_session.flush()
    
    # Create documents with various statuses
    doc_pending = Document(
        run_id=run.id,
        case_id=case.id,
        filename="pending.pdf",
        storage_key="test/pending.pdf",
        status=DocumentStatus.PENDING
    )
    
    doc_failed = Document(
        run_id=run.id,
        case_id=case.id,
        filename="failed.pdf",
        storage_key="test/failed.pdf",
        status=DocumentStatus.FAILED,
        error="Processing failed"
    )
    
    doc_success = Document(
        run_id=run.id,
        case_id=case.id,
        filename="success.pdf",
        storage_key="test/success.pdf",
        status=DocumentStatus.SUCCESS,
        processed_at=datetime.utcnow()
    )
    
    doc_stuck = Document(
        run_id=run.id,
        case_id=case.id,
        filename="stuck.pdf",
        storage_key="test/stuck.pdf",
        status=DocumentStatus.PROCESSING,
        created_at=datetime.utcnow() - timedelta(hours=2)  # Stuck for 2 hours
    )
    
    db_session.add_all([doc_pending, doc_failed, doc_success, doc_stuck])
    db_session.commit()
    
    return {
        "client": client,
        "case": case,
        "run": run,
        "doc_pending": doc_pending,
        "doc_failed": doc_failed,
        "doc_success": doc_success,
        "doc_stuck": doc_stuck
    }


class TestWorkerRetryLogic:
    """Test worker's ability to automatically retry failed documents"""
    
    @patch('worker.tasks_refactored.MinioStorage')
    @patch('worker.tasks_refactored.LegalEventsPipeline')
    @patch('worker.tasks_refactored.WorkerEventEmitter')
    def test_worker_processes_failed_documents(self, mock_emitter, mock_pipeline, mock_storage, db_session, test_data):
        """Test that worker processes FAILED documents without API intervention"""
        # Setup mocks
        mock_storage_instance = Mock()
        mock_storage.return_value = mock_storage_instance
        mock_storage_instance.download_file = Mock()
        
        mock_pipeline_instance = Mock()
        mock_pipeline.return_value = mock_pipeline_instance
        mock_pipeline_instance.process_documents_for_legal_events = Mock(
            return_value=(Mock(empty=True, to_dict=Mock(return_value=[])), None)
        )
        
        mock_emitter_instance = Mock()
        mock_emitter.return_value = mock_emitter_instance
        
        # Mock SessionLocal to use our test session
        with patch('worker.tasks_refactored.SessionLocal', return_value=db_session):
            # Process run - should pick up FAILED document
            result = process_run(test_data["run"].id)
        
        # Verify that FAILED document was included
        assert mock_emitter_instance.emit_document_started.call_count >= 1
        
        # Check that run started event was emitted
        mock_emitter_instance.emit_run_started.assert_called_once_with(test_data["run"].id)
    
    @patch('worker.tasks_refactored.MinioStorage')
    @patch('worker.tasks_refactored.LegalEventsPipeline')
    @patch('worker.tasks_refactored.WorkerEventEmitter')
    def test_worker_processes_stuck_documents(self, mock_emitter, mock_pipeline, mock_storage, db_session, test_data):
        """Test that worker processes stuck PROCESSING documents"""
        # Remove all PENDING and FAILED docs to test stuck document recovery
        db_session.query(Document).filter(
            Document.status.in_([DocumentStatus.PENDING, DocumentStatus.FAILED])
        ).delete()
        db_session.commit()
        
        # Setup mocks
        mock_storage_instance = Mock()
        mock_storage.return_value = mock_storage_instance
        mock_storage_instance.download_file = Mock()
        
        mock_pipeline_instance = Mock()
        mock_pipeline.return_value = mock_pipeline_instance
        mock_pipeline_instance.process_documents_for_legal_events = Mock(
            return_value=(Mock(empty=True, to_dict=Mock(return_value=[])), None)
        )
        
        mock_emitter_instance = Mock()
        mock_emitter.return_value = mock_emitter_instance
        
        with patch('worker.tasks_refactored.SessionLocal', return_value=db_session):
            result = process_run(test_data["run"].id)
        
        # Should process the stuck document
        assert mock_emitter_instance.emit_document_started.call_count >= 1
    
    @patch('worker.tasks_refactored.MinioStorage')
    @patch('worker.tasks_refactored.WorkerEventEmitter')
    def test_worker_skips_successful_documents(self, mock_emitter, mock_storage, db_session, test_data):
        """Test that worker does NOT reprocess SUCCESS documents"""
        # Remove all documents except SUCCESS
        db_session.query(Document).filter(
            Document.status != DocumentStatus.SUCCESS
        ).delete()
        db_session.commit()
        
        mock_storage_instance = Mock()
        mock_storage.return_value = mock_storage_instance
        
        mock_emitter_instance = Mock()
        mock_emitter.return_value = mock_emitter_instance
        
        with patch('worker.tasks_refactored.SessionLocal', return_value=db_session):
            result = process_run(test_data["run"].id)
        
        # Should emit run failed because no documents to process
        mock_emitter_instance.emit_run_failed.assert_called_once()
        assert result["error"] == "No documents to process"


class TestAPIRetryEndpoint:
    """Test API retry endpoint functionality"""
    
    def test_retry_endpoint_resets_failed_documents(self, test_client, db_session, test_data, auth_headers):
        """Test that retry endpoint resets FAILED documents to PENDING"""
        with patch('api.main.enqueue_job', return_value="test_job_id"):
            response = test_client.put(
                f"/v1/runs/{test_data['run'].id}/retry",
                headers=auth_headers
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "accepted"
        assert data["failed_documents"] == 1  # One failed document
        
        # Verify document status was reset
        doc = db_session.query(Document).filter(
            Document.id == test_data["doc_failed"].id
        ).first()
        assert doc.status == DocumentStatus.PENDING
        assert doc.error is None
    
    def test_retry_endpoint_resets_stuck_documents(self, test_client, db_session, test_data, auth_headers):
        """Test that retry endpoint resets stuck PROCESSING documents"""
        with patch('api.main.enqueue_job', return_value="test_job_id"):
            response = test_client.put(
                f"/v1/runs/{test_data['run'].id}/retry",
                headers=auth_headers
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["stuck_documents"] == 1  # One stuck document
        
        # Verify stuck document was reset
        doc = db_session.query(Document).filter(
            Document.id == test_data["doc_stuck"].id
        ).first()
        assert doc.status == DocumentStatus.PENDING
    
    def test_retry_endpoint_requires_authentication(self, test_client, test_data):
        """Test that retry endpoint requires authentication"""
        response = test_client.put(f"/v1/runs/{test_data['run'].id}/retry")
        assert response.status_code == 401
    
    def test_retry_endpoint_prevents_active_run_retry(self, test_client, db_session, test_data, auth_headers):
        """Test that retry endpoint prevents retrying actively processing runs"""
        # Set run to PROCESSING with recent start time
        run = test_data["run"]
        run.status = RunStatus.PROCESSING
        run.started_at = datetime.utcnow()
        db_session.commit()
        
        response = test_client.put(
            f"/v1/runs/{test_data['run'].id}/retry",
            headers=auth_headers
        )
        
        assert response.status_code == 400
        assert "still processing" in response.json()["detail"]
    
    def test_retry_endpoint_allows_stuck_run_retry(self, test_client, db_session, test_data, auth_headers):
        """Test that retry endpoint allows retrying stuck PROCESSING runs"""
        # Set run to PROCESSING but with old start time (stuck)
        run = test_data["run"]
        run.status = RunStatus.PROCESSING
        run.started_at = datetime.utcnow() - timedelta(hours=2)
        db_session.commit()
        
        with patch('api.main.enqueue_job', return_value="test_job_id"):
            response = test_client.put(
                f"/v1/runs/{test_data['run'].id}/retry",
                headers=auth_headers
            )
        
        assert response.status_code == 200
        
        # Verify run was reset
        db_session.refresh(run)
        assert run.status == RunStatus.QUEUED
        assert run.error is None


class TestEventProcessorRetryHandling:
    """Test event processor's handling of retry scenarios"""
    
    def test_event_processor_clears_error_on_retry(self, db_session, test_data):
        """Test that event processor clears document errors when retrying"""
        from api.event_processor import APIEventProcessor
        from infra.worker_events import WorkerEvent, WorkerEventType
        
        # Create processor
        processor = APIEventProcessor("redis://localhost:6379/15")
        
        # Create document started event for failed document
        event = WorkerEvent(
            event_type=WorkerEventType.DOCUMENT_STARTED,
            timestamp=datetime.utcnow(),
            run_id=test_data["run"].id,
            document_id=test_data["doc_failed"].id
        )
        
        # Process event
        processor._handle_document_started(db_session, event)
        
        # Verify error was cleared and status updated
        doc = db_session.query(Document).filter(
            Document.id == test_data["doc_failed"].id
        ).first()
        assert doc.status == DocumentStatus.PROCESSING
        assert doc.error is None


class TestEndToEndRetryScenarios:
    """Test complete retry scenarios"""
    
    def test_manual_retry_flow(self, test_client, db_session, test_data, auth_headers):
        """Test complete manual retry flow via API"""
        # 1. Initial state: failed run
        assert test_data["run"].status == RunStatus.FAILED
        
        # 2. Call retry endpoint
        with patch('api.main.enqueue_job', return_value="test_job_id") as mock_enqueue:
            response = test_client.put(
                f"/v1/runs/{test_data['run'].id}/retry",
                headers=auth_headers
            )
        
        assert response.status_code == 200
        
        # 3. Verify job was enqueued with correct parameters
        mock_enqueue.assert_called_once_with(
            "process_run",
            run_id=test_data["run"].id,
            provider="openrouter",
            model="test-model"
        )
        
        # 4. Verify run status reset
        db_session.refresh(test_data["run"])
        assert test_data["run"].status == RunStatus.QUEUED
        
        # 5. Verify document statuses reset appropriately
        db_session.refresh(test_data["doc_failed"])
        assert test_data["doc_failed"].status == DocumentStatus.PENDING
        
        db_session.refresh(test_data["doc_success"])
        assert test_data["doc_success"].status == DocumentStatus.SUCCESS  # Should NOT change
        
        db_session.refresh(test_data["doc_stuck"])
        assert test_data["doc_stuck"].status == DocumentStatus.PENDING


class TestRetryBugFixes:
    """Test fixes for bugs identified in recent commits"""
    
    def test_idempotency_key_protection(self, test_client, db_session, test_data, auth_headers):
        """Test that idempotency key prevents duplicate retry requests"""
        idempotency_key = "unique-retry-key-123"
        headers = {**auth_headers, "Idempotency-Key": idempotency_key}
        
        # First request
        with patch('api.main.enqueue_job', return_value="job_1") as mock_enqueue:
            response1 = test_client.put(
                f"/v1/runs/{test_data['run'].id}/retry",
                headers=headers
            )
        
        assert response1.status_code == 200
        job_id_1 = response1.json()["job_id"]
        mock_enqueue.assert_called_once()
        
        # Second request with same idempotency key (should return cached response)
        with patch('api.main.enqueue_job', return_value="job_2") as mock_enqueue_2:
            response2 = test_client.put(
                f"/v1/runs/{test_data['run'].id}/retry",
                headers=headers
            )
        
        assert response2.status_code == 200
        job_id_2 = response2.json()["job_id"]
        
        # Should return same job_id from cache, enqueue should NOT be called
        assert job_id_1 == job_id_2
        mock_enqueue_2.assert_not_called()
    
    def test_transaction_rollback_on_enqueue_failure(self, test_client, db_session, test_data, auth_headers):
        """Test that database changes are rolled back if job enqueue fails"""
        original_status = test_data["run"].status
        failed_doc_original_status = test_data["doc_failed"].status
        
        # Mock enqueue_job to raise an exception
        with patch('api.main.enqueue_job', side_effect=Exception("Queue is down")):
            response = test_client.put(
                f"/v1/runs/{test_data['run'].id}/retry",
                headers=auth_headers
            )
        
        assert response.status_code == 500
        
        # Verify database changes were rolled back
        db_session.refresh(test_data["run"])
        db_session.refresh(test_data["doc_failed"])
        
        assert test_data["run"].status == original_status
        assert test_data["doc_failed"].status == failed_doc_original_status
    
    def test_no_redundant_authentication_check(self, test_client, db_session, test_data):
        """Test that missing auth returns 401 via dependency (not redundant check)"""
        # Request without auth header
        response = test_client.put(f"/v1/runs/{test_data['run'].id}/retry")
        
        # Should get 401 from get_current_user dependency, not custom check
        assert response.status_code == 401
        assert "Authentication required" in response.json()["detail"] or "Not authenticated" in response.json()["detail"]
    
    def test_configurable_stuck_threshold(self, test_client, db_session, test_data, auth_headers):
        """Test that stuck document threshold is configurable via environment variable"""
        # Set custom threshold (2 hours)
        with patch.dict(os.environ, {"STUCK_DOCUMENT_HOURS": "2"}):
            # Create a document stuck for 1.5 hours (should NOT be retried with 2h threshold)
            stuck_doc_1_5h = Document(
                run_id=test_data["run"].id,
                filename="stuck_1.5h.pdf",
                file_path="stuck_1.5h.pdf",
                status=DocumentStatus.PROCESSING,
                created_at=datetime.utcnow() - timedelta(hours=1.5)
            )
            db_session.add(stuck_doc_1_5h)
            db_session.commit()
            
            with patch('api.main.enqueue_job', return_value="test_job"):
                response = test_client.put(
                    f"/v1/runs/{test_data['run'].id}/retry",
                    headers=auth_headers
                )
            
            assert response.status_code == 200
            result = response.json()
            
            # Verify 1.5h stuck doc was NOT reset (threshold is 2h)
            db_session.refresh(stuck_doc_1_5h)
            assert stuck_doc_1_5h.status == DocumentStatus.PROCESSING
    
    def test_redis_connection_properly_closed(self, test_client, db_session, test_data, auth_headers):
        """Test that Redis connections are properly closed after use"""
        idempotency_key = "test-redis-connection"
        headers = {**auth_headers, "Idempotency-Key": idempotency_key}
        
        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        
        with patch('redis.from_url', return_value=mock_redis):
            with patch('api.main.enqueue_job', return_value="job_id"):
                response = test_client.put(
                    f"/v1/runs/{test_data['run'].id}/retry",
                    headers=headers
                )
        
        assert response.status_code == 200
        
        # Verify Redis connection was closed (called twice: check + cache)
        assert mock_redis.close.call_count == 2
    
    def test_validation_no_documents(self, test_client, db_session, auth_headers):
        """Test that retry fails if run has no documents"""
        # Create client and case
        client = Client(
            name="Empty Client",
            reference_code="EMPTY001",
            status=ClientStatus.ACTIVE
        )
        db_session.add(client)
        db_session.flush()
        
        case = Case(
            client_id=client.id,
            case_name="Empty Case",
            status=CaseStatus.ACTIVE
        )
        db_session.add(case)
        db_session.flush()
        
        # Create run with no documents
        run = Run(
            case_id=case.id,
            status=RunStatus.FAILED,
            provider="openrouter",
            model="test-model"
        )
        db_session.add(run)
        db_session.commit()
        
        # Attempt retry
        response = test_client.put(f"/v1/runs/{run.id}/retry", headers=auth_headers)
        
        assert response.status_code == 400
        assert "no documents" in response.json()["detail"].lower()
    
    def test_logging_uses_authenticated_user(self, test_client, db_session, test_data, auth_headers, caplog):
        """Test that logging uses authenticated user email (no anonymous fallback)"""
        import logging
        caplog.set_level(logging.INFO)
        
        with patch('api.main.enqueue_job', return_value="test_job"):
            response = test_client.put(
                f"/v1/runs/{test_data['run'].id}/retry",
                headers=auth_headers
            )
        
        assert response.status_code == 200
        
        # Check that log contains user email, not "anonymous"
        log_messages = [record.message for record in caplog.records]
        retry_logs = [msg for msg in log_messages if "Retrying run" in msg]
        
        assert len(retry_logs) > 0
        assert "test@example.com" in retry_logs[0]
        assert "anonymous" not in retry_logs[0]
    
    def test_worker_uses_configurable_threshold(self, db_session, test_data):
        """Test that worker uses configurable stuck document threshold"""
        with patch.dict(os.environ, {"STUCK_DOCUMENT_HOURS": "3"}):
            # Create document stuck for 2 hours
            stuck_doc_2h = Document(
                run_id=test_data["run"].id,
                filename="stuck_2h.pdf",
                file_path="stuck_2h.pdf",
                status=DocumentStatus.PROCESSING,
                created_at=datetime.utcnow() - timedelta(hours=2)
            )
            db_session.add(stuck_doc_2h)
            db_session.commit()
            
            # Mock storage and pipeline
            with patch('worker.tasks_refactored.MinioStorage') as mock_storage:
                with patch('worker.tasks_refactored.LegalEventsPipeline') as mock_pipeline:
                    mock_storage.return_value.download_file.return_value = tempfile.NamedTemporaryFile(suffix=".pdf")
                    mock_pipeline.return_value.process_file.return_value = ([], {})
                    
                    # Worker should NOT process 2h stuck doc (threshold is 3h)
                    result = process_run(test_data["run"].id, provider="langextract")
                    
                    # Verify 2h stuck doc was NOT processed
                    db_session.refresh(stuck_doc_2h)
                    assert stuck_doc_2h.status == DocumentStatus.PROCESSING
    
    def test_concurrent_retry_requests(self, test_client, db_session, test_data, auth_headers):
        """Test behavior with concurrent retry requests (race condition protection)"""
        import threading
        
        results = []
        
        def make_retry_request():
            with patch('api.main.enqueue_job', return_value="job_id"):
                response = test_client.put(
                    f"/v1/runs/{test_data['run'].id}/retry",
                    headers=auth_headers
                )
                results.append(response.status_code)
        
        # Launch 5 concurrent requests
        threads = [threading.Thread(target=make_retry_request) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # All requests should succeed (transaction protection)
        assert all(status == 200 for status in results)
        
        # Run should be in QUEUED state
        db_session.refresh(test_data["run"])
        assert test_data["run"].status == RunStatus.QUEUED


if __name__ == "__main__":
    pytest.main([__file__, "-v"])