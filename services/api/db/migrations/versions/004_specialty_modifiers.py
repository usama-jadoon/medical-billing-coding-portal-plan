"""Persist deterministic proposals accepted by the reviewer."""
from alembic import op
import sqlalchemy as sa

revision = '004_specialty_modifiers'
down_revision = '003_audit_and_provenance'
branch_labels = None
depends_on = None


def upgrade():
    if 'modifiers_json' not in {c['name'] for c in sa.inspect(op.get_bind()).get_columns('code_candidates')}:
        op.add_column('code_candidates', sa.Column('modifiers_json', sa.JSON(), nullable=False, server_default='[]'))


def downgrade():
    op.drop_column('code_candidates', 'modifiers_json')
