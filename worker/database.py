"""
Database configuration and session management for Worker service

This module provides worker-owned database access.
Maintains service boundaries by not importing api business logic.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.declarative import declarative_base
import logging

# Create our own Base (worker-owned) instead of importing from api
# This avoids circular imports and maintains service boundaries
Base = declarative_base()

logger = logging.getLogger(__name__)

# Get database URL from environment
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://legal_user:legal_pass_2024@localhost:5432/legal_events"
)

# Create engine with connection pooling
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # Verify connections before using
    echo=False,  # Set to True for SQL debugging
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    """
    Get a database session
    Usage in worker tasks:
        db = SessionLocal()
        try:
            # use db
        finally:
            db.close()
    """
    db = SessionLocal()
    return db


def test_connection():
    """
    Test database connection
    """
    try:
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()
        logger.info("✅ Database connection successful")
        return True
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        return False
