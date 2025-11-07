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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])