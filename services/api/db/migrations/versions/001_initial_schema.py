"""Initial schema for medical billing and coding portal

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-09-22 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Organizations
    op.create_table(
        'organizations',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, index=True),
    )

    # Users
    op.create_table(
        'users',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('email', sa.String(255), nullable=False, unique=True, index=True),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('role', sa.String(50), nullable=False, server_default='Coder'),
        sa.Column('status', sa.String(50), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, index=True),
    )

    # Patients
    op.create_table(
        'patients',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('external_reference', sa.String(255), nullable=False, index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, index=True),
    )

    # Encounters
    op.create_table(
        'encounters',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('patient_id', sa.String(36), sa.ForeignKey('patients.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('service_date', sa.String(10), nullable=False, index=True),
        sa.Column('coding_domain', sa.String(100), nullable=False),
        sa.Column('place_of_service', sa.String(50), nullable=False, server_default='23'),
        sa.Column('status', sa.String(50), nullable=False, index=True, server_default='draft'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, index=True),
    )

    # Documents
    op.create_table(
        'documents',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('encounter_id', sa.String(36), sa.ForeignKey('encounters.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('object_key', sa.String(512), nullable=False, unique=True),
        sa.Column('sha256', sa.String(64), nullable=False, index=True),
        sa.Column('mime_type', sa.String(100), nullable=False),
        sa.Column('file_size_bytes', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('page_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, index=True),
    )

    # Document Pages
    op.create_table(
        'document_pages',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('document_id', sa.String(36), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('page_number', sa.Integer(), nullable=False),
        sa.Column('ocr_text', sa.Text(), nullable=False),
        sa.Column('ocr_engine', sa.String(100), nullable=False, server_default='local'),
        sa.Column('ocr_version', sa.String(50), nullable=False, server_default='1.0'),
    )

    # Evidence
    op.create_table(
        'evidence',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('document_id', sa.String(36), sa.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('page_number', sa.Integer(), nullable=False),
        sa.Column('start_offset', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('end_offset', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('quoted_text', sa.Text(), nullable=False),
        sa.Column('evidence_type', sa.String(100), nullable=False, server_default='clinical_snippet'),
    )

    # Clinical Facts
    op.create_table(
        'clinical_facts',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('encounter_id', sa.String(36), sa.ForeignKey('encounters.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('fact_type', sa.String(100), nullable=False, index=True),
        sa.Column('value_json', sa.JSON(), nullable=False),
        sa.Column('evidence_id', sa.String(36), sa.ForeignKey('evidence.id', ondelete='SET NULL'), nullable=True),
        sa.Column('extraction_model', sa.String(100), nullable=False, server_default='deterministic'),
        sa.Column('extraction_version', sa.String(50), nullable=False, server_default='1.0'),
    )

    # Code Candidates
    op.create_table(
        'code_candidates',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('encounter_id', sa.String(36), sa.ForeignKey('encounters.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('code_system', sa.String(50), nullable=False),
        sa.Column('code', sa.String(50), nullable=False, index=True),
        sa.Column('code_version', sa.String(50), nullable=False, server_default='FY2026'),
        sa.Column('status', sa.String(50), nullable=False, index=True, server_default='candidate'),
        sa.Column('rationale', sa.Text(), nullable=False),
        sa.Column('human_review_required', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, index=True),
    )

    # Candidate Evidence Link
    op.create_table(
        'candidate_evidence',
        sa.Column('candidate_id', sa.String(36), sa.ForeignKey('code_candidates.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('evidence_id', sa.String(36), sa.ForeignKey('evidence.id', ondelete='CASCADE'), primary_key=True),
    )

    # Rule Results
    op.create_table(
        'rule_results',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('candidate_id', sa.String(36), sa.ForeignKey('code_candidates.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('rule_id', sa.String(100), nullable=False, index=True),
        sa.Column('status', sa.String(50), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('source_reference', sa.String(255), nullable=False),
    )

    # Reviews
    op.create_table(
        'reviews',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('encounter_id', sa.String(36), sa.ForeignKey('encounters.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('reviewer_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('decision', sa.String(50), nullable=False),
        sa.Column('notes', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, index=True),
    )

    # Audit Events
    op.create_table(
        'audit_events',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('actor_id', sa.String(36), nullable=False, index=True),
        sa.Column('event_type', sa.String(100), nullable=False, index=True),
        sa.Column('entity_type', sa.String(100), nullable=False),
        sa.Column('entity_id', sa.String(36), nullable=False, index=True),
        sa.Column('metadata_json', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, index=True),
    )


def downgrade() -> None:
    op.drop_table('audit_events')
    op.drop_table('reviews')
    op.drop_table('rule_results')
    op.drop_table('candidate_evidence')
    op.drop_table('code_candidates')
    op.drop_table('clinical_facts')
    op.drop_table('evidence')
    op.drop_table('document_pages')
    op.drop_table('documents')
    op.drop_table('encounters')
    op.drop_table('patients')
    op.drop_table('users')
    op.drop_table('organizations')
