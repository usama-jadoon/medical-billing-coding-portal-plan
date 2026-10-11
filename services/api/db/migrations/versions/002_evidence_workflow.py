"""Versioned evidence, isolated analysis snapshots, and transactional events.

Supports databases created by either the initial migration or development create_all.
"""
from alembic import op
import sqlalchemy as sa

revision = "002_evidence_workflow"
down_revision = "001_initial_schema"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    from services.api.db.models import CaseSnapshot, OutboxEvent, ValidationFinding
    for table in [CaseSnapshot.__table__, OutboxEvent.__table__, ValidationFinding.__table__]:
        table.create(bind, checkfirst=True)
    additions = {
        "encounters": [sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
                       sa.Column("active_snapshot_id", sa.String(36), nullable=True)],
        "clinical_facts": [sa.Column("snapshot_id", sa.String(36), nullable=True)],
        "code_candidates": [sa.Column("snapshot_id", sa.String(36), nullable=True)],
        "validation_findings": [sa.Column("snapshot_id", sa.String(36), nullable=True)],
        "evidence": [sa.Column("region_id", sa.String(36), nullable=True),
                     sa.Column("bbox_x", sa.Float(), nullable=True), sa.Column("bbox_y", sa.Float(), nullable=True),
                     sa.Column("bbox_w", sa.Float(), nullable=True), sa.Column("bbox_h", sa.Float(), nullable=True),
                     sa.Column("quote_hash", sa.String(64), nullable=True),
                     sa.Column("evidence_role", sa.String(50), nullable=False, server_default="SUPPORT")],
    }
    for table, columns in additions.items():
        existing = {c["name"] for c in sa.inspect(bind).get_columns(table)}
        for column in columns:
            if column.name not in existing:
                op.add_column(table, column)


def downgrade():
    # Deliberately preserve provenance. Roll back application code rather than deleting evidence.
    raise RuntimeError("Evidence migration is forward-only; restore a verified backup to downgrade.")
