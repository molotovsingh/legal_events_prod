"""Initial schema creation

Revision ID: 001_initial_schema
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic
revision = '001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enums
    op.execute("CREATE TYPE userrole AS ENUM ('admin', 'case_manager', 'reviewer')")
    op.execute("CREATE TYPE runstatus AS ENUM ('queued', 'processing', 'partial', 'success', 'failed')")
    op.execute("CREATE TYPE documentstatus AS ENUM ('pending', 'processing', 'success', 'failed')")
    op.execute("CREATE TYPE clientstatus AS ENUM ('active', 'inactive', 'suspended')")
    op.execute("CREATE TYPE casestatus AS ENUM ('open', 'closed', 'archived')")
    
    # Create clients table
    op.create_table('clients',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('reference_code', sa.String(length=100), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('status', postgresql.ENUM('active', 'inactive', 'suspended', name='clientstatus'), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('reference_code')
    )
    
    # Create users table
    op.create_table('users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('role', postgresql.ENUM('admin', 'case_manager', 'reviewer', name='userrole'), nullable=True),
        sa.Column('password_hash', sa.String(length=255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email')
    )
    
    # Create cases table
    op.create_table('cases',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('client_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('retention_days', sa.Integer(), nullable=True),
        sa.Column('status', postgresql.ENUM('open', 'closed', 'archived', name='casestatus'), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_case_client_status', 'cases', ['client_id', 'status'], unique=False)
    
    # Create case_assignments table
    op.create_table('case_assignments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('case_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('role_in_case', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_case_user_unique', 'case_assignments', ['case_id', 'user_id'], unique=True)
    
    # Create runs table
    op.create_table('runs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('case_id', sa.Integer(), nullable=False),
        sa.Column('status', postgresql.ENUM('queued', 'processing', 'partial', 'success', 'failed', name='runstatus'), nullable=True),
        sa.Column('provider', sa.String(length=50), nullable=True),
        sa.Column('model', sa.String(length=100), nullable=True),
        sa.Column('prompt_version', sa.String(length=20), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
        sa.Column('docling_seconds', sa.Float(), nullable=True),
        sa.Column('extractor_seconds', sa.Float(), nullable=True),
        sa.Column('total_seconds', sa.Float(), nullable=True),
        sa.Column('cost_usd', sa.Float(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_run_case_status', 'runs', ['case_id', 'status'], unique=False)
    op.create_index('idx_run_created', 'runs', ['created_at'], unique=False)
    
    # Create documents table
    op.create_table('documents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('run_id', sa.Integer(), nullable=False),
        sa.Column('case_id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('size_bytes', sa.Integer(), nullable=True),
        sa.Column('sha256', sa.String(length=64), nullable=True),
        sa.Column('storage_key', sa.String(length=500), nullable=True),
        sa.Column('mime_type', sa.String(length=100), nullable=True),
        sa.Column('ocr_detected', sa.Boolean(), nullable=True),
        sa.Column('pages', sa.Integer(), nullable=True),
        sa.Column('status', postgresql.ENUM('pending', 'processing', 'success', 'failed', name='documentstatus'), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.Column('processing_time_seconds', sa.Float(), nullable=True),
        sa.Column('extracted_text', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['run_id'], ['runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_doc_run_status', 'documents', ['run_id', 'status'], unique=False)
    op.create_index('idx_doc_sha256', 'documents', ['sha256'], unique=False)
    
    # Create artifacts table
    op.create_table('artifacts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('run_id', sa.Integer(), nullable=False),
        sa.Column('kind', sa.String(length=20), nullable=True),
        sa.Column('storage_key', sa.String(length=500), nullable=True),
        sa.Column('size_bytes', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['run_id'], ['runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create events table
    op.create_table('events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('run_id', sa.Integer(), nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('number', sa.Integer(), nullable=True),
        sa.Column('date', sa.String(length=100), nullable=True),
        sa.Column('event_particulars', sa.Text(), nullable=False),
        sa.Column('citation', sa.Text(), nullable=True),
        sa.Column('document_reference', sa.String(length=255), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['run_id'], ['runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_event_date', 'events', ['date'], unique=False)
    op.create_index('idx_event_document', 'events', ['document_id'], unique=False)
    op.create_index('idx_event_run', 'events', ['run_id'], unique=False)
    
    # Create model_catalog table
    op.create_table('model_catalog',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('model_id', sa.String(length=100), nullable=False),
        sa.Column('display_name', sa.String(length=255), nullable=True),
        sa.Column('cost_input_per_million', sa.Float(), nullable=True),
        sa.Column('cost_output_per_million', sa.Float(), nullable=True),
        sa.Column('context_window', sa.Integer(), nullable=True),
        sa.Column('supports_json_mode', sa.Boolean(), nullable=True),
        sa.Column('supports_vision', sa.Boolean(), nullable=True),
        sa.Column('badges', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('is_recommended', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_model_provider_id', 'model_catalog', ['provider', 'model_id'], unique=True)


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('model_catalog')
    op.drop_table('events')
    op.drop_table('artifacts')
    op.drop_table('documents')
    op.drop_table('runs')
    op.drop_table('case_assignments')
    op.drop_table('cases')
    op.drop_table('users')
    op.drop_table('clients')
    
    # Drop enums
    op.execute('DROP TYPE IF EXISTS casestatus')
    op.execute('DROP TYPE IF EXISTS clientstatus')
    op.execute('DROP TYPE IF EXISTS documentstatus')
    op.execute('DROP TYPE IF EXISTS runstatus')
    op.execute('DROP TYPE IF EXISTS userrole')
