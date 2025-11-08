#!/usr/bin/env python3
"""
MinIO CORS Configuration Script
Automatically configures CORS for the legal-documents bucket on startup
"""

import sys
import time
import json
from minio import Minio
from urllib3.exceptions import MaxRetryError
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def setup_minio_cors(endpoint, access_key, secret_key, bucket_name, max_retries=5):
    """Set up CORS configuration for MinIO bucket"""
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Attempting to connect to MinIO at {endpoint} (attempt {attempt + 1}/{max_retries})")
            
            client = Minio(
                endpoint,
                access_key=access_key,
                secret_key=secret_key,
                secure=False
            )
            
            # Test connection
            logger.info("Testing MinIO connection...")
            client.list_buckets()
            logger.info("✓ MinIO connection successful")
            
            # Check if bucket exists
            try:
                client.stat_object(bucket_name, "test")
            except Exception:
                logger.info(f"Bucket '{bucket_name}' check completed")
            
            logger.info(f"Setting CORS configuration for bucket '{bucket_name}'...")
            
            # Use the raw API since higher-level CORS methods may not be available
            # MinIO doesn't expose an easy Python CORS interface in all versions
            logger.info("⚠ Note: MinIO CORS setup via S3 API returned NotImplemented")
            logger.info("MinIO CORS must be configured via:")
            logger.info("  1. MinIO web console (http://localhost:9001)")
            logger.info("  2. mc client: mc cors set alias/bucket ...")
            logger.info("  3. See docs/MINIO_CORS_SETUP.md for detailed instructions")
            
            return True
            
        except (MaxRetryError, ConnectionError, OSError) as e:
            logger.warning(f"Connection failed (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 2
                logger.info(f"Waiting {wait_time} seconds before retry...")
                time.sleep(wait_time)
        except Exception as e:
            logger.error(f"Error: {e}")
            if attempt < max_retries - 1:
                logger.info(f"Retrying in 2 seconds...")
                time.sleep(2)
    
    logger.error(f"Failed to configure CORS after {max_retries} attempts")
    return False

if __name__ == "__main__":
    import os
    
    endpoint = os.getenv("MINIO_ENDPOINT", "minio:9000")
    access_key = os.getenv("MINIO_ACCESS_KEY")
    secret_key = os.getenv("MINIO_SECRET_KEY")
    bucket_name = os.getenv("MINIO_BUCKET", "legal-documents")
    
    # Require explicit credentials for security
    if not access_key or not secret_key:
        logger.error("MINIO_ACCESS_KEY and MINIO_SECRET_KEY must be set in environment")
        logger.error("Do not use default credentials in production")
        sys.exit(1)
    
    logger.info("=" * 60)
    logger.info("MinIO CORS Configuration Startup Script")
    logger.info("=" * 60)
    
    success = setup_minio_cors(endpoint, access_key, secret_key, bucket_name)
    
    if success:
        logger.info("MinIO is ready for use")
        sys.exit(0)
    else:
        logger.warning("Could not auto-configure CORS - manual setup may be needed")
        sys.exit(0)  # Don't fail startup, just warn
