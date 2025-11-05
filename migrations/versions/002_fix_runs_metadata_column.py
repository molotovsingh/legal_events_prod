"""Fix runs table metadata column name

Revision ID: 002_fix_runs_metadata
Revises: 001_initial_schema
Create Date: 2025-11-05 16:50:00.000000

This migration renames the 'metadata' column to 'run_metadata' to avoid
SQLAlchemy Declarative API reserved attribute conflict.

Issue: api/models.py defines 'run_metadata' but migration created 'metadata'.
SQLAlchemy treats 'metadata' as reserved attribute for ORM metadata object.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic
revision = '002_fix_runs_metadata'
down_revision = '001_initial_schema'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Rename metadata column to run_metadata"""
    # Check if column exists before renaming (idempotent)
    # This handles fresh installs that might use the model directly
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (
                SELECT FROM information_schema.columns
                WHERE table_name = 'runs' AND column_name = 'metadata'
            ) THEN
                ALTER TABLE runs RENAME COLUMN metadata TO run_metadata;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    """Rollback: rename run_metadata back to metadata"""
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (
                SELECT FROM information_schema.columns
                WHERE table_name = 'runs' AND column_name = 'run_metadata'
            ) THEN
                ALTER TABLE runs RENAME COLUMN run_metadata TO metadata;
            END IF;
        END $$;
    """)
