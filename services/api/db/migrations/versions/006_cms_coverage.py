"""Independent public CMS snapshots; no licensed catalog completion claim."""
from alembic import op
import sqlalchemy as sa

revision = '006_cms_coverage'
down_revision = '005_catalog_sync'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('cms_coverage_snapshots',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('sync_date', sa.Date(), nullable=False),
        sa.Column('scope_sha256', sa.String(64), nullable=False),
        sa.Column('scope_json', sa.JSON(), nullable=False),
        sa.Column('records_json', sa.JSON(), nullable=False),
        sa.Column('sha256', sa.String(64), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('sync_date', 'scope_sha256'))
    if op.get_bind().dialect.name == 'sqlite':
        for action in ['UPDATE', 'DELETE']:
            op.execute(f"CREATE TRIGGER cms_coverage_no_{action.lower()} BEFORE {action} ON cms_coverage_snapshots BEGIN SELECT RAISE(ABORT, 'Reference records are append-only'); END")
    elif op.get_bind().dialect.name == 'postgresql':
        op.execute('CREATE TRIGGER cms_coverage_immutable BEFORE UPDATE OR DELETE ON cms_coverage_snapshots FOR EACH ROW EXECUTE FUNCTION reject_reference_mutation()')


def downgrade():
    op.drop_table('cms_coverage_snapshots')
