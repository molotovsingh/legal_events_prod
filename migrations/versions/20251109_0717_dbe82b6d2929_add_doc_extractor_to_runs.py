"""add_doc_extractor_to_runs

Revision ID: dbe82b6d2929
Revises: 002_fix_runs_metadata
Create Date: 2025-11-09 07:17:38.836782

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'dbe82b6d2929'
down_revision = '002_fix_runs_metadata'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add doc_extractor column to runs table
    op.add_column('runs', sa.Column('doc_extractor', sa.String(length=50), nullable=True, server_default='docling'))
    
    # Update existing runs to have default doc_extractor
    op.execute("UPDATE runs SET doc_extractor = 'docling' WHERE doc_extractor IS NULL")


def downgrade() -> None:
    # Remove doc_extractor column from runs table
    op.drop_column('runs', 'doc_extractor')
