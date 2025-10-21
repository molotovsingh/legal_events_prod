"""
MinIO Storage Handler
Manages file uploads, downloads, and presigned URLs
"""

import os
import logging
from typing import Optional, BinaryIO
from datetime import timedelta
from minio import Minio
from minio.error import S3Error
import hashlib

logger = logging.getLogger(__name__)


class MinioStorage:
    """
    MinIO client for S3-compatible object storage
    """
    
    def __init__(self):
        """Initialize MinIO client from environment variables"""
        self.endpoint = os.getenv("MINIO_ENDPOINT", "localhost:9000")
        self.access_key = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
        self.secret_key = os.getenv("MINIO_SECRET_KEY", "minioadmin123")
        self.bucket = os.getenv("MINIO_BUCKET", "legal-documents")
        self.secure = os.getenv("MINIO_SECURE", "false").lower() == "true"
        
        # Initialize client
        self.client = Minio(
            self.endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=self.secure
        )
        
        logger.info(f"📦 MinIO client initialized for {self.endpoint}")
    
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
        case_id: int,
        run_id: int,
        filename: str,
        expiry: timedelta = timedelta(hours=1)
    ) -> str:
        """
        Generate presigned URL for file upload
        
        Args:
            case_id: Case ID
            run_id: Run ID  
            filename: Original filename
            expiry: URL expiration time
            
        Returns:
            Presigned URL for PUT operation
        """
        # Generate object key
        # Note: In production, we'd include client_id too
        object_name = f"cases/{case_id}/runs/{run_id}/docs/{filename}"
        
        try:
            # Generate presigned PUT URL
            url = self.client.presigned_put_object(
                self.bucket,
                object_name,
                expires=expiry
            )
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
            logger.error(f"Failed to upload file: {e}")
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
            logger.error(f"Failed to upload bytes: {e}")
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
            logger.error(f"Failed to download file: {e}")
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
            logger.error(f"Failed to download bytes: {e}")
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
            logger.error(f"Failed to delete object: {e}")
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
            logger.error(f"Failed to list objects: {e}")
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
        except S3Error:
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
    
    def health_check(self) -> bool:
        """
        Check if MinIO is accessible
        
        Returns:
            True if healthy
        """
        try:
            # Try to list buckets as a health check
            self.client.list_buckets()
            return True
        except Exception as e:
            logger.error(f"MinIO health check failed: {e}")
            return False


# Singleton instance (optional)
_storage_instance = None


def get_storage() -> MinioStorage:
    """
    Get singleton storage instance
    """
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = MinioStorage()
    return _storage_instance
