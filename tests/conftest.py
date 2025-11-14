"""
Pytest configuration and shared fixtures for v0.12.0 tests.

Provides MinIO test fixtures for integration testing the /v1/estimate-tokens endpoint.
"""

import pytest
import os
import hashlib
from pathlib import Path
from typing import List
from infra.storage import MinioStorage
from api.schemas import FileRef


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    """Return the fixtures directory path."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def sample_1page_pdf(fixtures_dir: Path) -> Path:
    """Return path to 1-page sample PDF."""
    pdf_path = fixtures_dir / "sample_1page.pdf"
    assert pdf_path.exists(), f"Sample PDF not found: {pdf_path}. Run tests/create_sample_pdfs.py first."
    return pdf_path


@pytest.fixture(scope="session")
def sample_5page_pdf(fixtures_dir: Path) -> Path:
    """Return path to 5-page sample PDF."""
    pdf_path = fixtures_dir / "sample_5page.pdf"
    assert pdf_path.exists(), f"Sample PDF not found: {pdf_path}. Run tests/create_sample_pdfs.py first."
    return pdf_path


@pytest.fixture(scope="session")
def minio_storage():
    """
    Initialize MinIO storage client for tests.

    Requires MinIO environment variables to be set:
    - MINIO_ENDPOINT
    - MINIO_ACCESS_KEY
    - MINIO_SECRET_KEY
    - MINIO_BUCKET

    Raises:
        pytest.skip: If MinIO is not configured (allows tests to run in CI without MinIO)
    """
    try:
        storage = MinioStorage()
        storage.ensure_bucket()
        return storage
    except (ValueError, Exception) as e:
        pytest.skip(f"MinIO not configured or unavailable: {e}")


def _compute_sha256(file_path: Path) -> str:
    """Compute SHA256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            sha256.update(chunk)
    return sha256.hexdigest()


@pytest.fixture(scope="session")
def uploaded_sample_1page(sample_1page_pdf: Path, minio_storage: MinioStorage) -> FileRef:
    """
    Upload sample_1page.pdf to MinIO and return FileRef.

    This fixture uploads the file once per test session and returns a FileRef
    that can be used in /v1/estimate-tokens requests.
    """
    # Generate test storage key (use test/ prefix to isolate from production data)
    storage_key = f"test/token_estimation/sample_1page.pdf"

    # Upload the file
    success = minio_storage.upload_file(
        file_path=str(sample_1page_pdf),
        object_name=storage_key,
        metadata={"test": "true", "fixture": "sample_1page"}
    )

    if not success:
        pytest.fail(f"Failed to upload {sample_1page_pdf.name} to MinIO")

    # Return FileRef for use in tests
    return FileRef(
        filename=sample_1page_pdf.name,
        storage_key=storage_key,
        size_bytes=sample_1page_pdf.stat().st_size,
        mime_type="application/pdf"
    )


@pytest.fixture(scope="session")
def uploaded_sample_5page(sample_5page_pdf: Path, minio_storage: MinioStorage) -> FileRef:
    """
    Upload sample_5page.pdf to MinIO and return FileRef.

    This fixture uploads the file once per test session and returns a FileRef
    that can be used in /v1/estimate-tokens requests.
    """
    # Generate test storage key
    storage_key = f"test/token_estimation/sample_5page.pdf"

    # Upload the file
    success = minio_storage.upload_file(
        file_path=str(sample_5page_pdf),
        object_name=storage_key,
        metadata={"test": "true", "fixture": "sample_5page"}
    )

    if not success:
        pytest.fail(f"Failed to upload {sample_5page_pdf.name} to MinIO")

    # Return FileRef for use in tests
    return FileRef(
        filename=sample_5page_pdf.name,
        storage_key=storage_key,
        size_bytes=sample_5page_pdf.stat().st_size,
        mime_type="application/pdf"
    )


@pytest.fixture(scope="session")
def uploaded_sample_files(uploaded_sample_1page: FileRef, uploaded_sample_5page: FileRef) -> List[FileRef]:
    """
    Return list of all uploaded sample files.

    Useful for testing multi-file estimation requests.
    """
    return [uploaded_sample_1page, uploaded_sample_5page]


@pytest.fixture
def invalid_storage_key() -> str:
    """Return a storage key that doesn't exist in MinIO (for error testing)."""
    return "test/nonexistent/file_that_does_not_exist.pdf"


# Cleanup fixture (optional - runs after all tests)
@pytest.fixture(scope="session", autouse=False)
def cleanup_test_files(minio_storage: MinioStorage):
    """
    Cleanup test files from MinIO after test session completes.

    This is disabled by default (autouse=False) to allow manual inspection.
    Enable by setting autouse=True or calling explicitly.
    """
    yield  # Tests run here

    # Cleanup after tests
    try:
        # List and delete all files under test/ prefix
        objects = minio_storage.client.list_objects(
            minio_storage.bucket,
            prefix="test/token_estimation/",
            recursive=True
        )

        deleted_count = 0
        for obj in objects:
            minio_storage.client.remove_object(minio_storage.bucket, obj.object_name)
            deleted_count += 1

        if deleted_count > 0:
            print(f"\n🧹 Cleaned up {deleted_count} test files from MinIO")
    except Exception as e:
        print(f"\n⚠️ Failed to cleanup test files: {e}")
