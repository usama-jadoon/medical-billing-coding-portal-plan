import importlib
import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError


def test_fresh_schema_and_append_only_audit():
    engine = create_engine('sqlite:///:memory:')
    with engine.begin() as connection:
        with Operations.context(MigrationContext.configure(connection)):
            for module in ('001_initial_schema', '002_evidence_workflow', '003_audit_and_provenance', '004_specialty_modifiers', '005_catalog_sync'):
                importlib.import_module('services.api.db.migrations.versions.' + module).upgrade()
        assert {'version', 'active_snapshot_id'} <= {c['name'] for c in inspect(connection).get_columns('encounters')}
        assert 'provenance_json' in {c['name'] for c in inspect(connection).get_columns('case_snapshots')}
        assert 'modifiers_json' in {c['name'] for c in inspect(connection).get_columns('code_candidates')}
        assert {'is_active', 'effective_from', 'effective_to', 'replacement_code', 'last_synced_at'} <= {c['name'] for c in inspect(connection).get_columns('medical_code_catalog')}
        connection.execute(text("INSERT INTO catalog_sync_audit_logs (id, event, timestamp, metadata_json) VALUES ('sync', 'CATALOG_SYNC_COMPLETED', CURRENT_TIMESTAMP, '{}')"))
        with pytest.raises(IntegrityError, match='append-only'):
            connection.execute(text("DELETE FROM catalog_sync_audit_logs WHERE id='sync'"))
        connection.execute(text("INSERT INTO organizations (id, name, status, created_at) VALUES ('org', 'Synthetic', 'active', CURRENT_TIMESTAMP)"))
        connection.execute(text("INSERT INTO audit_events (id, organization_id, actor_id, event_type, entity_type, entity_id, metadata_json, created_at) VALUES ('audit', 'org', 'owner', 'test', 'case', 'case', '{}', CURRENT_TIMESTAMP)"))
        for sql in ("UPDATE audit_events SET event_type='tampered' WHERE id='audit'", "DELETE FROM audit_events WHERE id='audit'"):
            with pytest.raises(IntegrityError, match='append-only'):
                connection.execute(text(sql))
        assert connection.execute(text("SELECT event_type FROM audit_events WHERE id='audit'")).scalar_one() == 'test'
    engine.dispose()
