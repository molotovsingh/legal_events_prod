"""
Database configuration and session management
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool
import logging

from .models import Base

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


def init_db():
    """
    Initialize database tables
    Called on application startup
    """
    try:
        # Create all tables
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Database tables created/verified")
        
        # Populate initial data if needed
        populate_initial_data()
        
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        raise


def get_db() -> Session:
    """
    Dependency to get database session
    Usage in FastAPI:
        @app.get("/example")
        def example(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def populate_initial_data():
    """
    Populate database with initial/default data
    """
    db = SessionLocal()
    try:
        from .models import ModelCatalog, User, UserRole
        
        # Check if we already have data
        if db.query(ModelCatalog).count() > 0:
            logger.info("Database already has data, skipping initial population")
            return
        
        # Add default models to catalog
        default_models = [
            {
                "provider": "openrouter",
                "model_id": "meta-llama/llama-3.3-70b-instruct",
                "display_name": "Llama 3.3 70B",
                "cost_input_per_million": 0.52,
                "cost_output_per_million": 0.52,
                "context_window": 128000,
                "supports_json_mode": True,
                "badges": ["open-source", "recommended"],
                "is_recommended": True,
                "status": "stable"
            },
            {
                "provider": "anthropic",
                "model_id": "claude-3-haiku-20240307",
                "display_name": "Claude 3 Haiku",
                "cost_input_per_million": 0.25,
                "cost_output_per_million": 1.25,
                "context_window": 200000,
                "supports_json_mode": True,
                "badges": ["fast", "efficient"],
                "is_recommended": True,
                "status": "stable"
            },
            {
                "provider": "openai",
                "model_id": "gpt-4o-mini",
                "display_name": "GPT-4 Mini",
                "cost_input_per_million": 0.15,
                "cost_output_per_million": 0.60,
                "context_window": 128000,
                "supports_json_mode": True,
                "badges": ["quality", "popular"],
                "is_recommended": False,
                "status": "stable"
            },
            {
                "provider": "openai",
                "model_id": "gpt-4o",
                "display_name": "GPT-4 Optimized",
                "cost_input_per_million": 2.50,
                "cost_output_per_million": 10.00,
                "context_window": 128000,
                "supports_json_mode": True,
                "badges": ["premium", "quality"],
                "is_recommended": False,
                "status": "stable"
            }
        ]
        
        for model_data in default_models:
            model = ModelCatalog(**model_data)
            db.add(model)
        
        # Add default admin user
        admin_user = User(
            email="admin@legalevents.local",
            name="System Administrator",
            role=UserRole.ADMIN,
            password_hash="$2b$12$dummy_hash_replace_with_real"  # TODO: Hash real password
        )
        db.add(admin_user)
        
        # Add sample user
        sample_user = User(
            email="paralegal@example.com",
            name="Sample Paralegal",
            role=UserRole.REVIEWER
        )
        db.add(sample_user)
        
        db.commit()
        logger.info("✅ Initial data populated")
        
    except Exception as e:
        logger.error(f"Failed to populate initial data: {e}")
        db.rollback()
    finally:
        db.close()


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
