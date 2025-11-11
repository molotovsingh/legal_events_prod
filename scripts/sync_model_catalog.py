#!/usr/bin/env python3
"""
Model Catalog Sync Script
==========================

Synchronizes the Python model registry (core/model_catalog.py) to the database
(model_catalog table). This ensures the UI can query model metadata via API.

Usage:
    python scripts/sync_model_catalog.py

Features:
- Idempotent: Safe to run multiple times
- Upserts: Updates existing models, inserts new ones
- Maintains referential integrity with unique constraints
- Logs all operations for audit trail

Sync Strategy:
1. Load Python model registry (_MODEL_REGISTRY)
2. For each model, UPSERT into database (INSERT ON CONFLICT UPDATE)
3. Preserve database-only fields (id, created_at)
4. Report sync statistics (added, updated, skipped)
"""

import sys
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import insert
import logging

from core.model_catalog import _MODEL_REGISTRY
from infra.models import ModelCatalog
from infra.database import DATABASE_URL

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


def sync_models_to_database(dry_run: bool = False):
    """
    Sync Python model registry to database.

    Args:
        dry_run: If True, report what would be synced without making changes

    Returns:
        Dict with sync statistics: {added: int, updated: int, total: int}
    """
    logger.info(f"Starting model catalog sync (dry_run={dry_run})")
    logger.info(f"Found {len(_MODEL_REGISTRY)} models in Python registry")

    # Create database connection
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    stats = {"added": 0, "updated": 0, "total": len(_MODEL_REGISTRY)}

    try:
        for model_entry in _MODEL_REGISTRY:
            # Prepare database row data
            row_data = {
                "provider": model_entry.provider,
                "model_id": model_entry.model_id,
                "display_name": model_entry.display_name,
                "cost_input_per_million": model_entry.cost_input_per_1m,
                "cost_output_per_million": model_entry.cost_output_per_1m,
                "context_window": model_entry.context_window,
                "supports_json_mode": model_entry.supports_json_mode,
                "supports_vision": model_entry.supports_vision,
                "badges": model_entry.badges,
                "status": model_entry.status.value,  # Convert enum to string
                "is_recommended": model_entry.recommended,
            }

            if dry_run:
                logger.info(f"[DRY RUN] Would sync: {model_entry.provider}/{model_entry.model_id}")
                continue

            # Check if model exists
            existing = session.query(ModelCatalog).filter_by(
                provider=model_entry.provider,
                model_id=model_entry.model_id
            ).first()

            if existing:
                # Update existing model
                for key, value in row_data.items():
                    setattr(existing, key, value)
                stats["updated"] += 1
                logger.info(f"Updated: {model_entry.provider}/{model_entry.model_id}")
            else:
                # Insert new model
                new_model = ModelCatalog(**row_data)
                session.add(new_model)
                stats["added"] += 1
                logger.info(f"Added: {model_entry.provider}/{model_entry.model_id}")

        if not dry_run:
            session.commit()
            logger.info(f"✓ Sync complete: {stats['added']} added, {stats['updated']} updated, {stats['total']} total")
        else:
            logger.info(f"[DRY RUN] Would sync: {stats['total']} models")

    except Exception as e:
        session.rollback()
        logger.error(f"✗ Sync failed: {e}")
        raise
    finally:
        session.close()

    return stats


def verify_sync():
    """
    Verify that all Python registry models exist in database.

    Returns:
        Tuple of (success: bool, missing_count: int, message: str)
    """
    logger.info("Verifying sync integrity...")

    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Get all provider/model_id pairs from database
        db_models = session.query(
            ModelCatalog.provider,
            ModelCatalog.model_id
        ).all()
        db_keys = {(m.provider, m.model_id) for m in db_models}

        # Get all provider/model_id pairs from Python registry
        registry_keys = {(m.provider, m.model_id) for m in _MODEL_REGISTRY}

        # Find missing models
        missing = registry_keys - db_keys

        if missing:
            logger.warning(f"✗ Verification failed: {len(missing)} models missing from database")
            for provider, model_id in missing:
                logger.warning(f"  Missing: {provider}/{model_id}")
            return False, len(missing), f"{len(missing)} models not synced"
        else:
            logger.info(f"✓ Verification passed: All {len(registry_keys)} models present in database")
            return True, 0, "All models synced successfully"

    except Exception as e:
        logger.error(f"✗ Verification error: {e}")
        return False, -1, str(e)
    finally:
        session.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Sync model catalog to database")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be synced without making changes"
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify sync integrity after completion"
    )

    args = parser.parse_args()

    try:
        # Run sync
        stats = sync_models_to_database(dry_run=args.dry_run)

        # Verify if requested
        if args.verify and not args.dry_run:
            success, missing_count, message = verify_sync()
            if not success:
                sys.exit(1)

        sys.exit(0)

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
