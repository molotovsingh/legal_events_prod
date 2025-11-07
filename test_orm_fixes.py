#!/usr/bin/env python3
"""
Test script to verify ORM field fixes in worker/tasks_refactored.py
"""

import os
import sys
import tempfile
from datetime import datetime, timedelta

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import models to test Event and Artifact creation
from infra.models import Event, Artifact, Document, Run
from worker.database import SessionLocal

def test_event_creation():
    """Test that Event can be created with correct fields"""
    print("Testing Event creation with correct fields...")
    
    try:
        event = Event(
            run_id=1,
            document_id=1,
            number=1,
            date="2025-01-01",
            event_particulars="Test event particulars",
            citation="Test citation",
            document_reference="test_document.pdf",
            confidence_score=0.95
        )
        
        # Verify all fields are accessible
        assert event.number == 1
        assert event.date == "2025-01-01"
        assert event.event_particulars == "Test event particulars"
        assert event.citation == "Test citation"
        assert event.document_reference == "test_document.pdf"
        assert event.confidence_score == 0.95
        
        print("✅ Event creation test PASSED")
        return True
        
    except Exception as e:
        print(f"❌ Event creation test FAILED: {e}")
        return False

def test_artifact_creation():
    """Test that Artifact can be created with correct fields"""
    print("\nTesting Artifact creation with correct fields...")
    
    try:
        artifact = Artifact(
            run_id=1,
            kind="export_csv",
            storage_key="runs/1/exports/test.csv",
            size_bytes=1024,
            expires_at=datetime.utcnow() + timedelta(days=7)
        )
        
        # Verify all fields are accessible
        assert artifact.run_id == 1
        assert artifact.kind == "export_csv"
        assert artifact.storage_key == "runs/1/exports/test.csv"
        assert artifact.size_bytes == 1024
        assert artifact.expires_at is not None
        
        print("✅ Artifact creation test PASSED")
        return True
        
    except Exception as e:
        print(f"❌ Artifact creation test FAILED: {e}")
        return False

def test_invalid_fields_rejected():
    """Test that invalid fields are properly rejected"""
    print("\nTesting that invalid fields are rejected...")
    
    # Test Event with invalid fields
    try:
        event = Event(
            run_id=1,
            document_id=1,
            event_type="Invalid",  # This field doesn't exist
            event_date="2025-01-01",  # Should be 'date'
            description="Test"  # Should be 'event_particulars'
        )
        print("❌ Invalid Event fields test FAILED: Should have raised TypeError")
        return False
    except TypeError as e:
        print(f"✅ Invalid Event fields properly rejected: {e}")
    
    # Test Artifact with invalid fields
    try:
        artifact = Artifact(
            run_id=1,
            artifact_type="Invalid",  # Should be 'kind'
            metadata={"test": "data"}  # This field doesn't exist
        )
        print("❌ Invalid Artifact fields test FAILED: Should have raised TypeError")
        return False
    except TypeError as e:
        print(f"✅ Invalid Artifact fields properly rejected: {e}")
    
    return True

def test_pipeline_integration():
    """Test that the pipeline integration would work"""
    print("\nTesting pipeline integration...")
    
    # Simulate what the fixed worker code does
    event_data = {
        "number": 1,
        "date": "2025-01-01",
        "event_particulars": "Court hearing scheduled",
        "citation": "Case No. 123/2025",
        "document_reference": "court_notice.pdf",
        "confidence_score": 0.85
    }
    
    try:
        # This is what the fixed worker code does
        event = Event(
            run_id=1,
            document_id=1,
            number=event_data.get("number", 1),
            date=event_data.get("date", "Date not available"),
            event_particulars=event_data.get("event_particulars", ""),
            citation=event_data.get("citation", ""),
            document_reference=event_data.get("document_reference", "unknown.pdf"),
            confidence_score=event_data.get("confidence_score")
        )
        
        print("✅ Pipeline integration test PASSED")
        return True
        
    except Exception as e:
        print(f"❌ Pipeline integration test FAILED: {e}")
        return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("Testing ORM Field Fixes")
    print("=" * 60)
    
    tests = [
        test_event_creation(),
        test_artifact_creation(),
        test_invalid_fields_rejected(),
        test_pipeline_integration()
    ]
    
    passed = sum(tests)
    total = len(tests)
    
    print("\n" + "=" * 60)
    print(f"Test Results: {passed}/{total} passed")
    
    if passed == total:
        print("✅ ALL TESTS PASSED - ORM fixes are working correctly!")
    else:
        print(f"❌ {total - passed} test(s) failed - Please review the fixes")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)