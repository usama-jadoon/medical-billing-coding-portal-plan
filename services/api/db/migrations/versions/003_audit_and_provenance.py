"""Pin runtime provenance and protect prior audit events from application writes."""
from alembic import op
import sqlalchemy as sa

revision = '003_audit_and_provenance'
down_revision = '002_evidence_workflow'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if 'provenance_json' not in {c['name'] for c in sa.inspect(bind).get_columns('case_snapshots')}:
        op.add_column('case_snapshots', sa.Column('provenance_json', sa.JSON(), nullable=False, server_default='{}'))
    if bind.dialect.name == 'sqlite':
        for operation in ('UPDATE', 'DELETE'):
            op.execute(f"CREATE TRIGGER IF NOT EXISTS audit_no_{operation.lower()} BEFORE {operation} ON audit_events BEGIN SELECT RAISE(ABORT, 'Audit events are append-only'); END")
    elif bind.dialect.name == 'postgresql':
        op.execute("CREATE OR REPLACE FUNCTION reject_audit_mutation() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Audit events are append-only'; END; $$")
        op.execute("CREATE TRIGGER audit_append_only BEFORE UPDATE OR DELETE ON audit_events FOR EACH ROW EXECUTE FUNCTION reject_audit_mutation()")


def downgrade():
    raise RuntimeError('Restore a verified backup to downgrade provenance controls.')
