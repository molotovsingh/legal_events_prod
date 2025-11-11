"""
MinIO Storage Handler
Manages file uploads, downloads, and presigned URLs
"""

import os
import logging
from typing import Optional, BinaryIO
from datetime import timedelta
from urllib.parse import urlparse
from urllib3 import Timeout
from minio import Minio
from minio.error import S3Error
import hashlib
import signal
from contextlib import contextmanager

from infra.storage_keys import generate_document_key

logger = logging.getLogger(__name__)


class MinioStorage:
    """
    MinIO client for S3-compatible object storage
    """

    def __init__(self):
        """Initialize MinIO client from environment variables"""
        # Normalize endpoints by stripping any existing http:// or https://
        endpoint_raw = os.getenv("MINIO_ENDPOINT", "localhost:9000")
        public_endpoint_raw = os.getenv("MINIO_PUBLIC_ENDPOINT", "localhost:9000")

        self.endpoint = self._normalize_endpoint(endpoint_raw)
        # Public endpoint for browser presigned URLs (must be accessible from browser)
        self.public_endpoint = self._normalize_endpoint(public_endpoint_raw)

        # Require explicit credentials - no defaults for security
        self.access_key = os.getenv("MINIO_ACCESS_KEY")
        self.secret_key = os.getenv("MINIO_SECRET_KEY")
        
        if not self.access_key or not self.secret_key:
            raise ValueError(
                "MINIO_ACCESS_KEY and MINIO_SECRET_KEY must be set in environment. "
                "Do not use default credentials in production for security reasons."
            )
        
        self.bucket = os.getenv("MINIO_BUCKET", "legal-documents")
        self.secure = os.getenv("MINIO_SECURE", "false").lower() == "true"

        # Initialize client (timeout handled via urllib3 HTTPAdapter in MinIO SDK)
        self.client = Minio(
            self.endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=self.secure
        )

        logger.info(f"📦 MinIO client initialized for {self.endpoint}")
        logger.info(f"📦 MinIO public endpoint for presigned URLs: {self.public_endpoint}")

    def _normalize_endpoint(self, endpoint: str) -> str:
        """
        Strip http:// or https:// from endpoint to ensure consistent format.
        MinIO client expects endpoint without scheme; presigned URLs will add it as needed.

        Args:
            endpoint: Raw endpoint string (may include scheme)

        Returns:
            Normalized endpoint without scheme (just host:port)
        """
        parsed = urlparse(endpoint)
        # Check if this is actually a URL scheme (http/https) vs hostname with port
        if parsed.scheme in ('http', 'https'):
            # Has http/https scheme, return netloc (host:port)
            return parsed.netloc
        # No scheme or non-URL scheme (like "minio:9000"), return as-is
        return endpoint

    def ensure_bucket(self) -> bool:
        """
        Ensure the bucket exists, create if not
        """
        try:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
                logger.info(f"✅ Created bucket: {self.bucket}")
            else:
                logger.info(f"✅ Bucket exists: {self.bucket}")
            return True
        except S3Error as e:
            logger.error(f"❌ Failed to ensure bucket: {e}")
            return False

    def generate_upload_url(
        self,
        client_id: int,
        case_id: int,
        run_id: int,
        filename: str,
        expiry: timedelta = timedelta(hours=1)
    ) -> str:
        """
        Generate presigned URL for file upload

        Args:
            client_id: Client ID (for multi-tenancy)
            case_id: Case ID
            run_id: Run ID
            filename: Original filename
            expiry: URL expiration time

        Returns:
            Presigned URL for PUT operation (using public endpoint for browser access)
        """
        # Generate object key with standardized utility
        object_name = generate_document_key(
            client_id=client_id,
            case_id=case_id,
            run_id=run_id,
            filename=filename
        )

        try:
            # Generate presigned PUT URL
            url = self.client.presigned_put_object(
                self.bucket,
                object_name,
                expires=expiry
            )

            # Replace internal endpoint with public endpoint for browser access
            if self.endpoint != self.public_endpoint:
                # Both endpoints are normalized (no scheme), construct with proper scheme
                scheme = "https://" if self.secure else "http://"
                internal_url = f"{scheme}{self.endpoint}"
                public_url = f"{scheme}{self.public_endpoint}"
                url = url.replace(internal_url, public_url)
                logger.debug(f"Replaced endpoint {self.endpoint} with public endpoint {self.public_endpoint}")

            logger.debug(f"Generated upload URL for {object_name}")
            return url
        except S3Error as e:
            logger.error(f"Failed to generate upload URL: {e}")
            raise

    def generate_download_url(
        self,
        object_name: str,
        expiry: timedelta = timedelta(hours=24)
    ) -> str:
        """
        Generate presigned URL for file download

        Args:
            object_name: Object key in bucket
            expiry: URL expiration time

        Returns:
            Presigned URL for GET operation
        """
        try:
            url = self.client.presigned_get_object(
                self.bucket,
                object_name,
                expires=expiry
            )
            logger.debug(f"Generated download URL for {object_name}")
            return url
        except S3Error as e:
            logger.error(f"Failed to generate download URL: {e}")
            raise

    def upload_file(
        self,
        file_path: str,
        object_name: str,
        metadata: Optional[dict] = None
    ) -> bool:
        """
        Upload a file to MinIO

        Args:
            file_path: Local file path
            object_name: Destination object key
            metadata: Optional metadata dict

        Returns:
            True if successful
        """
        try:
            # Upload file
            result = self.client.fput_object(
                self.bucket,
                object_name,
                file_path,
                metadata=metadata
            )
            logger.info(f"✅ Uploaded {file_path} to {object_name}")
            return True
        except S3Error as e:
            logger.error(f"Failed to upload file {file_path}: {e.code} - {e.message}")
            return False
        except FileNotFoundError as e:
            logger.error(f"File not found: {file_path}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error uploading file {file_path}: {type(e).__name__} - {e}")
            return False

    def upload_bytes(
        self,
        object_name: str,
        data: bytes,
        content_type: str = "application/octet-stream",
        metadata: Optional[dict] = None
    ) -> bool:
        """
        Upload bytes directly to MinIO

        Args:
            object_name: Destination object key
            data: Bytes to upload
            content_type: MIME type
            metadata: Optional metadata dict

        Returns:
            True if successful
        """
        try:
            import io
            data_stream = io.BytesIO(data)

            result = self.client.put_object(
                self.bucket,
                object_name,
                data_stream,
                length=len(data),
                content_type=content_type,
                metadata=metadata
            )
            logger.info(f"✅ Uploaded {len(data)} bytes to {object_name}")
            return True
        except S3Error as e:
            logger.error(f"Failed to upload bytes to {object_name}: {e.code} - {e.message}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error uploading bytes to {object_name}: {type(e).__name__} - {e}")
            return False

    def download_file(
        self,
        object_name: str,
        file_path: str
    ) -> bool:
        """
        Download a file from MinIO

        Args:
            object_name: Source object key
            file_path: Destination file path

        Returns:
            True if successful
        """
        try:
            self.client.fget_object(
                self.bucket,
                object_name,
                file_path
            )
            logger.info(f"✅ Downloaded {object_name} to {file_path}")
            return True
        except S3Error as e:
            logger.error(f"Failed to download file {object_name}: {e.code} - {e.message}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error downloading {object_name}: {type(e).__name__} - {e}")
            return False

    def download_bytes(self, object_name: str) -> Optional[bytes]:
        """
        Download object as bytes

        Args:
            object_name: Object key

        Returns:
            Bytes if successful, None otherwise
        """
        try:
            response = self.client.get_object(self.bucket, object_name)
            data = response.read()
            response.close()
            response.release_conn()
            logger.debug(f"Downloaded {len(data)} bytes from {object_name}")
            return data
        except S3Error as e:
            logger.error(f"Failed to download bytes from {object_name}: {e.code} - {e.message}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error downloading bytes from {object_name}: {type(e).__name__} - {e}")
            return None

    def delete_object(self, object_name: str) -> bool:
        """
        Delete an object from MinIO

        Args:
            object_name: Object key to delete

        Returns:
            True if successful
        """
        try:
            self.client.remove_object(self.bucket, object_name)
            logger.info(f"✅ Deleted {object_name}")
            return True
        except S3Error as e:
            logger.error(f"Failed to delete object {object_name}: {e.code} - {e.message}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error deleting {object_name}: {type(e).__name__} - {e}")
            return False

    def list_objects(self, prefix: str) -> list:
        """
        List objects with a given prefix

        Args:
            prefix: Object key prefix

        Returns:
            List of object names
        """
        try:
            objects = self.client.list_objects(
                self.bucket,
                prefix=prefix,
                recursive=True
            )
            return [obj.object_name for obj in objects]
        except S3Error as e:
            logger.error(f"Failed to list objects with prefix '{prefix}': {e.code} - {e.message}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error listing objects with prefix '{prefix}': {type(e).__name__} - {e}")
            return []

    def object_exists(self, object_name: str) -> bool:
        """
        Check if an object exists

        Args:
            object_name: Object key

        Returns:
            True if exists
        """
        try:
            self.client.stat_object(self.bucket, object_name)
            return True
        except S3Error as e:
            # Log error details for debugging (404 is expected for non-existent objects)
            if e.code != "NoSuchKey":
                logger.debug(f"S3Error checking object existence for {object_name}: {e.code} - {e.message}")
            return False

    def get_object_metadata(self, object_name: str) -> Optional[dict]:
        """
        Get object metadata

        Args:
            object_name: Object key

        Returns:
            Metadata dict if exists
        """
        try:
            stat = self.client.stat_object(self.bucket, object_name)
            return {
                "size": stat.size,
                "etag": stat.etag,
                "content_type": stat.content_type,
                "last_modified": stat.last_modified,
                "metadata": stat.metadata
            }
        except S3Error as e:
            logger.error(f"Failed to get metadata: {e}")
            return None

    def calculate_sha256(self, data: bytes) -> str:
        """
        Calculate SHA256 hash of data

        Args:
            data: Bytes to hash

        Returns:
            Hex digest string
        """
        return hashlib.sha256(data).hexdigest()

    def health_check(self, timeout_override: Optional[int] = None) -> bool:
        """
        Check if MinIO is accessible with timeout protection

        Args:
            timeout_override: Override timeout in seconds (default: 5s for health checks)

        Returns:
            True if healthy, False if unreachable or timeout

        Note:
            Uses a shorter timeout (5s default) than regular operations to fail fast
            during health checks and prevent blocking API startup.
        """
        timeout = timeout_override or 5

        @contextmanager
        def timeout_handler(seconds):
            """Context manager for operation timeout"""
            def _timeout_handler(signum, frame):
                raise TimeoutError(f"Operation timed out after {seconds}s")

            # Set up signal handler for timeout (Unix-like systems only)
            old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
            signal.alarm(seconds)
            try:
                yield
            finally:
                signal.alarm(0)  # Cancel alarm
                signal.signal(signal.SIGALRM, old_handler)

        try:
            # Try to list buckets as a health check with timeout
            with timeout_handler(timeout):
                self.client.list_buckets()
            return True
        except TimeoutError as e:
            logger.error(f"MinIO health check timed out after {timeout}s: {e}")
            return False
        except Exception as e:
            logger.error(f"MinIO health check failed: {e}")
            return False

    def close(self):
        """
        Close and cleanup MinIO client resources.

        The Minio SDK uses urllib3's PoolManager for HTTP connections.
        While connections are automatically managed and reused, explicitly
        clearing the pool helps prevent resource accumulation in long-running workers.
        """
        try:
            # Access the underlying HTTP client's connection pool
            if hasattr(self.client, '_http') and hasattr(self.client._http, 'clear'):
                self.client._http.clear()
                logger.debug("Cleared MinIO HTTP connection pool")
        except Exception as e:
            logger.warning(f"Failed to clear MinIO connection pool: {e}")


# Singleton instance with thread safety
import threading

_storage_instance = None
_storage_lock = threading.Lock()


def get_storage() -> MinioStorage:
    """
    Get singleton storage instance (thread-safe)
    
    Uses double-checked locking pattern to ensure only one instance
    is created even in multi-threaded environments.
    """
    global _storage_instance
    
    # First check without lock (fast path)
    if _storage_instance is not None:
        return _storage_instance
    
    # Acquire lock for initialization (slow path)
    with _storage_lock:
        # Double-check inside lock to prevent race condition
        if _storage_instance is None:
            _storage_instance = MinioStorage()
        return _storage_instance
