"""
Database configuration and session management
"""

import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool
import logging

from infra.models import Base

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
        from infra.models import ModelCatalog, User, UserRole

        # FIRST: Always handle admin user provisioning (regardless of existing data)
        admin_email = os.getenv("ADMIN_EMAIL")
        admin_password_hash = os.getenv("ADMIN_PASSWORD_HASH")
        admin_name = os.getenv("ADMIN_NAME", "System Administrator")

        if admin_email and admin_password_hash:
            # Check if admin user already exists
            existing_admin = db.query(User).filter(User.email == admin_email).first()
            if not existing_admin:
                admin_user = User(
                    email=admin_email,
                    name=admin_name,
                    role=UserRole.ADMIN,
                    password_hash=admin_password_hash
                )
                db.add(admin_user)
                logger.info(f"✅ Admin user created from environment: {admin_email}")
            else:
                logger.info(f"Admin user already exists: {admin_email}")
        else:
            # Check environment and enforce security
            env_mode = os.getenv("ENVIRONMENT", "development").lower()
            if env_mode in ["production", "staging"]:
                logger.error("❌ SECURITY ERROR: Admin credentials not configured!")
                logger.error("Set ADMIN_EMAIL and ADMIN_PASSWORD_HASH environment variables")
                logger.error("Generate password hash with: python -c \"import bcrypt; print(bcrypt.hashpw(b'password', bcrypt.gensalt()).decode())\"")
                raise RuntimeError("Admin credentials must be configured in production/staging environments")
            else:
                # Development mode - create minimal test user (not admin)
                logger.warning("⚠️ No admin configured - running in development mode")
                logger.warning("For admin access, set ADMIN_EMAIL and ADMIN_PASSWORD_HASH")

                # Only create a development reviewer user if no users exist
                if db.query(User).count() == 0:
                    dev_user = User(
                        email="dev@localhost",
                        name="Development User",
                        role=UserRole.REVIEWER,
                        # This is a bcrypt hash for "devpass123" - ONLY for development
                        password_hash="$2b$12$R5.VmZzYh0x.UqpEEl86OeLzBsT.blHm0M85OpQ9kT3lPPZhAVgCi"
                    )
                    db.add(dev_user)
                    logger.info("✅ Development user created: dev@localhost (password: devpass123)")

        # SECOND: Check if we need to populate model catalog
        if db.query(ModelCatalog).count() > 0:
            logger.info("Model catalog already populated, skipping model seeding")
            db.commit()
            logger.info("✅ Admin provisioning completed")
            return

        # Add default models to catalog (only if empty)
        logger.info("Populating model catalog with default models...")
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

        db.commit()
        logger.info("✅ Initial data populated (models and admin)")

    except Exception as e:
        logger.error(f"Failed to populate initial data: {e}")
        db.rollback()
        raise  # Re-raise to fail startup on critical errors
    finally:
        db.close()


def test_connection():
    """
    Test database connection
    """
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        logger.info("✅ Database connection successful")
        return True
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        return False
