"""Immutable daily licensed code and coverage reference snapshots."""
from alembic import op
import sqlalchemy as sa

revision = '005_catalog_sync'
down_revision = '004_specialty_modifiers'
branch_labels = None
depends_on = None
TABLES = ('catalog_sync_runs', 'medical_code_catalog', 'coverage_policy_references', 'catalog_sync_audit_logs')


def upgrade():
    op.create_table('catalog_sync_runs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('sync_date', sa.Date(), nullable=False, unique=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('manifest_json', sa.JSON(), nullable=False))
    op.create_table('medical_code_catalog',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('sync_run_id', sa.String(36), sa.ForeignKey('catalog_sync_runs.id'), nullable=False, index=True),
        sa.Column('source', sa.String(100), nullable=False),
        sa.Column('code_system', sa.String(20), nullable=False),
        sa.Column('code', sa.String(30), nullable=False, index=True),
        sa.Column('release', sa.String(100), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('effective_from', sa.Date(), nullable=False),
        sa.Column('effective_to', sa.Date(), nullable=True),
        sa.Column('replacement_code', sa.String(30), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('sync_run_id', 'code_system', 'code', 'release', 'effective_from'))
    op.create_table('coverage_policy_references',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('sync_run_id', sa.String(36), sa.ForeignKey('catalog_sync_runs.id'), nullable=False, index=True),
        sa.Column('source', sa.String(100), nullable=False),
        sa.Column('document_type', sa.String(30), nullable=False),
        sa.Column('document_id', sa.String(100), nullable=False),
        sa.Column('version', sa.String(100), nullable=False),
        sa.Column('status', sa.String(100), nullable=False),
        sa.Column('payload_json', sa.JSON(), nullable=False),
        sa.Column('sha256', sa.String(64), nullable=False),
        sa.UniqueConstraint('sync_run_id', 'source', 'document_type', 'document_id', 'version'))
    op.create_table('catalog_sync_audit_logs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('event', sa.String(100), nullable=False, index=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('metadata_json', sa.JSON(), nullable=False))
    dialect = op.get_bind().dialect.name
    if dialect == 'postgresql':
        op.execute("""CREATE FUNCTION reject_reference_mutation() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'Reference records are append-only'; END;
        $$ LANGUAGE plpgsql""")
        for table in TABLES:
            op.execute(f'CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION reject_reference_mutation()')
    elif dialect == 'sqlite':
        for table in TABLES:
            for action in ('UPDATE', 'DELETE'):
                op.execute(f"CREATE TRIGGER {table}_no_{action.lower()} BEFORE {action} ON {table} BEGIN SELECT RAISE(ABORT, 'Reference records are append-only'); END")


def downgrade():
    for table in reversed(TABLES):
        op.drop_table(table)
    if op.get_bind().dialect.name == 'postgresql':
        op.execute('DROP FUNCTION reject_reference_mutation()')
